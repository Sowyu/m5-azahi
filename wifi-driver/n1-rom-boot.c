// SPDX-License-Identifier: GPL-2.0
/* Experimental J714s ROM-stage transfer, pinned to one reviewed candidate.
 * Default: prepare and verify DMA mappings, then free them, without starting
 * DMA. launch=1 sends one image to ROM only. No second-stage/RF operation.
 * After launch, the module and DMA buffers stay pinned until reboot.
 */
#include <crypto/sha2.h>
#include <linux/delay.h>
#include <linux/dma-mapping.h>
#include <linux/firmware.h>
#include <linux/interrupt.h>
#include <linux/io.h>
#include <linux/iommu.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/unaligned.h>

#define FW_NAME "azahi-n1/n1-boot-candidate.bin"
#define FW_SIZE 31117312
#define EXEC_STAGE 0x8000
#define CHIP_INFO 0x8008
#define BOOT_NONCE 0x8034
#define BOOT_MODE 0x803c
#define IMAGE_RESPONSE 0x8040
#define IMAGE_ADDRESS_LO 0x8044
#define IMAGE_ADDRESS_HI 0x8048
#define IMAGE_SIZE 0x804c
#define HOST_PLATFORM_ID 0x807c
#define ROM_DOORBELL 0x9000

static bool launch;
module_param(launch, bool, 0400);
MODULE_PARM_DESC(launch, "Send one reviewed image to ROM; pins resources until reboot");

struct n1_image_table {
	__le64 address;
	__le32 length;
	__le32 reserved;
	__le64 end_address;
	__le64 end_length_reserved;
};
static_assert(sizeof(struct n1_image_table) == 32);

struct n1_boot {
	struct pci_dev *pdev;
	void __iomem *bar;
	void *image;
	dma_addr_t image_dma, table_dma;
	struct n1_image_table *table;
	u64 old_dma_mask, old_coherent_mask;
	u16 old_command;
	atomic_t interrupts;
};

static int probe_result = -ENODEV;

static irqreturn_t n1_irq(int irq, void *data)
{
	struct n1_boot *n1 = data;

	atomic_inc(&n1->interrupts);
	return IRQ_HANDLED;
}

static int count_group_device(struct device *dev, void *data)
{
	(*(unsigned int *)data)++;
	return 0;
}

static int n1_release(struct n1_boot *n1)
{
	struct pci_dev *pdev = n1->pdev;
	u16 command;
	int ret = 0;

	/* Only used before any image doorbell or bus-master enable. */
	if (n1->table)
		dma_free_coherent(&pdev->dev, PAGE_SIZE, n1->table, n1->table_dma);
	if (n1->image)
		dma_free_coherent(&pdev->dev, PAGE_ALIGN(FW_SIZE), n1->image, n1->image_dma);
	dma_set_mask(&pdev->dev, n1->old_dma_mask);
	dma_set_coherent_mask(&pdev->dev, n1->old_coherent_mask);
	if (n1->bar)
		pci_iounmap(pdev, n1->bar);
	pci_release_region(pdev, 0);
	pci_disable_device(pdev);
	if (pci_write_config_word(pdev, PCI_COMMAND, n1->old_command) ||
	    pci_read_config_word(pdev, PCI_COMMAND, &command) ||
	    command != n1->old_command) {
		dev_err(&pdev->dev, "could not restore PCI command\n");
		ret = -EIO;
	}
	kfree(n1);
	return ret;
}

static int n1_probe(struct pci_dev *pdev, const struct pci_device_id *id)
{
	static const u8 expected_sha256[32] = {
		0x75, 0x53, 0x79, 0xaa, 0x14, 0xe9, 0x88, 0x4f,
		0x3f, 0xdd, 0x9c, 0xfe, 0x2e, 0xc1, 0x44, 0x81,
		0x52, 0x52, 0xcd, 0xfc, 0xa0, 0xd5, 0xd1, 0x76,
		0x73, 0x65, 0xf7, 0x82, 0xc7, 0x45, 0x59, 0x37,
	};
	struct iommu_domain *domain;
	struct iommu_group *group;
	const struct firmware *fw;
	struct n1_boot *n1;
	u8 digest[32];
	u32 response, stage, before_response, before_stage;
	u64 nonce;
	u16 command;
	bool rom_accepted = false;
	unsigned int devices = 0, elapsed;
	int ret, irq, cleanup_ret;

	ret = -ENODEV;
	if (!of_machine_is_compatible("apple,j714s") ||
	    pci_domain_nr(pdev->bus) != 0 || pdev->bus->number != 1 ||
	    pdev->devfn != 0 || pdev->current_state != PCI_D0 ||
	    pci_resource_len(pdev, 0) != 0x10000 ||
	    !(pci_resource_flags(pdev, 0) & IORESOURCE_MEM))
		goto result;
	ret = -EIO;
	if (pci_read_config_word(pdev, PCI_COMMAND, &command))
		goto result;
	ret = -EBUSY;
	if (command != 0)
		goto result;
	ret = -EPERM;
	domain = iommu_get_domain_for_dev(&pdev->dev);
	if (!domain || !iommu_is_dma_domain(domain))
		goto result;
	group = iommu_group_get(&pdev->dev);
	if (!group)
		goto result;
	iommu_group_for_each_dev(group, &devices, count_group_device);
	iommu_group_put(group);
	if (devices != 1)
		goto result;
	ret = request_firmware_direct(&fw, FW_NAME, &pdev->dev);
	if (ret)
		goto result;
	if (fw->size != FW_SIZE) {
		ret = -EINVAL;
		goto release_fw;
	}
	sha256(fw->data, fw->size, digest);
	if (memcmp(digest, expected_sha256, sizeof(digest))) {
		ret = -EBADMSG;
		goto release_fw;
	}
	n1 = kzalloc(sizeof(*n1), GFP_KERNEL);
	if (!n1) {
		ret = -ENOMEM;
		goto release_fw;
	}
	n1->pdev = pdev;
	n1->old_command = command;
	n1->old_dma_mask = dma_get_mask(&pdev->dev);
	n1->old_coherent_mask = pdev->dev.coherent_dma_mask;
	atomic_set(&n1->interrupts, 0);
	ret = pci_enable_device_mem(pdev);
	if (ret) {
		kfree(n1);
		goto release_fw;
	}
	ret = pci_request_region(pdev, 0, "n1-rom-boot");
	if (ret) {
		pci_disable_device(pdev);
		pci_write_config_word(pdev, PCI_COMMAND, command);
		kfree(n1);
		goto release_fw;
	}
	n1->bar = pci_iomap(pdev, 0, 0x10000);
	if (!n1->bar) {
		ret = -ENOMEM;
		goto release;
	}
	ret = -EINVAL;
	if (readl(n1->bar + EXEC_STAGE) != 0 ||
	    readl(n1->bar + CHIP_INFO) != 0x20260841 ||
	    readl(n1->bar + IMAGE_RESPONSE) != 0 ||
	    readl(n1->bar + IMAGE_SIZE) != 0)
		goto release;
	ret = dma_set_mask_and_coherent(&pdev->dev, DMA_BIT_MASK(40));
	if (ret)
		goto release;
	n1->image = dma_alloc_coherent(&pdev->dev, PAGE_ALIGN(FW_SIZE),
				      &n1->image_dma, GFP_KERNEL);
	n1->table = dma_alloc_coherent(&pdev->dev, PAGE_SIZE,
				      &n1->table_dma, GFP_KERNEL);
	if (!n1->image || !n1->table) {
		ret = -ENOMEM;
		goto release;
	}
	if (!IS_ALIGNED(n1->image_dma, 4096) || !IS_ALIGNED(n1->table_dma, 4096) ||
	    !iommu_iova_to_phys(domain, n1->image_dma) ||
	    !iommu_iova_to_phys(domain, n1->image_dma + FW_SIZE - 1) ||
	    !iommu_iova_to_phys(domain, n1->table_dma)) {
		ret = -EFAULT;
		goto release;
	}
	memcpy(n1->image, fw->data, fw->size);
	/* Echo the ROM's current boot-session nonce, as the Apple boot path does. */
	nonce = readl(n1->bar + BOOT_NONCE);
	nonce |= (u64)readl(n1->bar + BOOT_NONCE + 4) << 32;
	put_unaligned_le64(nonce, n1->image + 8);
	memset(n1->table, 0, PAGE_SIZE);
	n1->table->address = cpu_to_le64(n1->image_dma);
	n1->table->length = cpu_to_le32(FW_SIZE);
	dev_info(&pdev->dev, "N1_PREPARED image=%u table=%zu IOMMU=DMA exclusive=1 launch=%d\n",
		 FW_SIZE, sizeof(*n1->table), launch);
	if (!launch) {
		ret = 0;
		goto release;
	}
	ret = pci_alloc_irq_vectors(pdev, 1, 1, PCI_IRQ_MSI);
	if (ret < 0)
		goto release;
	irq = pci_irq_vector(pdev, 0);
	ret = request_irq(irq, n1_irq, 0, "n1-rom-boot", n1);
	if (ret) {
		pci_free_irq_vectors(pdev);
		goto release;
	}
	release_firmware(fw);
	pci_set_drvdata(pdev, n1);
	/* Once armed, never free memory that the peripheral might still use. */
	__module_get(THIS_MODULE);
	pci_set_master(pdev);
	writel(0, n1->bar + BOOT_MODE); /* normal boot (not debug/manufacturing) */
	writel(0x00086050, n1->bar + HOST_PLATFORM_ID); /* J714s: board 8, T6050 */
	dma_wmb();
	writel(lower_32_bits(n1->table_dma), n1->bar + IMAGE_ADDRESS_LO);
	writel(upper_32_bits(n1->table_dma), n1->bar + IMAGE_ADDRESS_HI);
	writel(sizeof(*n1->table), n1->bar + IMAGE_SIZE);
	writel(1, n1->bar + ROM_DOORBELL);
	readl(n1->bar + EXEC_STAGE); /* flush posted writes */
	dev_info(&pdev->dev, "N1_ROM_SENT; resources pinned until reboot\n");
	before_response = before_stage = ~0U;
	for (elapsed = 0; elapsed <= 15000; elapsed += 10) {
		response = readl(n1->bar + IMAGE_RESPONSE);
		stage = readl(n1->bar + EXEC_STAGE);
		if (response == 1)
			rom_accepted = true;
		if (response != before_response || stage != before_stage)
			dev_info(&pdev->dev, "N1_ROM_STATE ms=%u response=%#x stage=%#x irq=%d\n",
				 elapsed, response, stage, atomic_read(&n1->interrupts));
		before_response = response;
		before_stage = stage;
		/* Preboot asks the host to re-enumerate; this experiment stops there. */
		if (stage == 1 || stage == 2 || stage == 3 || stage == 4 ||
		    stage == ~0U || response >= 2)
			break;
		msleep(10);
	}
	/* There is no next-stage request in this module. Retain all DMA mappings. */
	pci_clear_master(pdev);
	dev_info(&pdev->dev, "N1_ROM_RESULT accepted_seen=%d response=%#x stage=%#x irq=%d; DMA disabled, buffers retained\n",
		 rom_accepted, response, stage, atomic_read(&n1->interrupts));
	if (stage == 4 && response < 2)
		dev_info(&pdev->dev, "N1_PREBOOT: host port re-enumeration required; not implemented\n");
	else if (stage != 1 || response >= 2)
		dev_err(&pdev->dev, "ROM transfer ended outside preboot/boot stage\n");
	probe_result = 0; /* transfer result is reported separately from driver binding */
	return 0;
release:
	cleanup_ret = n1_release(n1);
	if (cleanup_ret)
		ret = cleanup_ret;
release_fw:
	release_firmware(fw);
result:
	probe_result = ret;
	/* Dry preparation always detaches; init uses probe_result to report errors. */
	return ret ? ret : -ENODEV;
}

static void n1_shutdown(struct pci_dev *pdev)
{
	pci_clear_master(pdev);
}

static const struct pci_device_id n1_ids[] = {
	{ PCI_DEVICE(0x106b, 0x1900) }, { }
};
/* No MODULE_DEVICE_TABLE: never auto-load this experiment. */
static struct pci_driver n1_driver = {
	.name = "n1-rom-boot",
	.id_table = n1_ids,
	.probe = n1_probe,
	.shutdown = n1_shutdown,
	.driver = { .suppress_bind_attrs = true },
};

static int __init n1_init(void)
{
	int ret = pci_register_driver(&n1_driver);

	if (ret)
		return ret;
	if (!launch || probe_result) {
		pci_unregister_driver(&n1_driver);
		return probe_result;
	}
	return 0;
}

static void __exit n1_exit(void) { }
module_init(n1_init);
module_exit(n1_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("J714s N1 single ROM-stage transfer experiment");
