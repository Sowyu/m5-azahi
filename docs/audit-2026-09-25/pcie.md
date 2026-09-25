# Native Wi-Fi PCIe bring-up for T6050 / J714s (apcie0, Apple N1)

Author area: PCIe root port, DART and device-tree so a PCI driver can bind the
Apple N1 functions 106b:1901 (control), 106b:1902 (alpha/WLAN) and 106b:1903
(beta/BT) behind /arm-io/apcie0/pci-bridge0, with the SSD root untouched. A
separate agent owns the N1 protocol (ACIPC, firmware, WLAN) and builds on this.

No hardware was available. Everything here is source review, static RE of the
public macOS 27.0 (26A428) restore image, host tests and cross-compilation.
Nothing was run on the target. Claims are pinned to an ADT property, a
kernelcache function and address in build 26A428, or a Linux source line.

## What shipped

- `pcie-driver/gen-pcie-dt.py` builds the overlay from the ADT JSON.
- `pcie-driver/dts/t6050-j714s-pcie-wifi.dtso` the generated overlay, port 0.
- `pcie-driver/test-pcie-dt.py` host test, 15 checks, skips without the ADT.
- `pcie-driver/pcie-apple-t6050.c` a minimal fork of the stock driver.
- `pcie-driver/vendor/pcie-apple.original.c` the stock driver, for diffing.
- `standalone-loader/m1n1-20260911/src/azahi_pcie.c` and `.h` the loader-side
  controller and port-0 bring-up, default off.
- A local, additive, default-off hook in `standalone-loader/.../kboot.c`.

## How the pieces fit at boot

Apple iBoot brings apcie0 up far enough to boot NVMe (the SSD is on the storage
"ST" fabric of this controller), so the deep common and AXI init is already
done when Linux starts. It does not bring up the general-purpose (GP) ports,
so port 0 (the N1 port) still needs GP PHY init plus per-port bring-up.

The division follows the M4 result that got Broadcom Wi-Fi working under Linux
(wallace repo, 2026-07-29): the loader does the controller and port register
init, and Linux (`pcie-apple`) drives PERST#, refclk and LTSSM and enumerates.

1. Loader (`azahi_pcie.c`, opt-in): enable only the GP-branch clocks, run
   `_apcieGPInit` (GP PHY), run the port-0 `_resetPortHardware` block, release
   the root-port reset, and stop at PORT_STATUS RUN.
2. Linux (`pcie-apple-t6050.c` via the overlay): PERST# GPIO, refclk request/
   ack, LTSSM start, link-up wait, MSI, RID-to-SID, ECAM enumeration.
3. N1 agent (later): power the N1 chip with SMC key gP13 and drive the 'PrtC'
   port-control path so the link trains and the functions probe.

## apcie,t6050 versus Linux t602x_hw and t8103_hw

Evidence tags: ADT = j714s ADT property; KC = kernelcache build 26A428 function
at address; SRC = Linux 7.0.13 source line. RE detail with per-instruction
addresses is in the working notes (not committed); the load-bearing facts are
below.

### Ports and topology

- apcie0 is `apcie,t6050`, 4 ports, `#msi-vectors` 128, `msi-vector-offset`
  1824, `msi-address` 0xfffff000, `first-bypass-sid` 16 (ADT /arm-io/apcie0).
- Two bridges are populated: pci-bridge0 = N1 (control/alpha/beta), pci-bridge1
  = a GL9755 sd-reader (ADT). Only port 0 is described here; the sd-reader port
  is left out.
- Endpoint identity: pci-bridge0 children centauri-control (106b:1901),
  centauri-alpha (106b:1902, publishes WLAN), centauri-beta (106b:1903), each
  with iommu-parent mapper-apcie0-{control,alpha,beta} (ADT; matches the saved
  ioreg IDs in probe/N1-WIFI-20260913.md).

### Register layout

The macOS AppleT6050PCIe kext maps the ADT `reg` entries by role (KC
`AppleT6050PCIe::start`, `APCIECoreRCGen4Port::initWithAPCIeAndRegistryEntry`):

| Role | ADT reg index | CPU address | Linux name |
| --- | --- | --- | --- |
| ECAM | 0 | 0x1cb0000000 | config |
| Common | 1 | 0x214000000 | rc |
| GP PHY (PhyCommon = +0x4000) | 2 | 0x217000000 | (loader) |
| PhyPhy | 3 | 0x217020000 | (loader) |
| Axi2Af | 5 | 0x216000000 | (loader/iBoot) |
| PcieClkgen | 6 | 0x215044000 | (unused at boot) |
| port0 config | 16 | 0x210028000 | port0 |
| port0 PHY glue | 18 | 0x217010000 | phy0 |
| port0 intr2axi | 19 | 0x210024000 | (loader) |

The per-port config block uses the t602x layout, confirmed in KC
`APCIECoreRCGen4Port`: PERST/reset 0x82c, RID2SID 0x3000, MSIMAP 0x3800, MSI
address 0x16c/0x170, APPCLK 0x800, STATUS 0x804, LINKSTS 0x208, LTSSMCTL 0x80.
These are exactly the `t602x_hw` offsets in SRC pcie-apple.c
(PORT_T602X_PERST 0x82c, PORT_T602X_RID2SID 0x3000, PORT_T602X_MSIMAP 0x3800,
PORT_T602X_MSIADDR 0x16c/0x170). So the driver hw_info is t602x; the fork's
`t6050_hw` is a renamed copy of it.

Differences from t8103_hw: t8103 uses PORT_MSIADDR 0x168, PORT_PERST 0x814,
PORT_RID2SID 0x828, no MSIMAP table, and needs `phy_lane_ctl`. None apply to
T6050 (SRC t8103_hw versus t602x_hw). T6050 is not t8103-like.

### Controller bring-up (what the loader must do, and does not)

macOS at cold boot runs (KC `AppleEmbeddedPCIE::configure` ->
`_enableRootComplex(false)`):

1. `_enableClocks`: enable apcie0 clock-gates indices 0..9 = ANS, APCIE_GP,
   APCIE_SYS_GP, APCIE_GE, APCIE_SYS_GE, APCIE_ST0, APCIE_SYS_ST0, APCIE_ST1,
   APCIE_SYS_ST1, APCIE_PHY_SW (KC `AppleT6050PCIe::_enableClocks`; index list
   is ADT /arm-io/apcie0 clock-gates). Enable only, never disable.
2. `_apcieCommonInit` is skipped at cold boot; it only runs on wake (KC
   `_socEnableRC` tests the flag; the true path is the IOPlatformActiveAction
   wake action). iBoot has therefore already done AUS5 un-gating, the AON
   dynamic-power-gate bit and `apcie-axi2af-tunables`. Linux and the loader
   must assume it and must not redo the common/AXI init.
3. `_apcieGPInit`: apply `apcie-common-tunables` to Common, Common+0x04 = 0
   (lane-cfg), apply `apcie-phy-tunables` to GP PHY, poll PhyCommon+0 bit31
   (100 MHz refclk), Gen5 PHY (PhyPhy+4 |= 0x10, wait +8 bit4, PhyPhy+4 &=
   ~0x20, wait +8 bit0, PhyCommon+0 bit0 = 1, PhyPhy+0 |= BIT27), Common+0x54
   = 0x140, Common+0x50 |= 1 (GTB to PTM), poll Common+0x58 bit0.

m1n1's t8122 path (`src/pcie.c`) does the same shape (rc+0x4 = 0, rc+0x54 =
0x140, rc+0x50 = 1, poll rc+0x58; PhyCommon 100 MHz poll; PHY reset bit 0x10).
The T6050 reset bit in the PHY control is BIT(4), matching m1n1's t8132/t8122
`APCIE_PHY_CTRL_RESET_T8132`, not the t602x BIT(14). This is also the M4 fix
that unblocked link-up (wallace op-115 note). `azahi_pcie.c` reuses this
sequence and reads the tunables from the live ADT.

### Port 0 bring-up

macOS `enablePortHardware` (KC `APCIECoreRCGen4Port::enablePortHardware`) does
`_resetPortHardware` then config tunables, APPCLK, refclk buffer, root-port
reset release, and STATUS RUN. The confirmed T6050 register values (deltas
against m1n1 t8122 in parentheses):

0x088=0x110, 0x100/0x148/0x210=~0, 0x080=0, 0x084=0, 0x104=0xfffffff0,
0x124=0x100, 0x16c=0, 0x13c=0 (m1n1 0x10), 0x800=0x00100100,
0x808=0x001001ff (m1n1 0x1000ff), 0x82c=0x10000 (m1n1 0), RID2SID x64 = 0,
MSIMAP x256 = 0, 0x130=0x03020000 (m1n1 0x3000000), 0x140=0x10,
0x144=0x00253770, 0x21c=0, 0x834=0, 0x83c=0.

The 0x82c write sets RET_PIPE_RESET_EN (bit16). macOS panics if it is not set
before the lane-pipe-reset wait (KC 0xfffffe0009c7fe74), so it is load-bearing
on this SoC. The sequence then sets APPCLK_EN, does the port PHY glue refclk
request/ack and clears the PHY reset bit, waits the lane-pipe-reset status at
CFG+0xa8 (mask 0x1 for the x1 GP port, KC `_getLanePipeRstStsMask`), sets
0x82c bit0 to release the root-port reset, clears RET_PIPE_RESET_EN, and polls
CFG+0x804 bit0 (STATUS RUN). `azahi_pcie.c` stops here.

Stock Linux does none of the RET_PIPE_RESET_EN dance and never clears the PHY
glue reset bit (SRC apple_pcie_setup_refclk only touches PHY_LANE_CFG refclk
req/ack and REFCLKEN). So neither the loader nor Linux would release that PHY
reset unless the loader does it. `azahi_pcie.c` does it.

Left to Linux `pcie-apple`: PERST# GPIO (reset-gpios, ADT function-perst GPIO
80), the refclk request/ack (idempotent re-poke), LTSSM start (CFG+0x80 bit0),
and link-up. Left out entirely for now: the DBI/root-port-config-space tuning
(pcie-rc and gen3/4/5 shadow tunables, link width, max speed). Stock Linux does
not do it and trains links on M1/M2; it sets caps, not the training gate. It is
a documented follow-up if the negotiated speed or width is wrong.

### MSI

macOS `configMSIRange` (KC `APCIECoreRCGen4Port::configMSIRange`): CFG+0x124 =
1, CFG+0x16c/0x170 = 0xfffff000, MSIMAP entry base+i = BIT31 | (base+i). Port 0
uses base 0, 32 vectors. The MSI data value v maps to AIC IRQ 1824+v (ADT
`msi-vector-offset` 1824; INFERRED from the ApplePCIEMSIController init args).
This is the same register layout as SRC t602x_hw (MSIMAP 0x3800, MSIADDR
0x16c/0x170). The overlay carries `msi-ranges = <&aic 0 1824 1 32>` and lets
the driver program it.

### Interrupts

apcie0 ADT `interrupts` = 1523, 1531, 1539, 1547 (the four ports), then 1558,
1559. Port 0 uses 1523. dart-apcie0 uses 1524 (ADT). The overlay uses the
project's 3-cell AIC form `<0 1523 4>` with `interrupt-parent = <&aic>`, the
same as the USB overlay. Port interrupt status bits (KC, CFG+0x100 W1C,
CFG+0x104 mask): 4 port error, 5..7 AER, 11 bandwidth, 12 link up, 14 link
down, 15 AF timeout, 17 addr>32, 19 MSI miscompare, 21 read error, 23
completion timeout, 25 completer abort. Linux uses the same bit numbers for
link up/down (SRC PORT_INT_LINK_UP 12, PORT_INT_LINK_DOWN 14) and names bit 21
CPL_ABORT where Apple uses it for read error; that only affects log text.

### PERST, clkreq, refclk

- PERST#: ADT pci-bridge0 function-perst is GPIO 80 on gpio0 (the AP pinctrl).
  macOS releases it at link-training time, after refclk and the 100 us
  t-refclk-to-perst delay (KC `enableLinkTraining` -> `setEndpointReset(false)`).
  The overlay sets `reset-gpios = <&pinctrl_ap 80 GPIO_ACTIVE_LOW>` so Linux
  drives it in `apple_pcie_setup_link`. INFERRED: GPIO 80 is asserted from boot
  or by iBoot; macOS never explicitly asserts it on this path.
- clkreq: ADT function-clkreq GPIO 76 is only consulted when clkreq-wait-time
  is set, which pci-bridge0 does not set (KC). No clkreq handling is needed.
- refclk: the port PHY glue (reg 18) is the t602x/t8122 PHY_LANE_CFG. The
  loader does the request/ack and clears the reset bit; Linux re-does the
  request/ack. `t-refclk-to-perst` and `perst-to-config` are both 100 in the
  ADT and both already handled by SRC pcie-apple.c (100 us Tperst-clk, 100 ms
  Tpvperl).

### Tunables (unknown offline, and why)

Every apcie tunable is an ADT property read at runtime (KC
`AppleEmbeddedPCIE::_applyTunablesFromData`, 24-byte entries {offset, size,
mask, value}, applied read-modify-write, missing property skipped). The public
restore-image ADT has none of them. iBoot inserts them at boot, the same way
the live atc-phy ADT has `tunable_USB2PHY_*` that the restore image lacks.
There is no fallback table in the kernelcache. So the exact tunable values
cannot be recovered offline. They must come from a live ADT dump. `azahi_pcie.c`
reads them by name from the live ADT, which is correct on the target even
though the values are invisible here. Names used: `apcie-common-tunables`,
`apcie-phy-tunables` (controller), `apcie-config-tunables` (port). Not applied
on T6050: `apcie-phy-ip-pll-tunables`, `apcie-phy-ip-auspma-tunables` (read but
never used, KC). `apcie-axi2af-tunables` is wake-only and assumed done by iBoot.

### DART and SIDs

dart-apcie0 is `dart,t8110`, reg 0x210000000, IRQ 1524, sid-count 19, sid list
16,17,18, bypass-16, bypass-18, first-bypass-sid 16, apcie-piodma-sid 17 (ADT).
Linux apple-dart already supports t8110 (SRC apple_dart_hw_t8110, max_sid_count
256, reads NUM_SIDS from PARAMS4). RID-to-SID (KC
`APCIECoreRCGen4Port::_updateRIDToSIDMappings`): CFG+0x3000+4i = BIT31 |
(sid&0xf)<<16 | rid, and SID 0 is never a valid entry. The table size is
min(dart sid-count, first-bypass-sid) = 16. SIDs are handed out dynamically,
lowest free first from 1 (KC `AppleT8110DART::_dartAssignDynamicSID`). So
control, alpha and beta get SIDs 1, 2, 3 (INFERRED, nothing else allocates on
this DART first). The overlay uses iommu-map RID->SID {0x100->1, 0x101->2,
0x102->3} with mask 0xffff. Any SIDs 1..15 work as long as the DART and the
RID2SID table agree; Linux's `apple_pcie_enable_device` writes RID2SID from the
iommu-map, so they will. SID 17 is the PIO-DMA engine (fault attribution only);
16 and 18 are DART bypass SIDs outside the 4-bit RID2SID range.

## SSD safety

The SSD path uses ANS/NVMe on the apcie0 "ST" (storage) fabric. Evidence:
research-archive/t6050-j714s-hv-nvme.dts and t602x-nvme.dtsi give nvme
power-domains `ps_ans2`, `ps_apcie_st_sys`, `ps_apcie_st1_sys`; the loader's
own `azahi_standalone.c prepare_ans()` touches FAB6_SOC, APCIE_ST0, ANS,
APCIE_SYS_ST0; the PMGR tree (research-archive/t6050-pmgr.dtsi) shows
`ps_apcie_sys_st0 -> ps_apcie_st0, ps_ans`. NVMe uses SART, not dart-apcie0
(t602x-nvme.dtsi apple,sart), so the Wi-Fi DART is not shared with the SSD.

The hazard is the PMGR power/clock gates, not the DART. The apcie0 gate list
mixes the GP (Wi-Fi) branch with the storage branch (ANS, APCIE_ST0/ST1,
APCIE_SYS_ST0/ST1). Turning these on is safe and idempotent (macOS re-enables
them every boot too, KC `_enableClocks`). Turning any of them off would kill
the SSD root. macOS only ever gates them on sleep/hibernate (KC
`_quiesceClocks`, `_gateAUS5Phys`, `_shutdownPciePLLs`), never at boot.

How the code enforces it:

- `azahi_pcie.c` refuses to do anything unless ANS, APCIE_ST0 and
  APCIE_SYS_ST0 are already ACTIVE (read-only PMGR reads). If they are not, the
  loader is not responsible for SSD power and must not proceed.
- On bring-up it enables only the GP-branch clock-gate indices 1, 2, 9, 10, 11
  (APCIE_GP, APCIE_SYS_GP, APCIE_PHY_SW, APHY_GP_AUS5_A, APHY_GP_AUS5), never
  the storage indices 0, 5, 6, 7, 8. The recursive parent walk of those GP
  devices reaches FAB6_SOC and the GE branch, never ST or ANS (verified against
  the PMGR device parent table in the ADT).
- It never calls any disable or reset path.
- After the GP enable it re-reads the ST/ANS domains and aborts if they moved.
- The Linux overlay carries no `power-domains` at all, so genpd cannot power a
  shared domain down; the base DT boots with `pd_ignore_unused` and the pmgr
  driver deleted, exactly like the USB overlay. The loader owns power.
- The forked driver keeps `suppress_bind_attrs` and does no runtime PM on any
  shared domain (it inherits the stock driver's behaviour, which has none).

## Build and test results

- Overlay: `gen-pcie-dt.py` builds it from the ADT; `test-pcie-dt.py` runs 15
  checks (addresses, interrupts, MSI base, ranges flags, three N1 functions,
  per-function SIDs, PERST GPIO, sd-reader absent, azahi compatible, and the
  t6031 reference shape). All pass. With the ADT absent the ADT-dependent tests
  skip cleanly and the reference-shape checks still run (2 pass, skipped 2).
- dtc builds the overlay with `-@` (it emits `__fixups__` for aic and
  pinctrl_ap and `__local_fixups__` for the internal references) and
  `fdtoverlay` merges it onto a base DTB built from
  research-archive/t6050-j714s-native-rootguard.dts. In the merged tree the
  three functions are present and interrupt-parent, reset-gpios and msi-ranges
  resolve to the base phandles. The private installed DTB is not available, so
  this validates structure and label resolution, not the installed image.
- `pcie-apple-t6050.c` cross-compiles against the exact Fedora Asahi
  7.0.13-400 kernel (make -C $KDIR M=... W=1): a .ko is produced, no compile
  errors, only the expected unresolved-symbol warnings from the missing
  Module.symvers. The diff against the vendored stock driver is 50 added lines:
  the azahi compatible, the t6050_hw struct, and the link-timeout diagnostic.
- `azahi_pcie.c` cross-compiles against m1n1 headers with
  `-std=gnu11 -Wall -Wextra -Werror` (upstream m1n1 clone): clean object, all
  undefined symbols are real m1n1 APIs (adt_*, pmgr_adt_power_enable_index,
  tunables_apply_local*). The private standalone-loader m1n1 tree is not
  buildable from a clean clone, so a full loader link was not attempted.
- The kboot.c hook is additive: default boots keep the exact skip behaviour;
  the loader-guard host test still passes.
- Publication guard passes with the new files added to safety/allowed-paths.txt.

## Attended first-test plan

Prerequisite: the daily macOS is untouched, the SSD Linux boots, and the phone
or another recovery route exists. Every USB-C socket empty at boot.

Every stage needs a new bundle image. The kernel cmdline and DT are baked into
the pinned bundle, so "add `azahi.pcie=probe`" means: rebuild the private
loader with `azahi_pcie.c` linked in (add `azahi_pcie.o` to the private
tree's object list), build a bundle whose bootargs carry the token, and
install it through the same private Recovery procedure as v7. Rollback for
any stage is reinstalling the pinned v7 image. `azahi_pcie.c` was
compile-checked against upstream m1n1 HEAD, not the private 20260911 tree;
confirm `pmgr_adt_power_enable_index` and `tunables_apply_local_addr` exist
there before building.

Stage 0, read-only, no writes:

1. Build the standalone loader from the private tree with `azahi_pcie.c` in it.
2. Boot Linux once with `azahi.pcie=probe` added to the kernel cmdline. Expect
   loader log: `azahi-pcie: SSD domains ANS=0x...f APCIE_ST0=0x...f
   APCIE_SYS_ST0=0x...f`, then `probe only, no writes`, then a normal boot to
   KDE with the SSD root intact.
3. Abort criterion: if the loader prints `SSD domains not all active; refusing`
   or the machine does not reach KDE, stop. Do not go to stage 1. That means
   iBoot did not leave the storage fabric up the way this analysis assumes.
4. Capture: the full loader log and `dmesg | grep -i pcie`. There should be no
   pcie-apple probe yet (no overlay merged).

Stage 1, controller and port register bring-up, no endpoint power:

1. Merge the overlay into the bundle DTB with `fdtoverlay` (the base must be
   compiled with `dtc -@` so `aic` and `pinctrl_ap` resolve; fdtoverlay fails
   loudly otherwise) and boot with `azahi.pcie=bringup`. The overlay's DART
   and PCIe nodes ship `status = "disabled"`. The loader sets them to `okay`
   only after port 0 reaches STATUS RUN, so if any loader step fails, Linux
   never probes the controller or DART. The N1 chip is still unpowered (no gP13 yet), so the
   link is not expected to train. This isolates the loader/driver plumbing from
   the N1 power sequence.
2. Expect loader log `azahi-pcie: port0 up to STATUS RUN`, then
   `enabled /soc/iommu@410000000` and `enabled /soc/pcie@1cb0000000`. Expect
   `pcie-apple-t6050 ...: host bridge ... ranges` and
   `[106b:...] type 01 ... PCIe Root Port` for 00:00.0, then the fork's
   `LINKSTS ... STATUS ... link didn't come up` diagnostic. The SSD root must
   still be intact and `dmesg | grep -i nvme` unchanged.
3. Abort criteria: any NVMe error, any PMGR SError, or the loader poll timeouts
   (`GP PHY 100MHz refclk not ready`, `STATUS RUN timeout`, `lane pipe reset
   status timeout`). The bounded timeouts mean the boot continues either way;
   record which poll failed and stop.
4. Capture: loader log, `lspci -nnvv` (config space of the root port),
   `dmesg | grep -iE 'pcie|dart|106b'`, and the fork's LINKSTS/STATUS line.

Stage 2, endpoint power (the N1 agent's step, needed for enumeration):

1. Add the N1 power: SMC key gP13 = 0x00800001, wait 100 ms, then let the port
   train. The upstream-shaped way is `pwren-gpios = <&smc_gpio 0x13 0>` on
   `pcie0_port0` (gP13 is SMC GPIO 0x13); stock pcie-apple already drives
   `pwren-gpios`. It is deliberately not in the stage-1 overlay, so stage 1
   isolates loader and driver plumbing from endpoint power. This is
   outside this area; the interface above (root port at STATUS RUN, PERST on
   GPIO 80, DART SIDs 1/2/3) is what it builds on.
2. Expect `pcie-apple ...: link up`, then 01:00.0 106b:1901, 01:00.1 106b:1902,
   01:00.2 106b:1903 under `lspci`, each mapped to a DART SID.
3. Rollback for any stage: reinstall the pinned v7 image through Recovery.
   Nothing in these stages writes to storage or the boot policy.

Stage 1 should be run before anything enables bus mastering. The loader does
not enable bus mastering; Linux PCI core does that during enumeration, so
stage 1's read of config space happens before any DMA is possible from the
endpoints (they are unpowered).

## Confidence and ranked unknowns

Confidence is moderate for the register sequences (they are pinned to the
macOS driver at named addresses and match m1n1's proven t8122 path) and high
for the DT description and SSD-safety design. It is low that link-up happens on
the first try, because three things cannot be settled offline.

1. Tunable values. `apcie-common/phy/config-tunables` come from the live ADT
   and are invisible in the restore image. If iBoot did not populate them, or
   populated different registers than assumed, the GP PHY or port may not come
   up. The loader logs the PhyCommon and STATUS registers so the first session
   sees this. Highest-risk unknown.
2. Whether iBoot leaves the GP PHY and the common/AXI fabric in the exact state
   macOS's cold-boot path assumes (it skips `_apcieCommonInit`). If iBoot on
   this machine does less than macOS's iBoot, `_apcieGPInit` alone may be
   insufficient and the AXI/AUS5 init would be needed too. The stage-0 probe
   dump is the first read on this.
3. The N1 endpoint power and 'PrtC' sequence (SMC gP13, the 100 ms delay, port
   control). Confirmed in the kext but owned by the N1 agent; without it the
   link cannot train and nothing enumerates.

Lower unknowns: the exact SIDs (1/2/3 is inferred, but any 1..15 works as long
as DART and RID2SID agree, which the driver guarantees); DBI link-width and
max-speed tuning is skipped and may leave the link at a default speed; the
`dart-options` 55, `manual-availability` and DART instance tunables are not
analysed and are absent from the restore ADT.

## Orchestrator review changes (2026-09-25)

After the agent finished, three problems were fixed and re-tested:

- The overlay listed `apple,t6020-pcie` as a fallback compatible. The stock
  `pcie-apple` is built in (`CONFIG_PCIE_APPLE=y`), so it would have bound the
  node at boot, ungated, before the fork could load. The compatible is now
  `azahi,t6050-pcie` only, and the fork matches only that string (the unused
  stock hw tables were removed from the fork).
- The overlay nodes were always enabled once merged, so a boot where the
  loader bring-up failed or was not requested would still probe the DART and
  controller, possibly unpowered. Both nodes now ship disabled and
  `azahi_pcie_init()` enables them only after STATUS RUN.
- `azahi.pcie=probe` was described as read-only but read controller
  registers without checking their power domain. Reading a gated block can
  SError, and that would cost a Recovery reinstall. `dump_state()` now skips
  controller reads unless APCIE_GP and APCIE_SYS_GP are ACTIVE. This narrows
  the risk; other GP-branch gates may still be off.

Re-checked: `test-pcie-dt.py` 16 pass with the ADT, the fork builds with 0
warnings at W=1 against `$KDIR`, and `azahi_pcie.c` compiles with
`-Wall -Wextra -Werror` against upstream m1n1 headers.
