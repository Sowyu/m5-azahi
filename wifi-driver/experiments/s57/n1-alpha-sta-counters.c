// SPDX-License-Identifier: GPL-2.0
/* One read-only station-counter request through the current v9 owner.
 * No reset, ring changes, DMA ownership or credential inputs. */
#include <linux/module.h>
#include <linux/proc_fs.h>
#include <linux/unaligned.h>
#include <linux/uaccess.h>
#include "../s49/n1-v9-api.h"
static bool launch;
module_param(launch,bool,0400);
static int result=-EINPROGRESS;
module_param(result,int,0444);
static unsigned int received;
module_param(received,uint,0444);
static u8 reply[4096];
static ssize_t reply_read(struct file *f,char __user *buf,size_t count,loff_t *pos)
{ return simple_read_from_buffer(buf,count,pos,reply,received); }
static const struct proc_ops ops={.proc_read=reply_read};
static int __init counter_init(void)
{
 u8 request[46]={0},handle;
 u16 sequence;
 size_t length=sizeof(reply);
 int ret;
 if (!launch) return 0;
 ret=n1_alpha_cursor_v9(&sequence,&handle);
 if (ret) return ret;
 sequence=sequence==65535?1:sequence+1;
 put_unaligned_le16(sizeof(request),request+16);
 put_unaligned_le16(sequence,request+18);
 put_unaligned_le32(0xb0001,request+20);
 put_unaligned_le64(1ULL<<37,request+24);
 request[32]=1;
 put_unaligned_le16(0x16b,request+33);
 put_unaligned_le16(9,request+35);
 /* Global station counters: selector0, scope0, matching native getStatistics. */
 if (!proc_create("n1_alpha_sta_counters",0400,NULL,&ops)) return -ENOMEM;
 result=n1_alpha_exchange_v9(request,sizeof(request),reply,&length,false);
 if (!result) {
  received=length;
  if (length<24 || reply[0]!=0x41 || reply[1]!=24 ||
      get_unaligned_le16(reply+16)!=length || get_unaligned_le16(reply+18)!=sequence ||
      (get_unaligned_le32(reply+20)&~BIT(30))!=0xb0001 || get_unaligned_le16(reply+14)) result=-EPROTO;
 }
 pr_info("N1_STA_COUNTERS seq=%u result=%d received=%u\n",sequence,result,received);
 return 0;
}
static void __exit counter_exit(void) { remove_proc_entry("n1_alpha_sta_counters",NULL); }
module_init(counter_init);
module_exit(counter_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only native N1 station counters");
