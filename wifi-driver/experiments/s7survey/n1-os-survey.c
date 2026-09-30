// SPDX-License-Identifier: GPL-2.0
/* Read-only survey of the live N1 control OS. No PCI enable/disable or writes. */
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pci.h>

static int __init survey_init(void)
{
	static const u32 regs[] = { 0x8000, 0x8040, 0x8050, 0x8054, 0x8058 };
	struct pci_dev *pdev;
	void __iomem *bar;
	u16 command;
	int ret = -ENODEV, i;
	if (!of_machine_is_compatible("apple,j714s"))
		return ret;
	pdev = pci_get_domain_bus_and_slot(0, 1, 0);
	if (!pdev)
		return ret;
	device_lock(&pdev->dev);
	if (pdev->vendor != 0x106b || pdev->device != 0x1901 ||
	    !pdev->driver || strcmp(pdev->driver->name, "n1-control-boot") ||
	    pdev->current_state != PCI_D0 || !pci_is_enabled(pdev) ||
	    pci_resource_len(pdev, 0) != 0x10000 ||
	    pci_read_config_word(pdev, PCI_COMMAND, &command) ||
	    (command & (PCI_COMMAND_MEMORY | PCI_COMMAND_MASTER)) != 6)
		goto out;
	bar = pci_iomap(pdev, 0, 0x10000);
	if (!bar) {
		ret = -ENOMEM;
		goto out;
	}
	for (i = 0; i < ARRAY_SIZE(regs); i++)
		pr_info("n1-os-survey: BAR0+%04x=%08x\n", regs[i], readl(bar + regs[i]));
	pci_iounmap(pdev, bar);
	ret = 0;
out:
	device_unlock(&pdev->dev);
	pci_dev_put(pdev);
	return ret;
}
static void __exit survey_exit(void) { }
module_init(survey_init);
module_exit(survey_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only live N1 control OS status");
