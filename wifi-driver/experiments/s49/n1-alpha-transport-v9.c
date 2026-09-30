// SPDX-License-Identifier: GPL-2.0
/* Alpha IPC and persistent receiver after guarded S54 function reset. S32 ring layout, S40 event
 * correlation. No old-state adoption or optional debug rings. Published DMA
 * stays pinned until reboot, including every failure after publication. */
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
#include "../common/n1-aci-events.h"
#include "n1-v9-api.h"
#define CTX_SIZE (PAGE_SIZE + 5*1024*1024)
#define POOL_SIZE 0x80000
#define RINGS 4
#define COUNT 16
#define CR_HEAD 0x78
#define TR_TAIL 0x24c
#define CR_TAIL 0x3cc
#define TR_HEAD 0x5a0
#define MCR 0x720
#define MTR 0x820
#define MAGIC 0x5334395452414e53ULL
#define CR(id) (0x1000 + (id)*0x400)
#define TR(id) (CR(id) + 0x200)
#define DATA(id,tag) (0x10000*(id) + 4096*(tag))
static struct transport *active;
static struct rx_record *history;
static struct delayed_work receiver_work;
static bool command_pending, command_accept_ack;
static bool scan_pending;
static unsigned int scans_completed, scan_status, scan_results, scan_dwell;
static u16 scan_sequence;
static u8 scan_handle;
module_param(scan_pending,bool,0444);
module_param(scans_completed,uint,0444);
module_param(scan_status,uint,0444);
module_param(scan_results,uint,0444);
module_param(scan_dwell,uint,0444);
static bool launch;
module_param(launch, bool, 0400);
static int result = -EINPROGRESS;
module_param(result, int, 0444);
static unsigned int phase, saved, dropped, replies, events, management_frames, debug_frames;
module_param(phase, uint, 0444);
module_param(saved, uint, 0444);
module_param(dropped, uint, 0444);
module_param(replies, uint, 0444);
module_param(events, uint, 0444);
module_param(management_frames, uint, 0444);
module_param(debug_frames, uint, 0444);
static u16 index_read(void *ctx, unsigned int off)
{
	u16 v = le16_to_cpu(READ_ONCE(*(__le16 *)(ctx + off)));
	dma_rmb();
	return v;
}
static void index_write(void *ctx, unsigned int off, u16 v)
{
	WRITE_ONCE(*(__le16 *)(ctx + off), cpu_to_le16(v));
}
static bool running(struct transport *s)
{
	return pci_get_drvdata(s->pdev) == s &&
	       readl(s->shared.owner->bar + 8) == 2 && readl(s->shared.owner->bar + 12) == 2;
}
static void bell(struct transport *s)
{
	dma_wmb();
	writel(1, s->shared.owner->bar + 0x1004);
}
static unsigned int bufsize(unsigned int id) { return id == 3 ? 4096 : 2048; }
static void post(struct transport *s, u16 id, u16 tag)
{
	u8 *td = s->pool + TR(id) + 16*tag;
	put_unaligned_le32(1 | (bufsize(id)<<8), td);
	put_unaligned_le64(s->dma + DATA(id, tag), td+4);
	put_unaligned_le32(tag, td+12);
}
static int mgmt(struct transport *s, unsigned int length)
{
	u8 *ctx = s->shared.memory, *td, *cd;
	u16 tag = s->mh, next = (tag+1)%COUNT;
	unsigned int i;
	if (!running(s) || index_read(ctx, CR_HEAD) != tag || index_read(ctx, CR_TAIL) != tag ||
	    index_read(ctx, TR_HEAD) != tag || index_read(ctx, TR_TAIL) != tag) return -EBUSY;
	td = ctx+MTR+16*tag;
	cd = ctx+MCR+16*tag;
	put_unaligned_le32(1 | (length<<8), td);
	put_unaligned_le64(s->dma + 128*tag, td+4);
	put_unaligned_le32(tag, td+12);
	dma_wmb();
	index_write(ctx, TR_HEAD, next);
	bell(s);
	for (i=0; i<1000; i++) {
		if (!running(s)) return -EIO;
		if (index_read(ctx, CR_HEAD) == next && index_read(ctx, TR_TAIL) == next) {
			dma_rmb();
			pr_info("N1_V9_MGMT tag=%u raw=%*phN\n", tag,16,cd);
			if (cd[0]!=1 || cd[1]!=4 || get_unaligned_le16(cd+2) ||
			    get_unaligned_le16(cd+4)!=tag || get_unaligned_le16(cd+6)!=length ||
			    get_unaligned_le32(cd+8) || get_unaligned_le32(cd+12)) return -EPROTO;
			memset(cd,0,16);
			dma_wmb();
			index_write(ctx, CR_TAIL, next);
			dma_wmb();
			s->mh=next;
			return 0;
		}
		usleep_range(1000,1500);
	}
	return -ETIMEDOUT;
}
static int open_rings(struct transport *s)
{
	unsigned int id, tag;
	int ret;
	for (id=1; id<=RINGS; id++) {
		u8 *m=s->pool+128*s->mh;
		m[0]=2;
		put_unaligned_le16(id,m+4);
		put_unaligned_le16(id,m+6);
		put_unaligned_le64(s->dma+CR(id),m+8);
		put_unaligned_le16(COUNT,m+16);
		put_unaligned_le16(0xffff,m+18);
		put_unaligned_le16(0xffff,m+20);
		put_unaligned_le16(2,m+28);
		ret=mgmt(s,44);
		if (ret) return ret;
		m=s->pool+128*s->mh;
		m[0]=1;
		put_unaligned_le16(id,m+4);
		put_unaligned_le16(id,m+6);
		put_unaligned_le64(s->dma+TR(id),m+8);
		put_unaligned_le64(U64_MAX,m+16);
		put_unaligned_le16(COUNT,m+24);
		put_unaligned_le16(id,m+26);
		put_unaligned_le16(2,m+36);
		ret=mgmt(s,52);
		if (ret) return ret;
		if (id==1) continue;
		for (tag=0; tag<COUNT-1; tag++) post(s,id,tag);
		s->rxhead[id]=COUNT-1;
		dma_wmb();
		index_write(s->shared.memory,TR_HEAD+2*id,COUNT-1);
		bell(s);
	}
	return 0;
}
static void record(unsigned int id, u8 *data, unsigned int length)
{
	{
		struct rx_record *r=&history[saved % 256];
		if (saved>=256) dropped++;
		saved++;
		r->id=cpu_to_le32(id);
		r->length=cpu_to_le32(length);
		r->time_ns=cpu_to_le64(ktime_get_ns());
		memcpy(r->data,data,length);
	}
}
static int process_event(const u8 *data, unsigned int length)
{
 struct n1_aci_event e;
 int ret=n1_aci_parse_event(data,length,&e);
 if (ret) return ret;
 if (e.kind==N1_EVENT_SCAN_COMPLETE && scan_pending &&
     e.header.sequence==scan_sequence && e.data.scan.handle==scan_handle) {
  scan_status=e.data.scan.status; scan_results=e.data.scan.results;
  scan_dwell=e.data.scan.dwell_ms; scan_pending=false; scans_completed++;
  pr_info("N1_V9_SCAN_COMPLETE seq=%u handle=%u status=%u results=%u dwell_ms=%u\n",
   scan_sequence,scan_handle,scan_status,scan_results,scan_dwell);
 }
 if (e.kind==N1_EVENT_CONNECT_COMPLETE || e.kind==N1_EVENT_ASSOCIATED ||
     e.kind==N1_EVENT_CONNECTION_LOST || e.kind==N1_EVENT_CONNECTION_FAILED ||
     e.kind==N1_EVENT_FOUR_WAY)
  pr_info("N1_V9_LINK_EVENT kind=%u seq=%u status=%u detail=%u stage=%u\n",
   e.kind,e.header.sequence,e.header.status,
   e.kind==N1_EVENT_FOUR_WAY?e.data.four_way.status:0,
   e.kind==N1_EVENT_FOUR_WAY?e.data.four_way.stage:0);
 return 0;
}
static int drain(struct transport *s, bool alive)
{
	u8 *ctx=s->shared.memory;
	unsigned int id, n;
	if (index_read(ctx,CR_HEAD+2)>=COUNT) return -EPROTO;
	while (index_read(ctx,CR_HEAD+2)!=s->txtail) {
		u8 *cd=s->pool+CR(1)+16*s->txtail;
		dma_rmb();
		if (!get_unaligned_le64(cd) && !get_unaligned_le64(cd+8)) break;
		if (!command_pending || cd[0]!=1 || cd[1]!=4 || get_unaligned_le16(cd+2)!=1 ||
		    get_unaligned_le16(cd+4)!=s->txtail || get_unaligned_le16(cd+6)!=s->request_length || get_unaligned_le32(cd+8) ||
		    get_unaligned_le32(cd+12)) return -EPROTO;
		if (s->cid==0x20000)
            memzero_explicit(s->pool+DATA(1,s->txtail),s->request_length);
        memset(cd,0,16);
        s->txtail=(s->txtail+1)%COUNT;
		dma_wmb();
		index_write(ctx,CR_TAIL+2,s->txtail);
		s->tx_done=true;
	}
	for (id=2; id<=RINGS; id++) {
		for (n=0; n<COUNT && index_read(ctx,CR_HEAD+2*id)!=s->rxtail[id]; n++) {
			u16 tag=s->rxtail[id];
			u8 *cd=s->pool+CR(id)+16*tag, *data=s->pool+DATA(id,tag);
			u32 length;
			dma_rmb();
			if (!get_unaligned_le64(cd) && !get_unaligned_le64(cd+8)) break;
			length=get_unaligned_le16(cd+6) | ((get_unaligned_le32(cd+8)&255)<<16);
			if (index_read(ctx,CR_HEAD+2*id)>=COUNT || cd[0]!=1 || cd[1]!=4 ||
			    get_unaligned_le16(cd+2)!=id || get_unaligned_le16(cd+4)!=tag ||
			    length>bufsize(id) || get_unaligned_le32(cd+8) || get_unaligned_le32(cd+12)) {
				pr_err("N1_V9_BAD_CD ring=%u raw=%*phN\n",id,16,cd);
				return -EPROTO;
			}
			record(id,data,length);
            if (id==2 || id==3) {
                struct n1_aci_header header;
                int action=n1_aci_parse_header(data,length,&header);
                if (action) return action;
                if (header.opcode==0x43) {
                    events++;
                    action=process_event(data,length);
                    if (action) return action;
                } else {
                    replies++;
                    pr_info("N1_V9_REPLY len=%u cid=%08x seq=%u status=%u\n",
                        length,header.cid,header.sequence,header.status);
                    action=n1_aci_classify_reply(data,length,s->cid,s->sequence,0,
                        command_accept_ack);
                    if (action<0) return action;
                    /* Preserve late/unrelated replies in history. They cannot
                     * complete a different request or stop event reception. */
                    if (command_pending && action==N1_REPLY_COMPLETE && !s->response_done) {
                        s->command_result=header.status?-EREMOTEIO:0;
                        memcpy(s->response,data,length); s->response_length=length;
                        s->response_done=true;
                        if (s->cid==0x1000f && header.status) scan_pending=false;
                    }
                }
            } else if (id==4) management_frames++;
            memset(cd,0,16);
			s->rxtail[id]=(tag+1)%COUNT;
			dma_wmb();
			index_write(ctx,CR_TAIL+2*id,s->rxtail[id]);
			if (alive) {
				post(s,id,s->rxhead[id]);
				s->rxhead[id]=(s->rxhead[id]+1)%COUNT;
				dma_wmb();
				index_write(ctx,TR_HEAD+2*id,s->rxhead[id]);
				bell(s);
			}
		}
	}
	dma_wmb();
	return 0;
}
static void poll_transport(struct work_struct *work)
{
	struct transport *s=active;
	bool alive;
	int ret;
	mutex_lock(&s->io_lock);
	alive=running(s);
	ret=drain(s,alive); /* collect completed host RAM even after firmware stops */
	if (!alive || ret) {
		result=ret?ret:-EIO;
		s->command_result=result;
		pr_err("N1_V9_STOP result=%d replies=%u events=%u management=%u debug=%u; DMA retained\n",
			result,replies,events,management_frames,debug_frames);
	}
	wake_up_all(&s->wait);
	mutex_unlock(&s->io_lock);
	if (!result) schedule_delayed_work(&receiver_work,msecs_to_jiffies(1));
}
int n1_alpha_exchange_v9(const void *request, size_t length, void *response,
    size_t *response_length, bool accept_ack)
{
	struct transport *s=active;
	const u8 *r=request;
	u8 *td;
	u16 tag;
	u32 cid;
	int ret;
	if (!s || !r || !response || !response_length || length<24 || length>2048 ||
	    get_unaligned_le16(r+16)!=length || !get_unaligned_le16(r+18)) return -EINVAL;
	cid=get_unaligned_le32(r+20);
	if (cid!=0 && cid!=1 && cid!=2 && cid!=8 && cid!=10 && cid!=19 && cid!=47 && cid!=0x1000f &&
        cid!=0x1c && cid!=0x20000 && cid!=0x20001)
		return -EOPNOTSUPP;
	if (r[0] || r[1] || r[12] || r[13]) return -EINVAL;
    if ((cid==0x1c && (length!=25 || r[24]!=0x3f)) ||
        (cid==0x20000 && (length<207 || length>269)) ||
        (cid==0x20001 && length!=40)) return -EINVAL;
    mutex_lock(&s->command_lock);
    mutex_lock(&s->io_lock);
    ret=-EBUSY;
	if (result || !running(s) || command_pending || s->txtail!=s->txhead ||
	    index_read(s->shared.memory,TR_TAIL+2)!=s->txhead || (cid==0x1000f && scan_pending)) goto unlock;
	if (get_unaligned_le16(r+18)!=(u16)(s->sequence==65535?1:s->sequence+1)) {
        ret=-ESTALE; goto unlock;
    }
    command_accept_ack=accept_ack;
    if (cid==0x1000f) {
		if (length<38) { ret=-EINVAL; goto unlock; }
		scan_sequence=get_unaligned_le16(r+18); scan_handle=r[24]; scan_pending=true;
	}
	s->sequence=get_unaligned_le16(r+18);
	s->request_length=length;
	s->cid=cid;
	command_pending=true;
	s->tx_done=s->response_done=false;
	s->command_result=0;
	s->response_length=0;
	tag=s->txhead;
	memcpy(s->pool+DATA(1,tag),request,length);
	td=s->pool+TR(1)+16*tag;
	put_unaligned_le32(1|(length<<8),td);
	put_unaligned_le64(s->dma+DATA(1,tag),td+4);
	put_unaligned_le32(tag,td+12);
	s->txhead=(tag+1)%COUNT;
	dma_wmb();
	index_write(s->shared.memory,TR_HEAD+2,s->txhead);
	bell(s);
	mutex_unlock(&s->io_lock);
	wait_event_timeout(s->wait, READ_ONCE(result) ||
		(READ_ONCE(s->tx_done) && READ_ONCE(s->response_done)), msecs_to_jiffies(4000));
	mutex_lock(&s->io_lock);
	ret=s->command_result;
	if (!ret && !(s->tx_done && s->response_done)) ret=-ETIMEDOUT;
	if (s->response_done) {
		if (s->response_length>*response_length) ret=-EMSGSIZE;
		else {
			memcpy(response,s->response,s->response_length);
			*response_length=s->response_length;
		}
	}
	/* Timeout makes transport fail closed so a late reply can't match a new command. */
	if (ret==-ETIMEDOUT) { result=ret; scan_pending=false; }
	command_pending=false;
unlock:
	mutex_unlock(&s->io_lock);
	mutex_unlock(&s->command_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(n1_alpha_exchange_v9);

int n1_alpha_record_v9(unsigned int index, unsigned int *ring, void *data, size_t *length);
int n1_alpha_record_v9(unsigned int index, unsigned int *ring, void *data, size_t *length)
{
 struct transport *s=active;
 struct rx_record *r;
 int ret=0;
 if (!s || !ring || !data || !length) return -EINVAL;
 mutex_lock(&s->io_lock);
 if (index>=saved) { ret=-ENOENT; goto out; }
 if (saved-index>256) { ret=-EOVERFLOW; goto out; }
 r=&history[index%256];
 if (le32_to_cpu(r->length)>*length) { ret=-EMSGSIZE; goto out; }
 *length=le32_to_cpu(r->length); *ring=le32_to_cpu(r->id); memcpy(data,r->data,*length);
out:
 mutex_unlock(&s->io_lock); return ret;
}
EXPORT_SYMBOL_GPL(n1_alpha_record_v9);
int n1_alpha_scan_status_v9(unsigned int *completed, unsigned int *status, unsigned int *count, bool *pending);
int n1_alpha_scan_status_v9(unsigned int *completed, unsigned int *status, unsigned int *count, bool *pending)
{
 struct transport *s=active;
 int ret;
 if (!s || !completed || !status || !count || !pending) return -EINVAL;
 mutex_lock(&s->io_lock);
 *completed=scans_completed; *status=scan_status; *count=scan_results; *pending=scan_pending;
 ret=result;
 mutex_unlock(&s->io_lock); return ret;
}
EXPORT_SYMBOL_GPL(n1_alpha_scan_status_v9);

static ssize_t records_read(struct file *f,char __user *buf,size_t count,loff_t *pos)
{
	ssize_t ret;
	if (!active) return 0;
	mutex_lock(&active->io_lock);
	ret=simple_read_from_buffer(buf,count,pos,history,min_t(unsigned int,saved,256)*sizeof(struct rx_record));
	mutex_unlock(&active->io_lock);
	return ret;
}
static const struct proc_ops records_ops={.proc_read=records_read};
int n1_alpha_cursor_v9(u16 *sequence,u8 *handle)
{
 if (!active || !sequence || !handle) return -EINVAL;
 mutex_lock(&active->io_lock);
 *sequence=active->sequence; *handle=scan_handle;
 mutex_unlock(&active->io_lock);
 return READ_ONCE(result);
}
EXPORT_SYMBOL_GPL(n1_alpha_cursor_v9);

static int ipc_wait(struct transport *s,u32 want)
{
	unsigned int i;
	for (i=0;i<2000;i++) {
		if (readl(s->shared.owner->bar+8)!=2) return -EIO;
		if (readl(s->shared.owner->bar+12)==want) return 0;
		usleep_range(1000,1500);
	}
	return -ETIMEDOUT;
}
static int __init transport_init(void)
{
	struct pci_dev *p,*control;
	struct old_boot *c;
	struct n1_alpha *a;
	struct transport *s=NULL;
 struct alpha_restart *previous;
	struct iommu_domain *domain;
	u8 *ctx;
	u16 command;
	u32 cfg;
	int ret=-ENODEV;
	if (!of_machine_is_compatible("apple,j714s")) return ret;
	p=pci_get_domain_bus_and_slot(0,1,PCI_DEVFN(0,1));
	if (!p) return ret;
	control=pci_get_slot(p->bus,0);
	if (!control) goto put;
	device_lock(&control->dev);
	device_lock(&p->dev);
	if (!control->driver || strcmp(control->driver->name,"n1-control-handoff") || p->driver ||
	    p->vendor!=0x106b || p->device!=0x1902 || pci_read_config_word(p,PCI_COMMAND,&command) ||
	    command!=0x406) goto out;
	c=pci_get_drvdata(control);
 previous=pci_get_drvdata(p);
	if (!c || c->pdev!=control || !c->bar || !(a=c->alpha) || a->pdev!=p ||
	    !a->bar || !a->working || a->old_command || !previous || previous->shared.owner!=a ||
     previous->magic!=0x533534414c504841ULL || previous->shared.memory ||
     !previous->previous ||
	    control->vendor!=0x106b || control->device!=0x1901 ||
	    atomic_read(&p->enable_cnt)!=1 || !p->msi_enabled || p->msix_enabled ||
	    pci_irq_vector(p,ALPHA_IRQS-1)<0 || p->current_state!=PCI_D0 ||
	    readl(c->bar+0x8000)!=2 || readl(c->bar+0x8050)!=2 ||
	    pci_read_config_dword(p,0xf88,&cfg) || cfg!=lower_32_bits(a->dma) ||
	    pci_read_config_dword(p,0xf8c,&cfg) || cfg!=upper_32_bits(a->dma) ||
	    pci_read_config_dword(p,0xf90,&cfg) || cfg!=ALPHA_SIZE) goto out;
	ret=-EBUSY;
	if (readl(a->bar+8)!=2 || readl(a->bar+12) || readl(a->bar+16) ||
	    readl(a->bar+20) || readl(a->bar+24) || readl(a->bar+28) || readl(a->bar+32)) goto out;
	domain=iommu_get_domain_for_dev(&p->dev);
	ret=-EPERM;
	if (!domain || !iommu_is_dma_domain(domain) ||
	    domain==iommu_get_domain_for_dev(&control->dev)) goto out;
	s=kvzalloc(sizeof(*s),GFP_KERNEL);
	ret=-ENOMEM;
	if (!s) goto out;
	s->shared.owner=c->alpha;
	s->previous=previous;
	s->pdev=p;
	s->magic=MAGIC;
	s->shared.memory=dma_alloc_coherent(&p->dev,CTX_SIZE,&s->shared.dma,GFP_KERNEL);
	if (!s->shared.memory) goto free_state;
	s->pool=dma_alloc_coherent(&p->dev,POOL_SIZE,&s->dma,GFP_KERNEL);
	if (!s->pool) goto free_ctx;
	ret=-EFAULT;
	if (!IS_ALIGNED(s->dma,PAGE_SIZE) || !IS_ALIGNED(s->shared.dma,PAGE_SIZE) ||
	    a->dma>U32_MAX-ALPHA_SIZE || s->dma>U32_MAX-POOL_SIZE || s->shared.dma>U32_MAX-CTX_SIZE ||
	    !iommu_iova_to_phys(domain,s->dma) || !iommu_iova_to_phys(domain,s->dma+POOL_SIZE-1) ||
	    !iommu_iova_to_phys(domain,s->shared.dma) ||
	    !iommu_iova_to_phys(domain,s->shared.dma+CTX_SIZE-1)) goto free_pool;
	memset(s->pool,0,POOL_SIZE);
	ctx=s->shared.memory;
	memset(ctx,0,CTX_SIZE);
	put_unaligned_le16(0x300,ctx);
	put_unaligned_le16(104,ctx+2);
	put_unaligned_le64(s->shared.dma+0x68,ctx+8);
	put_unaligned_le64(s->shared.dma+CR_HEAD,ctx+0x10);
	put_unaligned_le64(s->shared.dma+TR_TAIL,ctx+0x18);
	put_unaligned_le64(s->shared.dma+CR_TAIL,ctx+0x20);
	put_unaligned_le64(s->shared.dma+TR_HEAD,ctx+0x28);
	put_unaligned_le16(234,ctx+0x30);
	put_unaligned_le16(192,ctx+0x32);
	put_unaligned_le64(s->shared.dma+MCR,ctx+0x34);
	put_unaligned_le64(s->shared.dma+MTR,ctx+0x3c);
	put_unaligned_le16(COUNT,ctx+0x44);
	put_unaligned_le16(COUNT,ctx+0x46);
	put_unaligned_le16(0xffff,ctx+0x4a);
	put_unaligned_le64(s->shared.dma+PAGE_SIZE,ctx+0x58);
	put_unaligned_le32(5*1024*1024,ctx+0x60);
	put_unaligned_le32(2,ctx+0x68);
	put_unaligned_le32(2,ctx+0x6c);
	mutex_init(&s->io_lock);
	mutex_init(&s->command_lock);
	init_waitqueue_head(&s->wait);
	INIT_DELAYED_WORK(&receiver_work,poll_transport);
	pr_info("N1_V9_PREPARED launch=%d rings=1..4 persistent_RX=15_each\n",launch);
	ret=0;
	if (!launch) goto free_pool;
	history=kvcalloc(256,sizeof(*history),GFP_KERNEL);
	if (!history) { ret=-ENOMEM; goto free_pool; }
	if (!proc_create("n1_alpha_v9_records",0400,NULL,&records_ops)) {
		kvfree(history); history=NULL; ret=-ENOMEM; goto free_pool;
	}
	__module_get(THIS_MODULE);
	pci_set_drvdata(p,s);
	active=s;
	phase=1;
	dma_wmb();
	writel(0,c->alpha->bar+24);
	writel(0,c->alpha->bar+28);
	writel(U32_MAX,c->alpha->bar+32);
	writel(1,c->alpha->bar+0x1028);
	result=ipc_wait(s,1);
	if (result) goto pinned;
	writel(lower_32_bits(s->shared.dma),c->alpha->bar+16);
	writel(upper_32_bits(s->shared.dma),c->alpha->bar+20);
	writel(2,c->alpha->bar+0x1028);
	result=ipc_wait(s,2);
	if (result) goto pinned;
	phase=2;
	result=open_rings(s);
	if (!result) {
		phase=3;
		schedule_delayed_work(&receiver_work,msecs_to_jiffies(1));
	}
pinned:
	pr_info("N1_V9_RESULT result=%d phase=%u mgmt=%u stage=%u ipc=%u\n",result,phase,s->mh,
		readl(c->alpha->bar+8),readl(c->alpha->bar+12));
	device_unlock(&p->dev);
	device_unlock(&control->dev);
	pci_dev_put(control);
	return 0;
free_pool:
	dma_free_coherent(&p->dev,POOL_SIZE,s->pool,s->dma);
free_ctx:
	dma_free_coherent(&p->dev,CTX_SIZE,s->shared.memory,s->shared.dma);
free_state:
	kvfree(s);
out:
	device_unlock(&p->dev);
	device_unlock(&control->dev);
	pci_dev_put(control);
put:
	pci_dev_put(p);
	return ret;
}
static void __exit transport_exit(void) { }
module_init(transport_init);
module_exit(transport_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Private N1 fresh Alpha transport with connection event decoding");
