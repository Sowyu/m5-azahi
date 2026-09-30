// SPDX-License-Identifier: GPL-2.0
/* Private S41 + S44 + S46 recovery. Only Alpha FLR; no bus, port or chip reset.
 * Native: cfg f80=5 means ready-for-reset; clear f80..ffc before FLR.
 * Preserve all old DMA and disable its callers with a new drvdata marker.
 * IRQ handlers only increment the retained S19 owner's atomic counter.
 */
#include <linux/delay.h>
#include <linux/dma-mapping.h>
#include <linux/interrupt.h>
#include <linux/io.h>
#include <linux/iommu.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/slab.h>
#include <linux/unaligned.h>
#include "../s41/n1-s19-abi.h"
#include <linux/mutex.h>
#include <linux/wait.h>
#include <linux/workqueue.h>
#include "../s41/n1-transport-abi.h"
#include "../s41/n1-v8-api.h"
#include "../s44/n1-data-api.h"
#include "../s46/n1-tx-api.h"
#define RESTART_MAGIC 0x533438414c504841ULL
static bool launch;
module_param(launch, bool, 0400);
static int result = -EINPROGRESS;
module_param(result, int, 0444);
static unsigned int phase;
module_param(phase, uint, 0444);
static u16 idx(void *ctx, unsigned int off)
{
	u16 v = le16_to_cpu(READ_ONCE(*(__le16 *)(ctx + off)));
	dma_rmb();
	return v;
}
static int __init restart_init(void)
{
	struct pci_dev *p, *control;
	struct old_boot *c;
	struct n1_alpha *a;
	struct transport *q;
	struct alpha_restart *s = NULL;
	struct iommu_domain *domain;
	u16 command, devsta;
	u32 v, mask, identity;
	unsigned int i, scans, status, count;
 bool pending;
	int aer, ret = -ENODEV;
	if (!of_machine_is_compatible("apple,j714s")) return ret;
 if (n1_alpha_scan_status_v8(&scans,&status,&count,&pending)!=-EIO ||
     pending || scans!=1 || status) return -EBUSY;
	p = pci_get_domain_bus_and_slot(0, 1, PCI_DEVFN(0, 1));
	if (!p) return ret;
	control = pci_get_slot(p->bus, 0);
	if (!control) goto put;
	device_lock(&control->dev);
	device_lock(&p->dev);
	if (!control->driver || strcmp(control->driver->name, "n1-control-handoff") ||
	    p->driver || p->vendor != 0x106b || p->device != 0x1902 ||
	    !p->msi_enabled || p->msix_enabled || pci_irq_vector(p, 15) < 0 ||
	    atomic_read(&p->enable_cnt) != 1 || p->current_state != PCI_D0 ||
	    pci_read_config_word(p, PCI_COMMAND, &command) || command != 0x406 ||
	    !(p->devcap & PCI_EXP_DEVCAP_FLR)) goto out;
	c = pci_get_drvdata(control);
	q = pci_get_drvdata(p);
	if (!c || !(a = c->alpha) || !q || q->shared.owner != a ||
	    q->pdev != p || q->previous || !q->pool || !q->shared.memory ||
	    q->magic != 0x5334315452414e53ULL || q->mh != 12 || q->sequence != 29 ||
     q->txhead != 13 || q->txtail != 13 || q->waiting || q->cid != 0x20000 ||
	    a->pdev != p || !a->working || !a->bar ||
	    readl(c->bar + 0x8000) != 2 || readl(c->bar + 0x8050) != 2 ||
	    readl(a->bar + 8) != 3 || readl(a->bar + 12) != 2 ||
	    pci_read_config_dword(p, 0xf80, &v) || v != 5 ||
	    pci_read_config_dword(p, 0xf88, &v) || v != lower_32_bits(a->dma) ||
	    pci_read_config_dword(p, 0xf8c, &v) || v != upper_32_bits(a->dma) ||
	    pci_read_config_dword(p, 0xf90, &v) || v != ALPHA_SIZE ||
	    pcie_capability_read_word(p, PCI_EXP_DEVSTA, &devsta) ||
	    (devsta & PCI_EXP_DEVSTA_TRPND)) goto out;
 /* Completed management and command TX; RX data deliberately remains
  * unconsumed and all allocations stay pinned through function reset. */
 if (idx(q->shared.memory,0x78)!=12 || idx(q->shared.memory,0x3cc)!=12 ||
     idx(q->shared.memory,0x24c)!=12 || idx(q->shared.memory,0x5a0)!=12 ||
     idx(q->shared.memory,0x24e)!=13 || idx(q->shared.memory,0x5a2)!=13 ||
     idx(q->shared.memory,0x78+2*207)!=127 || idx(q->shared.memory,0x3cc+2*207)) goto out;
	domain = iommu_get_domain_for_dev(&p->dev);
	if (!domain || !iommu_is_dma_domain(domain) ||
	    domain == iommu_get_domain_for_dev(&control->dev) ||
	    !iommu_iova_to_phys(domain, a->dma) ||
	    !iommu_iova_to_phys(domain, a->dma + ALPHA_SIZE - 1)) goto out;
	aer = pci_find_ext_capability(p, PCI_EXT_CAP_ID_ERR);
	if (!aer || pci_read_config_dword(p, aer + PCI_ERR_COR_MASK, &mask)) goto out;
	s = kzalloc(sizeof(*s), GFP_KERNEL);
	if (!s) { ret = -ENOMEM; goto out; }
	s->shared.owner = a;
	s->previous = q;
	s->magic = RESTART_MAGIC;
	pr_info("N1_ALPHA_RESTART48_PREPARED launch=%d ready=5 stage=3; only FLR, all DMA retained\n", launch);
	ret = 0;
	if (!launch) { kfree(s); goto out; }
	__module_get(THIS_MODULE);
	/* S41 returned EIO after its last poll and cannot restart; its worker
  * is separate from the legacy q->work field, which must not be touched. */
 n1_data_rx_quiesce_v1();
 n1_data_tx_quiesce_v1();
	mutex_lock(&q->command_lock);
	mutex_lock(&q->io_lock);
	pci_set_drvdata(p, s); /* old exchange and event callers fail closed */
	phase = 1;
	for (i = 0; i < ALPHA_IRQS; i++) disable_irq(pci_irq_vector(p, i));
	pci_clear_master(p);
	result = -EIO;
	if (pci_read_config_word(p, PCI_COMMAND, &command) || command != 0x402 ||
	    pcie_capability_read_word(p, PCI_EXP_DEVSTA, &devsta) ||
	    (devsta & PCI_EXP_DEVSTA_TRPND)) goto irq_on;
	/* Native ClearConfigSpaceMailboxes and MaskUnsupportedRequestAER. */
	for (i = 0xf80; i <= 0xffc; i += 4)
		if (pci_write_config_dword(p, i, 0)) goto irq_on;
	if (pci_write_config_dword(p, aer + PCI_ERR_COR_MASK, mask | BIT(13))) goto irq_on;
	result = pci_save_state(p);
	if (result) goto irq_on;
	phase = 2;
	result = pcie_flr(p); /* explicit FLR; never falls back to bus reset */
	pci_restore_state(p);
	if (result) goto irq_on;
	if (pci_read_config_dword(p, PCI_VENDOR_ID, &identity) || identity != 0x1902106b ||
	    pci_read_config_word(p, PCI_COMMAND, &command) || command != 0x402) {
		result = -EIO;
		goto irq_on;
	}
	pci_write_config_dword(p, aer + PCI_ERR_COR_STATUS, BIT(13));
	pci_write_config_dword(p, aer + PCI_ERR_COR_MASK, mask);
	phase = 3;
	pr_info("N1_ALPHA_RESTART48_FLR_COMPLETE stage=%u ipc=%u\n", readl(a->bar+8), readl(a->bar+12));
	/* Native ConfigureEndpointForMemSwap republishes its retained working copy. */
	dma_wmb();
	if (pci_write_config_dword(p, 0xf88, lower_32_bits(a->dma)) ||
	    pci_write_config_dword(p, 0xf8c, upper_32_bits(a->dma)) ||
	    pci_write_config_dword(p, 0xf90, ALPHA_SIZE)) { result = -EIO; goto irq_on; }
	pci_set_master(p);
	phase = 4;
irq_on:
	for (i = 0; i < ALPHA_IRQS; i++) enable_irq(pci_irq_vector(p, i));
	if (phase == 4) {
		result = -ETIMEDOUT;
		for (i = 0; i < 3000; i++) {
			v = readl(a->bar + 8);
			if (v == 2) { result = 0; phase = 5; break; }
			if (v == 3 || readl(c->bar + 0x8000) != 2) { result = -EIO; break; }
			usleep_range(1000, 1500);
		}
	}
	mutex_unlock(&q->io_lock);
	mutex_unlock(&q->command_lock);
	pr_info("N1_ALPHA_RESTART48_RESULT result=%d phase=%u; old resources remain pinned\n", result, phase);
out:
	device_unlock(&p->dev);
	device_unlock(&control->dev);
	pci_dev_put(control);
put:
	pci_dev_put(p);
	return ret;
}
static void __exit restart_exit(void) { }
module_init(restart_init);
module_exit(restart_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Guarded Alpha-only restart at native reset-ready state");
