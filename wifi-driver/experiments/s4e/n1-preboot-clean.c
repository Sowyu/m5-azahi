// SPDX-License-Identifier: GPL-2.0
/* Private one-session migration from the exact 2026-09-29 ROM experiment.
 * Default is read-only preflight. arm=1 retires its resources and asserts
 * endpoint PERST only, then rescans port 0. No common/PHY/power reset.
 * The original module stays pinned; this module also pins after mutation.
 */
#include <linux/delay.h>
#include <linux/dma-mapping.h>
#include <linux/interrupt.h>
#include <linux/io.h>
#include <linux/iommu.h>
#include <linux/iopoll.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/unaligned.h>

#define FW_SIZE 31117312
#define GPIO_PS 0x280600250ULL
#define PMGR 0x280900000ULL
#define GPIO 0x29c000000ULL
#define PORT0 0x410028000ULL
#define PIN 80
#define LINKSTS 0x208
#define LTSSMCTL 0x80
#define STATUS 0x804

/* ABI of s3-tested-20260929/n1-rom-boot.c, not a general driver API. */
struct old_table {
	__le64 address;
	__le32 length, reserved;
	__le64 end_address, end_length_reserved;
};
struct old_boot {
	struct pci_dev *pdev;
	void __iomem *bar;
	void *image;
	dma_addr_t image_dma, table_dma;
	struct old_table *table;
	u64 old_dma_mask, old_coherent_mask;
	u16 old_command;
	atomic_t interrupts;
	bool armed;
};
static_assert(offsetof(struct old_boot, armed) == 72);
static_assert(sizeof(struct old_boot) == 80);

static bool arm;
module_param(arm, bool, 0400);
static bool hold_for_port_cycle;
module_param(hold_for_port_cycle, bool, 0400);
static bool pme_turnoff;
module_param(pme_turnoff, bool, 0400);
static int result = -EINPROGRESS;
module_param(result, int, 0444);
static unsigned int phase;
module_param(phase, uint, 0444);
/* Preserve the primary image's session nonce for the next transfer. Root only;
 * never print it, and never infer a replacement from reset BAR contents. */
static unsigned long long rom_nonce;
module_param(rom_nonce, ullong, 0400);

static bool check_power(void __iomem *pmgr)
{
	static const u32 offsets[] = { 0x140, 0x128, 0x150, 0x138,
		0x118, 0x148, 0x1b0, 0x258, 0x280 };
	unsigned int i;
	for (i = 0; i < ARRAY_SIZE(offsets); i++)
		if (((readl(pmgr + offsets[i]) >> 4) & 15) != 15)
			return false;
	return true;
}

static int run(void)
{
	struct pci_dev *pdev, *rp, *child;
	struct pci_driver *old_driver;
	struct old_boot *old;
	struct pci_bus *bus;
	struct iommu_domain *domain;
	void __iomem *ps = NULL, *pmgr = NULL, *gpio = NULL, *port = NULL;
	u16 command, root_link, root_dev;
	u32 v, pin, old_ltssm, root_err = 0, raw_id;
	unsigned int children = 0;
	int ret = -ENODEV, irq, aer;
	bool locked = false, root_modified = false, removed = false;

	if (!of_machine_is_compatible("apple,j714s"))
		return -ENODEV;
	pdev = pci_get_domain_bus_and_slot(0, 1, PCI_DEVFN(0, 0));
	if (!pdev)
		return -ENODEV;
	bus = pdev->bus;
	rp = pci_dev_get(bus->self);
	if (!rp || rp->vendor != 0x106b || rp->device != 0x100c ||
	    rp->devfn || !pci_is_root_bus(rp->bus) || rp->current_state != PCI_D0)
		goto out;
	pci_lock_rescan_remove();
	device_lock(&pdev->dev);
	locked = true;
	list_for_each_entry(child, &bus->devices, bus_list)
		children++;
	if (children != 1 || pdev->vendor != 0x106b || pdev->device != 0x1900 ||
	    pdev->current_state != PCI_D0 || atomic_read(&pdev->enable_cnt) != 1 ||
	    pci_resource_len(pdev, 0) != 0x10000)
		goto unlock;
	old_driver = pdev->driver;
	if (!old_driver || strcmp(old_driver->name, "n1-rom-retry") || old_driver->remove)
		goto unlock;
	old = pci_get_drvdata(pdev);
	if (!old || old->pdev != pdev || !old->armed || !old->bar || !old->image ||
	    !old->table || old->old_command != 0 || !pdev->msi_enabled || pdev->msix_enabled ||
	    le64_to_cpu(old->table->address) != old->image_dma ||
	    le32_to_cpu(old->table->length) != FW_SIZE || old->table->reserved ||
	    old->table->end_address || old->table->end_length_reserved ||
	    memcmp(old->image + 32, "rkosftab", 8) ||
	    get_unaligned_le32(old->image + 40) != 83)
		goto unlock;
	domain = iommu_get_domain_for_dev(&pdev->dev);
	if (!domain || !iommu_is_dma_domain(domain) ||
	    !iommu_iova_to_phys(domain, old->image_dma) ||
	    !iommu_iova_to_phys(domain, old->image_dma + FW_SIZE - 1) ||
	    !iommu_iova_to_phys(domain, old->table_dma))
		goto unlock;
	ret = -EBUSY;
	if (pci_read_config_word(pdev, PCI_COMMAND, &command) || command != 0x402 ||
	    readl(old->bar + 0x8000) != 4 || readl(old->bar + 0x8008) != 0x20260841 ||
	    readl(old->bar + 0x8040) != 0 || !pci_wait_for_pending_transaction(pdev))
		goto unlock;
	irq = pci_irq_vector(pdev, 0);
	if (irq < 0 || atomic_read(&old->interrupts) != 2)
		goto unlock;
	ps = ioremap_np(GPIO_PS, 4);
	pmgr = ioremap_np(PMGR, 0x4000);
	ret = -ENOMEM;
	if (!ps || !pmgr)
		goto unlock;
	ret = -EHOSTDOWN;
	if (((readl(ps) >> 4) & 15) != 15 || !check_power(pmgr))
		goto unlock;
	gpio = ioremap_np(GPIO, 0x4000);
	port = ioremap_np(PORT0, 0x8000);
	ret = -ENOMEM;
	if (!gpio || !port)
		goto unlock;
	pin = readl(gpio + PIN * 4);
	old_ltssm = readl(port + LTSSMCTL);
	ret = -EBUSY;
	if ((pin & 15) != 3 || !(readl(port + STATUS) & 1) ||
	    !(readl(port + LINKSTS) & 1) || old_ltssm != 1)
		goto unlock;
	ret = -EIO;
	if (pcie_capability_read_word(rp, PCI_EXP_LNKCTL, &root_link) ||
	    pcie_capability_read_word(rp, PCI_EXP_DEVCTL, &root_dev))
		goto unlock;
	aer = pci_find_ext_capability(rp, PCI_EXT_CAP_ID_ERR);
	if (aer && pci_read_config_dword(rp, aer + PCI_ERR_ROOT_COMMAND, &root_err))
		goto unlock;
	pr_info("n1-reenum: preflight passed stage=4 irq=%d pending=0 single_endpoint=1 arm=%d\n", irq, arm);
	phase = 1;
	rom_nonce = get_unaligned_le64(old->image + 8);
	ret = 0;
	if (!arm)
		goto unlock;

	/* No code in the old driver runs asynchronously except its trivial IRQ. */
	pci_clear_master(pdev);
	if (pci_read_config_word(pdev, PCI_COMMAND, &command) ||
	    command & PCI_COMMAND_MASTER || !pci_wait_for_pending_transaction(pdev)) {
		ret = -EBUSY;
		goto unlock;
	}
	__module_get(THIS_MODULE);
	free_irq(irq, old);
	pci_free_irq_vectors(pdev);
	phase = 2;
	/* The intended reset is not an AER fault. Mask root error reporting. */
	root_modified = true;
	if (pcie_capability_write_word(rp, PCI_EXP_DEVCTL, root_dev & ~0xf) ||
	    (aer && pci_write_config_dword(rp, aer + PCI_ERR_ROOT_COMMAND, 0)) ||
	    pcie_capability_write_word(rp, PCI_EXP_LNKCTL,
				      root_link & ~PCI_EXP_LNKCTL_ASPMC)) {
		ret = -EIO;
		goto unlock;
	}
	/* Retire the host RID entry while configuration space is still reachable. */
	pci_disable_device(pdev);
	if (pme_turnoff) {
		u16 root_command;
		u32 root_bus;
		int ack, l2;
		if (pci_read_config_word(rp, PCI_COMMAND, &root_command) ||
		    pci_read_config_dword(rp, PCI_PRIMARY_BUS, &root_bus)) {
			ret = -EIO;
			goto unlock;
		}
		/* Apple disableGated clears bridge decoding/bus routing, then asks
		 * the endpoint to enter L2 before asserting PERST. */
		pci_write_config_word(rp, PCI_COMMAND, 0);
		pci_write_config_dword(rp, PCI_PRIMARY_BUS, root_bus & 0xff0000ff);
		writel(readl(port + 0x800) | BIT(8), port + 0x800);
		writel(0x11, port + 0x88);
		ack = readl_poll_timeout(port + 0x88, v, !(v & 1), 100, 10000);
		pr_info("n1-reenum: PME turnoff=%#x ack_result=%d\n", v, ack);
		l2 = readl_poll_timeout(port + LINKSTS, v, v & BIT(6), 100, 100000);
		pr_info("n1-reenum: L2 LINKSTS=%#x result=%d\n", v, l2);
		pci_write_config_dword(rp, PCI_PRIMARY_BUS, root_bus);
		pci_write_config_word(rp, PCI_COMMAND, root_command);
	}
	/* PERST assertion precedes LTSSM stop, as endpoint reset in Apple's path. */
	writel(pin & ~1U, gpio + PIN * 4);
	readl(gpio + PIN * 4);
	ret = readl_poll_timeout(port + LINKSTS, v, !(v & 1) || (v & BIT(6)), 100, 1000000);
	pr_info("n1-reenum: PERST asserted LINKSTS=%#x result=%d\n", v, ret);
	if (ret)
		goto unlock; /* retain old DMA mappings; no uncertain memory release */
	phase = 3;
	writel(0, port + LTSSMCTL);
	if (readl(port + LTSSMCTL) != 0) {
		ret = -EIO;
		goto unlock;
	}
	msleep(10);
	if ((readl(gpio + PIN * 4) & 1) || readl(port + 0x820)) {
		ret = -EBUSY;
		goto unlock;
	}

	/* Bus mastering is disabled, transactions drained, endpoint held reset. */
	dma_free_coherent(&pdev->dev, PAGE_SIZE, old->table, old->table_dma);
	dma_free_coherent(&pdev->dev, PAGE_ALIGN(FW_SIZE), old->image, old->image_dma);
	dma_set_mask(&pdev->dev, old->old_dma_mask);
	dma_set_coherent_mask(&pdev->dev, old->old_coherent_mask);
	pci_iounmap(pdev, old->bar);
	pci_release_region(pdev, 0);
	pci_set_drvdata(pdev, NULL);
	kfree(old);
	device_unlock(&pdev->dev);
	locked = false;
	pci_unregister_driver(old_driver);
	pci_stop_and_remove_bus_device(pdev);
	removed = true;
	/* The retry module has no callbacks/resources after driver unregister. */
	module_put(old_driver->driver.owner);
	phase = 4;
	if (hold_for_port_cycle) {
		pr_info("n1-reenum: endpoint retired; PERST held for full port cycle\n");
		ret = 0;
		goto unlock;
	}
	msleep(100);
	writel(pin, gpio + PIN * 4);
	readl(gpio + PIN * 4);
	msleep(100);
	writel(old_ltssm, port + LTSSMCTL);
	readl(port + LTSSMCTL);
	ret = readl_poll_timeout(port + LINKSTS, v, v & 1, 1000, 2000000);
	pr_info("n1-reenum: PERST released LINKSTS=%#x result=%d\n", v, ret);
	if (ret)
		goto unlock;
	phase = 5;
	msleep(100);
	ret = pci_bus_read_config_dword(bus, PCI_DEVFN(0, 0), PCI_VENDOR_ID, &raw_id);
	pr_info("n1-reenum: new raw PCI ID=%#x config_result=%d\n", raw_id, ret);
	if (ret || (raw_id & 0xffff) != 0x106b) {
		ret = -EIO;
		goto unlock;
	}
	/* PCI core assigns BARs and attaches the new device's DMA domain. */
	pci_rescan_bus(bus);
	phase = 6;
	list_for_each_entry(child, &bus->devices, bus_list)
		pr_info("n1-reenum: enumerated %s %04x:%04x BAR0=%#llx size=%#llx\n",
			pci_name(child), child->vendor, child->device,
			(unsigned long long)pci_resource_start(child, 0),
			(unsigned long long)pci_resource_len(child, 0));
	ret = check_power(pmgr) ? 0 : -EIO;
unlock:
	if (root_modified) {
		/* Clear status raised by the intentional endpoint reset, then restore. */
		if (aer) {
			pci_read_config_dword(rp, aer + PCI_ERR_UNCOR_STATUS, &v);
			if (v)
				pr_info("n1-reenum: reset AER uncorrectable status=%#x\n", v);
			pci_write_config_dword(rp, aer + PCI_ERR_UNCOR_STATUS, v);
			pci_read_config_dword(rp, aer + PCI_ERR_COR_STATUS, &v);
			pci_write_config_dword(rp, aer + PCI_ERR_COR_STATUS, v);
			pci_read_config_dword(rp, aer + PCI_ERR_ROOT_STATUS, &v);
			pci_write_config_dword(rp, aer + PCI_ERR_ROOT_STATUS, v);
			pci_write_config_dword(rp, aer + PCI_ERR_ROOT_COMMAND, root_err);
		}
		pcie_capability_write_word(rp, PCI_EXP_DEVCTL, root_dev);
		pcie_capability_write_word(rp, PCI_EXP_LNKCTL, root_link);
	}
	if (locked)
		device_unlock(&pdev->dev);
	pci_unlock_rescan_remove();
	pr_info("n1-reenum: phase=%u removed=%d result=%d\n", phase, removed, ret);
out:
	if (port) iounmap(port);
	if (gpio) iounmap(gpio);
	if (pmgr) iounmap(pmgr);
	if (ps) iounmap(ps);
	pci_dev_put(rp);
	pci_dev_put(pdev);
	if (removed)
		module_put(THIS_MODULE);
	return ret;
}

static int __init reenum_init(void)
{
	result = run();
	return phase >= 2 ? 0 : result;
}
static void __exit reenum_exit(void) { }
module_init(reenum_init);
module_exit(reenum_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("J714s single-session preboot endpoint reset and PCI re-enumeration");
