// SPDX-License-Identifier: GPL-2.0
/* Temporary Ethernet frontend for the already associated native N1 STA.
 * Owns no DMA. Firmware connection events control carrier. Packet APIs run
 * only in process context; ndo_start_xmit only queues bounded host skbs.
 */
#include <linux/module.h>
#include <linux/etherdevice.h>
#include <linux/hex.h>
#include <linux/netdevice.h>
#include <linux/workqueue.h>
#include "../s49/n1-v9-api.h"
#include "../s50/n1-data-api.h"
#include "../s51/n1-tx-api.h"
#include "../common/n1-aci-events.h"
#define QUEUE_LIMIT 128
struct n1_front {
 struct net_device *dev;
 struct delayed_work work;
 struct sk_buff_head tx;
 unsigned int rx_cursor,event_cursor;
 bool stopping,linked;
 u8 frame[16384],event[4096],tx_frame[1514];
};
static struct net_device *active;
static char *mac;
module_param(mac,charp,0400);
static int events(struct n1_front *s)
{
 unsigned int n,ring;
 size_t len;
 struct n1_aci_event event;
 int ret;
 for(n=0;n<512;n++) {
  len=sizeof(s->event);
  ret=n1_alpha_record_v9(s->event_cursor,&ring,s->event,&len);
  if(ret==-ENOENT) return 0;
  if(ret) return ret; /* lost history cannot establish connection state */
  s->event_cursor++;
  if(n1_aci_parse_event(s->event,len,&event)) continue;
  if(event.kind==N1_EVENT_CONNECT_COMPLETE) s->linked=!event.header.status;
  else if(event.kind==N1_EVENT_CONNECTION_LOST || event.kind==N1_EVENT_CONNECTION_FAILED)
   s->linked=false;
 }
 return -EOVERFLOW;
}
static void io_work(struct work_struct *work)
{
 struct n1_front *s=container_of(to_delayed_work(work),struct n1_front,work);
 struct net_device *dev=s->dev;
 struct sk_buff *skb;
 unsigned int n,count,done,errors;
 size_t len;
 u8 cd[32];
 int ret;
 if(READ_ONCE(s->stopping)) return;
 ret=events(s);
 if(ret || n1_data_rx_status_v2(&count) || n1_data_tx_status_v2(&done,&errors)) {
  s->linked=false;
  netif_carrier_off(dev); netif_stop_queue(dev);
  pr_err("N1_NET_STOP transport unavailable; host frontend stopped\n");
  return;
 }
 if(!s->linked) { netif_carrier_off(dev); netif_stop_queue(dev); goto again; }
 netif_carrier_on(dev);
 for(n=0;n<128;n++) {
  skb=skb_dequeue(&s->tx);
  if(!skb) break;
  if(skb->len>sizeof(s->tx_frame) || skb_copy_bits(skb,0,s->tx_frame,skb->len)) ret=-EMSGSIZE;
  else ret=n1_data_tx_v2(s->tx_frame,skb->len);
  if(ret==-EAGAIN) { skb_queue_head(&s->tx,skb); break; }
  if(ret) dev->stats.tx_errors++;
  else { dev->stats.tx_packets++; dev->stats.tx_bytes+=skb->len; }
  dev_kfree_skb_any(skb);
 }
 if(skb_queue_len(&s->tx)<QUEUE_LIMIT/2) netif_wake_queue(dev);
 for(n=0;n<256;n++) {
  len=sizeof(s->frame);
  ret=n1_data_rx_read_v2(s->rx_cursor,cd,s->frame,&len);
  if(ret==-ENOENT) break;
  if(ret==-EOVERFLOW) { s->rx_cursor++; dev->stats.rx_missed_errors++; continue; }
  if(ret) { dev->stats.rx_errors++; break; }
  s->rx_cursor++;
  /* Observed native STA payload: two padding bytes then Ethernet frame.
   * CHECKSUM_NONE makes Linux validate checksums; no metadata offloads yet. */
  if(len<ETH_HLEN+2 || len>1516 || s->frame[0] || s->frame[1]) {
   dev->stats.rx_length_errors++; continue;
  }
  len-=2;
  skb=netdev_alloc_skb_ip_align(dev,len);
  if(!skb) { dev->stats.rx_dropped++; continue; }
  skb_put_data(skb,s->frame+2,len);
  skb->protocol=eth_type_trans(skb,dev);
  skb->ip_summed=CHECKSUM_NONE;
  dev->stats.rx_packets++; dev->stats.rx_bytes+=len;
  netif_rx(skb);
 }
again:
 if(!READ_ONCE(s->stopping)) schedule_delayed_work(&s->work,msecs_to_jiffies(1));
}
static int net_open(struct net_device *dev)
{
 struct n1_front *s=netdev_priv(dev);
 s->stopping=false;
 netif_start_queue(dev);
 schedule_delayed_work(&s->work,0);
 return 0;
}
static int net_stop(struct net_device *dev)
{
 struct n1_front *s=netdev_priv(dev);
 WRITE_ONCE(s->stopping,true);
 netif_stop_queue(dev); netif_carrier_off(dev);
 cancel_delayed_work_sync(&s->work);
 skb_queue_purge(&s->tx);
 return 0;
}
static netdev_tx_t net_xmit(struct sk_buff *skb,struct net_device *dev)
{
 struct n1_front *s=netdev_priv(dev);
 if(skb_queue_len(&s->tx)>=QUEUE_LIMIT) { netif_stop_queue(dev); return NETDEV_TX_BUSY; }
 skb_queue_tail(&s->tx,skb);
 if(skb_queue_len(&s->tx)>=QUEUE_LIMIT) netif_stop_queue(dev);
 return NETDEV_TX_OK;
}
static const struct net_device_ops net_ops={
 .ndo_open=net_open,.ndo_stop=net_stop,.ndo_start_xmit=net_xmit,
 .ndo_validate_addr=eth_validate_addr,
};
static int __init front_init(void)
{
 struct n1_front *s;
 u8 addr[ETH_ALEN];
 unsigned int count,done,errors;
 int ret;
 if(!mac || !mac_pton(mac,addr) || !is_valid_ether_addr(addr)) return -EINVAL;
 if(n1_data_rx_status_v2(&count) || n1_data_tx_status_v2(&done,&errors)) return -EIO;
 active=alloc_netdev(sizeof(*s),"n1data%d",NET_NAME_USER,ether_setup);
 if(!active) return -ENOMEM;
 s=netdev_priv(active); s->dev=active; s->rx_cursor=count;
 skb_queue_head_init(&s->tx); INIT_DELAYED_WORK(&s->work,io_work);
 ret=events(s);
 if(ret || !s->linked) { free_netdev(active); active=NULL; return ret?ret:-ENOLINK; }
 active->netdev_ops=&net_ops; active->min_mtu=68; active->max_mtu=1500;
 eth_hw_addr_set(active,addr); netif_carrier_off(active);
 ret=register_netdev(active);
 if(ret) { free_netdev(active); active=NULL; return ret; }
 pr_info("N1_NET_READY %s: temporary packet frontend, native STA association verified\n",active->name);
 return 0;
}
static void __exit front_exit(void)
{
 if(!active) return;
 unregister_netdev(active); free_netdev(active);
}
module_init(front_init);
module_exit(front_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Private N1 native packet path validation frontend");
