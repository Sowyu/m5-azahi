// SPDX-License-Identifier: GPL-2.0
/*
 * J714s (T6050) apcie0 port-0 (Apple N1 Wi-Fi) runtime bring-up, stage 1/2.
 * Linux port of standalone-loader azahi_pcie.c with the LIVE-ADT reg layout
 * (38 entries; port0 cfg/glue/intr2axi = reg 14/16/17). Private experiment.
 *
 *   stage=1  Enable ONLY the GP-branch PMGR domains (parents first, virtual
 *            ones skipped, never storage), verify SSD domains unchanged, then
 *            READ-ONLY dump of Common / PHY / port0 registers.
 *   stage=2  stage 1, then the loader's controller + port0 register sequence
 *            up to PORT_STATUS RUN. Bounded polls; stops at the first failure,
 *            no teardown. Leaves endpoint PERST#, refclk and LTSSM to Linux.
 *
 * Safety: refuses unless the machine is apple,j714s and ANS, APCIE_ST0,
 * APCIE_SYS_ST0 and FAB6_SOC are ACTIVE (the SSD path is up and not ours).
 * Controller MMIO is touched only after all five GP domains read ACTIVE.
 * PHY tunables are applied to port0 glue and PhyPhy only; unused ports 1-3
 * are never accessed. The shared Common block is never written.
 */
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/module.h>
#include <linux/of.h>

static int stage;
module_param(stage, int, 0444);
MODULE_PARM_DESC(stage, "1 = power GP domains + read-only dump, 2 = bring port0 to RUN");
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

static const struct { const char *name; u32 off; } gp_domains[] = {
	{ "APCIE_GP", 0x118 }, { "APCIE_SYS_GP", 0x148 }, { "APCIE_PHY_SW", 0x1b0 },
	{ "APHY_GP_AUS5_A", 0x258 }, { "APHY_GP_AUS5", 0x280 },
};

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

#define TAG "azahi-apcie: "

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

/* m1n1 pmgr_set_mode(ACTIVE): clear AUTO/WAS_* and target, set target, poll. */
static int gp_power_on(void)
{
	size_t i;

	for (i = 0; i < ARRAY_SIZE(gp_domains); i++) {
		void __iomem *reg = pmgr + gp_domains[i].off;
		u32 before = readl(reg), v;
		int ret;

		if (PS_ACTUAL(before) == PS_ACTIVE && !(before & PS_AUTO_ENABLE) &&
		    (before & PS_TARGET) == PS_ACTIVE) {
			pr_info(TAG "%-15s already ACTIVE %#x\n", gp_domains[i].name, before);
			continue;
		}
		v = before & ~(PS_AUTO_ENABLE | PS_WAS_CLKGATED | PS_WAS_PWRGATED | PS_TARGET);
		writel(v | PS_ACTIVE, reg);
		ret = readl_poll_timeout(reg, v, PS_ACTUAL(v) == PS_ACTIVE, 10, 100000);
		pr_info(TAG "%-15s %#x -> %#x%s\n", gp_domains[i].name, before, readl(reg),
			ret ? " TIMEOUT" : "");
		if (ret)
			return ret;
	}
	return 0;
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

/*
 * GP PHY part of _apcieGPInit. The shared Common block is NOT written: on
 * T6050 iBoot has already initialised it for the storage ports (stage 1 read
 * LANECFG=3, 0x54=0x140, RC_STAT bit0=1), and m1n1's "LANECFG=0" write is an
 * unexplained "/ * ??? * /" from older SoCs. Require iBoot's state instead.
 */
static int gp_controller_init(void)
{
	u32 stat = readl(common + COMMON_RC_STAT), r54 = readl(common + COMMON_54);

	if (!(stat & BIT(0)) || r54 != 0x140) {
		pr_err(TAG "Common not initialised by iBoot (RC_STAT=%#x 54=%#x); refusing\n",
		       stat, r54);
		return -EBUSY;
	}
	/* apcie-phy-tunables (live ADT), port0 glue + PhyPhy entries only. */
	rmw(phy + PHYPHY_OFF, 0x4000000, 0);
	rmw(phy + GLUE0_OFF, 0x10000000, 0);

	POLL(phy + PHYCMN_OFF, PHYCMN_CLK_100M, PHYCMN_CLK_100M, "GP PHY 100MHz refclk");
	rmw(phy + PHYPHY_OFF + 4, 0, 0x10);
	POLL(phy + PHYPHY_OFF + 8, BIT(4), BIT(4), "Gen5 PHY step1");
	rmw(phy + PHYPHY_OFF + 4, 0x20, 0);
	POLL(phy + PHYPHY_OFF + 8, BIT(0), BIT(0), "Gen5 PHY step2");
	rmw(phy + PHYCMN_OFF, PHYCMN_CLK_MODE, PHYCMN_CLK_MODE);
	rmw(phy + PHYPHY_OFF, 0, BIT(27));
	return 0;
}

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

static int run(void)
{
	int ret;

	pmgr = ioremap_np(PMGR1_BASE, PMGR1_SIZE);
	if (!pmgr)
		return -ENOMEM;
	if (!ssd_active("before"))
		return -EBUSY;
	ret = gp_power_on();
	if (ret)
		return ret;
	if (!ssd_active("after GP power"))
		return -EIO;

	common = ioremap_np(COMMON_BASE, 0x4000);
	phy = ioremap_np(PHY_BASE, PHY_MAP);
	cfg = ioremap_np(CFG0_BASE, 0x8000);
	i2a = ioremap_np(I2A0_BASE, 0x4000);
	if (!common || !phy || !cfg || !i2a)
		return -ENOMEM;
	dump("stage1");
	if (stage < 2)
		return 0;

	if (readl(cfg + PORT_STATUS) & PORT_STATUS_RUN) {
		pr_info(TAG "port0 already RUN; nothing to do\n");
		return 0;
	}
	ret = gp_controller_init();
	if (ret)
		return ret;
	dump("after GP controller init");
	ret = port0_bringup();
	dump(ret ? "port0 FAILED" : "port0 RUN");
	if (!ret)
		ret = ssd_active("after bring-up") ? 0 : -EIO;
	return ret;
}

static int __init apcie_init(void)
{
	if (stage != 1 && stage != 2)
		return -EINVAL;
	if (!of_machine_is_compatible("apple,j714s"))
		return -ENODEV;
	result = run();
	pr_info(TAG "stage %d result %d\n", stage, result);
	unmap_all();
	return 0;	/* stay loaded so 'result' can be read; rmmod is harmless */
}

static void __exit apcie_exit(void) { unmap_all(); }
module_init(apcie_init);
module_exit(apcie_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("J714s apcie0 port0 runtime bring-up (private experiment)");
