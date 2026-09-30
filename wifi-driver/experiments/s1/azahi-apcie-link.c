// SPDX-License-Identifier: GPL-2.0
/*
 * J714s apcie0 port-0 stage 3: release N1 PERST#, start LTSSM, poll link-up,
 * and (only if the link is up) read the endpoint IDs through ECAM.
 * Prerequisites: azahi-apcie.ko stage=2 reached PORT_STATUS RUN this boot, and
 * N1 power (SMC gP13 = gpiochip0 line 19) was switched on >=100 ms before.
 * Mirrors upstream pcie-apple apple_pcie_setup_link()/setup_port() ordering
 * for the t602x register layout. Private experiment, 2026-09-29.
 */
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/module.h>
#include <linux/of.h>

static bool ecam = true;
module_param(ecam, bool, 0444);
static int result = -EINPROGRESS;
module_param(result, int, 0444);

#define TAG "azahi-apcie-link: "
#define PMGR1_BASE	0x280900000ULL
#define GPIO_PS		0x280600250ULL
#define GPIO0_BASE	0x29c000000ULL
#define PERST_PIN	80
#define CFG0_BASE	0x410028000ULL
#define GLUE0_BASE	0x417010000ULL
#define ECAM_BASE	0x1cb0000000ULL

#define PORT_LTSSMCTL	0x080
#define PORT_LINKSTS	0x208
#define PORT_APPCLK	0x800
#define PORT_APPCLK_CGDIS BIT(8)
#define PORT_STATUS	0x804
#define PORT_PERST	0x82c
#define GLUE_REFCLKCGEN	(BIT(30) | BIT(31))

static void __iomem *pmgr, *gpio, *cfg, *glue;

static bool ssd_active(void)
{
	static const u32 offs[] = { 0x140, 0x128, 0x150, 0x138 };
	size_t i;

	for (i = 0; i < ARRAY_SIZE(offs); i++)
		if (((readl(pmgr + offs[i]) >> 4) & 0xf) != 0xf)
			return false;
	return true;
}

static void ecam_probe(void)
{
	void __iomem *rp, *ep;
	int fn;

	rp = ioremap_np(ECAM_BASE, 0x1000);
	if (!rp)
		return;
	pr_info(TAG "root port 00:00.0 id=%#010x class=%#010x busnr=%#010x\n",
		readl(rp + 0x0), readl(rp + 0x8), readl(rp + 0x18));
	/* primary 0, secondary 1, subordinate 1 so type-1 accesses reach bus 1 */
	writel((readl(rp + 0x18) & 0xff000000) | 0x00010100, rp + 0x18);
	pr_info(TAG "root port busnr now %#010x\n", readl(rp + 0x18));
	for (fn = 0; fn < 3; fn++) {
		ep = ioremap_np(ECAM_BASE + (1 << 20) + (fn << 12), 0x1000);
		if (!ep)
			break;
		pr_info(TAG "01:00.%d id=%#010x class=%#010x hdr=%#010x\n", fn,
			readl(ep + 0x0), readl(ep + 0x8), readl(ep + 0xc));
		iounmap(ep);
	}
	iounmap(rp);
}

static int run(void)
{
	u32 v, pin, lnk;
	int ret, i;

	pmgr = ioremap_np(PMGR1_BASE, 0x4000);
	gpio = ioremap_np(GPIO0_BASE, 0x4000);
	cfg = ioremap_np(CFG0_BASE, 0x8000);
	glue = ioremap_np(GLUE0_BASE, 0x4000);
	if (!pmgr || !gpio || !cfg || !glue)
		return -ENOMEM;
	if (!ssd_active())
		return -EBUSY;
	{
		void __iomem *ps = ioremap_np(GPIO_PS, 4);

		v = ps ? readl(ps) : 0;
		if (ps)
			iounmap(ps);
		if (((v >> 4) & 0xf) != 0xf)
			return -EHOSTDOWN;
	}
	v = readl(cfg + PORT_STATUS);
	pin = readl(gpio + 4 * PERST_PIN);
	lnk = readl(cfg + PORT_LINKSTS);
	pr_info(TAG "before: STATUS=%#x PERST(0x82c)=%#x APPCLK=%#x glue=%#x pin80=%#x LINKSTS=%#x\n",
		v, readl(cfg + PORT_PERST), readl(cfg + PORT_APPCLK), readl(glue), pin, lnk);
	if (!(v & BIT(0)))
		return -EAGAIN;			/* run azahi-apcie stage=2 first */
	if (((pin >> 1) & 7) != 1)
		return -EINVAL;			/* PERST# pin not a GPIO output */

	if (!(lnk & BIT(0))) {
		msleep(100);			/* Tpvperl margin after userspace power-on */
		writel(readl(cfg + PORT_PERST) | BIT(0), cfg + PORT_PERST);
		writel(readl(gpio + 4 * PERST_PIN) | BIT(0), gpio + 4 * PERST_PIN);
		pr_info(TAG "PERST# released: pin80=%#x\n", readl(gpio + 4 * PERST_PIN));
		msleep(100);
		ret = readl_poll_timeout(cfg + PORT_STATUS, v, v & BIT(0), 100, 250000);
		if (ret)
			return ret;
		writel(readl(glue) | GLUE_REFCLKCGEN, glue);
		writel(readl(cfg + PORT_APPCLK) & ~PORT_APPCLK_CGDIS, cfg + PORT_APPCLK);
		writel(BIT(0), cfg + PORT_LTSSMCTL);
		for (i = 0; i < 100; i++) {
			lnk = readl(cfg + PORT_LINKSTS);
			if (lnk & BIT(0))
				break;
			if (i % 10 == 0)
				pr_info(TAG "t=%dms LINKSTS=%#x\n", i * 10, lnk);
			msleep(10);
		}
		pr_info(TAG "after %dms: LINKSTS=%#x STATUS=%#x\n", i * 10, lnk,
			readl(cfg + PORT_STATUS));
	}
	if (!(lnk & BIT(0)))
		return -ETIMEDOUT;
	pr_info(TAG "LINK UP\n");
	if (ecam)
		ecam_probe();
	return 0;
}

static int __init link_init(void)
{
	if (!of_machine_is_compatible("apple,j714s"))
		return -ENODEV;
	result = run();
	pr_info(TAG "result %d\n", result);
	if (pmgr) iounmap(pmgr);
	if (gpio) iounmap(gpio);
	if (cfg) iounmap(cfg);
	if (glue) iounmap(glue);
	return 0;
}
static void __exit link_exit(void) { }
module_init(link_init);
module_exit(link_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("J714s apcie0 port0 link-up test (private experiment)");
