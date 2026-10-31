// SPDX-License-Identifier: GPL-2.0
/* N1 station frontend over the guarded S49/S50/S51 transport.
 * This module owns host memory only. RX is delivered directly; management
 * history is used only for scan results, never for connection lifetime.
 * Passive 2.4/5 GHz scans, open/WPA2-PSK CCMP, one station.
 */
#include <linux/module.h>
#include <linux/delay.h>
#include <linux/etherdevice.h>
#include <linux/ethtool.h>
#include <linux/hex.h>
#include <linux/ieee80211.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/unaligned.h>
#include <linux/workqueue.h>
#include <net/cfg80211.h>
#include <net/ieee80211_radiotap.h>
#include "../s49/n1-v9-api.h"
#include "../s50/n1-data-api.h"
#include "../s51/n1-tx-api.h"
#include "../common/n1-aci-connect.h"
#include "../common/n1-tx-msdu.h"

#define TX_LIMIT 128
struct n1_wifi {
	struct wiphy *wiphy;
	struct wireless_dev wdev;
	struct net_device *dev;
	struct pci_dev *pdev;
	struct mutex lock;
	struct delayed_work control_work, tx_work;
	struct sk_buff_head tx;
	struct ieee80211_supported_band bands[2];
	struct ieee80211_channel channels[38];
	struct ieee80211_rate rates[12];
	struct cfg80211_scan_request *scan;
	struct cfg80211_bss *join_bss;
	struct n1_link_state link;
	unsigned int cursor, scan_baseline, join_generation, loss_baseline;
	unsigned long scan_deadline, join_deadline, leave_deadline, roam_deadline;
	bool stopping, dead, opened, linked, reported_connected, connecting, join_sent;
	bool leaving, leave_sent, local_leave, scan_sent;
	u16 leave_reason;
	u8 bssid[ETH_ALEN], ssid[32], ssid_len;
	u8 request[300], reply[4096], frame[4096], tx_frame[1514];
	size_t request_len;
};
static struct n1_wifi *active;
static char *mac;
module_param(mac,charp,0400);

static struct n1_wifi *from_dev(struct net_device *dev)
{
	return wiphy_priv(dev->ieee80211_ptr->wiphy);
}

/* The RX callback cannot take the frontend mutex: transport holds io_lock. */
static void receive(void *context,const void *data,size_t length)
{
	struct n1_wifi *s=context;
	const u8 *p=data;
	struct sk_buff *skb;
	if (!READ_ONCE(s->opened) || !READ_ONCE(s->linked)) return;
	if (length<ETH_HLEN+2 || length>1516 || p[0] || p[1]) {
		s->dev->stats.rx_length_errors++; return;
	}
	length-=2;
	skb=netdev_alloc_skb_ip_align(s->dev,length);
	if (!skb) { s->dev->stats.rx_dropped++; return; }
	skb_put_data(skb,p+2,length);
	skb->protocol=eth_type_trans(skb,s->dev);
	skb->ip_summed=CHECKSUM_NONE;
	s->dev->stats.rx_packets++; s->dev->stats.rx_bytes+=length;
	netif_rx(skb);
}

static void transmit(struct work_struct *work)
{
	struct n1_wifi *s=container_of(to_delayed_work(work),struct n1_wifi,tx_work);
	struct sk_buff *skb;
	unsigned int n;
	int ret;
	if (!READ_ONCE(s->opened) || !READ_ONCE(s->linked)) return;
	for (n=0;n<TX_LIMIT;n++) {
		skb=skb_dequeue(&s->tx);
		if (!skb) break;
		if (skb->len<ETH_HLEN || skb->len>sizeof(s->tx_frame) ||
		    skb_copy_bits(skb,0,s->tx_frame,skb->len)) ret=-EMSGSIZE;
		else {
			ret=n1_ethernet_to_snap(s->tx_frame,sizeof(s->tx_frame),s->tx_frame,skb->len);
			if (ret>=0) ret=n1_data_tx_v2(s->tx_frame,ret);
		}
		if (ret==-EAGAIN) { skb_queue_head(&s->tx,skb); break; }
		if (ret) s->dev->stats.tx_errors++;
		else { s->dev->stats.tx_packets++; s->dev->stats.tx_bytes+=skb->len; }
		dev_kfree_skb_any(skb);
	}
	if (READ_ONCE(s->opened) && READ_ONCE(s->linked)) {
		if (skb_queue_len(&s->tx)<TX_LIMIT/2) netif_wake_queue(s->dev);
		schedule_delayed_work(&s->tx_work,msecs_to_jiffies(1));
	}
}

/* Called with frontend lock held; TX worker never acquires that lock. */
static void packets_off(struct n1_wifi *s)
{
	WRITE_ONCE(s->linked,false);
	netif_stop_queue(s->dev); netif_carrier_off(s->dev);
	cancel_delayed_work_sync(&s->tx_work);
	netif_stop_queue(s->dev); netif_carrier_off(s->dev);
	skb_queue_purge(&s->tx);
}

static void scan_done(struct n1_wifi *s,bool aborted)
{
	struct cfg80211_scan_request *request=s->scan;
	struct cfg80211_scan_info info={.aborted=aborted};
	s->scan=NULL; s->scan_sent=false;
	if (request) cfg80211_scan_done(request,&info);
}

static void packets_on(struct n1_wifi *s)
{
	WRITE_ONCE(s->linked,true); netif_carrier_on(s->dev);
	if (s->opened) { netif_wake_queue(s->dev); schedule_delayed_work(&s->tx_work,0); }
}

static void join_done(struct n1_wifi *s,int status)
{
	struct cfg80211_bss *bss=s->join_bss;
	if (!s->connecting) return;
	s->join_bss=NULL; s->connecting=false;
	memzero_explicit(s->request,sizeof(s->request)); s->request_len=0;
	pr_info("N1_WIFI_JOIN_DONE status=%d generation=%u complete=%u secure=%u failed=%u\n",
		status,s->link.generation,s->link.complete,s->link.secure,s->link.failed);
	/* Supply both: the target kernel's success path copies the BSSID even
	 * with a held BSS. cfg80211 consumes that reference on all paths. */
	cfg80211_connect_bss(s->dev,s->bssid,bss,NULL,0,NULL,0,status,GFP_KERNEL,
		NL80211_TIMEOUT_UNSPECIFIED);
	if (!status) {
		s->reported_connected=true;
		packets_on(s);
	}
}

static void notify_down(struct n1_wifi *s,u16 reason,bool local)
{
	bool was_linked=s->reported_connected;
	s->reported_connected=false;
	packets_off(s);
	if (s->connecting) join_done(s,-1);
	else if (was_linked) cfg80211_disconnected(s->dev,reason,NULL,0,local,GFP_KERNEL);
}

static void request_leave(struct n1_wifi *s,u16 reason,bool local)
{
	/* Keep cfg80211's connected state until the asynchronous completion. */
	packets_off(s);
	memzero_explicit(s->request,sizeof(s->request)); s->request_len=0;
	if (s->leaving) return;
	s->leaving=true; s->leave_sent=false; s->local_leave=local;
	s->leave_reason=reason; s->loss_baseline=s->link.losses;
	s->leave_deadline=jiffies+msecs_to_jiffies(6000);
	pr_info("N1_WIFI_LEAVE requested reason=%u local=%u scan=%u\n",reason,local,!!s->scan);
}

static int next_sequence(u16 *sequence,u8 *handle)
{
	int ret=n1_alpha_cursor_v9(sequence,handle);
	if (!ret) *sequence=*sequence==65535?1:*sequence+1;
	return ret;
}

static int exchange(struct n1_wifi *s,const u8 *req,size_t length,bool ack)
{
	size_t reply_len=sizeof(s->reply);
	return n1_alpha_exchange_v9(req,length,s->reply,&reply_len,ack);
}

static void inform_frame(struct n1_wifi *s,u8 *data,size_t length)
{
	struct ieee80211_radiotap_iterator it;
	struct ieee80211_radiotap_header *rt;
	struct ieee80211_mgmt *mgmt;
	struct cfg80211_inform_bss info={0};
	struct cfg80211_bss *bss;
	size_t rtlen,mlen;
	int ret,frequency=0,signal=0;
	bool have_signal=false;
	u8 flags=0;
	if (length<32 || data[0]!=0x71 || data[1]!=24 ||
	    get_unaligned_le16(data+16)!=length) return;
	rt=(void *)(data+24); rtlen=get_unaligned_le16(data+26);
	if (rt->it_version || rtlen<8 || rtlen>length-24) return;
	ret=ieee80211_radiotap_iterator_init(&it,rt,length-24,NULL);
	if (ret) return;
	while (!(ret=ieee80211_radiotap_iterator_next(&it))) {
		if (!it.is_radiotap_ns) continue;
		switch (it.this_arg_index) {
		case IEEE80211_RADIOTAP_CHANNEL: frequency=get_unaligned_le16(it.this_arg); break;
		case IEEE80211_RADIOTAP_DBM_ANTSIGNAL: signal=(s8)*it.this_arg; have_signal=true; break;
		case IEEE80211_RADIOTAP_FLAGS: flags=*it.this_arg; break;
		}
	}
	if (ret!=-ENOENT || !frequency || !have_signal || signal>0) return;
	info.chan=ieee80211_get_channel(s->wiphy,frequency);
	if (!info.chan) return;
	mlen=length-24-rtlen;
	if (flags&IEEE80211_RADIOTAP_F_FCS) { if (mlen<4) return; mlen-=4; }
	if (mlen<36 || (flags&IEEE80211_RADIOTAP_F_BADFCS)) return;
	mgmt=(void *)(data+24+rtlen);
	if (!ieee80211_is_beacon(mgmt->frame_control) &&
	    !ieee80211_is_probe_resp(mgmt->frame_control)) return;
	info.signal=signal*100; info.boottime_ns=ktime_get_boottime_ns();
	bss=cfg80211_inform_bss_frame_data(s->wiphy,&info,mgmt,mlen,GFP_KERNEL);
	if (bss) cfg80211_put_bss(s->wiphy,bss);
}

static int collect_scan(struct n1_wifi *s)
{
	unsigned int n,ring;
	size_t length;
	int ret;
	for (n=0;n<512;n++) {
		length=sizeof(s->frame);
		ret=n1_alpha_record_v9(s->cursor,&ring,s->frame,&length);
		if (ret==-ENOENT) return 0;
		if (ret) return ret;
		s->cursor++;
		if (ring==4) inform_frame(s,s->frame,length);
	}
	return -EOVERFLOW;
}

static int progress_scan(struct n1_wifi *s)
{
	u8 req[256]={0},handle;
	u16 seq;
	unsigned int completed,status,count,i,end;
	bool pending;
	int ret;
	size_t length;
	ret=n1_alpha_scan_status_v9(&completed,&status,&count,&pending);
	if (ret) return ret;
	if (!s->scan_sent) {
		if (pending) return -EBUSY;
		ret=n1_alpha_state_v9(&s->link,&s->cursor);
		if (ret) return ret;
		s->scan_baseline=completed;
		ret=next_sequence(&seq,&handle);
		if (ret) return ret;
		length=52+4*s->scan->n_channels;
		put_unaligned_le16(length,req+16); put_unaligned_le16(seq,req+18);
		put_unaligned_le32(0x1000f,req+20);
		req[24]=(handle+1)%32; req[27]=0x80; req[31]=0x12;
		put_unaligned_le16(40,req+32); put_unaligned_le16(40,req+34);
		put_unaligned_le16(120,req+36);
		put_unaligned_le16(0x104,req+38);
		put_unaligned_le16(1+4*s->scan->n_channels,req+40);
		req[42]=s->scan->n_channels;
		for (i=0;i<s->scan->n_channels;i++) {
			ret=n1_channel20(req+43+4*i,s->scan->channels[i]->hw_value,
				s->scan->channels[i]->band==NL80211_BAND_5GHZ?1:0);
			if (ret) return ret;
		}
		end=43+4*s->scan->n_channels;
		put_unaligned_le16(0x165,req+end); put_unaligned_le16(5,req+end+2); req[end+6]=1;
		ret=exchange(s,req,length,true);
		if (ret) return ret;
		s->scan_sent=true; s->scan_deadline=jiffies+msecs_to_jiffies(10000);
	}
	ret=collect_scan(s);
	if (ret) return ret;
	ret=n1_alpha_scan_status_v9(&completed,&status,&count,&pending);
	if (ret) return ret;
	if (completed!=s->scan_baseline && !pending) {
		ret=collect_scan(s); scan_done(s,ret || status); return 0;
	}
	return time_after(jiffies,s->scan_deadline)?-ETIMEDOUT:0;
}

static int progress_join(struct n1_wifi *s)
{
	u8 clear[25],handle;
	u16 seq;
	unsigned int cursor;
	int ret;
	if (!s->join_sent) {
		ret=next_sequence(&seq,&handle);
		if (ret) return ret;
		n1_build_clear_vendor_ie(clear,sizeof(clear),seq);
		ret=exchange(s,clear,sizeof(clear),false);
		if (ret) return ret;
		ret=next_sequence(&seq,&handle);
		if (ret) return ret;
		put_unaligned_le16(seq,s->request+18);
		ret=exchange(s,s->request,s->request_len,true);
		memzero_explicit(s->request,sizeof(s->request)); s->request_len=0;
		if (ret) return ret;
		ret=n1_alpha_state_v9(&s->link,&cursor);
		if (ret) return ret;
		s->join_generation=s->link.generation; s->join_sent=true;
		s->join_deadline=jiffies+msecs_to_jiffies(20000);
		pr_info("N1_WIFI_JOIN_SENT sequence=%u generation=%u\n",seq,s->join_generation);
	}
	if (s->link.generation!=s->join_generation || s->link.failed) return -ECONNREFUSED;
	if (n1_link_ready(&s->link)) {
		if (!ether_addr_equal(s->bssid,s->link.bssid) ||
		    s->link.ssid_length!=s->ssid_len || memcmp(s->ssid,s->link.ssid,s->ssid_len))
			return -EPROTO;
		join_done(s,0); return 0;
	}
	return time_after(jiffies,s->join_deadline)?-ETIMEDOUT:0;
}

static int progress_leave(struct n1_wifi *s)
{
	u8 req[40],handle;
	u16 seq;
	unsigned int pending;
	int ret;
	if (!s->leave_sent) {
		ret=n1_data_tx_pending_v2(&pending);
		if (ret) return ret;
		if (pending) return time_after(jiffies,s->leave_deadline)?-ETIMEDOUT:0;
		ret=next_sequence(&seq,&handle);
		if (ret) return ret;
		n1_build_disconnect(req,sizeof(req),seq,s->leave_reason,10);
		ret=exchange(s,req,sizeof(req),true);
		if (ret) return ret;
		s->leave_sent=true;
	}
	if (s->link.losses!=s->loss_baseline) {
		pr_info("N1_WIFI_LEAVE completed\n");
		s->leaving=false; notify_down(s,s->leave_reason,s->local_leave); return 0;
	}
	return time_after(jiffies,s->leave_deadline)?-ETIMEDOUT:0;
}

static int report_roam(struct n1_wifi *s)
{
	struct cfg80211_roam_info info={0};
	struct ieee80211_channel *channel;
	unsigned int band;
	int primary=n1_primary_channel(s->link.channel,&band);
	if (primary<0) return primary;
	channel=ieee80211_get_channel(s->wiphy,(band?5000:2407)+5*primary);
	if (!channel) return -EINVAL;
	info.links[0].bss=cfg80211_get_bss(s->wiphy,channel,s->link.bssid,s->ssid,s->ssid_len,
		IEEE80211_BSS_TYPE_ESS,s->link.protected?IEEE80211_PRIVACY_ON:IEEE80211_PRIVACY_OFF);
	if (!info.links[0].bss) return -ENOENT;
	memcpy(s->bssid,s->link.bssid,ETH_ALEN);
	cfg80211_roamed(s->dev,&info,GFP_KERNEL);
	return 0;
}

static void control(struct work_struct *work)
{
	struct n1_wifi *s=container_of(to_delayed_work(work),struct n1_wifi,control_work);
	unsigned int cursor,count,done,errors;
	int ret;
	mutex_lock(&s->lock);
	if (s->stopping || s->dead) goto out;
	ret=n1_alpha_state_v9(&s->link,&cursor);
	if (ret || n1_data_rx_status_v2(&count) || n1_data_tx_status_v2(&done,&errors)) goto failed;
	if (!s->scan && collect_scan(s)) s->cursor=cursor; /* Diagnostic history loss cannot change link state. */
	if (s->leaving) {
		ret=progress_leave(s); if (ret) goto failed;
	} else if (s->connecting) {
		ret=progress_join(s);
		if (ret) {
			pr_info("N1_WIFI_JOIN_FAILED result=%d complete=%u secure=%u failed=%u\n",
				ret,s->link.complete,s->link.secure,s->link.failed);
			request_leave(s,WLAN_REASON_DEAUTH_LEAVING,true);
		}
	} else if (s->reported_connected && s->link.roaming) {
		if (s->linked) { packets_off(s); s->roam_deadline=jiffies+msecs_to_jiffies(20000); }
		if (time_after(jiffies,s->roam_deadline)) request_leave(s,WLAN_REASON_UNSPECIFIED,false);
	} else if (s->reported_connected && !n1_link_ready(&s->link)) {
		notify_down(s,s->link.reason,false);
	} else if (s->reported_connected) {
		if (!ether_addr_equal(s->bssid,s->link.bssid) && report_roam(s))
			request_leave(s,WLAN_REASON_UNSPECIFIED,false);
		else if (!s->linked) packets_on(s);
	}
	if (s->scan && progress_scan(s)) scan_done(s,true);
	schedule_delayed_work(&s->control_work,msecs_to_jiffies(10));
	goto out;
failed:
	s->dead=true;
	scan_done(s,true); notify_down(s,WLAN_REASON_UNSPECIFIED,false);
	pr_err("N1_WIFI: transport unavailable; DMA retained, reboot required\n");
out:
	mutex_unlock(&s->lock);
}

static int scan(struct wiphy *wiphy,struct cfg80211_scan_request *req)
{
	struct n1_wifi *s=wiphy_priv(wiphy);
	unsigned int i;
	int ret=0;
	u8 encoded[4];
	pr_info("N1_WIFI_SCAN channels=%u ssids=%d ie_length=%zu flags=%x\n",
		req->n_channels,req->n_ssids,req->ie_len,req->flags);
	/* This implementation only listens. Probe-request IEs and directed SSIDs
	 * need no transmission during a passive scan; visible BSSes are returned. */
	if (!req->n_channels || req->n_channels>ARRAY_SIZE(s->channels) || req->n_ssids>1)
		return -EOPNOTSUPP;
	for (i=0;i<req->n_channels;i++)
		if ((req->channels[i]->band!=NL80211_BAND_2GHZ && req->channels[i]->band!=NL80211_BAND_5GHZ) ||
		    n1_channel20(encoded,req->channels[i]->hw_value,req->channels[i]->band==NL80211_BAND_5GHZ?1:0) ||
		    (req->channels[i]->flags&IEEE80211_CHAN_DISABLED))
			return -EINVAL;
	mutex_lock(&s->lock);
	if (s->dead || s->stopping || !s->opened) ret=-ENETDOWN;
	else if (s->scan || s->connecting || s->leaving) ret=-EBUSY;
	else { s->scan=req; s->scan_sent=false; mod_delayed_work(system_wq,&s->control_work,0); }
	mutex_unlock(&s->lock);
	return ret;
}

static bool has_suite(const u32 *suites,int count,u32 wanted)
{
	int i;
	for (i=0;i<count;i++) if (suites[i]==wanted) return true;
	return false;
}

static bool supported_psk(const struct cfg80211_crypto_settings *crypto)
{
	/* These arrays are alternatives allowed by userspace. Select our
	 * supported PSK/CCMP combination; do not require one-element lists. */
	return crypto->wpa_versions==NL80211_WPA_VERSION_2 &&
		has_suite(crypto->ciphers_pairwise,crypto->n_ciphers_pairwise,WLAN_CIPHER_SUITE_CCMP) &&
		crypto->cipher_group==WLAN_CIPHER_SUITE_CCMP &&
		has_suite(crypto->akm_suites,crypto->n_akm_suites,WLAN_AKM_SUITE_PSK) && crypto->psk;
}

static int connect(struct wiphy *wiphy,struct net_device *dev,struct cfg80211_connect_params *p)
{
	struct n1_wifi *s=wiphy_priv(wiphy);
	struct cfg80211_bss *bss;
	const u8 *pmk=NULL;
	int ret;
	pr_info("N1_WIFI_CONNECT privacy=%u auth=%u mfp=%u wpa=%x pairwise_count=%d pairwise=%x group=%x akm_count=%d akm=%x pmk_present=%u key_len=%u prev=%u want_1x=%u\n",
		p->privacy,p->auth_type,p->mfp,p->crypto.wpa_versions,p->crypto.n_ciphers_pairwise,
		p->crypto.n_ciphers_pairwise?p->crypto.ciphers_pairwise[0]:0,p->crypto.cipher_group,
		p->crypto.n_akm_suites,p->crypto.n_akm_suites?p->crypto.akm_suites[0]:0,
		!!p->crypto.psk,p->key_len,!!p->prev_bssid,p->want_1x);
	if (!p->ssid || !p->ssid_len || p->ssid_len>32 || p->key_len || p->pbss ||
	    p->prev_bssid || p->want_1x || p->mfp==NL80211_MFP_REQUIRED ||
	    (p->auth_type!=NL80211_AUTHTYPE_OPEN_SYSTEM && p->auth_type!=NL80211_AUTHTYPE_AUTOMATIC))
		return -EOPNOTSUPP;
	if (p->privacy) {
		if (!supported_psk(&p->crypto)) return -EOPNOTSUPP;
		pmk=p->crypto.psk;
	} else if (p->crypto.wpa_versions || p->crypto.n_akm_suites || p->crypto.n_ciphers_pairwise)
		return -EOPNOTSUPP;
	bss=cfg80211_get_bss(wiphy,p->channel,p->bssid,p->ssid,p->ssid_len,
		IEEE80211_BSS_TYPE_ESS,p->privacy?IEEE80211_PRIVACY_ON:IEEE80211_PRIVACY_OFF);
	if (!bss) { pr_info("N1_WIFI_CONNECT no matching BSS\n"); return -ENOENT; }
	mutex_lock(&s->lock);
	if (s->dead || s->stopping || !s->opened) { ret=-ENETDOWN; goto put; }
	if (s->scan || s->connecting || s->leaving || s->linked) { ret=-EBUSY; goto put; }
	if ((bss->channel->band!=NL80211_BAND_2GHZ && bss->channel->band!=NL80211_BAND_5GHZ) ||
	    (bss->channel->flags&IEEE80211_CHAN_DISABLED)) { ret=-EOPNOTSUPP; goto put; }
	ret=n1_build_connect_station_91_104_6(s->request,sizeof(s->request),1,bss->bssid,
		bss->channel->hw_value,bss->channel->band==NL80211_BAND_5GHZ?1:0,
		p->ssid,p->ssid_len,pmk,pmk?32:0);
	if (ret<0) goto put;
	s->request_len=ret; s->join_bss=bss; s->connecting=true; s->join_sent=false;
	memcpy(s->bssid,bss->bssid,ETH_ALEN); memcpy(s->ssid,p->ssid,p->ssid_len); s->ssid_len=p->ssid_len;
	mod_delayed_work(system_wq,&s->control_work,0);
	mutex_unlock(&s->lock);
	return 0;
put:
	pr_info("N1_WIFI_CONNECT rejected result=%d\n",ret);
	mutex_unlock(&s->lock); cfg80211_put_bss(wiphy,bss); return ret;
}

static int disconnect(struct wiphy *wiphy,struct net_device *dev,u16 reason)
{
	struct n1_wifi *s=wiphy_priv(wiphy);
	mutex_lock(&s->lock);
	if (s->reported_connected || s->connecting) request_leave(s,reason,true);
	mod_delayed_work(system_wq,&s->control_work,0);
	mutex_unlock(&s->lock);
	return 0;
}

static int get_station(struct wiphy *wiphy,struct net_device *dev,const u8 *addr,
	struct station_info *info)
{
	struct n1_wifi *s=wiphy_priv(wiphy);
	int ret=0;
	mutex_lock(&s->lock);
	if (!s->linked || !ether_addr_equal(addr,s->bssid)) ret=-ENOENT;
	else {
		info->filled=BIT_ULL(NL80211_STA_INFO_RX_PACKETS)|BIT_ULL(NL80211_STA_INFO_TX_PACKETS)|
			BIT_ULL(NL80211_STA_INFO_RX_BYTES64)|BIT_ULL(NL80211_STA_INFO_TX_BYTES64);
		info->rx_packets=dev->stats.rx_packets; info->tx_packets=dev->stats.tx_packets;
		info->rx_bytes=dev->stats.rx_bytes; info->tx_bytes=dev->stats.tx_bytes;
	}
	mutex_unlock(&s->lock); return ret;
}

static int dump_station(struct wiphy *wiphy,struct net_device *dev,int idx,u8 *addr,
	struct station_info *info)
{
	struct n1_wifi *s=wiphy_priv(wiphy);
	if (idx) return -ENOENT;
	mutex_lock(&s->lock); memcpy(addr,s->bssid,ETH_ALEN); mutex_unlock(&s->lock);
	return get_station(wiphy,dev,addr,info);
}

static const struct cfg80211_ops cfg_ops={
	.scan=scan,.connect=connect,.disconnect=disconnect,.get_station=get_station,.dump_station=dump_station,
};

static int net_open(struct net_device *dev)
{
	struct n1_wifi *s=from_dev(dev);
	mutex_lock(&s->lock);
	if (s->dead || s->stopping) { mutex_unlock(&s->lock); return -ENODEV; }
	WRITE_ONCE(s->opened,true); netif_carrier_off(dev); netif_stop_queue(dev);
	mutex_unlock(&s->lock); return 0;
}
static int net_stop(struct net_device *dev)
{
	struct n1_wifi *s=from_dev(dev);
	mutex_lock(&s->lock);
	WRITE_ONCE(s->opened,false); scan_done(s,true);
	if (!s->stopping && (s->reported_connected || s->connecting)) request_leave(s,WLAN_REASON_DEAUTH_LEAVING,true);
	packets_off(s);
	mutex_unlock(&s->lock); return 0;
}
static netdev_tx_t net_xmit(struct sk_buff *skb,struct net_device *dev)
{
	struct n1_wifi *s=from_dev(dev);
	if (!READ_ONCE(s->linked) || !READ_ONCE(s->opened)) {
		dev->stats.tx_dropped++; dev_kfree_skb_any(skb); return NETDEV_TX_OK;
	}
	if (skb_queue_len(&s->tx)>=TX_LIMIT) { netif_stop_queue(dev); return NETDEV_TX_BUSY; }
	skb_queue_tail(&s->tx,skb);
	if (skb_queue_len(&s->tx)>=TX_LIMIT) netif_stop_queue(dev);
	return NETDEV_TX_OK;
}
static const struct net_device_ops net_ops={
	.ndo_open=net_open,.ndo_stop=net_stop,.ndo_start_xmit=net_xmit,.ndo_validate_addr=eth_validate_addr,
};
static void driver_info(struct net_device *dev,struct ethtool_drvinfo *info)
{
	strscpy(info->driver,"n1-wifi",sizeof(info->driver));
}
static const struct ethtool_ops ethtool_ops={.get_drvinfo=driver_info,.get_link=ethtool_op_get_link};

static int __init wifi_init(void)
{
	static const int rates[]={10,20,55,110,60,90,120,180,240,360,480,540};
	static const u32 ciphers[]={WLAN_CIPHER_SUITE_CCMP};
	static const u32 akms[]={WLAN_AKM_SUITE_PSK};
	static const u8 channels5[]={36,40,44,48,52,56,60,64,100,104,108,112,116,120,124,128,
		132,136,140,144,149,153,157,161,165};
	struct n1_wifi *s;
	struct wiphy *wiphy;
	struct pci_dev *p;
	u8 addr[ETH_ALEN];
	unsigned int i,count,done,errors;
	int ret;
	if (!of_machine_is_compatible("apple,j714s") || !mac || !mac_pton(mac,addr) ||
	    !is_valid_ether_addr(addr)) return -EINVAL;
	if (n1_data_rx_status_v2(&count) || n1_data_tx_status_v2(&done,&errors)) return -EIO;
	p=pci_get_domain_bus_and_slot(0,1,PCI_DEVFN(0,1));
	if (!p || p->vendor!=0x106b || p->device!=0x1902) { pci_dev_put(p); return -ENODEV; }
	wiphy=wiphy_new(&cfg_ops,sizeof(*s));
	if (!wiphy) { pci_dev_put(p); return -ENOMEM; }
	s=wiphy_priv(wiphy); s->wiphy=wiphy; s->pdev=p;
	mutex_init(&s->lock); skb_queue_head_init(&s->tx);
	INIT_DELAYED_WORK(&s->control_work,control); INIT_DELAYED_WORK(&s->tx_work,transmit);
	ret=n1_alpha_state_v9(&s->link,&s->cursor);
	/* No adoption of an association unknown to cfg80211. */
	if (ret || (s->link.requested && !s->link.failed)) { ret=ret?ret:-EBUSY; goto free_wiphy; }
	for (i=0;i<ARRAY_SIZE(s->channels);i++) {
		s->channels[i].band=i<13?NL80211_BAND_2GHZ:NL80211_BAND_5GHZ;
		s->channels[i].hw_value=i<13?1+i:channels5[i-13];
		s->channels[i].center_freq=i<13?2412+5*i:5000+5*channels5[i-13];
		s->channels[i].max_power=20;
	}
	for (i=0;i<ARRAY_SIZE(rates);i++) { s->rates[i].bitrate=rates[i]; s->rates[i].hw_value=i; }
	s->bands[0].band=NL80211_BAND_2GHZ; s->bands[0].channels=s->channels; s->bands[0].n_channels=13;
	s->bands[0].bitrates=s->rates; s->bands[0].n_bitrates=ARRAY_SIZE(rates);
	s->bands[1].band=NL80211_BAND_5GHZ; s->bands[1].channels=s->channels+13;
	s->bands[1].n_channels=ARRAY_SIZE(channels5); s->bands[1].bitrates=s->rates+4;
	s->bands[1].n_bitrates=ARRAY_SIZE(rates)-4;
	wiphy->bands[NL80211_BAND_2GHZ]=&s->bands[0]; wiphy->bands[NL80211_BAND_5GHZ]=&s->bands[1];
	wiphy->interface_modes=BIT(NL80211_IFTYPE_STATION); wiphy->max_scan_ssids=1;
	wiphy->max_scan_ie_len=2048;
	wiphy->signal_type=CFG80211_SIGNAL_TYPE_MBM;
	wiphy->cipher_suites=ciphers; wiphy->n_cipher_suites=ARRAY_SIZE(ciphers);
	wiphy->akm_suites=akms; wiphy->n_akm_suites=ARRAY_SIZE(akms);
	wiphy->flags|=WIPHY_FLAG_SUPPORTS_FW_ROAM;
	wiphy_ext_feature_set(wiphy,NL80211_EXT_FEATURE_4WAY_HANDSHAKE_STA_PSK);
	memcpy(wiphy->perm_addr,addr,ETH_ALEN); set_wiphy_dev(wiphy,&p->dev);
	ret=wiphy_register(wiphy);
	if (ret) goto free_wiphy;
	s->dev=alloc_netdev(0,"wlan%d",NET_NAME_ENUM,ether_setup);
	if (!s->dev) { ret=-ENOMEM; goto unregister_wiphy; }
	s->wdev.wiphy=wiphy; s->wdev.iftype=NL80211_IFTYPE_STATION; s->wdev.netdev=s->dev;
	s->dev->ieee80211_ptr=&s->wdev; s->dev->netdev_ops=&net_ops; s->dev->ethtool_ops=&ethtool_ops;
	s->dev->min_mtu=68; s->dev->max_mtu=1500;
	SET_NETDEV_DEV(s->dev,&p->dev); eth_hw_addr_set(s->dev,addr);
	memcpy(s->dev->perm_addr,addr,ETH_ALEN); netif_carrier_off(s->dev);
	ret=n1_data_rx_attach_v2(receive,s);
	if (ret) goto free_netdev;
	ret=register_netdev(s->dev);
	if (ret) goto detach;
	active=s; schedule_delayed_work(&s->control_work,0);
	pr_info("N1_WIFI: %s registered, scan/connect/disconnect and direct RX\n",s->dev->name);
	return 0;
detach:
	n1_data_rx_detach_v2(s);
free_netdev:
	free_netdev(s->dev);
unregister_wiphy:
	wiphy_unregister(wiphy);
free_wiphy:
	wiphy_free(wiphy); pci_dev_put(p); return ret;
}
static void __exit wifi_exit(void)
{
	struct n1_wifi *s=active;
	unsigned int cursor;
	int ret;
	if (!s) return;
	mutex_lock(&s->lock); s->stopping=true; mutex_unlock(&s->lock);
	cancel_delayed_work_sync(&s->control_work);
	n1_data_rx_detach_v2(s);
	mutex_lock(&s->lock); scan_done(s,true);
	if (!s->dead && (s->reported_connected || s->connecting))
		request_leave(s,WLAN_REASON_DEAUTH_LEAVING,true);
	while (s->leaving && !s->dead) {
		ret=n1_alpha_state_v9(&s->link,&cursor);
		if (!ret) ret=progress_leave(s);
		if (ret) break;
		if (s->leaving) msleep(10);
	}
	notify_down(s,WLAN_REASON_DEAUTH_LEAVING,true);
	mutex_unlock(&s->lock);
	unregister_netdev(s->dev); free_netdev(s->dev);
	wiphy_unregister(s->wiphy); pci_dev_put(s->pdev); wiphy_free(s->wiphy);
}
module_init(wifi_init);
module_exit(wifi_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Native N1 cfg80211 station frontend");
