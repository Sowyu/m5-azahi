// SPDX-License-Identifier: GPL-2.0
/*
 * One-shot J714s N1 boot-ROM survey. BAR reads only; the PCI memory-decode
 * bit is enabled temporarily and the original command word is restored.
 * Never enables bus mastering, allocates DMA memory, or rings a doorbell.
 * Register offsets: macOS 26.6.2 AirshipDK t2026-CentauriControl.plist.
 * Bank 0 is passed directly to IOPCIDevice::MemoryRead32 by pci_transport.
 */
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pci.h>

static int __init n1_rom_survey_init(void)
{
	static const struct { u32 off; const char *name; } regs[] = {
		{ 0x8000, "exec_stage" },
		{ 0x8004, "domain_mode" },
		{ 0x8008, "chip_info" },
		{ 0x803c, "boot_mode" },
		{ 0x8040, "image_response" },
		{ 0x8044, "image_address_lo" },
		{ 0x8048, "image_address_hi" },
		{ 0x804c, "image_size" },
		{ 0x807c, "host_platform_id" },
	};
	struct pci_dev *pdev;
	void __iomem *bar;
	u16 command, restored_command;
	unsigned int i;
	int ret;

	if (!of_machine_is_compatible("apple,j714s"))
		return -ENODEV;
	pdev = pci_get_domain_bus_and_slot(0, 1, PCI_DEVFN(0, 0));
	if (!pdev)
		return -ENODEV;
	device_lock(&pdev->dev);
	ret = -ENODEV;
	if (pdev->vendor != 0x106b || pdev->device != 0x1900 ||
	    pdev->current_state != PCI_D0 ||
	    !(pci_resource_flags(pdev, 0) & IORESOURCE_MEM) ||
	    pci_resource_len(pdev, 0) != 0x10000)
		goto unlock;
	ret = -EBUSY;
	if (pdev->driver || pci_is_enabled(pdev))
		goto unlock;
	ret = pci_read_config_word(pdev, PCI_COMMAND, &command);
	if (ret) {
		ret = -EIO;
		goto unlock;
	}
	if (command & PCI_COMMAND_MASTER) {
		ret = -EBUSY;
		goto unlock;
	}
	ret = pci_request_region(pdev, 0, "n1-rom-survey");
	if (ret)
		goto unlock;
	ret = pci_enable_device_mem(pdev);
	if (ret)
		goto release;
	bar = pci_iomap(pdev, 0, 0x10000);
	if (!bar) {
		ret = -ENOMEM;
		goto disable;
	}
	/* Reject a non-ROM/all-ones response before reading any other fields. */
	if (readl(bar + 0x8000) != 0) {
		pr_err("n1-rom-survey: device is not in ROM stage\n");
		ret = -EIO;
		goto unmap;
	}
	for (i = 0; i < ARRAY_SIZE(regs); i++)
		pr_info("n1-rom-survey: %s +%04x = %08x\n",
			regs[i].name, regs[i].off, readl(bar + regs[i].off));
	ret = 0;
unmap:
	pci_iounmap(pdev, bar);
disable:
	pci_disable_device(pdev);
	/* pci_disable_device() alone does not restore memory decoding. */
	if (pci_write_config_word(pdev, PCI_COMMAND, command) ||
	    pci_read_config_word(pdev, PCI_COMMAND, &restored_command) ||
	    restored_command != command) {
		pr_err("n1-rom-survey: could not restore PCI command\n");
		ret = -EIO;
	}
release:
	pci_release_region(pdev, 0);
unlock:
	device_unlock(&pdev->dev);
	pci_dev_put(pdev);
	pr_info("n1-rom-survey: result=%d (no firmware/DMA requested)\n", ret);
	return ret;
}

static void __exit n1_rom_survey_exit(void) { }
module_init(n1_rom_survey_init);
module_exit(n1_rom_survey_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("J714s N1 boot-ROM register survey, no DMA");
