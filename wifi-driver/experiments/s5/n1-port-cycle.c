// SPDX-License-Identifier: GPL-2.0
/* Private port-0-only cycle after the N1 endpoint was cleanly removed.
 * The port0_bringup routine is copied unchanged from the tested s1 source.
 * No Common, parent-power, PLL or storage-port writes. arm=0 is read-only.
 */
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pci.h>
#include <linux/pm_runtime.h>

static bool arm;
module_param(arm, bool, 0400);
static bool hold_reset;
module_param(hold_reset, bool, 0400);
static int result = -EINPROGRESS;
module_param(result, int, 0444);

#define PMGR1_BASE	0x280900000ULL
#define PMGR1_SIZE	0x4000
#define PS_ANS		0x140
#define PS_APCIE_ST0	0x128
#define PS_APCIE_SYS_ST0 0x150
#define PS_FAB6_SOC	0x138
#define PS_TARGET	GENMASK(3, 0)
#define PS_ACTUAL(v)	(((v) >> 4) & 0xf)
#define PS_WAS_PWRGATED	BIT(8)
#define PS_WAS_CLKGATED	BIT(9)
#define PS_AUTO_ENABLE	BIT(28)
#define PS_ACTIVE	0xf

/* Live ADT /arm-io/apcie0 reg[] (CPU addresses). */
#define COMMON_BASE	0x414000000ULL	/* reg 1, 0x4000 */
#define PHY_BASE	0x417000000ULL	/* reg 2, 0x800000; we map 0x24000 */
#define PHY_MAP		0x24000
#define PHYPHY_OFF	0x20000		/* reg 3 = 0x417020000 */
#define PHYCMN_OFF	0x4000
#define GLUE0_OFF	0x10000		/* reg 16 = 0x417010000 */
#define CFG0_BASE	0x410028000ULL	/* reg 14, 0x8000 */
#define I2A0_BASE	0x410024000ULL	/* reg 17, 0x4000 */

#define COMMON_LANECFG	0x0004
#define COMMON_RC_CTL	0x0050
#define COMMON_54	0x0054
#define COMMON_RC_STAT	0x0058
#define PHYCMN_CLK_100M	BIT(31)
#define PHYCMN_CLK_MODE	BIT(0)

#define PORT_LANESTAT	0x00a8
#define PORT_LINKSTS	0x0208
#define PORT_APPCLK	0x0800
#define PORT_APPCLK_EN	BIT(0)
#define PORT_STATUS	0x0804
#define PORT_STATUS_RUN	BIT(0)
#define PORT_RESET	0x082c
#define PORT_RESET_DIS	BIT(0)
#define PORT_RET_PIPE_EN BIT(16)
#define PORT_RID2SID	0x3000
#define PORT_MSIMAP	0x3800
#define PORT_COUNTERS	0x4020

#define GLUE_CLK0REQ	BIT(0)
#define GLUE_CLK1REQ	BIT(1)
#define GLUE_CLK0ACK	BIT(2)
#define GLUE_CLK1ACK	BIT(3)
#define GLUE_RESET	BIT(4)
#define GLUE_REFCLKEN	(BIT(9) | BIT(10))

#define POLL_US		250000

static void __iomem *pmgr, *common, *phy, *cfg, *i2a;

#define TAG "n1-port-cycle: "

static void unmap_all(void)
{
	void __iomem **m[] = { &pmgr, &common, &phy, &cfg, &i2a };
	size_t i;

	for (i = 0; i < ARRAY_SIZE(m); i++) {
		if (*m[i])
			iounmap(*m[i]);
		*m[i] = NULL;
	}
}

static bool ssd_active(const char *when)
{
	u32 ans = readl(pmgr + PS_ANS), st0 = readl(pmgr + PS_APCIE_ST0);
	u32 sst0 = readl(pmgr + PS_APCIE_SYS_ST0), fab = readl(pmgr + PS_FAB6_SOC);

	pr_info(TAG "%s: ANS=%#x ST0=%#x SYS_ST0=%#x FAB6=%#x\n", when, ans, st0, sst0, fab);
	return PS_ACTUAL(ans) == PS_ACTIVE && PS_ACTUAL(st0) == PS_ACTIVE &&
	       PS_ACTUAL(sst0) == PS_ACTIVE && PS_ACTUAL(fab) == PS_ACTIVE;
}

static void dump(const char *when)
{
	pr_info(TAG "%s: Common LANECFG=%#x RC_CTL=%#x 54=%#x RC_STAT=%#x\n", when,
		readl(common + COMMON_LANECFG), readl(common + COMMON_RC_CTL),
		readl(common + COMMON_54), readl(common + COMMON_RC_STAT));
	pr_info(TAG "%s: PhyCommon CLK=%#x PhyPhy +0=%#x +4=%#x +8=%#x glue0=%#x\n", when,
		readl(phy + PHYCMN_OFF), readl(phy + PHYPHY_OFF), readl(phy + PHYPHY_OFF + 4),
		readl(phy + PHYPHY_OFF + 8), readl(phy + GLUE0_OFF));
	pr_info(TAG "%s: port0 88=%#x 100=%#x 13c=%#x 140=%#x 144=%#x APPCLK=%#x STATUS=%#x 808=%#x RESET=%#x LANESTAT=%#x LINKSTS=%#x 8a8=%#x 8ac=%#x i2a80=%#x\n",
		when, readl(cfg + 0x88), readl(cfg + 0x100), readl(cfg + 0x13c),
		readl(cfg + 0x140), readl(cfg + 0x144), readl(cfg + PORT_APPCLK),
		readl(cfg + PORT_STATUS), readl(cfg + 0x808), readl(cfg + PORT_RESET),
		readl(cfg + PORT_LANESTAT), readl(cfg + PORT_LINKSTS), readl(cfg + 0x8a8),
		readl(cfg + 0x8ac), readl(i2a + 0x80));
}

static void rmw(void __iomem *reg, u32 clear, u32 set)
{
	writel((readl(reg) & ~clear) | set, reg);
}

#define POLL(reg, mask, want, what) do {					\
	u32 _v;									\
	if (readl_poll_timeout((reg), _v, (_v & (mask)) == (want), 10, POLL_US)) { \
		pr_err(TAG "%s timeout (%#x)\n", what, readl(reg));		\
		return -ETIMEDOUT;						\
	}									\
} while (0)

/* _resetPortHardware + T6050 enablePortHardware, as in azahi_pcie.c port0_bringup(). */
static int port0_bringup(void)
{
	int i;

	writel(0x110, cfg + 0x088);
	writel(0xffffffff, cfg + 0x100);
	writel(0xffffffff, cfg + 0x148);
	writel(0xffffffff, cfg + 0x210);
	writel(0x0, cfg + 0x080);
	writel(0x0, cfg + 0x084);
	writel(0xfffffff0, cfg + 0x104);
	writel(0x100, cfg + 0x124);
	writel(0x0, cfg + 0x16c);
	writel(0x0, cfg + 0x13c);
	writel(0x00100100, cfg + 0x800);
	writel(0x001001ff, cfg + 0x808);
	writel(PORT_RET_PIPE_EN, cfg + PORT_RESET);
	for (i = 0; i < 64; i++)
		writel(0, cfg + PORT_RID2SID + 4 * i);
	for (i = 0; i < 256; i++)
		writel(0, cfg + PORT_MSIMAP + 4 * i);
	writel(0x03020000, cfg + 0x130);
	writel(0x10, cfg + 0x140);
	writel(0x00253770, cfg + 0x144);
	writel(0x0, cfg + 0x21c);
	writel(0x0, cfg + 0x834);
	writel(0x0, cfg + 0x83c);

	if (!(readl(cfg + PORT_RESET) & PORT_RET_PIPE_EN)) {
		pr_err(TAG "RET_PIPE_RESET_EN did not stick\n");
		return -EIO;
	}
	/* apcie-config-tunables (live ADT). */
	rmw(cfg + 0x140, 0x1, 0x1);
	rmw(cfg + 0x144, 0xffffff, 0x253770);
	rmw(cfg + 0x8a8, 0x1, 0x1);
	rmw(cfg + 0x8ac, 0x1, 0x1);

	rmw(cfg + PORT_APPCLK, 0, PORT_APPCLK_EN);

	rmw(phy + GLUE0_OFF, GLUE_CLK0REQ | GLUE_CLK1REQ, 0);
	rmw(phy + GLUE0_OFF, 0, GLUE_CLK0REQ);
	POLL(phy + GLUE0_OFF, GLUE_CLK0ACK, GLUE_CLK0ACK, "port0 PHY CLK0 ack");
	rmw(phy + GLUE0_OFF, 0, GLUE_CLK1REQ);
	POLL(phy + GLUE0_OFF, GLUE_CLK1ACK, GLUE_CLK1ACK, "port0 PHY CLK1 ack");
	rmw(phy + GLUE0_OFF, GLUE_RESET, 0);
	udelay(1);
	rmw(phy + GLUE0_OFF, 0, GLUE_REFCLKEN);

	POLL(cfg + PORT_LANESTAT, 0x1, 0x0, "lane pipe reset clear");
	rmw(cfg + PORT_RESET, 0, PORT_RESET_DIS);
	POLL(cfg + PORT_LANESTAT, 0x1, 0x1, "lane pipe reset assert");
	rmw(cfg + PORT_RESET, PORT_RET_PIPE_EN, 0);
	POLL(cfg + PORT_STATUS, PORT_STATUS_RUN, PORT_STATUS_RUN, "port0 STATUS RUN");

	writel(0x3, cfg + PORT_COUNTERS);
	writel(0x1, i2a + 0x80);
	return 0;
}

#define GPIO_BASE 0x29c000000ULL
#define GPIO_PS 0x280600250ULL
static unsigned int phase;
module_param(phase, uint, 0444);

static int port0_disable(void)
{
	/* AppleEmbeddedPCIEPort::disableGated + Gen4Port::disablePortHardware. */
	POLL(cfg + PORT_STATUS, BIT(2), BIT(2), "port link reset");
	POLL(cfg + 0x820, 0x00ff01ff, 0, "outstanding transactions");
	rmw(cfg + 0x13c, 0, BIT(8));
	POLL(cfg + PORT_LANESTAT, 1, 1, "lane pipe released before disable");
	rmw(cfg + PORT_RESET, 0, BIT(24));
	POLL(cfg + PORT_LANESTAT, BIT(16), BIT(16), "lane UCTRL idle ack");
	rmw(cfg + PORT_RESET, 0, BIT(16));
	udelay(1);
	rmw(cfg + PORT_RESET, BIT(0), 0);
	udelay(1);
	rmw(cfg + PORT_RESET, BIT(24), 0);
	rmw(cfg + 0x13c, BIT(8), 0);
	rmw(phy + GLUE0_OFF, BIT(31), 0);
	rmw(phy + GLUE0_OFF, BIT(10), 0);
	rmw(phy + GLUE0_OFF, BIT(9), 0);
	rmw(phy + GLUE0_OFF, 0, GLUE_RESET);
	rmw(phy + GLUE0_OFF, GLUE_CLK0REQ, 0);
	rmw(phy + GLUE0_OFF, GLUE_CLK1REQ, 0);
	writel(~0U, cfg + 0x100);
	rmw(cfg + PORT_APPCLK, PORT_APPCLK_EN, 0);
	POLL(cfg + PORT_STATUS, PORT_STATUS_RUN, 0, "port stopped");
	return 0;
}

static int run(void)
{
	static const u32 gp[] = { 0x118, 0x148, 0x1b0, 0x258, 0x280 };
	struct pci_dev *rp;
	void __iomem *ps = NULL, *gpio = NULL;
	u32 irqmask, msicfg, msilo, msihi, msimap[32], pin, v, id;
	u16 link2;
	int ret = -ENODEV, attach_ret, i;
	bool detached = false, restored = false;

	if (!of_machine_is_compatible("apple,j714s"))
		return -ENODEV;
	rp = pci_get_domain_bus_and_slot(0, 0, PCI_DEVFN(0, 0));
	if (!rp)
		return -ENODEV;
	/* PCI core runtime-suspends an empty bridge after the endpoint is removed.
	 * Resume it through the core and hold a reference across the entire cycle. */
	ret = pm_runtime_resume_and_get(&rp->dev);
	if (ret < 0) {
		pci_dev_put(rp);
		return ret;
	}
	pci_lock_rescan_remove();
	ret = -ENODEV;
	if (rp->vendor != 0x106b || rp->device != 0x100c ||
	    !rp->subordinate || !list_empty(&rp->subordinate->devices) ||
	    !rp->driver || strcmp(rp->driver->name, "pcieport") ||
	    rp->current_state != PCI_D0)
		goto out;
	pmgr = ioremap_np(PMGR1_BASE, PMGR1_SIZE);
	ps = ioremap_np(GPIO_PS, 4);
	ret = -ENOMEM;
	if (!pmgr || !ps)
		goto out;
	ret = -EHOSTDOWN;
	if (!ssd_active("preflight") || PS_ACTUAL(readl(ps)) != PS_ACTIVE)
		goto out;
	for (i = 0; i < ARRAY_SIZE(gp); i++)
		if (PS_ACTUAL(readl(pmgr + gp[i])) != PS_ACTIVE)
			goto out;
	common = ioremap_np(COMMON_BASE, 0x4000);
	phy = ioremap_np(PHY_BASE, PHY_MAP);
	cfg = ioremap_np(CFG0_BASE, 0x8000);
	i2a = ioremap_np(I2A0_BASE, 0x4000);
	gpio = ioremap_np(GPIO_BASE, 0x4000);
	ret = -ENOMEM;
	if (!common || !phy || !cfg || !i2a || !gpio)
		goto out;
	ret = -EBUSY;
	pin = readl(gpio + 80 * 4);
	if ((pin & 14) != 2 || !(readl(cfg + PORT_STATUS) & 1) ||
	    ((readl(cfg + PORT_LINKSTS) & 1) &&
	     !((readl(cfg + PORT_LINKSTS) & BIT(6)) && !(pin & 1) &&
	       !readl(cfg + 0x80))) || readl(common + COMMON_54) != 0x140 ||
	    !(readl(common + COMMON_RC_STAT) & 1))
		goto out;
	for (i = 0; i < 64; i++)
		if (readl(cfg + PORT_RID2SID + 4 * i) & BIT(31))
			goto out;
	irqmask = readl(cfg + 0x104);
	msicfg = readl(cfg + 0x124);
	msilo = readl(cfg + 0x16c);
	msihi = readl(cfg + 0x170);
	for (i = 0; i < 32; i++)
		msimap[i] = readl(cfg + PORT_MSIMAP + 4 * i);
	dump("preflight");
	pr_info(TAG "OUTS=%#x empty_bus=1 arm=%d\n", readl(cfg + 0x820), arm);
	ret = 0;
	phase = 1;
	if (!arm)
		goto out;
	ret = pci_save_state(rp);
	if (ret)
		goto out;
	/* Stop the root port's AER/PME services and release its MSI first. */
	device_release_driver(&rp->dev);
	detached = true;
	if (rp->driver || pci_is_enabled(rp) || rp->msi_enabled || rp->msix_enabled) {
		ret = -EBUSY;
		goto out;
	}
	phase = 2;
	writel(~0U, cfg + 0x104);
	writel(pin & ~1U, gpio + 80 * 4);
	readl(gpio + 80 * 4);
	writel(0, cfg + 0x80);
	rmw(phy + GLUE0_OFF, BIT(30) | BIT(31), 0);
	ret = port0_disable();
	dump("after disable");
	if (ret)
		goto out;
	phase = 3;
	msleep(100);
	ret = port0_bringup();
	dump("after bringup");
	if (ret)
		goto out;
	phase = 4;
	/* Restore host routing before config access or any new driver binding. */
	writel(msilo, cfg + 0x16c);
	writel(msihi, cfg + 0x170);
	for (i = 0; i < 32; i++)
		writel(msimap[i], cfg + PORT_MSIMAP + 4 * i);
	writel(msicfg, cfg + 0x124);
	writel(~0U, cfg + 0x100);
	writel(irqmask, cfg + 0x104);
	ret = pci_read_config_dword(rp, PCI_VENDOR_ID, &id);
	if (ret || id != 0x100c106b) {
		ret = -EIO;
		goto out;
	}
	pci_restore_state(rp);
	ret = pci_set_power_state(rp, PCI_D0);
	if (ret)
		goto out;
	restored = true;
	pcie_capability_read_word(rp, PCI_EXP_LNKCTL2, &link2);
	pcie_capability_write_word(rp, PCI_EXP_LNKCTL2, (link2 & ~PCI_EXP_LNKCTL2_TLS) | 1);
	pcie_capability_clear_word(rp, PCI_EXP_LNKCTL, PCI_EXP_LNKCTL_ASPMC);
	if (hold_reset) {
		pr_info(TAG "root restored; endpoint PERST held, LTSSM stopped\n");
		ret = 0;
		goto out;
	}
	/* ADT t-refclk-to-perst=100 us; Apple initializes the buffer, then
	 * explicitly delays before deasserting endpoint PERST. Keep margin. */
	usleep_range(1000, 2000);
	writel(pin | 1U, gpio + 80 * 4);
	readl(gpio + 80 * 4);
	msleep(100);
	rmw(phy + GLUE0_OFF, 0, BIT(30) | BIT(31));
	rmw(cfg + PORT_APPCLK, BIT(8), 0);
	writel(1, cfg + 0x80);
	ret = readl_poll_timeout(cfg + PORT_LINKSTS, v, v & 1, 1000, 3000000);
	pr_info(TAG "link after cycle=%#x result=%d\n", v, ret);
	if (!ret) {
		phase = 5;
		msleep(100);
		pci_bus_read_config_dword(rp->subordinate, 0, PCI_VENDOR_ID, &id);
		pr_info(TAG "new endpoint id=%#x\n", id);
		pci_rescan_bus(rp->subordinate);
	}
out:
	/* No MMIO reset writes occurred if the detach postcondition failed. */
	if (detached && phase == 1 && !rp->driver) {
		pci_restore_state(rp);
		if (!pci_set_power_state(rp, PCI_D0))
			restored = true;
	}
	if (restored) {
		attach_ret = device_attach(&rp->dev);
		pr_info(TAG "root services reattach=%d\n", attach_ret);
		if (attach_ret < 1 && !ret)
			ret = attach_ret ? attach_ret : -ENODEV;
	} else if (detached) {
		pr_err(TAG "root services detached; port recovery required before rescan\n");
	}
	if (pmgr && !ssd_active("exit"))
		ret = -EIO;
	if (gpio) iounmap(gpio);
	if (ps) iounmap(ps);
	unmap_all();
	pci_unlock_rescan_remove();
	pm_runtime_mark_last_busy(&rp->dev);
	pm_runtime_put_autosuspend(&rp->dev);
	pci_dev_put(rp);
	pr_info(TAG "phase=%u result=%d\n", phase, ret);
	return ret;
}

static int __init cycle_init(void)
{
	result = run();
	return phase >= 2 ? 0 : result;
}
static void __exit cycle_exit(void) { }
module_init(cycle_init);
module_exit(cycle_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("J714s isolated N1 root-port cycle with PCI state restoration");
