// SPDX-License-Identifier: GPL-2.0
/* Private one-shot STA connection caller. Credential bytes enter through a
 * root-only write, never module arguments, logs or a readable proc node. */
#include <linux/capability.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/proc_fs.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include "../s41/n1-v8-api.h"
#include "../common/n1-aci-connect.h"
static DEFINE_MUTEX(connect_lock);
static bool attempted;
static int result=-EINPROGRESS;
static unsigned int sequence;
module_param(attempted,bool,0444);
module_param(result,int,0444);
module_param(sequence,uint,0444);
struct connect_buffers { u8 input[73],request[300],reply[4096]; };
static ssize_t connect_write(struct file *file,const char __user *input,
 size_t count,loff_t *pos)
{
 struct connect_buffers *b;
 u16 last_sequence;
 u8 handle;
 size_t reply_length;
 int ret,length;
 if (!capable(CAP_NET_ADMIN)) return -EPERM;
 if (count!=73 || *pos) return -EINVAL;
 b=kzalloc(sizeof(*b),GFP_KERNEL);
 if (!b) return -ENOMEM;
 if (copy_from_user(b->input,input,count)) { ret=-EFAULT; goto free; }
 mutex_lock(&connect_lock);
 if (attempted) { ret=-EALREADY; goto unlock; }
 ret=n1_alpha_cursor_v8(&last_sequence,&handle);
 if (ret) goto unlock;
 /* Validate every input before any command is sent. */
 length=n1_build_connect_91_104_6(b->request,sizeof(b->request),1,b->input,
  b->input[6],b->input+8,b->input[7],b->input+41,b->input[40]);
 if (length<0) { ret=length; goto unlock; }
 sequence=last_sequence==65535?1:last_sequence+1;
 length=n1_build_clear_vendor_ie(b->request,sizeof(b->request),sequence);
 if (length<0) { ret=length; goto unlock; }
 attempted=true;
 reply_length=sizeof(b->reply);
 ret=n1_alpha_exchange_v8(b->request,length,b->reply,&reply_length,false);
 if (ret) goto done;
 sequence=sequence==65535?1:sequence+1;
 length=n1_build_connect_91_104_6(b->request,sizeof(b->request),sequence,b->input,
  b->input[6],b->input+8,b->input[7],b->input+41,b->input[40]);
 if (length<0) { ret=length; goto done; }
 reply_length=sizeof(b->reply);
 ret=n1_alpha_exchange_v8(b->request,length,b->reply,&reply_length,true);
done:
 result=ret;
 pr_info("N1_CONNECT_V8 command_result=%d sequence=%u; association is asynchronous\n",ret,sequence);
unlock:
 mutex_unlock(&connect_lock);
free:
 kfree_sensitive(b);
 if (ret) return ret;
 *pos+=count;
 return count;
}
static const struct proc_ops connect_ops={.proc_write=connect_write};
static int __init connect_init(void)
{
 return proc_create("n1_connect_v8",0200,NULL,&connect_ops)?0:-ENOMEM;
}
static void __exit connect_exit(void) { remove_proc_entry("n1_connect_v8",NULL); }
module_init(connect_init);
module_exit(connect_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Private bounded native N1 station connection caller");
