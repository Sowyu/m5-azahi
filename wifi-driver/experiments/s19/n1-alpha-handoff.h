/* Native memswap handoff: copy the boot-populated msww region into a
 * working allocation in Alpha's own DMA domain; publish PCI f88/f8c/f90.
 * No RF commands, BAR4 access, or function reset. All post-launch resources
 * remain pinned, including failures. Private S19-only resource ABI.
 */
#include <linux/sizes.h>
#define ALPHA_SIZE SZ_2M
#define ALPHA_OFFSET 640
#define ALPHA_IRQS 16
struct n1_alpha {
	struct pci_dev *pdev;
	void __iomem *bar;
	void *working;
	dma_addr_t dma;
	u64 old_dma_mask, old_coherent_mask;
	u16 old_command;
	atomic_t interrupts;
};
static_assert(sizeof(struct n1_alpha) == 56);
static_assert(offsetof(struct n1_boot, alpha) == 752);
static_assert(sizeof(struct n1_boot) == 760);
static unsigned int alpha_phase;
module_param(alpha_phase, uint, 0444);
static int alpha_result = -EINPROGRESS;
module_param(alpha_result, int, 0444);

static irqreturn_t alpha_irq(int irq, void *data)
{
	struct n1_alpha *a = data;
	atomic_inc(&a->interrupts);
	return IRQ_HANDLED;
}

/* Only before any Alpha address publication / bus-master enable. */
static void release_alpha_unpublished(struct n1_boot *n1)
{
	struct n1_alpha *a = n1->alpha;
	unsigned int i;
	if (WARN_ON(alpha_phase || !a))
		return;
	for (i = 0; i < ALPHA_IRQS; i++)
		free_irq(pci_irq_vector(a->pdev, i), a);
	pci_free_irq_vectors(a->pdev);
	dma_free_coherent(&a->pdev->dev, ALPHA_SIZE, a->working, a->dma);
	dma_set_mask(&a->pdev->dev, a->old_dma_mask);
	dma_set_coherent_mask(&a->pdev->dev, a->old_coherent_mask);
	pci_iounmap(a->pdev, a->bar);
	pci_disable_device(a->pdev);
	pci_write_config_word(a->pdev, PCI_COMMAND, a->old_command);
	pci_release_region(a->pdev, 0);
	pci_dev_put(a->pdev);
	kfree(a);
	n1->alpha = NULL;
}

static int prepare_alpha(struct n1_boot *n1)
{
	struct pci_dev *p = pci_get_slot(n1->pdev->bus, PCI_DEVFN(0, 1));
	struct n1_alpha *a = NULL;
	struct iommu_domain *domain;
	struct iommu_group *group;
	u16 command;
	u32 v;
	unsigned int i, count = 0, irqs = 0;
	int ret = -ENODEV;
	if (!p)
		return ret;
	device_lock(&p->dev);
	if (p->vendor != 0x106b || p->device != 0x1902 || p->driver ||
	    pci_is_enabled(p) || p->msi_enabled || p->msix_enabled ||
	    p->current_state != PCI_D0 || pci_resource_len(p, 0) != 0x10000 ||
	    pci_read_config_word(p, PCI_COMMAND, &command) || command)
		goto out;
	for (i = 0xf88; i <= 0xf90; i += 4)
		if (pci_read_config_dword(p, i, &v) || v)
			goto out;
	domain = iommu_get_domain_for_dev(&p->dev);
	if (!domain || !iommu_is_dma_domain(domain) ||
	    domain == iommu_get_domain_for_dev(&n1->pdev->dev))
		goto out;
	group = iommu_group_get(&p->dev);
	if (!group)
		goto out;
	ret = iommu_group_for_each_dev(group, &count, count_group_device);
	iommu_group_put(group);
	if (ret || count != 1) {
		ret = -EPERM;
		goto out;
	}
	/* Match the exact input FTAB entry, not just the hard-coded offset. */
	ret = -EBADMSG;
	for (i = 0; i < 34; i++) {
		u8 *e = n1->secondary + 48 + 16 * i;
		if (!memcmp(e, "msww", 4)) {
			if (get_unaligned_le32(e + 4) == ALPHA_OFFSET &&
			    get_unaligned_le32(e + 8) == ALPHA_SIZE)
				ret = 0;
			break;
		}
	}
	if (ret)
		goto out;
	a = kzalloc(sizeof(*a), GFP_KERNEL);
	ret = -ENOMEM;
	if (!a)
		goto out;
	a->pdev = p;
	a->old_command = command;
	a->old_dma_mask = *p->dev.dma_mask;
	a->old_coherent_mask = p->dev.coherent_dma_mask;
	ret = pci_request_region(p, 0, "n1-alpha-handoff");
	if (ret)
		goto free_state;
	ret = pci_enable_device_mem(p);
	if (ret)
		goto release_region;
	a->bar = pci_iomap(p, 0, 0x10000);
	ret = -ENOMEM;
	if (!a->bar)
		goto disable;
	ret = dma_set_mask_and_coherent(&p->dev, DMA_BIT_MASK(40));
	if (ret)
		goto restore_mask;
	a->working = dma_alloc_coherent(&p->dev, ALPHA_SIZE, &a->dma, GFP_KERNEL);
	ret = -ENOMEM;
	if (!a->working)
		goto restore_mask;
	ret = -EFAULT;
	if (!IS_ALIGNED(a->dma, PAGE_SIZE) || !iommu_iova_to_phys(domain, a->dma) ||
	    !iommu_iova_to_phys(domain, a->dma + ALPHA_SIZE - 1))
		goto free_dma;
	ret = pci_alloc_irq_vectors(p, ALPHA_IRQS, ALPHA_IRQS, PCI_IRQ_MSI);
	if (ret < 0)
		goto free_dma;
	for (irqs = 0; irqs < ALPHA_IRQS; irqs++) {
		ret = request_irq(pci_irq_vector(p, irqs), alpha_irq, 0, "n1-alpha-handoff", a);
		if (ret)
			goto free_irqs;
	}
	n1->alpha = a;
	dev_info(&p->dev, "N1_ALPHA_PREPARED bytes=%u IRQs=%u own_DMA_domain=1 BM=0\n",
		 ALPHA_SIZE, ALPHA_IRQS);
	device_unlock(&p->dev);
	return 0;
free_irqs:
	while (irqs)
		free_irq(pci_irq_vector(p, --irqs), a);
	pci_free_irq_vectors(p);
free_dma:
	dma_free_coherent(&p->dev, ALPHA_SIZE, a->working, a->dma);
restore_mask:
	dma_set_mask(&p->dev, a->old_dma_mask);
	dma_set_coherent_mask(&p->dev, a->old_coherent_mask);
	pci_iounmap(p, a->bar);
disable:
	pci_disable_device(p);
	pci_write_config_word(p, PCI_COMMAND, a->old_command);
release_region:
	pci_release_region(p, 0);
free_state:
	kfree(a);
out:
	device_unlock(&p->dev);
	pci_dev_put(p);
	return ret;
}

static int handoff_alpha(struct n1_boot *n1)
{
	struct n1_alpha *a = n1->alpha;
	u32 v;
	u16 command;
	if (!a || readl(n1->bar + EXEC_STAGE) != 2 ||
	    memcmp(n1->secondary, n1->expected_secondary_header, SECONDARY_HEADER_SIZE))
		return -EBUSY;
	dma_rmb();
	memcpy(a->working, n1->secondary + ALPHA_OFFSET, ALPHA_SIZE);
	dma_wmb();
	alpha_phase = 1; /* Even partial publication must retain the allocation. */
	if (pci_write_config_dword(a->pdev, 0xf88, lower_32_bits(a->dma)) ||
	    pci_write_config_dword(a->pdev, 0xf8c, upper_32_bits(a->dma)) ||
	    pci_write_config_dword(a->pdev, 0xf90, ALPHA_SIZE) ||
	    pci_read_config_dword(a->pdev, 0xf88, &v) || v != lower_32_bits(a->dma) ||
	    pci_read_config_dword(a->pdev, 0xf8c, &v) || v != upper_32_bits(a->dma) ||
	    pci_read_config_dword(a->pdev, 0xf90, &v) || v != ALPHA_SIZE)
		return -EIO;
	pci_set_master(a->pdev);
	if (pci_read_config_word(a->pdev, PCI_COMMAND, &command) || command != 0x406)
		return -EIO;
	alpha_phase = 2;
	dev_info(&a->pdev->dev, "N1_ALPHA_PUBLISHED stage=%u ipc=%u IRQ=%d\n",
		 readl(a->bar + 8), readl(a->bar + 12), atomic_read(&a->interrupts));
	return 0;
}

static void observe_alpha(struct n1_boot *n1)
{
	struct n1_alpha *a = n1->alpha;
	u32 stage, old = ~0U;
	unsigned int i;
	if (!a)
		return;
	for (i = 0; i < 200; i++) {
		if (readl(n1->bar + EXEC_STAGE) != 2)
			break;
		stage = readl(a->bar + 8);
		if (stage != old) {
			dev_info(&a->pdev->dev, "N1_ALPHA_OBSERVE poll=%u stage=%u ipc=%u IRQ=%d\n",
				 i, stage, readl(a->bar + 12), atomic_read(&a->interrupts));
			old = stage;
		}
		if (stage == 2 || stage == 3)
			break;
		usleep_range(10000, 11000);
	}
}
