// SPDX-License-Identifier: GPL-2.0
/* Bounded callers for S41. Only known queries, station setup and one
 * native passive channel1 scan. Owns no DMA; raw copies are private.
 */
#include <linux/module.h>
#include <linux/etherdevice.h>
#include <linux/hex.h>
#include <linux/proc_fs.h>
#include <linux/uaccess.h>
#include <linux/unaligned.h>
#include "../s49/n1-v9-api.h"
static bool launch;
module_param(launch,bool,0400);
static unsigned int query, sequence=0, repeat=1, completed, received;
module_param(query,uint,0400);
module_param(sequence,uint,0400);
module_param(repeat,uint,0400);
module_param(completed,uint,0444);
module_param(received,uint,0444);
static char *mac;
module_param(mac,charp,0400);
static int result=-EINPROGRESS;
module_param(result,int,0444);
static u8 reply[4096];
static ssize_t reply_read(struct file *f,char __user *buf,size_t count,loff_t *pos)
{
	return simple_read_from_buffer(buf,count,pos,reply,received);
}
static const struct proc_ops ops={.proc_read=reply_read};
static int __init client_init(void)
{
	u8 req[56]={0};
	size_t length=24,got;
	unsigned int i;
	u16 last_sequence;
	u8 handle;
	int ret;
	if (!launch) return 0;
	ret=n1_alpha_cursor_v9(&last_sequence,&handle);
	if (ret) return ret;
	if (!sequence) sequence=last_sequence==65535?1:last_sequence+1;
	if (!sequence || !repeat || repeat>32 || sequence+repeat>65536 ||
	    (query!=0 && query!=1 && query!=2 && query!=8 && query!=10 && query!=19 && query!=47 && query!=0x1000f))
		return -EINVAL;
	if ((query==1 || query==2 || query==0x1000f) && repeat!=1) return -EINVAL;
	if (query==1) {
		if (!mac || !mac_pton(mac,req+24) || !is_valid_ether_addr(req+24)) return -EINVAL;
		length=30;
	} else if (query==2) {
		length=29;
		put_unaligned_le16(0xb00,req+24);
	} else if (query==19 || query==47) {
		length=25;
		req[24]=1;
	} else if (query==0x1000f) {
		length=56;
		req[24]=1;
		req[27]=0x80;
		req[31]=0x12;
		put_unaligned_le16(40,req+32);
		put_unaligned_le16(40,req+34);
		put_unaligned_le16(120,req+36);
		put_unaligned_le16(0x104,req+38);
		put_unaligned_le16(5,req+40);
		req[42]=1;
		req[43]=10;
		put_unaligned_le16(0x165,req+47);
		put_unaligned_le16(5,req+49);
		req[53]=1;
	}
	if (!proc_create("n1_alpha_v9_reply",0400,NULL,&ops)) return -ENOMEM;
	put_unaligned_le16(length,req+16);
	put_unaligned_le32(query,req+20);
	for (i=0;i<repeat;i++) {
		put_unaligned_le16(sequence+i,req+18);
		got=sizeof(reply);
		result=n1_alpha_exchange_v9(req,length,reply,&got,query==0x1000f);
		if (result) break;
		received=got;
		if (got<24 || reply[0]!=0x41 || reply[1]!=24 ||
		    get_unaligned_le16(reply+16)!=got || get_unaligned_le16(reply+18)!=sequence+i ||
		    (get_unaligned_le32(reply+20)&~BIT(30))!=query || get_unaligned_le16(reply+14)) {
			result=-EPROTO;
			break;
		}
		completed++;
	}
	pr_info("N1_V9_CLIENT cid=%08x sequence=%u repeat=%u completed=%u result=%d received=%u\n",
		query,sequence,repeat,completed,result,received);
	return 0;
}
static void __exit client_exit(void) { remove_proc_entry("n1_alpha_v9_reply",NULL); }
module_init(client_init);
module_exit(client_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Bounded queries, station setup and passive scan through Alpha v2");
