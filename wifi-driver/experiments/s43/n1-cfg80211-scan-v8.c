// SPDX-License-Identifier: GPL-2.0
/* Experimental scan-only cfg80211 integration with the running S41
 * transport. No association, keys or data-path support is advertised.
 * This module owns no DMA and may be unloaded normally.
 */
#include <linux/module.h>
#include <linux/etherdevice.h>
#include <linux/hex.h>
#include <linux/ieee80211.h>
#include <linux/mutex.h>
#include <linux/netdevice.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/unaligned.h>
#include <linux/workqueue.h>
#include <net/cfg80211.h>
#include <net/ieee80211_radiotap.h>
#include "../s41/n1-v8-api.h"
struct n1_wifi {
	struct wiphy *wiphy;
	struct wireless_dev wdev;
	struct net_device *netdev;
	struct pci_dev *pdev;
	struct mutex lock;
	struct delayed_work work;
	struct cfg80211_scan_request *scan;
	struct ieee80211_supported_band band;
	struct ieee80211_channel channels[11];
	struct ieee80211_rate rates[12];
	u16 sequence;
	u8 handle;
	unsigned int cursor, baseline, submitted, informed, rejected;
	unsigned long deadline;
	bool stopping;
	u8 frame[4096], reply[4096];
};
static struct n1_wifi *active;
static char *mac;
module_param(mac,charp,0400);
static int launch;
module_param(launch,int,0400);
static void inform_frame(struct n1_wifi *s,u8 *data,size_t length)
{
	struct ieee80211_radiotap_iterator it;
	struct ieee80211_radiotap_header *rt;
	struct ieee80211_mgmt *mgmt;
	struct cfg80211_inform_bss info={0};
	struct cfg80211_bss *bss;
	size_t rtlen, mlen;
	int ret, frequency=0, signal=0;
	bool have_signal=false;
	u8 flags=0;
	if (length<24+8 || data[0]!=0x71 || data[1]!=24 ||
	    get_unaligned_le16(data+16)!=length) goto bad;
	rt=(void *)(data+24);
	rtlen=get_unaligned_le16(data+26);
	if (rt->it_version || rtlen<8 || rtlen>length-24) goto bad;
	ret=ieee80211_radiotap_iterator_init(&it,rt,length-24,NULL);
	if (ret) goto bad;
	while (!(ret=ieee80211_radiotap_iterator_next(&it))) {
		if (!it.is_radiotap_ns) continue;
		switch (it.this_arg_index) {
		case IEEE80211_RADIOTAP_CHANNEL: frequency=get_unaligned_le16(it.this_arg); break;
		case IEEE80211_RADIOTAP_DBM_ANTSIGNAL: signal=(s8)*it.this_arg; have_signal=true; break;
		case IEEE80211_RADIOTAP_FLAGS: flags=*it.this_arg; break;
		}
	}
	if (ret!=-ENOENT || !frequency || !have_signal || signal>0) goto bad;
	info.chan=ieee80211_get_channel(s->wiphy,frequency);
	if (!info.chan) goto bad;
	mlen=length-24-rtlen;
	if (flags&IEEE80211_RADIOTAP_F_FCS) {
		if (mlen<4) goto bad;
		mlen-=4;
	}
	if (mlen<36 || (flags&IEEE80211_RADIOTAP_F_BADFCS)) goto bad;
	mgmt=(void *)(data+24+rtlen);
	if (!ieee80211_is_beacon(mgmt->frame_control) && !ieee80211_is_probe_resp(mgmt->frame_control)) goto bad;
	info.signal=signal*100;
	info.boottime_ns=ktime_get_boottime_ns();
	bss=cfg80211_inform_bss_frame_data(s->wiphy,&info,mgmt,mlen,GFP_KERNEL);
	if (bss) { cfg80211_put_bss(s->wiphy,bss); s->informed++; }
	else s->rejected++;
	return;
bad:
	s->rejected++;
}
static int collect(struct n1_wifi *s)
{
	unsigned int n,ring;
	size_t length;
	int ret;
	for (n=0;n<512;n++) {
		length=sizeof(s->frame);
		ret=n1_alpha_record_v8(s->cursor,&ring,s->frame,&length);
		if (ret==-ENOENT) return 0;
		if (ret==-EOVERFLOW) { s->cursor++; s->rejected++; continue; }
		if (ret) return ret;
		s->cursor++;
		if (ring==4) inform_frame(s,s->frame,length);
	}
	return -EOVERFLOW;
}
static void finish(struct n1_wifi *s,bool aborted)
{
	struct cfg80211_scan_info info={.aborted=aborted};
	struct cfg80211_scan_request *req=s->scan;
	s->scan=NULL;
	s->submitted=0;
	pr_info("N1_CFG_SCAN_DONE aborted=%d informed=%u rejected=%u\n",aborted,s->informed,s->rejected);
	if (req) cfg80211_scan_done(req,&info);
}
static void scan_work(struct work_struct *work)
{
	struct n1_wifi *s=container_of(to_delayed_work(work),struct n1_wifi,work);
	unsigned int completed,status,count,i,end;
	bool pending;
	size_t reply_length=sizeof(s->reply),length;
	u8 req[128]={0};
	int ret;
	mutex_lock(&s->lock);
	if (!s->scan) goto out;
	if (s->stopping) goto fail;
	ret=n1_alpha_scan_status_v8(&completed,&status,&count,&pending);
	if (ret) goto fail;
	if (!s->submitted) {
		if (pending) goto fail;
		s->baseline=completed;
		s->informed=s->rejected=0;
		length=52+4*s->scan->n_channels;
		ret=n1_alpha_cursor_v8(&s->sequence,&s->handle);
		if (ret) goto fail;
		s->sequence++;
		if (!s->sequence) s->sequence++;
		s->handle=(s->handle+1)%32;
		put_unaligned_le16(length,req+16);
		put_unaligned_le16(s->sequence,req+18);
		put_unaligned_le32(0x1000f,req+20);
		req[24]=s->handle; req[27]=0x80; req[31]=0x12;
		put_unaligned_le16(40,req+32); put_unaligned_le16(40,req+34);
		put_unaligned_le16(120,req+36);
		put_unaligned_le16(0x104,req+38);
		put_unaligned_le16(1+4*s->scan->n_channels,req+40);
		req[42]=s->scan->n_channels;
		for (i=0;i<s->scan->n_channels;i++) req[43+4*i]=s->scan->channels[i]->hw_value;
		end=43+4*s->scan->n_channels;
		put_unaligned_le16(0x165,req+end); put_unaligned_le16(5,req+end+2); req[end+6]=1;
		ret=n1_alpha_exchange_v8(req,length,s->reply,&reply_length,true);
		if (ret || reply_length!=24 || s->reply[0]!=0x41 ||
		    (get_unaligned_le32(s->reply+20)&~BIT(30))!=0x1000f) goto fail;
		s->submitted=1;
		s->deadline=jiffies+msecs_to_jiffies(5000);
	}
	ret=collect(s);
	if (ret) goto fail;
	ret=n1_alpha_scan_status_v8(&completed,&status,&count,&pending);
	if (ret) goto fail;
	if (completed>s->baseline && !pending) {
		ret=collect(s); /* completion and final frames share the transport lock */
		finish(s,ret || status);
		goto out;
	}
	if (time_after(jiffies,s->deadline)) goto fail;
	schedule_delayed_work(&s->work,msecs_to_jiffies(10));
	goto out;
fail:
	finish(s,true);
out:
	mutex_unlock(&s->lock);
}
static int scan(struct wiphy *wiphy,struct cfg80211_scan_request *req)
{
	struct n1_wifi *s=wiphy_priv(wiphy);
	unsigned int i;
	int ret=0;
	if (!req->n_channels || req->n_channels>11 || req->n_ssids>1 ||
	    (req->n_ssids && req->ssids[0].ssid_len) || req->ie_len) return -EOPNOTSUPP;
	for (i=0;i<req->n_channels;i++)
		if (req->channels[i]->band!=NL80211_BAND_2GHZ || req->channels[i]->hw_value<1 ||
		    req->channels[i]->hw_value>11) return -EINVAL;
	mutex_lock(&s->lock);
	if (s->stopping) ret=-ESHUTDOWN;
	else if (s->scan) ret=-EBUSY;
	else { s->scan=req; schedule_delayed_work(&s->work,0); }
	mutex_unlock(&s->lock);
	return ret;
}
static const struct cfg80211_ops cfg_ops={.scan=scan};
static int net_open(struct net_device *dev) { netif_carrier_off(dev); return 0; }
static int net_stop(struct net_device *dev) { netif_stop_queue(dev); return 0; }
static netdev_tx_t net_xmit(struct sk_buff *skb,struct net_device *dev)
{
	dev->stats.tx_dropped++;
	dev_kfree_skb_any(skb);
	return NETDEV_TX_OK;
}
static const struct net_device_ops net_ops={.ndo_open=net_open,.ndo_stop=net_stop,.ndo_start_xmit=net_xmit};
static int __init wifi_init(void)
{
	static const int rates[]={10,20,55,110,60,90,120,180,240,360,480,540};
	struct wiphy *wiphy;
	struct n1_wifi *s;
	struct pci_dev *p;
	u8 address[ETH_ALEN];
	unsigned int i,completed,status,count;
	bool pending;
	int ret;
	if (!launch) return 0;
	if (!of_machine_is_compatible("apple,j714s") || !mac || !mac_pton(mac,address) ||
	    !is_valid_ether_addr(address)) return -EINVAL;
	ret=n1_alpha_scan_status_v8(&completed,&status,&count,&pending);
	if (ret || pending) return ret?ret:-EBUSY;
	p=pci_get_domain_bus_and_slot(0,1,PCI_DEVFN(0,1));
	if (!p || p->vendor!=0x106b || p->device!=0x1902) { pci_dev_put(p); return -ENODEV; }
	wiphy=wiphy_new(&cfg_ops,sizeof(*s));
	if (!wiphy) { pci_dev_put(p); return -ENOMEM; }
	s=wiphy_priv(wiphy); s->wiphy=wiphy; s->pdev=p;
	ret=n1_alpha_cursor_v8(&s->sequence,&s->handle);
	if (ret) goto free_wiphy;
	mutex_init(&s->lock); INIT_DELAYED_WORK(&s->work,scan_work);
	for (i=0;i<11;i++) {
		s->channels[i].band=NL80211_BAND_2GHZ;
		s->channels[i].center_freq=2412+5*i;
		s->channels[i].hw_value=1+i;
		s->channels[i].flags=IEEE80211_CHAN_NO_IR;
		s->channels[i].max_power=0; /* only passive scans are implemented */
	}
	for (i=0;i<ARRAY_SIZE(rates);i++) { s->rates[i].bitrate=rates[i]; s->rates[i].hw_value=i; }
	s->band.channels=s->channels; s->band.n_channels=11;
	s->band.bitrates=s->rates; s->band.n_bitrates=ARRAY_SIZE(rates);
	wiphy->bands[NL80211_BAND_2GHZ]=&s->band;
	wiphy->interface_modes=BIT(NL80211_IFTYPE_STATION);
	wiphy->max_scan_ssids=1;
	wiphy->signal_type=CFG80211_SIGNAL_TYPE_MBM;
	memcpy(wiphy->perm_addr,address,ETH_ALEN);
	set_wiphy_dev(wiphy,&p->dev);
	ret=wiphy_register(wiphy);
	if (ret) goto free_wiphy;
	s->netdev=alloc_netdev(0,"n1test%d",NET_NAME_UNKNOWN,ether_setup);
	if (!s->netdev) { ret=-ENOMEM; goto unregister_wiphy; }
	s->wdev.wiphy=wiphy; s->wdev.iftype=NL80211_IFTYPE_STATION; s->wdev.netdev=s->netdev;
	s->netdev->ieee80211_ptr=&s->wdev; s->netdev->netdev_ops=&net_ops;
	SET_NETDEV_DEV(s->netdev,&p->dev); eth_hw_addr_set(s->netdev,address);
	netif_carrier_off(s->netdev);
	ret=register_netdev(s->netdev);
	if (ret) goto free_netdev;
	active=s;
	pr_info("N1_CFG_READY interface=%s passive2GHzscan; association/data unavailable\n",s->netdev->name);
	return 0;
free_netdev:
	free_netdev(s->netdev);
unregister_wiphy:
	wiphy_unregister(wiphy);
free_wiphy:
	wiphy_free(wiphy); pci_dev_put(p); return ret;
}
static void __exit wifi_exit(void)
{
	struct n1_wifi *s=active;
	if (!s) return;
	mutex_lock(&s->lock);
	s->stopping=true;
	mutex_unlock(&s->lock);
	cancel_delayed_work_sync(&s->work);
	mutex_lock(&s->lock);
	if (s->scan) finish(s,true);
	mutex_unlock(&s->lock);
	unregister_netdev(s->netdev); free_netdev(s->netdev);
	wiphy_unregister(s->wiphy); pci_dev_put(s->pdev); wiphy_free(s->wiphy);
}
module_init(wifi_init);
module_exit(wifi_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Experimental native N1 cfg80211 passive scan interface");
