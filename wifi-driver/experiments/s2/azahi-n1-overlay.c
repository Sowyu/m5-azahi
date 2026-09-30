// SPDX-License-Identifier: GPL-2.0
/*
 * Apply the J714s apcie0 port-0 (Apple N1) runtime overlay: dart-apcie0 +
 * pcie@1cb0000000 (compatible azahi,t6050-pcie, bound by the private
 * pcie-apple-t6050 fork). Refuses unless the AIC is phandle 2, the nodes do
 * not exist yet, and port 0's link is already up (so the fork never needs
 * the unavailable PERST# GPIO). Once applied the module pins itself: the
 * overlay is never removed. Private experiment, 2026-09-29.
 */
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>

#include "overlay-blob.h"

#define AIC_PATH	"/soc/interrupt-controller@280400000"
#define AIC_PHANDLE	2
#define PORT0_LINKSTS	0x410028208ULL

static int __init n1_overlay_init(void)
{
	static const char *const new_nodes[] = { "/soc/iommu@410000000", "/soc/pcie@1cb0000000" };
	struct device_node *np;
	void __iomem *lnk;
	int ret, i, id = 0;
	u32 v;

	if (!of_machine_is_compatible("apple,j714s"))
		return -ENODEV;
	np = of_find_node_by_path(AIC_PATH);
	if (!np || np->phandle != AIC_PHANDLE || !of_device_is_compatible(np, "apple,t6050-aic3")) {
		pr_err("azahi-n1-overlay: AIC check failed\n");
		of_node_put(np);
		return -EINVAL;
	}
	of_node_put(np);
	for (i = 0; i < ARRAY_SIZE(new_nodes); i++) {
		np = of_find_node_by_path(new_nodes[i]);
		if (np) {
			of_node_put(np);
			pr_err("azahi-n1-overlay: %s already exists\n", new_nodes[i]);
			return -EEXIST;
		}
	}
	lnk = ioremap_np(PORT0_LINKSTS, 4);
	if (!lnk)
		return -ENOMEM;
	v = readl(lnk);
	iounmap(lnk);
	if (!(v & BIT(0))) {
		pr_err("azahi-n1-overlay: port0 link down (LINKSTS %#x); run the bring-up first\n", v);
		return -ENOLINK;
	}
	ret = of_overlay_fdt_apply(n1_overlay, n1_overlay_size, &id, NULL);
	if (ret) {
		pr_err("azahi-n1-overlay: apply failed: %d\n", ret);
		if (id)
			of_overlay_remove(&id);
		return ret;
	}
	__module_get(THIS_MODULE);
	pr_info("azahi-n1-overlay: applied, changeset %d (LINKSTS %#x)\n", id, v);
	return 0;
}

static void __exit n1_overlay_exit(void) { }
module_init(n1_overlay_init);
module_exit(n1_overlay_exit);
MODULE_DESCRIPTION("J714s apcie0 port0 N1 runtime overlay loader (azahi private)");
MODULE_LICENSE("GPL");
