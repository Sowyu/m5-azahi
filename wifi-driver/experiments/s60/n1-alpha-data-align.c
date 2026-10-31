// SPDX-License-Identifier: GPL-2.0
/* Paired payload DMA-alignment diagnostic on a separate native AC2/TID4 queue.
 * Proc writes are one alignment byte (0 or 2), then an unchanged Ethernet frame.
 * At most twelve submissions; the frontend must remain down. All
 * published DMA remains pinned even on rejection/timeout/firmware abort.
 * This module must be quiesced before any future transport handover/reset.
 */
#include <linux/bitmap.h>
#include <linux/netdevice.h>
#include <linux/rtnetlink.h>
#include <net/net_namespace.h>
#include <linux/delay.h>
#include <linux/dma-mapping.h>
#include <linux/io.h>
#include <linux/iommu.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/proc_fs.h>
#include <linux/slab.h>
#include <linux/unaligned.h>
#include <linux/uaccess.h>
#include <linux/wait.h>
#include <linux/workqueue.h>
#include "../s41/n1-s19-abi.h"
#include "../s41/n1-transport-abi.h"
#include "../s49/n1-v9-api.h"
#include "../s58/n1-ac1-api.h"
#include "../s51/n1-tx-api.h"
#include "../common/n1-tx-footer.h"
#include "../common/n1-tx-completion.h"
#define COUNT 128
#define BUFFER_SIZE 2048
#define POOL_SIZE (0x4000 + COUNT*BUFFER_SIZE)
#define CR_OFF 0
#define TR_OFF 0x1000
#define BUF_OFF(tag) (0x4000 + BUFFER_SIZE*(tag))
#define CR_ID 78
#define CR_INDEX 194
#define TR_ID 27
#define CR_HEAD 0x78
#define CR_TAIL 0x3cc
#define TR_HEAD 0x5a0
#define TR_TAIL 0x24c
struct data_tx {
 struct transport *control;
 struct pci_dev *pdev;
 void *pool;
 dma_addr_t dma;
 struct delayed_work work;
 u16 head,tail,next_complete;
 DECLARE_BITMAP(posted,COUNT);
 u16 lengths[COUNT];
 u8 completions[COUNT][32];
};
static struct data_tx *active;
static bool launch,stopping;
static int result=-EINPROGRESS;
static unsigned int phase,submitted,completed,failed;
module_param(launch,bool,0400);
module_param(result,int,0444);
module_param(phase,uint,0444);
module_param(submitted,uint,0444);
module_param(completed,uint,0444);
module_param(failed,uint,0444);
static u16 idx(struct data_tx *s,unsigned int offset)
{
	u16 v=le16_to_cpu(READ_ONCE(*(__le16 *)(s->control->shared.memory+offset)));
	dma_rmb(); return v;
}
static void putidx(struct data_tx *s,unsigned int offset,u16 v)
{
	WRITE_ONCE(*(__le16 *)(s->control->shared.memory+offset),cpu_to_le16(v));
}
static bool alive(struct data_tx *s)
{
	return pci_get_drvdata(s->pdev)==s->control &&
		readl(s->control->shared.owner->bar+8)==2 &&
		readl(s->control->shared.owner->bar+12)==2;
}
static void bell(struct data_tx *s,unsigned int offset)
{
	dma_wmb(); writel(1,s->control->shared.owner->bar+offset);
}
/* Caller serializes the existing control management indices with S41. */
static int management(struct data_tx *s,const u8 *message,unsigned int length)
{
	struct transport *c=s->control;
	u16 tag=c->mh,next=(tag+1)%16;
	u8 *td=c->shared.memory+0x820+16*tag, *cd=c->shared.memory+0x720+16*tag;
	unsigned int i;
	if (length>128 || !alive(s) || idx(s,CR_HEAD)!=tag || idx(s,CR_TAIL)!=tag ||
	    idx(s,TR_HEAD)!=tag || idx(s,TR_TAIL)!=tag) return -EBUSY;
	memset(c->pool+128*tag,0,128); memcpy(c->pool+128*tag,message,length);
	put_unaligned_le32(1|(length<<8),td);
	put_unaligned_le64(c->dma+128*tag,td+4); put_unaligned_le32(tag,td+12);
	dma_wmb(); putidx(s,TR_HEAD,next); bell(s,0x1004);
	for (i=0;i<1000;i++) {
		if (!alive(s)) return -EIO;
		if (idx(s,CR_HEAD)==next && idx(s,TR_TAIL)==next) {
			dma_rmb();
			pr_info("N1_DATA_ALIGN_MGMT tag=%u raw=%*phN\n",tag,16,cd);
			if (cd[0]!=1 || cd[1]!=4 || get_unaligned_le16(cd+2) ||
			    get_unaligned_le16(cd+4)!=tag || get_unaligned_le16(cd+6)!=length ||
			    get_unaligned_le32(cd+8) || get_unaligned_le32(cd+12)) return -EPROTO;
			memset(cd,0,16); dma_wmb(); putidx(s,CR_TAIL,next); dma_wmb(); c->mh=next; return 0;
		}
		usleep_range(1000,1500);
	}
	return -ETIMEDOUT;
}
static int open_rings(struct data_tx *s)
{
 u8 m[64]={0};
 int ret;
 /* Independent second data-TX pool slots. Native default STA AC2.
  * The locally recovered AC-to-TID table is {0, 2, 4, 6}.
  * Client data: reserved0, hardware-interface0, TID4, AC2, zero peer. */
 m[0]=2; m[2]=4;
 put_unaligned_le16(CR_ID,m+4); put_unaligned_le16(CR_INDEX,m+6);
 put_unaligned_le64(s->dma+CR_OFF,m+8); put_unaligned_le16(COUNT,m+16);
 put_unaligned_le16(0xffff,m+18); put_unaligned_le16(18,m+20);
 put_unaligned_le16(3,m+28);
 m[46]=4; m[47]=2;
 ret=management(s,m,54);
 if (ret) return ret;
 phase=2;
 memset(m,0,sizeof(m)); m[0]=1; m[2]=4;
 put_unaligned_le16(TR_ID,m+4); put_unaligned_le16(TR_ID,m+6);
 put_unaligned_le64(s->dma+TR_OFF,m+8); put_unaligned_le64(U64_MAX,m+16);
 put_unaligned_le16(COUNT,m+24); put_unaligned_le16(CR_ID,m+26);
 put_unaligned_le16(18,m+28); put_unaligned_le16(3,m+36);
 m[54]=4; m[55]=2;
 ret=management(s,m,62);
 if (!ret) phase=3;
 return ret;
}
static int drain(struct data_tx *s)
{
 unsigned int n,i;
 for (n=0;n<COUNT;n++) {
  u16 head=idx(s,CR_HEAD+2*CR_INDEX),tag;
  struct n1_tx_completion completion;
  u8 *cd;
  if (head>=COUNT) return -EPROTO;
  if (head==s->tail) return 0;
  cd=s->pool+CR_OFF+32*s->tail; dma_rmb();
  if (!get_unaligned_le64(cd) && !get_unaligned_le64(cd+8)) return 0;
  if (n1_decode_tx_completion(cd,32,TR_ID,COUNT,s->next_complete,s->lengths,&completion)) {
   pr_err("N1_DATA_ALIGN_BAD_CD raw=%*phN; DMA retained\n",32,cd); return -EPROTO;
  }
  /* No partial ownership return if any member of the batch is invalid. */
  for (i=0;i<completion.count;i++)
   if (!test_bit((completion.first+i)%COUNT,s->posted)) return -EPROTO;
  if (completed<8) pr_info("N1_DATA_ALIGN_COMPLETE first=%u last=%u count=%u fw_status=%u raw=%*phN\n",
   completion.first,completion.last,completion.count,completion.firmware_status,32,cd);
  for (i=0;i<completion.count;i++) {
   tag=(completion.first+i)%COUNT;
   memcpy(s->completions[completed%COUNT],cd,32);
   if (!n1_tx_firmware_success(completion.firmware_status)) failed++;
   completed++;
   __clear_bit(tag,s->posted);
   s->lengths[tag]=0;
  }
  s->next_complete=(completion.last+1)%COUNT;
  memset(cd,0,32); s->tail=(s->tail+1)%COUNT;
  dma_wmb(); putidx(s,CR_TAIL+2*CR_INDEX,s->tail);
 }
 return 0;
}
static void poll_tx(struct work_struct *work)
{
 struct data_tx *s=container_of(to_delayed_work(work),struct data_tx,work);
 mutex_lock(&s->control->io_lock);
 result=stopping?-ESHUTDOWN:(alive(s)?drain(s):-EIO);
 mutex_unlock(&s->control->io_lock);
 if (!result && !READ_ONCE(stopping)) schedule_delayed_work(&s->work,msecs_to_jiffies(1));
 else pr_err("N1_DATA_ALIGN_STOP result=%d completed=%u; DMA retained\n",result,completed);
}
/* Process context only: copy now; DMA ownership ends at validated completion. */
static int submit_frame(const void *data,size_t length,unsigned int alignment)
{
 struct data_tx *s=active;
 u16 tail,next,tag;
 u8 *td;
 int ret=0;
 if (!s || !data || length<14 || length>1514 || (*(const u8 *)data & 1) ||
     (alignment!=0 && alignment!=2)) return -EINVAL;
 mutex_lock(&s->control->io_lock);
 if (result || stopping || !alive(s)) { ret=result?result:-EIO; goto out; }
 if (submitted>=12) { ret=-EDQUOT; goto out; }
 tail=idx(s,TR_TAIL+2*TR_ID);
 if (tail>=COUNT) { ret=-EPROTO; goto out; }
 tag=s->head; next=(tag+1)%COUNT;
 if (next==tail || test_bit(tag,s->posted)) { ret=-EAGAIN; goto out; }
 td=s->pool+TR_OFF+32*tag;
 memset(s->pool+BUF_OFF(tag)+alignment,0,60);
 memcpy(s->pool+BUF_OFF(tag)+alignment,data,length);
 length=max_t(size_t,length,60);
 memset(td,0,32);
 /* Native kind3 = DMA payload plus header/footer metadata. */
 put_unaligned_le32(3|(length<<8),td);
 put_unaligned_le64(s->dma+BUF_OFF(tag)+alignment,td+4); put_unaligned_le32(tag,td+12);
 ret=n1_build_tx_footer(td+16,16,0,0);
 if (ret<0) goto out;
 ret=0;
 s->lengths[tag]=length; __set_bit(tag,s->posted); s->head=next; submitted++;
 dma_wmb(); putidx(s,TR_HEAD+2*TR_ID,s->head); bell(s,0x1030);
out:
 mutex_unlock(&s->control->io_lock); return ret;
}
/* Bounded private diagnostic envelope, not a network interface. */
static ssize_t write_frame(struct file *file,const char __user *user,size_t length,loff_t *offset)
{
 u8 frame[1515];
 struct net_device *dev;
 int ret;
 if (length<15 || length>sizeof(frame)) return -EMSGSIZE;
 if (copy_from_user(frame,user,length)) return -EFAULT;
 rtnl_lock();
 dev=dev_get_by_name(&init_net,"n1data0");
 if (!dev) ret=-ENODEV;
 else {
  ret=netif_running(dev)?-EBUSY:submit_frame(frame+1,length-1,frame[0]);
  dev_put(dev);
 }
 rtnl_unlock();
 return ret?ret:length;
}
static const struct proc_ops frame_ops={.proc_write=write_frame};
static int __init data_init(void)
{
	struct pci_dev *p,*control;
	struct old_boot *boot;
	struct transport *c;
	struct data_tx *s=NULL;
	struct iommu_domain *domain;
	unsigned int completed,status,count,old_done,old_errors;
	bool pending;
	u16 command;
	int ret=-ENODEV;
	if (!of_machine_is_compatible("apple,j714s")) return ret;
	ret=n1_data_tx_status_v2(&old_done,&old_errors);
	if (ret || old_done!=227 || old_errors) return ret?ret:-EBUSY;
	ret=n1_data_tx_status_ac1(&old_done,&old_errors);
	if (ret || old_done!=70 || old_errors) return ret?ret:-EBUSY;
	ret=n1_alpha_scan_status_v9(&completed,&status,&count,&pending);
	if (ret || pending) return ret?ret:-EBUSY;
	ret=-ENODEV;
	p=pci_get_domain_bus_and_slot(0,1,PCI_DEVFN(0,1));
	if (!p) return ret;
	control=pci_get_slot(p->bus,0);
	if (!control) goto put;
	device_lock(&control->dev); device_lock(&p->dev);
	if (!control->driver || strcmp(control->driver->name,"n1-control-handoff") || p->driver ||
	    p->vendor!=0x106b || p->device!=0x1902 || pci_read_config_word(p,PCI_COMMAND,&command) || command!=0x406) goto out;
	boot=pci_get_drvdata(control); c=pci_get_drvdata(p);
	if (!boot || !boot->alpha || !c || c->magic!=0x5334395452414e53ULL ||
	    c->shared.owner!=boot->alpha || c->pdev!=p || !c->shared.memory || !c->pool) goto out;
	mutex_lock(&c->command_lock); mutex_lock(&c->io_lock);
	if (c->mh!=14 || c->sequence!=59 || c->waiting || c->txhead!=11 || c->txtail!=11 ||
	    !c->tx_done || !c->response_done || c->command_result || c->cid!=0xb0001 ||
	    readl(boot->bar+0x8000)!=2 || readl(boot->bar+0x8050)!=2) goto unlock;
	domain=iommu_get_domain_for_dev(&p->dev);
	if (!domain || !iommu_is_dma_domain(domain)) goto unlock;
	s=kvzalloc(sizeof(*s),GFP_KERNEL);
	if (!s) { ret=-ENOMEM; goto unlock; }
	s->control=c; s->pdev=p; INIT_DELAYED_WORK(&s->work,poll_tx);
	if (!alive(s) || idx(s,CR_HEAD+2*CR_INDEX) || idx(s,CR_TAIL+2*CR_INDEX) ||
	    idx(s,TR_HEAD+2*TR_ID) || idx(s,TR_TAIL+2*TR_ID)) goto free_state;
	s->pool=dma_alloc_coherent(&p->dev,POOL_SIZE,&s->dma,GFP_KERNEL);
	if (!s->pool) { ret=-ENOMEM; goto free_state; }
	ret=-EFAULT;
	if (s->dma>U32_MAX-POOL_SIZE || !iommu_iova_to_phys(domain,s->dma) ||
	    !iommu_iova_to_phys(domain,s->dma+POOL_SIZE-1)) goto free_pool;
	memset(s->pool,0,POOL_SIZE);
	pr_info("N1_DATA_ALIGN_PREPARED launch=%d count=128 buffer=2048 CR78/194 TR27 AC2 footer16 appendix10\n",launch);
	ret=0;
	if (!launch) goto free_pool;
	__module_get(THIS_MODULE); active=s; phase=1;
	result=open_rings(s);
	if (!result) {
		phase=4;
		if (!proc_create("n1_alpha_align_tx",0200,NULL,&frame_ops)) result=-ENOMEM;
		else schedule_delayed_work(&s->work,msecs_to_jiffies(1));
	}
	pr_info("N1_DATA_ALIGN_RESULT result=%d phase=%u submitted=%u; DMA pinned\n",result,phase,submitted);
	mutex_unlock(&c->io_lock); mutex_unlock(&c->command_lock);
	device_unlock(&p->dev); device_unlock(&control->dev); pci_dev_put(control);
	return 0;
free_pool:
	dma_free_coherent(&p->dev,POOL_SIZE,s->pool,s->dma);
free_state:
	kvfree(s);
unlock:
	mutex_unlock(&c->io_lock); mutex_unlock(&c->command_lock);
out:
	device_unlock(&p->dev); device_unlock(&control->dev); pci_dev_put(control);
put:
	pci_dev_put(p); return ret;
}
static void __exit data_exit(void) { }
module_init(data_init);
module_exit(data_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Bounded N1 AC2 payload DMA-alignment comparison");
