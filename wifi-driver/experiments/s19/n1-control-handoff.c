// SPDX-License-Identifier: GPL-2.0
/* Private J714s boot-stage transfer with experimental control IPC handshake.
 * Default: prepare and verify DMA mappings, then free them, without starting
 * DMA. launch=1 configures secondary memory and sends the original image.
 * Opens CCHI control queues after IPC handshake. No radio operation.
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
#define SECONDARY_NAME "azahi-n1/n1-secondary-candidate.bin"
#define SECONDARY_SIZE 11418624
#define SECONDARY_HEADER_SIZE 592
#define MEMSWAP_LO 0xf88
#define MEMSWAP_HI 0xf8c
#define MEMSWAP_SIZE 0xf90
#define EXEC_STAGE 0x8000
#define CHIP_INFO 0x8008
#define BOOT_NONCE 0x8034
#define BOOT_MODE 0x803c
#define IMAGE_RESPONSE 0x8040
#define IMAGE_ADDRESS_LO 0x8044
#define IMAGE_ADDRESS_HI 0x8048
#define IMAGE_SIZE 0x804c
#define HOST_PLATFORM_ID 0x807c
#define BOOT_DOORBELL 0x9070

static bool launch;
module_param(launch, bool, 0400);
MODULE_PARM_DESC(launch, "Boot signed firmware and test control queue opens; pins resources until reboot");
static unsigned long long rom_nonce;
module_param(rom_nonce, ullong, 0400);
static bool nonce_provided;
module_param(nonce_provided, bool, 0400);

struct n1_image_table {
	__le64 address;
	__le32 length;
	__le32 reserved;
	__le64 end_address;
	__le64 end_length_reserved;
};
static_assert(sizeof(struct n1_image_table) == 32);

struct n1_alpha;
struct n1_boot {
	struct pci_dev *pdev;
	void __iomem *bar;
	void *image;
	dma_addr_t image_dma, table_dma;
	struct n1_image_table *table;
	void *secondary;
	dma_addr_t secondary_dma;
	u8 expected_secondary_header[SECONDARY_HEADER_SIZE];
	u64 old_dma_mask, old_coherent_mask;
	u16 old_command;
	atomic_t interrupts;
	void *context;
	dma_addr_t context_dma;
	void *messages, *cchi[2];
	dma_addr_t messages_dma, cchi_dma[2];
	u16 mtr_head, mcr_tail;
	struct n1_alpha *alpha;
};

static int ipc_result = -EINPROGRESS;
module_param(ipc_result, int, 0444);

static int probe_result = -ENODEV;
static int transfer_result = -EINPROGRESS;
module_param(transfer_result, int, 0444);

static irqreturn_t n1_irq(int irq, void *data)
{
	struct n1_boot *n1 = data;

	atomic_inc(&n1->interrupts);
	return IRQ_HANDLED;
}

static int count_group_device(struct device *dev, void *data)
{
	struct pci_dev *pdev;
	u16 command;

	/* Only the three N1 functions may share this DMA domain. */
	if (!dev_is_pci(dev))
		return -EPERM;
	pdev = to_pci_dev(dev);
	if (pci_domain_nr(pdev->bus) || pdev->bus->number != 1 ||
	    PCI_SLOT(pdev->devfn) || PCI_FUNC(pdev->devfn) > 2 ||
	    pdev->vendor != 0x106b ||
	    pdev->device != 0x1901 + PCI_FUNC(pdev->devfn) ||
	    pci_read_config_word(pdev, PCI_COMMAND, &command) ||
	    command & PCI_COMMAND_MASTER || pdev->msi_enabled || pdev->msix_enabled)
		return -EPERM;
	if (PCI_FUNC(pdev->devfn) && pdev->driver)
		return -EBUSY;
	(*(unsigned int *)data)++;
	return 0;
}

#include "n1-context.h"
#include "n1-management.h"
#include "n1-cchi-ping.h"
#include "n1-cchi-board.h"
#include "n1-state-trace.h"
#include "n1-alpha-handoff.h"

static int n1_release(struct n1_boot *n1)
{
	struct pci_dev *pdev = n1->pdev;
	u16 command;
	int ret = 0;

	/* Only used before any image doorbell or bus-master enable. */
	if (n1->alpha)
		release_alpha_unpublished(n1);
	release_management(n1);
	if (n1->context)
		dma_free_coherent(&pdev->dev, PAGE_SIZE, n1->context, n1->context_dma);
	if (n1->table)
		dma_free_coherent(&pdev->dev, PAGE_SIZE, n1->table, n1->table_dma);
	if (n1->image)
		dma_free_coherent(&pdev->dev, PAGE_ALIGN(FW_SIZE), n1->image, n1->image_dma);
	if (n1->secondary)
		dma_free_coherent(&pdev->dev, PAGE_ALIGN(SECONDARY_SIZE),
				  n1->secondary, n1->secondary_dma);
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
	static const u8 secondary_sha256[32] = {
		0x7b, 0x98, 0xe7, 0xd7, 0xf7, 0xfa, 0x79, 0xb1,
		0x7b, 0x52, 0x86, 0x1c, 0x94, 0x86, 0xba, 0x65,
		0xc1, 0xe1, 0x31, 0x85, 0x2b, 0x24, 0x17, 0x0a,
		0x51, 0x03, 0xe4, 0xd9, 0x05, 0x8a, 0x43, 0xf9,
	};
	struct iommu_domain *domain;
	struct iommu_group *group;
	const struct firmware *fw;
	const struct firmware *secondary = NULL;
	struct n1_boot *n1;
	u8 digest[32];
	u32 response = ~0U, stage = ~0U, before_response, before_stage, cfg;
	u64 nonce;
	u16 command;
	bool boot_accepted = false, header_preserved;
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
	if (!nonce_provided) {
		ret = -EINVAL;
		goto result;
	}
	/* The live bridge gives each function a separate DART domain. Check
	 * siblings independently, as well as every member of our own group. */
	for (cfg = 1; cfg <= 2; cfg++) {
		struct pci_dev *sibling = pci_get_slot(pdev->bus, PCI_DEVFN(0, cfg));
		u16 sibling_command;
		bool idle = sibling && sibling->vendor == 0x106b &&
			sibling->device == 0x1901 + cfg && !sibling->driver &&
			!pci_is_enabled(sibling) && !sibling->msi_enabled &&
			!sibling->msix_enabled &&
			!pci_read_config_word(sibling, PCI_COMMAND, &sibling_command) &&
			!(sibling_command & PCI_COMMAND_MASTER);
		pci_dev_put(sibling);
		if (!idle) {
			ret = -EBUSY;
			goto result;
		}
	}
	ret = -EPERM;
	domain = iommu_get_domain_for_dev(&pdev->dev);
	if (!domain || !iommu_is_dma_domain(domain))
		goto result;
	group = iommu_group_get(&pdev->dev);
	if (!group)
		goto result;
	ret = iommu_group_for_each_dev(group, &devices, count_group_device);
	iommu_group_put(group);
	if (ret || !devices || devices > 3) {
		ret = ret ? ret : -EPERM;
		goto result;
	}
	for (cfg = MEMSWAP_LO; cfg <= MEMSWAP_SIZE; cfg += 4) {
		u32 old;
		if (pci_read_config_dword(pdev, cfg, &old) || old) {
			ret = -EBUSY;
			goto result;
		}
	}
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
	ret = request_firmware_direct(&secondary, SECONDARY_NAME, &pdev->dev);
	if (ret)
		goto release_fw;
	if (secondary->size != SECONDARY_SIZE) {
		ret = -EINVAL;
		goto release_fw;
	}
	sha256(secondary->data, secondary->size, digest);
	if (memcmp(digest, secondary_sha256, sizeof(digest))) {
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
	ret = pci_request_region(pdev, 0, "n1-control-handoff");
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
	if (readl(n1->bar + EXEC_STAGE) != 1 ||
	    readl(n1->bar + CHIP_INFO) != 0x20260841 ||
	    readl(n1->bar + IMAGE_RESPONSE) != 0 ||
	    readl(n1->bar + IMAGE_SIZE) != 32)
		goto release;
	ret = dma_set_mask_and_coherent(&pdev->dev, DMA_BIT_MASK(40));
	if (ret)
		goto release;
	n1->image = dma_alloc_coherent(&pdev->dev, PAGE_ALIGN(FW_SIZE),
				      &n1->image_dma, GFP_KERNEL);
	n1->table = dma_alloc_coherent(&pdev->dev, PAGE_SIZE,
				      &n1->table_dma, GFP_KERNEL);
	n1->secondary = dma_alloc_coherent(&pdev->dev, PAGE_ALIGN(SECONDARY_SIZE),
				          &n1->secondary_dma, GFP_KERNEL);
	if (!n1->image || !n1->table || !n1->secondary) {
		ret = -ENOMEM;
		goto release;
	}
	if (!IS_ALIGNED(n1->image_dma, 4096) || !IS_ALIGNED(n1->table_dma, 4096) ||
	    !iommu_iova_to_phys(domain, n1->image_dma) ||
	    !iommu_iova_to_phys(domain, n1->image_dma + FW_SIZE - 1) ||
	    !iommu_iova_to_phys(domain, n1->table_dma) ||
	    !IS_ALIGNED(n1->secondary_dma, PAGE_SIZE) ||
	    !iommu_iova_to_phys(domain, n1->secondary_dma) ||
	    !iommu_iova_to_phys(domain, n1->secondary_dma + SECONDARY_SIZE - 1)) {
		ret = -EFAULT;
		goto release;
	}
	memcpy(n1->image, fw->data, fw->size);
	memcpy(n1->secondary, secondary->data, secondary->size);
	memcpy(n1->expected_secondary_header, secondary->data, SECONDARY_HEADER_SIZE);
	/* Live survey confirmed stage 1 retains the original session nonce. */
	nonce = readl(n1->bar + BOOT_NONCE);
	nonce |= (u64)readl(n1->bar + BOOT_NONCE + 4) << 32;
	if (nonce != rom_nonce) {
		ret = -ESTALE;
		goto release;
	}
	put_unaligned_le64(nonce, n1->image + 8);
	memset(n1->table, 0, PAGE_SIZE);
	n1->table->address = cpu_to_le64(n1->image_dma);
	n1->table->length = cpu_to_le32(FW_SIZE);
	ret = prepare_context(n1);
	if (ret)
		goto release;
	ret = prepare_management(n1);
	if (ret)
		goto release;
	ret = prepare_alpha(n1);
	if (ret)
		goto release;
	dev_info(&pdev->dev, "N1_STAGE2_PREPARED image=%u secondary=%u table=%zu IOMMU=DMA n1_functions=%u launch=%d\n",
		 FW_SIZE, SECONDARY_SIZE, sizeof(*n1->table), devices, launch);
	if (!launch) {
		ret = 0;
		goto release;
	}
	ret = pci_alloc_irq_vectors(pdev, 1, 1, PCI_IRQ_MSI);
	if (ret < 0)
		goto release;
	irq = pci_irq_vector(pdev, 0);
	ret = request_irq(irq, n1_irq, 0, "n1-control-handoff", n1);
	if (ret) {
		pci_free_irq_vectors(pdev);
		goto release;
	}
	release_firmware(fw);
	release_firmware(secondary);
	pci_set_drvdata(pdev, n1);
	/* Once armed, never free memory that the peripheral might still use. */
	__module_get(THIS_MODULE);
	/* Advertise only a fully populated allocation while bus mastering is off. */
	dma_wmb();
	if (pci_write_config_dword(pdev, MEMSWAP_LO, lower_32_bits(n1->secondary_dma)) ||
	    pci_write_config_dword(pdev, MEMSWAP_HI, upper_32_bits(n1->secondary_dma)) ||
	    pci_write_config_dword(pdev, MEMSWAP_SIZE, SECONDARY_SIZE) ||
	    pci_read_config_dword(pdev, MEMSWAP_LO, &cfg) ||
	    cfg != lower_32_bits(n1->secondary_dma) ||
	    pci_read_config_dword(pdev, MEMSWAP_HI, &cfg) ||
	    cfg != upper_32_bits(n1->secondary_dma) ||
	    pci_read_config_dword(pdev, MEMSWAP_SIZE, &cfg) || cfg != SECONDARY_SIZE) {
		transfer_result = -EIO;
		dev_err(&pdev->dev, "secondary config readback failed; DMA remains off, buffers retained\n");
		goto bound;
	}
	pci_set_master(pdev);
	if (pci_read_config_word(pdev, PCI_COMMAND, &command) ||
	    !(command & PCI_COMMAND_MASTER)) {
		pci_clear_master(pdev);
		transfer_result = -EIO;
		goto bound;
	}
	dma_wmb();
	writel(lower_32_bits(n1->table_dma), n1->bar + IMAGE_ADDRESS_LO);
	writel(upper_32_bits(n1->table_dma), n1->bar + IMAGE_ADDRESS_HI);
	writel(sizeof(*n1->table), n1->bar + IMAGE_SIZE);
	writel(1, n1->bar + BOOT_DOORBELL);
	readl(n1->bar + EXEC_STAGE); /* flush posted writes */
	dev_info(&pdev->dev, "N1_STAGE2_SENT; resources pinned until reboot\n");
	before_response = before_stage = ~0U;
	for (elapsed = 0; elapsed <= 15000; elapsed += 10) {
		response = readl(n1->bar + IMAGE_RESPONSE);
		stage = readl(n1->bar + EXEC_STAGE);
		if (response == 1)
			boot_accepted = true;
		if (response != before_response || stage != before_stage)
			dev_info(&pdev->dev, "N1_STAGE2_STATE ms=%u response=%#x stage=%#x irq=%d\n",
				 elapsed, response, stage, atomic_read(&n1->interrupts));
		before_response = response;
		before_stage = stage;
		if (stage != 1 || response >= 2)
			break;
		msleep(10);
	}
	dma_rmb();
	header_preserved = !memcmp(n1->secondary, n1->expected_secondary_header,
				   SECONDARY_HEADER_SIZE);
	if (stage == 2 && response < 2 && header_preserved) {
		/* This allocation is the running firmware's working memory.
		 * Keep its DMA domain, IRQ and module alive through the IPC stage. */
		transfer_result = 0;
		dev_info(&pdev->dev, "N1_STAGE2_RUNNING accepted_seen=%d response=%#x stage=%#x irq=%d secondary_header_preserved=1; DMA retained\n",
			 boot_accepted, response, stage, atomic_read(&n1->interrupts));
		alpha_result = handoff_alpha(n1);
		dev_info(&pdev->dev, "N1_ALPHA_HANDOFF result=%d phase=%u\n", alpha_result, alpha_phase);
		trace_n1_states(n1, "before-ipc");
		ipc_result = start_context(n1);
		dev_info(&pdev->dev, "N1_CONTROL_IPC result=%d stage=%u ipc=%u irq=%d\n",
			ipc_result, readl(n1->bar + EXEC_STAGE), readl(n1->bar + 0x8050),
			atomic_read(&n1->interrupts));
		if (!ipc_result) {
			management_result = open_control_queues(n1);
			dev_info(&pdev->dev, "N1_MANAGEMENT result=%d stage=%u ipc=%u irq=%d; DMA retained\n",
				management_result, readl(n1->bar + EXEC_STAGE),
				readl(n1->bar + 0x8050), atomic_read(&n1->interrupts));
			if (!management_result) {
				ping_result = cchi_ping(n1);
				dev_info(&pdev->dev, "N1_CCHI_PING result=%d stage=%u irq=%d\n",
					ping_result, readl(n1->bar + EXEC_STAGE), atomic_read(&n1->interrupts));
				if (!ping_result) {
					board_result = cchi_board(n1);
					dev_info(&pdev->dev, "N1_CCHI_BOARD result=%d stage=%u\n", board_result, readl(n1->bar + EXEC_STAGE));
					observe_alpha(n1);
					observe_n1_states(n1);
				}
			}
		}
		goto bound;
	}
	/* An unsuccessful transfer is stopped; all mappings remain pinned. */
	pci_clear_master(pdev);
	if (pci_read_config_word(pdev, PCI_COMMAND, &command) ||
	    command & PCI_COMMAND_MASTER || !pci_wait_for_pending_transaction(pdev)) {
		transfer_result = -EIO;
		dev_err(&pdev->dev, "DMA quiescence unconfirmed; all resources retained\n");
		goto bound;
	}
	dev_info(&pdev->dev, "N1_STAGE2_RESULT accepted_seen=%d response=%#x stage=%#x irq=%d; DMA disabled, buffers retained\n",
		 boot_accepted, response, stage, atomic_read(&n1->interrupts));
	dma_rmb();
	header_preserved = !memcmp(n1->secondary, n1->expected_secondary_header,
				   SECONDARY_HEADER_SIZE);
	dev_info(&pdev->dev, "secondary_header_preserved=%d\n",
		 header_preserved);
	transfer_result = stage == 2 && response < 2 && header_preserved ? 0 : -EIO;
bound:
	probe_result = 0; /* transfer result is reported separately from driver binding */
	return 0;
release:
	cleanup_ret = n1_release(n1);
	if (cleanup_ret)
		ret = cleanup_ret;
release_fw:
	release_firmware(secondary);
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
	{ PCI_DEVICE(0x106b, 0x1901) }, { }
};
/* No MODULE_DEVICE_TABLE: never auto-load this experiment. */
static struct pci_driver n1_driver = {
	.name = "n1-control-handoff",
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
MODULE_DESCRIPTION("Private J714s N1 control queue bring-up experiment");
