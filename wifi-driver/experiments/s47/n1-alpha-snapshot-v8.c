// SPDX-License-Identifier: GPL-2.0
/* Copies only existing host DMA memory. Never maps or reads BAR4.
 * These are diagnostic, potentially non-atomic firmware snapshots.
 */
#include <linux/dma-mapping.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/proc_fs.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/unaligned.h>
#include <linux/mutex.h>
#include <linux/wait.h>
#include <linux/workqueue.h>
#include "../s41/n1-s19-abi.h"
#include "../s41/n1-transport-abi.h"
struct snapshot { const char *name; size_t size; void *data; struct proc_dir_entry *entry; };
static struct snapshot snaps[] = {
	{ .name = "n1_s47_secondary", .size = 11418624 },
	{ .name = "n1_s47_working", .size = 2*1024*1024 },
	{ .name = "n1_s47_scratch", .size = PAGE_SIZE + 5*1024*1024 },
	{ .name = "n1_s47_queues", .size = 0x80000 },
};
static ssize_t snapshot_read(struct file *f, char __user *buf, size_t count, loff_t *pos)
{
	struct snapshot *s = pde_data(file_inode(f));
	return simple_read_from_buffer(buf, count, pos, s->data, s->size);
}
static const struct proc_ops snapshot_ops = { .proc_read = snapshot_read, .proc_lseek = default_llseek };
static void cleanup(void)
{
	unsigned int i;
	for (i=0; i<ARRAY_SIZE(snaps); i++) { proc_remove(snaps[i].entry); kvfree(snaps[i].data); }
}
static int __init snapshot_init(void)
{
	struct pci_dev *p, *control;
	struct old_boot *c;
	struct transport *q;
	void *src[ARRAY_SIZE(snaps)];
	u16 command;
	unsigned int i;
	int ret = -ENODEV;
	if (!of_machine_is_compatible("apple,j714s")) return ret;
	p = pci_get_domain_bus_and_slot(0, 1, PCI_DEVFN(0,1));
	if (!p) return ret;
	control = pci_get_slot(p->bus,0);
	if (!control) goto put;
	device_lock(&control->dev); device_lock(&p->dev);
	if (!control->driver || strcmp(control->driver->name,"n1-control-handoff") ||
	    p->driver || p->device != 0x1902 || p->vendor != 0x106b ||
	    pci_read_config_word(p,PCI_COMMAND,&command) || command != 0x406) goto out;
	c=pci_get_drvdata(control); q=pci_get_drvdata(p);
	if (!c || !c->alpha || !q || q->pdev != p || q->shared.owner != c->alpha ||
	    !q->shared.memory || !q->pool || !c->secondary || !c->alpha->working ||
	    q->magic != 0x5334315452414e53ULL || q->mh != 12 || q->sequence != 29 ||
	    get_unaligned_le16(q->shared.memory) != 0x300) goto out;
	pr_info("N1_S47 control stage=%u ipc=%u Alpha stage=%u ipc=%u IRQ=%d\n",
		readl(c->bar+0x8000),readl(c->bar+0x8050),readl(c->alpha->bar+8),readl(c->alpha->bar+12),atomic_read(&c->alpha->interrupts));
	dma_rmb();
	pr_info("N1_S47 Alpha PI=%*phN indices crheads=%u/%u/%u trtails=%u/%u/%u\n",
		16,q->shared.memory+0x68,get_unaligned_le16(q->shared.memory+0x7a),
		get_unaligned_le16(q->shared.memory+0x7c),get_unaligned_le16(q->shared.memory+0x7e),
		get_unaligned_le16(q->shared.memory+0x24e),get_unaligned_le16(q->shared.memory+0x250),
		get_unaligned_le16(q->shared.memory+0x252));
	pr_info("N1_S47 cursors mh=%u seq=%u txhead=%u txtail=%u RXcr=%u/%u RXtr=%u/%u TXcr=%u/%u TXtr=%u/%u\n",
 q->mh,q->sequence,q->txhead,q->txtail,
 get_unaligned_le16(q->shared.memory+0x78+2*207),get_unaligned_le16(q->shared.memory+0x3cc+2*207),
 get_unaligned_le16(q->shared.memory+0x5a0+2*12),get_unaligned_le16(q->shared.memory+0x24c+2*12),
 get_unaligned_le16(q->shared.memory+0x78+2*192),get_unaligned_le16(q->shared.memory+0x3cc+2*192),
 get_unaligned_le16(q->shared.memory+0x5a0+2*25),get_unaligned_le16(q->shared.memory+0x24c+2*25));
 src[0]=c->secondary; src[1]=c->alpha->working; src[2]=q->shared.memory; src[3]=q->pool;
	ret=-ENOMEM;
	for(i=0;i<ARRAY_SIZE(snaps);i++) {
		snaps[i].data=kvmalloc(snaps[i].size,GFP_KERNEL);
		if(!snaps[i].data) goto fail;
		dma_rmb(); memcpy(snaps[i].data,src[i],snaps[i].size);
		snaps[i].entry=proc_create_data(snaps[i].name,0400,NULL,&snapshot_ops,&snaps[i]);
		if(!snaps[i].entry) goto fail;
	}
	ret=0; goto out;
fail:
	cleanup();
out:
	device_unlock(&p->dev); device_unlock(&control->dev); pci_dev_put(control);
put:
	pci_dev_put(p); return ret;
}
module_init(snapshot_init);
module_exit(cleanup);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Private host-memory-only Alpha diagnostic snapshot");
