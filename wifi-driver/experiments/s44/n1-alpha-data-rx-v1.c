// SPDX-License-Identifier: GPL-2.0
/* Private data RX bring-up alongside fresh S41. No reset or association.
 * One default STA completion ring and shared RX transfer ring. All
 * published DMA remains pinned even on rejection/timeout/firmware abort.
 * This module must be quiesced before any future transport handover/reset.
 */
#include <linux/bitmap.h>
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
#include "../s41/n1-v8-api.h"
#include "n1-data-api.h"
#define COUNT 128
#define BUFFER_SIZE 16384
#define POOL_SIZE (0x4000 + COUNT * BUFFER_SIZE)
#define CR_OFF 0
#define TR_OFF 0x2000
#define BUF_OFF(tag) (0x4000 + BUFFER_SIZE*(tag))
#define CR_ID 15
#define CR_INDEX 207
#define TR_ID 12
#define CR_HEAD 0x78
#define CR_TAIL 0x3cc
#define TR_HEAD 0x5a0
#define TR_TAIL 0x24c
struct data_record { __le32 length, crid; __le64 ns; u8 cd[32], data[BUFFER_SIZE]; };
struct data_rx {
	struct transport *control;
	struct pci_dev *pdev;
	void *pool;
	dma_addr_t dma;
	struct delayed_work work;
	u16 head, tail;
	DECLARE_BITMAP(posted,COUNT);
	struct data_record records[64];
};
static struct data_rx *active;
static bool stopping;
static bool launch;
static int result=-EINPROGRESS;
static unsigned int phase, received, dropped, posted_count;
module_param(launch,bool,0400);
module_param(result,int,0444);
module_param(phase,uint,0444);
module_param(received,uint,0444);
module_param(dropped,uint,0444);
module_param(posted_count,uint,0444);
static u16 idx(struct data_rx *s,unsigned int offset)
{
	u16 v=le16_to_cpu(READ_ONCE(*(__le16 *)(s->control->shared.memory+offset)));
	dma_rmb(); return v;
}
static void putidx(struct data_rx *s,unsigned int offset,u16 v)
{
	WRITE_ONCE(*(__le16 *)(s->control->shared.memory+offset),cpu_to_le16(v));
}
static bool alive(struct data_rx *s)
{
	return pci_get_drvdata(s->pdev)==s->control &&
		readl(s->control->shared.owner->bar+8)==2 &&
		readl(s->control->shared.owner->bar+12)==2;
}
static void bell(struct data_rx *s,unsigned int offset)
{
	dma_wmb(); writel(1,s->control->shared.owner->bar+offset);
}
/* Caller serializes the existing control management indices with S41. */
static int management(struct data_rx *s,const u8 *message,unsigned int length)
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
			pr_info("N1_DATA_RX_MGMT tag=%u raw=%*phN\n",tag,16,cd);
			if (cd[0]!=1 || cd[1]!=4 || get_unaligned_le16(cd+2) ||
			    get_unaligned_le16(cd+4)!=tag || get_unaligned_le16(cd+6)!=length ||
			    get_unaligned_le32(cd+8) || get_unaligned_le32(cd+12)) return -EPROTO;
			memset(cd,0,16); dma_wmb(); putidx(s,CR_TAIL,next); dma_wmb(); c->mh=next; return 0;
		}
		usleep_range(1000,1500);
	}
	return -ETIMEDOUT;
}
static int open_rings(struct data_rx *s)
{
	u8 message[64]={0};
	int ret;
	/* CR footer16, no header or scaling. Group12. Appendix10:
	 * version0, station0, TID0, AC0, no peer MAC filter. */
	message[0]=2; message[2]=4;
	put_unaligned_le16(CR_ID,message+4); put_unaligned_le16(CR_INDEX,message+6);
	put_unaligned_le64(s->dma+CR_OFF,message+8); put_unaligned_le16(COUNT,message+16);
	put_unaligned_le16(12,message+18); put_unaligned_le16(11,message+20);
	put_unaligned_le16(8,message+28);
	ret=management(s,message,44+10);
	if (ret) return ret;
	phase=2;
	memset(message,0,sizeof(message)); message[0]=1;
	put_unaligned_le16(TR_ID,message+4); put_unaligned_le16(TR_ID,message+6);
	put_unaligned_le64(s->dma+TR_OFF,message+8); put_unaligned_le64(U64_MAX,message+16);
	put_unaligned_le16(COUNT,message+24); put_unaligned_le16(12,message+26);
	put_unaligned_le16(11,message+28);
	put_unaligned_le16(0x220,message+30); /* out-of-order, completion group */
	put_unaligned_le16(8,message+36);
	ret=management(s,message,52+10);
	if (!ret) phase=3;
	return ret;
}
static int refill(struct data_rx *s)
{
	u16 tail=idx(s,TR_TAIL+2*TR_ID), next;
	unsigned int tag;
	bool changed=false;
	if (tail>=COUNT) return -EPROTO;
	while ((next=(s->head+1)%COUNT)!=tail) {
		u8 *td;
		tag=find_first_zero_bit(s->posted,COUNT);
		if (tag>=COUNT) break;
		td=s->pool+TR_OFF+16*s->head;
		put_unaligned_le32(1|(BUFFER_SIZE<<8),td);
		put_unaligned_le64(s->dma+BUF_OFF(tag),td+4); put_unaligned_le32(tag,td+12);
		__set_bit(tag,s->posted); s->head=next; changed=true;
	}
	if (changed) { dma_wmb(); putidx(s,TR_HEAD+2*TR_ID,s->head); bell(s,0x1050); }
	posted_count=bitmap_weight(s->posted,COUNT);
	return 0;
}
static int drain(struct data_rx *s)
{
	unsigned int n;
	for (n=0;n<COUNT;n++) {
		u16 head=idx(s,CR_HEAD+2*CR_INDEX),tag;
		u32 length;
		u8 *cd;
		struct data_record *r;
		if (head>=COUNT) return -EPROTO;
		if (head==s->tail) break;
		cd=s->pool+CR_OFF+32*s->tail; dma_rmb();
		if (!get_unaligned_le64(cd) && !get_unaligned_le64(cd+8)) break;
		tag=get_unaligned_le16(cd+4);
		length=get_unaligned_le16(cd+6)|((get_unaligned_le32(cd+8)&255)<<16);
		if (cd[0]!=1 || cd[1]!=4 || get_unaligned_le16(cd+2)!=TR_ID ||
		    tag>=COUNT || !test_bit(tag,s->posted) || length>BUFFER_SIZE) {
			pr_err("N1_DATA_RX_BAD_CD raw=%*phN\n",32,cd); return -EPROTO;
		}
		r=&s->records[received%ARRAY_SIZE(s->records)];
		r->length=cpu_to_le32(length); r->crid=cpu_to_le32(CR_ID); r->ns=cpu_to_le64(ktime_get_ns());
		memcpy(r->cd,cd,32); memcpy(r->data,s->pool+BUF_OFF(tag),length);
		if (received>=ARRAY_SIZE(s->records)) dropped++;
		received++; __clear_bit(tag,s->posted);
		memset(cd,0,32); s->tail=(s->tail+1)%COUNT;
		dma_wmb(); putidx(s,CR_TAIL+2*CR_INDEX,s->tail);
		if (received<=8) pr_info("N1_DATA_RX_FRAME tag=%u length=%u\n",tag,length);
	}
	return refill(s);
}
static void poll_rx(struct work_struct *work)
{
	struct data_rx *s=container_of(to_delayed_work(work),struct data_rx,work);
	mutex_lock(&s->control->io_lock);
	result=stopping?-ESHUTDOWN:(alive(s)?drain(s):-EIO);
	mutex_unlock(&s->control->io_lock);
	if (!result && !READ_ONCE(stopping)) schedule_delayed_work(&s->work,msecs_to_jiffies(1));
	else pr_err("N1_DATA_RX_STOP result=%d received=%u; all DMA retained\n",result,received);
}
static ssize_t records_read(struct file *file,char __user *buf,size_t count,loff_t *pos)
{
	ssize_t ret;
	if (!active) return 0;
	mutex_lock(&active->control->io_lock);
	ret=simple_read_from_buffer(buf,count,pos,active->records,
		min_t(unsigned int,received,ARRAY_SIZE(active->records))*sizeof(struct data_record));
	mutex_unlock(&active->control->io_lock); return ret;
}
static const struct proc_ops record_ops={.proc_read=records_read};
/* Host copies only; no consumer receives a pointer into live DMA memory. */
int n1_data_rx_read_v1(unsigned int index,void *completion,void *data,size_t *length)
{
 struct data_rx *s=active;
 struct data_record *r;
 int ret=0;
 if (!s || !completion || !data || !length) return -EINVAL;
 mutex_lock(&s->control->io_lock);
 if (index>=received) { ret=-ENOENT; goto out; }
 if (received-index>ARRAY_SIZE(s->records)) { ret=-EOVERFLOW; goto out; }
 r=&s->records[index%ARRAY_SIZE(s->records)];
 if (le32_to_cpu(r->length)>*length) { ret=-EMSGSIZE; goto out; }
 *length=le32_to_cpu(r->length); memcpy(completion,r->cd,32); memcpy(data,r->data,*length);
out:
 mutex_unlock(&s->control->io_lock); return ret;
}
EXPORT_SYMBOL_GPL(n1_data_rx_read_v1);
int n1_data_rx_status_v1(unsigned int *count)
{
 if (!active || !count) return -ENODEV;
 mutex_lock(&active->control->io_lock);
 *count=received;
 mutex_unlock(&active->control->io_lock);
 return READ_ONCE(result);
}
EXPORT_SYMBOL_GPL(n1_data_rx_status_v1);
void n1_data_rx_quiesce_v1(void)
{
 if (!active) return;
 WRITE_ONCE(stopping,true);
 cancel_delayed_work_sync(&active->work);
 WRITE_ONCE(result,-ESHUTDOWN);
 /* Device-owned buffers remain mapped and pinned. No resume without reset. */
}
EXPORT_SYMBOL_GPL(n1_data_rx_quiesce_v1);
static int __init data_init(void)
{
	struct pci_dev *p,*control;
	struct old_boot *boot;
	struct transport *c;
	struct data_rx *s=NULL;
	struct iommu_domain *domain;
	unsigned int completed,status,count;
	bool pending;
	u16 command;
	int ret=-ENODEV;
	if (!of_machine_is_compatible("apple,j714s")) return ret;
	ret=n1_alpha_scan_status_v8(&completed,&status,&count,&pending);
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
	if (!boot || !boot->alpha || !c || c->magic!=0x5334315452414e53ULL ||
	    c->shared.owner!=boot->alpha || c->pdev!=p || !c->shared.memory || !c->pool) goto out;
	mutex_lock(&c->command_lock); mutex_lock(&c->io_lock);
	if (c->mh!=8 || c->sequence!=23 || c->waiting || c->txhead!=7 || c->txtail!=7 ||
	    readl(boot->bar+0x8000)!=2 || readl(boot->bar+0x8050)!=2) goto unlock;
	domain=iommu_get_domain_for_dev(&p->dev);
	if (!domain || !iommu_is_dma_domain(domain)) goto unlock;
	s=kvzalloc(sizeof(*s),GFP_KERNEL);
	if (!s) { ret=-ENOMEM; goto unlock; }
	s->control=c; s->pdev=p; INIT_DELAYED_WORK(&s->work,poll_rx);
	if (!alive(s) || idx(s,CR_HEAD+2*CR_INDEX) || idx(s,CR_TAIL+2*CR_INDEX) ||
	    idx(s,TR_HEAD+2*TR_ID) || idx(s,TR_TAIL+2*TR_ID)) goto free_state;
	s->pool=dma_alloc_coherent(&p->dev,POOL_SIZE,&s->dma,GFP_KERNEL);
	if (!s->pool) { ret=-ENOMEM; goto free_state; }
	ret=-EFAULT;
	if (s->dma>U32_MAX-POOL_SIZE || !iommu_iova_to_phys(domain,s->dma) ||
	    !iommu_iova_to_phys(domain,s->dma+POOL_SIZE-1)) goto free_pool;
	memset(s->pool,0,POOL_SIZE);
	pr_info("N1_DATA_RX_PREPARED launch=%d count=128 buffer=16384 CR15/207 TR12 group12 appendix10\n",launch);
	ret=0;
	if (!launch) goto free_pool;
	if (!proc_create("n1_alpha_data_rx_records",0400,NULL,&record_ops)) { ret=-ENOMEM; goto free_pool; }
	__module_get(THIS_MODULE); active=s; phase=1;
	result=open_rings(s);
	if (!result) result=refill(s);
	if (!result) { phase=4; schedule_delayed_work(&s->work,msecs_to_jiffies(1)); }
	pr_info("N1_DATA_RX_RESULT result=%d phase=%u posted=%u; DMA pinned\n",result,phase,posted_count);
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
MODULE_DESCRIPTION("Private native N1 data receive queue bring-up");
