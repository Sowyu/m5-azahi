/* SPDX-License-Identifier: MIT */
/*
 * Private J714s (T6050 / M5 Pro) apcie0 Wi-Fi PCIe bring-up.
 *
 * The stock m1n1 pcie.c has no apcie,t6050 support, so kboot skips pcie_init()
 * on this SoC. This file adds a default-off, opt-in bring-up of controller 0,
 * port 0 only (the Apple N1 "Centauri" port, /arm-io/apcie0/pci-bridge0). It
 * follows the proven m1n1 t8122 sequence with the deltas confirmed by static
 * RE of the macOS AppleT6050PCIe kext (build 26A428), reading every tunable
 * from the LIVE ADT (the restore-image ADT has none of them; iBoot inserts
 * them at boot). Linux's pcie-apple-t6050 driver then drives PERST#, refclk
 * and LTSSM and enumerates 106b:1901/1902/1903 behind dart-apcie0.
 *
 * Gate (kboot passes the kernel cmdline):
 *   no "azahi.pcie=" token   -> do nothing (default; current boot behaviour).
 *   azahi.pcie=probe         -> read-only: dump controller/PMGR state, no writes.
 *   azahi.pcie=bringup       -> the guarded register sequence below.
 *
 * SSD SAFETY. The apcie0 clock/power-gate list mixes the Wi-Fi GP branch with
 * the storage branch (ANS, APCIE_ST0/ST1, APCIE_SYS_ST0/ST1) that the NVMe
 * root needs. This code:
 *   - refuses to do anything unless ANS + APCIE_ST0 + APCIE_SYS_ST0 are already
 *     ACTIVE (read-only), i.e. iBoot's NVMe path is up and we are not the ones
 *     responsible for the SSD's power;
 *   - only ever ENABLES the GP-branch domains (indices 1,2,9,10,11 of the ADT
 *     clock-gates list), never the storage indices, and never disables anything.
 * Enabling is idempotent (macOS re-enables these on every boot too).
 *
 * Every poll here has a bounded timeout: on any failure the routine logs and
 * returns, and the boot continues to Linux (which then reports the port state
 * via the fork's link-timeout diagnostic). It cannot hang the attended boot.
 *
 * Not for upstream. Compile-checked against upstream m1n1; runs in the private
 * standalone-loader m1n1 tree alongside azahi_standalone.c.
 */
#include "adt.h"
#include "libfdt/libfdt.h"
#include "pmgr.h"
#include "string.h"
#include "tunables.h"
#include "utils.h"

#include "azahi_pcie.h"

#define APCIE_PATH   "/arm-io/apcie0"
#define BRIDGE0_PATH "/arm-io/apcie0/pci-bridge0"

/* Overlay nodes (pcie-driver/dts), disabled until bring-up completes. */
#define FDT_DART_PATH "/soc/iommu@410000000"
#define FDT_PCIE_PATH "/soc/pcie@1cb0000000"

/* ADT reg indices for apcie0 (16 shared entries, then 6 per port). */
#define IDX_ECAM    0
#define IDX_COMMON  1  /* Linux "rc" */
#define IDX_PHY     2  /* GP PHY; PhyCommon = PHY + 0x4000 */
#define IDX_PHYPHY  3
#define IDX_PORT0   16 /* Linux port0 "config" */
#define IDX_I2A0    19 /* port0 intr2axi */
#define IDX_GLUE0   18 /* port0 PHY glue; Linux port0 "phy" */

/* Common (rc) registers. */
#define COMMON_LANECFG   0x0004
#define COMMON_RC_CTL    0x0050
#define COMMON_RC_STAT   0x0058
#define COMMON_54        0x0054

/* GP PHY. */
#define PHYCMN_OFF       0x4000  /* PhyCommon within the PHY block */
#define PHYCMN_CLK       0x0000
#define PHYCMN_CLK_100M  BIT(31)
#define PHYCMN_CLK_MODE  1

/* Port config (CFG). */
#define PORT_LINKSTS     0x0208
#define PORT_LINKSTS_UP  BIT(0)
#define PORT_LINKSTS_BUSY BIT(2)
#define PORT_LANESTAT    0x00a8  /* low16 lane pipe reset, hi16 uctrl idle ack */
#define PORT_APPCLK      0x0800
#define PORT_APPCLK_EN   BIT(0)
#define PORT_STATUS      0x0804
#define PORT_STATUS_RUN  BIT(0)
#define PORT_T6050_RESET 0x082c
#define PORT_RESET_DIS   BIT(0)   /* root-port PERST release */
#define PORT_RET_PIPE_EN BIT(16)  /* RET_PIPE_RESET_EN, must be set for AUS5 */
#define PORT_RID2SID     0x3000
#define PORT_MSIMAP      0x3800
#define PORT_COUNTERS    0x4020

/* Port PHY glue (GLUE). Same layout as m1n1 APCIE_PHY_CTRL / Linux PHY_LANE_CFG. */
#define GLUE_CTRL        0x0000
#define GLUE_CLK0REQ     BIT(0)
#define GLUE_CLK1REQ     BIT(1)
#define GLUE_CLK0ACK     BIT(2)
#define GLUE_CLK1ACK     BIT(3)
#define GLUE_RESET_T8132 BIT(4)   /* T6050 uses the t8132/t8122 reset bit, not BIT(14) */
#define GLUE_REFCLKEN    (BIT(9) | BIT(10))

/* PMGR pwrstate register offsets within pmgr group 1 (base = pmgr reg[1]). */
#define PS_APCIE_GP       0x118
#define PS_APCIE_ST0      0x128
#define PS_APCIE_SYS_GP   0x148
#define PS_ANS            0x140
#define PS_APCIE_SYS_ST0  0x150
#define PS_ACTUAL(v)      (((v) >> 4) & 0xf)
#define PS_ACTIVE         0xf

/* GP-branch indices into the apcie0 clock-gates list (never the storage ones). */
static const u32 gp_gate_index[] = { 1, 2, 9, 10, 11 };

/* ~250ms at 1us granularity: generous but bounded, so a stuck poll cannot hang. */
#define POLL_US 250000

static u64 apcie_reg(int *path, int idx)
{
    u64 addr, size;
    if (adt_get_reg(adt, path, "reg", idx, &addr, &size) < 0)
        return 0;
    (void)size;
    return addr;
}

/* Read the PMGR pwrstate register for a storage domain, without touching it. */
static u32 pmgr_group1_ps(u32 offset)
{
    int pmgr_path[8];
    u64 base;
    if (adt_path_offset_trace(adt, "/arm-io/pmgr", pmgr_path) < 0)
        return 0;
    if (adt_get_reg(adt, pmgr_path, "reg", 1, &base, NULL) < 0)
        return 0;
    return read32(base + offset);
}

static bool ssd_domains_active(void)
{
    u32 ans = pmgr_group1_ps(PS_ANS);
    u32 st0 = pmgr_group1_ps(PS_APCIE_ST0);
    u32 sst0 = pmgr_group1_ps(PS_APCIE_SYS_ST0);
    printf("azahi-pcie: SSD domains ANS=%#x APCIE_ST0=%#x APCIE_SYS_ST0=%#x\n", ans, st0, sst0);
    return PS_ACTUAL(ans) == PS_ACTIVE && PS_ACTUAL(st0) == PS_ACTIVE &&
           PS_ACTUAL(sst0) == PS_ACTIVE;
}

static void dump_state(int *apcie_path)
{
    u64 common = apcie_reg(apcie_path, IDX_COMMON);
    u64 phy = apcie_reg(apcie_path, IDX_PHY);
    u64 port = apcie_reg(apcie_path, IDX_PORT0);
    u32 gp = pmgr_group1_ps(PS_APCIE_GP), sys_gp = pmgr_group1_ps(PS_APCIE_SYS_GP);
    printf("azahi-pcie: GP=%#x SYS_GP=%#x\n", gp, sys_gp);
    /*
     * Reading a power-gated Apple block can SError, and bootargs are baked into
     * the image, so a crash here costs a Recovery reinstall. Only touch the
     * controller once both GP domains report ACTIVE. Other GP-branch gates may
     * still be off; this narrows the risk, it does not remove it.
     */
    if (PS_ACTUAL(gp) != PS_ACTIVE || PS_ACTUAL(sys_gp) != PS_ACTIVE) {
        printf("azahi-pcie: GP domains not active; skipping controller register reads\n");
        return;
    }
    if (common)
        printf("azahi-pcie: Common RC_CTL=%#x RC_STAT=%#x\n",
               read32(common + COMMON_RC_CTL), read32(common + COMMON_RC_STAT));
    if (phy)
        printf("azahi-pcie: PhyCommon CLK=%#x\n", read32(phy + PHYCMN_OFF + PHYCMN_CLK));
    if (port)
        printf("azahi-pcie: port0 APPCLK=%#x STATUS=%#x RESET(0x82c)=%#x LINKSTS=%#x\n",
               read32(port + PORT_APPCLK), read32(port + PORT_STATUS),
               read32(port + PORT_T6050_RESET), read32(port + PORT_LINKSTS));
}

/* Shared GP controller init. Assumes iBoot already did the deeper common/AXI
 * init (it boots NVMe off the ST fabric). Mirrors _apcieGPInit + _enableRootComplex. */
static int gp_controller_init(int *apcie_path)
{
    u64 common = apcie_reg(apcie_path, IDX_COMMON);
    u64 phy = apcie_reg(apcie_path, IDX_PHY);
    u64 phyphy = apcie_reg(apcie_path, IDX_PHYPHY);
    if (!common || !phy || !phyphy)
        return -1;

    /* apcie-common-tunables -> Common (live ADT); harmless if the prop is absent. */
    if (adt_getprop(adt, adt_path_offset(adt, APCIE_PATH), "apcie-common-tunables", NULL))
        tunables_apply_local(APCIE_PATH, "apcie-common-tunables", IDX_COMMON);
    write32(common + COMMON_LANECFG, 0);   /* lane-cfg 0 */

    if (adt_getprop(adt, adt_path_offset(adt, APCIE_PATH), "apcie-phy-tunables", NULL))
        tunables_apply_local(APCIE_PATH, "apcie-phy-tunables", IDX_PHY);

    if (poll32(phy + PHYCMN_OFF + PHYCMN_CLK, PHYCMN_CLK_100M, PHYCMN_CLK_100M, POLL_US)) {
        printf("azahi-pcie: GP PHY 100MHz refclk not ready\n");
        return -1;
    }

    /* Gen5 PHY: PhyPhy+4 |= 0x10; wait +8 bit4; PhyPhy+4 &= ~0x20; wait +8 bit0. */
    set32(phyphy + 0x4, 0x10);
    if (poll32(phyphy + 0x8, BIT(4), BIT(4), POLL_US)) {
        printf("azahi-pcie: Gen5 PHY step1 timeout\n");
        return -1;
    }
    clear32(phyphy + 0x4, 0x20);
    if (poll32(phyphy + 0x8, BIT(0), BIT(0), POLL_US)) {
        printf("azahi-pcie: Gen5 PHY step2 timeout\n");
        return -1;
    }
    mask32(phy + PHYCMN_OFF + PHYCMN_CLK, PHYCMN_CLK_MODE, PHYCMN_CLK_MODE);
    set32(phyphy + 0x0, BIT(27));

    write32(common + COMMON_54, 0x140);
    set32(common + COMMON_RC_CTL, BIT(0));   /* GTB -> PTM */
    if (poll32(common + COMMON_RC_STAT, BIT(0), BIT(0), POLL_US)) {
        printf("azahi-pcie: GTB not initialized (RC_STAT)\n");
        return -1;
    }
    return 0;
}

/* Port 0 register bring-up, up to STATUS RUN. Leaves DBI, RID2SID, endpoint
 * PERST# and LTSSM start to Linux (pcie-apple-t6050), matching the M4 split. */
static int port0_bringup(int *apcie_path)
{
    u64 cfg = apcie_reg(apcie_path, IDX_PORT0);
    u64 glue = apcie_reg(apcie_path, IDX_GLUE0);
    u64 i2a = apcie_reg(apcie_path, IDX_I2A0);
    if (!cfg || !glue || !i2a)
        return -1;

    /* _resetPortHardware (RE-confirmed T6050 values; deltas vs m1n1 t8122 noted). */
    write32(cfg + 0x088, 0x110);
    write32(cfg + 0x100, 0xffffffff);
    write32(cfg + 0x148, 0xffffffff);
    write32(cfg + 0x210, 0xffffffff);
    write32(cfg + 0x080, 0x0);
    write32(cfg + 0x084, 0x0);
    write32(cfg + 0x104, 0xfffffff0);
    write32(cfg + 0x124, 0x100);
    write32(cfg + 0x16c, 0x0);
    write32(cfg + 0x13c, 0x0);                 /* delta: m1n1 t8122 writes 0x10 */
    write32(cfg + 0x800, 0x00100100);
    write32(cfg + 0x808, 0x001001ff);          /* delta: m1n1 0x1000ff */
    write32(cfg + PORT_T6050_RESET, PORT_RET_PIPE_EN); /* 0x10000; delta: m1n1 0 */
    for (int i = 0; i < 64; i++)                /* RID2SID; Linux reprograms per device */
        write32(cfg + PORT_RID2SID + 4 * i, 0);
    for (int i = 0; i < 256; i++)              /* MSIMAP; Linux reprograms in setup_irq */
        write32(cfg + PORT_MSIMAP + 4 * i, 0);
    write32(cfg + 0x130, 0x03020000);          /* delta: m1n1 APCIE 0x3000000 */
    write32(cfg + 0x140, 0x10);
    write32(cfg + 0x144, 0x00253770);
    write32(cfg + 0x21c, 0x0);
    write32(cfg + 0x834, 0x0);
    write32(cfg + 0x83c, 0x0);

    /* AUS5: RET_PIPE_RESET_EN must already be set (Apple panics otherwise). */
    if (!(read32(cfg + PORT_T6050_RESET) & PORT_RET_PIPE_EN)) {
        printf("azahi-pcie: RET_PIPE_RESET_EN not set; aborting\n");
        return -1;
    }

    /* apcie-config-tunables -> port CFG (live ADT). */
    if (adt_getprop(adt, adt_path_offset(adt, BRIDGE0_PATH), "apcie-config-tunables", NULL))
        tunables_apply_local_addr(BRIDGE0_PATH, "apcie-config-tunables", cfg);

    set32(cfg + PORT_APPCLK, PORT_APPCLK_EN);

    /*
     * Port PHY glue: refclk request/ack, then release the PHY reset (BIT4, the
     * t8132/t8122 reset that M4 needed cleared) and enable the refclk. macOS
     * does this in its link-training step, but stock Linux setup_refclk never
     * clears BIT4, so the loader owns it here (m1n1's t8122 port loop does the
     * same). Linux re-pokes the request/ack idempotently.
     */
    clear32(glue + GLUE_CTRL, GLUE_CLK0REQ | GLUE_CLK1REQ);
    set32(glue + GLUE_CTRL, GLUE_CLK0REQ);
    if (poll32(glue + GLUE_CTRL, GLUE_CLK0ACK, GLUE_CLK0ACK, POLL_US)) {
        printf("azahi-pcie: port0 PHY CLK0 ack timeout\n");
        return -1;
    }
    set32(glue + GLUE_CTRL, GLUE_CLK1REQ);
    if (poll32(glue + GLUE_CTRL, GLUE_CLK1ACK, GLUE_CLK1ACK, POLL_US)) {
        printf("azahi-pcie: port0 PHY CLK1 ack timeout\n");
        return -1;
    }
    clear32(glue + GLUE_CTRL, GLUE_RESET_T8132);
    udelay(1);
    set32(glue + GLUE_CTRL, GLUE_REFCLKEN);

    /*
     * T6050 root-port reset handshake (macOS enablePortHardware, AUS5 path).
     * Phase 1: wait for the lane pipe reset status to clear (lanes in reset).
     * Then release the root-port reset. Phase 2: wait for it to assert again
     * (lanes out of reset), then drop RET_PIPE_RESET_EN. Mask is 0x1 for the
     * x1 GP port (lane-cfg 0). Stock Linux does none of this.
     */
    if (poll32(cfg + PORT_LANESTAT, 0x1, 0x0, POLL_US)) {
        printf("azahi-pcie: lane pipe reset did not clear (0xa8=%#x)\n",
               read32(cfg + PORT_LANESTAT));
        return -1;
    }
    set32(cfg + PORT_T6050_RESET, PORT_RESET_DIS);   /* release root-port reset */
    if (poll32(cfg + PORT_LANESTAT, 0x1, 0x1, POLL_US)) {
        printf("azahi-pcie: lane pipe reset did not assert (0xa8=%#x)\n",
               read32(cfg + PORT_LANESTAT));
        return -1;
    }
    clear32(cfg + PORT_T6050_RESET, PORT_RET_PIPE_EN); /* drop RET_PIPE_RESET_EN */

    if (poll32(cfg + PORT_STATUS, PORT_STATUS_RUN, PORT_STATUS_RUN, POLL_US)) {
        printf("azahi-pcie: port0 STATUS RUN timeout\n");
        return -1;
    }

    write32(cfg + PORT_COUNTERS, 0x3);
    write32(i2a + 0x80, 0x1);

    printf("azahi-pcie: port0 up to STATUS RUN; Linux drives PERST/refclk/LTSSM\n");
    return 0;
}

/* Returns 0 if the node was enabled, -1 if absent (overlay not merged). */
static int fdt_enable_node(void *fdt, const char *path)
{
    int off = fdt ? fdt_path_offset(fdt, path) : -1;
    if (off < 0) {
        printf("azahi-pcie: %s not in FDT (overlay not merged?)\n", path);
        return -1;
    }
    if (fdt_setprop_string(fdt, off, "status", "okay")) {
        printf("azahi-pcie: cannot set %s status\n", path);
        return -1;
    }
    printf("azahi-pcie: enabled %s\n", path);
    return 0;
}

int azahi_pcie_init(const char *cmdline, void *fdt)
{
    if (!cmdline || !strstr(cmdline, "azahi.pcie="))
        return 0;   /* default: opted out */

    bool bringup = strstr(cmdline, "azahi.pcie=bringup") != NULL;
    bool probe = bringup || strstr(cmdline, "azahi.pcie=probe") != NULL;
    if (!probe) {
        printf("azahi-pcie: unrecognised azahi.pcie mode; skipping\n");
        return 0;
    }

    int apcie_path[8];
    int off = adt_path_offset_trace(adt, APCIE_PATH, apcie_path);
    if (off < 0 || !adt_is_compatible(adt, off, "apcie,t6050")) {
        printf("azahi-pcie: apcie0 not apcie,t6050; skipping\n");
        return 0;
    }

    if (!ssd_domains_active()) {
        printf("azahi-pcie: SSD domains not all active; refusing (never own SSD power)\n");
        return -1;
    }

    printf("azahi-pcie: pre-bring-up state:\n");
    dump_state(apcie_path);

    if (!bringup) {
        printf("azahi-pcie: probe only, no writes\n");
        return 0;
    }

    /* Enable ONLY the GP-branch clocks (indices 1,2,9,10,11); never storage. */
    for (size_t i = 0; i < sizeof(gp_gate_index) / sizeof(*gp_gate_index); i++) {
        if (pmgr_adt_power_enable_index(APCIE_PATH, gp_gate_index[i])) {
            printf("azahi-pcie: failed to enable GP gate index %u\n", gp_gate_index[i]);
            return -1;
        }
    }
    /* Confirm we did not disturb the SSD branch. */
    if (!ssd_domains_active()) {
        printf("azahi-pcie: SSD domains changed after GP enable; STOP\n");
        return -1;
    }

    if (gp_controller_init(apcie_path)) {
        printf("azahi-pcie: GP controller init failed; leaving port for Linux\n");
        return -1;
    }
    if (port0_bringup(apcie_path)) {
        printf("azahi-pcie: port0 bring-up failed; leaving port for Linux\n");
        return -1;
    }

    printf("azahi-pcie: bring-up done:\n");
    dump_state(apcie_path);

    /* DART first: the PCIe node's iommu-map depends on it. */
    if (fdt_enable_node(fdt, FDT_DART_PATH) || fdt_enable_node(fdt, FDT_PCIE_PATH))
        return -1;
    return 0;
}
