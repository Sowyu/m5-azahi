// SPDX-License-Identifier: GPL-2.0
/* Stage-0 N1 Wi-Fi survey for J714s: READ-ONLY PMGR power-state registers.
 * Addresses decoded from the live ADT (ps-groups + devices, m1n1 pmgr logic)
 * and cross-checked against proven ones (APCIE_SYS_ST0, ATC2_USB*).
 * No writes, no controller/PHY/GPIO block access. Same ioremap_np read class
 * as azahi_hpm_once and the USB overlay preflight. 2026-09-29.
 */
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>

struct domain { const char *name; phys_addr_t ps; };
static const struct domain domains[] = {
	{ "FAB0_PIOGW",     0x2806001d8 }, { "SBR",           0x2806001f8 },
	{ "GPIO",           0x280600250 }, { "APCIE_GP",      0x280900118 },
	{ "APCIE_ST0",      0x280900128 }, { "APCIE_ST1",     0x280900130 },
	{ "FAB6_SOC",       0x280900138 }, { "ANS",           0x280900140 },
	{ "APCIE_SYS_GP",   0x280900148 }, { "APCIE_SYS_ST0", 0x280900150 },
	{ "APCIE_SYS_ST1",  0x280900158 }, { "APCIE_PHY_SW",  0x2809001b0 },
	{ "APHY_ST0_AUS5_A",0x280900240 }, { "APHY_ST1_AUS5_A",0x280900248 },
	{ "APHY_GP_AUS5_A", 0x280900258 }, { "APHY_ST0_AUS5", 0x280900268 },
	{ "APHY_ST1_AUS5",  0x280900270 }, { "APHY_GP_AUS5",  0x280900280 },
};

static int __init survey_init(void)
{
	size_t i;

	if (!of_machine_is_compatible("apple,j714s"))
		return -ENODEV;
	for (i = 0; i < ARRAY_SIZE(domains); i++) {
		void __iomem *reg = ioremap_np(domains[i].ps, 4);
		u32 v;

		if (!reg) {
			pr_err("azahi-pcie-survey: %s map failed\n", domains[i].name);
			continue;
		}
		v = readl(reg);
		iounmap(reg);
		pr_info("azahi-pcie-survey: %-16s %#llx = %#010x target=%x actual=%x%s%s%s\n",
			domains[i].name, (unsigned long long)domains[i].ps, v, v & 0xf, (v >> 4) & 0xf,
			v & BIT(31) ? " RESET" : "", v & BIT(28) ? " AUTO" : "",
			v & BIT(10) ? " DEVDIS" : "");
	}
	return 0;
}
static void __exit survey_exit(void) { }
module_init(survey_init);
module_exit(survey_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only J714s PMGR survey for apcie0/N1 bring-up");
