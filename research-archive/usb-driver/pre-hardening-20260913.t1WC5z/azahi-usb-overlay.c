// SPDX-License-Identifier: GPL-2.0
/*
 * azahi-usb-overlay: apply the J714s right-socket USB2 host device-tree
 * overlay at run time, after a read-only preflight of the PMGR / PHY / DWC3
 * state the loader left behind.
 *
 * Nothing persistent: the installed DTB and boot image are untouched, and
 * a reboot returns to the unchanged system. Once an overlay is applied the
 * module pins itself (the devices it created cannot be safely torn down).
 *
 * Private one-machine bring-up code. Not for upstream submission.
 */

#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/string.h>

#include "overlay-blobs.h"

static bool dry_run;
module_param(dry_run, bool, 0444);
MODULE_PARM_DESC(dry_run, "Only report PMGR/PHY/DWC3 state; do not apply any overlay");

static char *variant = "minimal";
module_param(variant, charp, 0444);
MODULE_PARM_DESC(variant, "Overlay variant: minimal (default, loader-prepared power) or pmgr");

static bool force;
module_param(force, bool, 0444);
MODULE_PARM_DESC(force, "Apply the minimal overlay even if the ATC2 USB domains are not active");

#define AIC_PATH		"/soc/interrupt-controller@280400000"
#define AIC_PHANDLE		2
#define USB_NODE_PATH		"/soc/usb@382280000"
#define PMGR0_NODE_PATH		"/soc/power-management@280600000"
#define PMGR2_NODE_PATH		"/soc/power-management@288300000"

/* ADT /arm-io/pmgr device table, Mac17,9 (see README.md) */
#define PMGR0_BASE		0x280600000ULL	/* ps group 0 = pmgr reg[0] */
#define PMGR2_BASE		0x288300000ULL	/* ps group 2 = pmgr reg[9] */
#define PS_FAB5_SOC		0x1f0
#define PS_ATC2_COMMON		0x238
#define PS_ATC2_USB_AON		0x178
#define PS_ATC2_USB		0x180
#define PS_ATC2_PHYMXWRAP	0x188
#define PS_TARGET(v)		((v) & 0xf)
#define PS_ACTUAL(v)		(((v) >> 4) & 0xf)
#define PS_ACTIVE		0xf

/* ADT instance 2 blocks (right socket) */
#define USB2PHY_BASE		0x382a90000ULL	/* atc-phy2 reg[0] */
#define USB2EVT_BASE		0x382800000ULL	/* atc-phy2 reg[1] */
#define PIPEHANDLER_BASE	0x382a84000ULL	/* usb-drd2 reg[3] */
#define DWC3_BASE		0x382280000ULL	/* usb-drd2 reg[0] */
#define DWC3_GSNPSID		0xc120
#define MMIO_BLOCK_SIZE		0x4000

static int overlay_id;
static bool applied;

static u32 read_block(u64 base, u32 off, bool *ok)
{
	void __iomem *p;
	u32 v;

	p = ioremap_np(base, MMIO_BLOCK_SIZE);
	if (!p) {
		pr_err("azahi-usb-overlay: cannot map %#llx\n", base);
		*ok = false;
		return 0;
	}
	v = readl(p + off);
	iounmap(p);
	return v;
}

struct ps_desc {
	const char *name;
	u64 base;
	u32 off;
	bool required;
};

static const struct ps_desc ps_descs[] = {
	{ "FAB5_SOC",       PMGR0_BASE, PS_FAB5_SOC,       true },
	{ "ATC2_COMMON",    PMGR0_BASE, PS_ATC2_COMMON,    true },
	{ "ATC2_USB_AON",   PMGR2_BASE, PS_ATC2_USB_AON,   true },
	{ "ATC2_USB",       PMGR2_BASE, PS_ATC2_USB,       true },
	{ "ATC2_PHYMXWRAP", PMGR2_BASE, PS_ATC2_PHYMXWRAP, false },
};

/* PMGR power-state registers are always-on and safe to read cold (project rule). */
static bool preflight_pmgr(void)
{
	bool ok = true, all_active = true;
	int i;

	for (i = 0; i < ARRAY_SIZE(ps_descs); i++) {
		u32 v = read_block(ps_descs[i].base, ps_descs[i].off, &ok);

		if (!ok)
			return false;
		pr_info("azahi-usb-overlay: PMGR %-14s @%#llx+%#x = %#010x target %#x actual %#x%s\n",
			ps_descs[i].name, ps_descs[i].base, ps_descs[i].off, v, PS_TARGET(v),
			PS_ACTUAL(v), PS_ACTUAL(v) == PS_ACTIVE ? " ACTIVE" : "");
		if (ps_descs[i].required && PS_ACTUAL(v) != PS_ACTIVE)
			all_active = false;
	}
	return all_active;
}

/* Only called after ATC2_USB was seen ACTIVE: reading a gated block would SError. */
static void preflight_blocks(void)
{
	bool ok = true;
	u32 usbctl = read_block(USB2PHY_BASE, 0x00, &ok);
	u32 ctl = read_block(USB2PHY_BASE, 0x04, &ok);
	u32 sig = read_block(USB2PHY_BASE, 0x08, &ok);
	u32 unk18 = read_block(USB2PHY_BASE, 0x18, &ok);
	u32 misctune = read_block(USB2PHY_BASE, 0x1c, &ok);
	u32 evt_ctl = read_block(USB2EVT_BASE, 0x00, &ok);
	u32 evt_status = read_block(USB2EVT_BASE, 0x20, &ok);
	u32 mux = read_block(PIPEHANDLER_BASE, 0x0c, &ok);
	u32 aon_gen = read_block(PIPEHANDLER_BASE, 0x1c, &ok);
	u32 nonsel = read_block(PIPEHANDLER_BASE, 0x20, &ok);
	u32 snpsid = read_block(DWC3_BASE + 0xc000, DWC3_GSNPSID - 0xc000, &ok);

	if (!ok)
		return;
	pr_info("azahi-usb-overlay: USB2PHY usbctl %#x ctl %#x sig %#x unk18 %#x misctune %#x\n",
		usbctl, ctl, sig, unk18, misctune);
	pr_info("azahi-usb-overlay: USB2EVT ctl %#x status %#x\n", evt_ctl, evt_status);
	pr_info("azahi-usb-overlay: PIPEHANDLER mux_ctrl %#x aon_gen %#x nonselected_override %#x (loader: 0x22 / 0x1 / 0x9332)\n",
		mux, aon_gen, nonsel);
	pr_info("azahi-usb-overlay: DWC3 GSNPSID %#x (expect 0x5533xxxx)\n", snpsid);
}

static int check_live_tree(void)
{
	struct device_node *np;

	if (!of_root || !of_device_is_compatible(of_root, "apple,j714s")) {
		pr_err("azahi-usb-overlay: not an apple,j714s device tree\n");
		return -ENODEV;
	}
	np = of_find_node_by_path(AIC_PATH);
	if (!np) {
		pr_err("azahi-usb-overlay: %s not found\n", AIC_PATH);
		return -ENODEV;
	}
	if (np->phandle != AIC_PHANDLE || !of_device_is_compatible(np, "apple,t6050-aic3")) {
		pr_err("azahi-usb-overlay: AIC phandle %u / compatible mismatch (overlay expects %u)\n",
		       np->phandle, AIC_PHANDLE);
		of_node_put(np);
		return -EINVAL;
	}
	of_node_put(np);
	np = of_find_node_by_path(USB_NODE_PATH);
	if (np) {
		of_node_put(np);
		pr_err("azahi-usb-overlay: %s already exists\n", USB_NODE_PATH);
		return -EEXIST;
	}
	return 0;
}

/* Children of an overlay-added simple-mfd are not populated by the OF notifier. */
static int populate_pmgr(const char *path)
{
	struct device_node *np = of_find_node_by_path(path);
	struct platform_device *pdev;
	int ret;

	if (!np) {
		pr_err("azahi-usb-overlay: %s missing after overlay\n", path);
		return -ENODEV;
	}
	pdev = of_find_device_by_node(np);
	if (!pdev) {
		pr_err("azahi-usb-overlay: no platform device for %s\n", path);
		of_node_put(np);
		return -ENODEV;
	}
	ret = of_platform_populate(np, NULL, NULL, &pdev->dev);
	pr_info("azahi-usb-overlay: populated %s children: %d\n", path, ret);
	platform_device_put(pdev);
	of_node_put(np);
	return ret;
}

static int __init azahi_usb_overlay_init(void)
{
	const u8 *blob;
	u32 blob_size;
	bool use_pmgr;
	bool active;
	int ret;

	if (!strcmp(variant, "minimal"))
		use_pmgr = false;
	else if (!strcmp(variant, "pmgr"))
		use_pmgr = true;
	else {
		pr_err("azahi-usb-overlay: unknown variant '%s'\n", variant);
		return -EINVAL;
	}

	ret = check_live_tree();
	if (ret)
		return ret;

	active = preflight_pmgr();
	pr_info("azahi-usb-overlay: required ATC2 USB domains %s\n",
		active ? "all ACTIVE (loader-prepared power confirmed)" : "NOT all active");
	if (active)
		preflight_blocks();

	if (dry_run) {
		pr_info("azahi-usb-overlay: dry run, no overlay applied (variant would be %s)\n", variant);
		return 0;
	}
	if (!use_pmgr && !active && !force) {
		pr_err("azahi-usb-overlay: refusing minimal overlay with inactive domains; use variant=pmgr or force=1\n");
		return -ENODEV;
	}

	if (use_pmgr) {
		blob = overlay_pmgr;
		blob_size = overlay_pmgr_size;
	} else {
		blob = overlay_minimal;
		blob_size = overlay_minimal_size;
	}

	ret = of_overlay_fdt_apply(blob, blob_size, &overlay_id, NULL);
	if (ret) {
		pr_err("azahi-usb-overlay: of_overlay_fdt_apply(%s) failed: %d\n", variant, ret);
		if (overlay_id)
			of_overlay_remove(&overlay_id);
		return ret;
	}
	applied = true;
	/* Devices now exist under /soc; never let the overlay be pulled from under them. */
	__module_get(THIS_MODULE);
	pr_info("azahi-usb-overlay: overlay '%s' applied, changeset id %d\n", variant, overlay_id);

	if (use_pmgr) {
		populate_pmgr(PMGR0_NODE_PATH);
		populate_pmgr(PMGR2_NODE_PATH);
	}
	return 0;
}

static void __exit azahi_usb_overlay_exit(void)
{
	/* Only reachable when nothing was applied (dry run or failure). */
	pr_info("azahi-usb-overlay: unloaded (applied=%d)\n", applied);
}

module_init(azahi_usb_overlay_init);
module_exit(azahi_usb_overlay_exit);

MODULE_DESCRIPTION("Runtime USB2 host overlay loader for the J714s right socket (azahi private)");
MODULE_LICENSE("GPL");
