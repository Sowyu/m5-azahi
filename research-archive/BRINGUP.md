# Asahi Linux on M5 Pro (T6050) — bring-up state

Machine: MacBook Pro 14" M5 Pro, Mac17,9 / board `j714sap`, chip ID `0x6050`
("Sotra"), 18 cores (12 M in 2 clusters + 6 P), 64 GB, macOS 27.0 firmware.
Date: 2026-08-15.

## Latest SSD checkpoint — 2026-09-06

The `--ans-zero-based-limit` hook passed: 8,192 direct reads / 128 MiB with
matching repeated checksums, controller `live`, no ANS assert or I/O errors.
It changes only pending-command limit `0x45dcc1210` from `0x00400040` to
`0x003f003f`; queue-create sizes were already correct. Input stays working,
systemd runs from RAM, and every SSD namespace remains read-only.

The supposed Linux partition is a 250 GB APFS container containing `Linux`,
`Linux - Data`, `Preboot`, `Recovery`, `VM`, and `Update`. No ext4/Btrfs root
partition exists. Do not format it or repartition without new explicit user
authority; preserve its boot environment and the separate macOS container.
See `probe/SSD-CHECKPOINT.md` and the latest PROGRESS.md entry. Earlier failed
SSD test notes below are historical, not the current read-capability status.

## Current input checkpoint — 2026-09-06

**Latest: both keyboard and trackpad physically verified.** Boot
`guest-hv-input-v2power.bin`, which adds a local J714s-only dockchannel-HID
module patch to the working SID0 baseline. Its v2 will/has power-request
pairs are accepted and produce `Touch MT ready`. A 90-second capture recorded
826 trackpad report frames, X/Y/pressure updates, two-finger detection, five
click press/release pairs, and keyboard A/B/C. DART fault count was zero.
Kernel image remains stock; PRIVATE-USER authorized the local module patch.
Evidence: `logs/input-v2power-boot-20260906/console.log`.

**SSD safety correction:** the older ANS power scripts/DT used PMGR base
0x280600000, but the saved real ADT puts these domains in group 1 at
**0x280900000**. Do not execute old `anspower_inline.py`. The new
`t6050-j714s-hv-input-ssd.dts` / `probe/prepare-ans.py` use and validate the
correct base, require ACTIVE state without host writes, and shadow the four
guest power controls. Cold APCIE_SYS_ST0 needed explicit, narrowly checked
`--activate-ans-link` activation; it reached ACTIVE. SSD probing then exposed
three namespaces and `nvme0n1: p1 p2 p3 p4`, but ANS firmware asserted at CQ
head 63 and removed the devices. The crash dump reports 65-entry I/O queues.
RAM-root systemd and input survived; no target disk data writes or mounts.
The next read-only test uses `--ans-zero-based-limit` to substitute 63 for
64 in both fields of pending-command register `0x45dcc1210`. See the current
PROGRESS.md entry and `probe/test-prepare-ans.py`; this is not yet verified.

Earlier checkpoint (trackpad blocker below now resolved):

**Built-in keyboard works on the unchanged 7.0.13 Asahi kernel.** The SID0
input image completes MTP/RTKit startup and registers Apple MTP keyboard and
multi-touch devices. Physical A/B/C and all arrow key press/release events
were captured from the keyboard. The critical DT correction is MTP IOMMU
stream **0** for both helper and HID, with the exact ADT DMA range and targeted
MTP DAPF setup before the guest starts.

Trackpad startup is still blocked: firmware upload succeeds, but both reset
commands are rejected (`0xe00002c2`), followed by timeout/EINPROGRESS. One
board-derived AFE GPIO reset pulse did not resolve it. Do not unbind the
dockchannel transport (its remove callback deliberately BUGs).

Working artifact: `guest-hv-input-sid0.bin`; DT:
`t6050-j714s-hv-input-sid0.dts`; runner: `probe/boot-input.py` with
`--prepare-mtp --trace-input`. Evidence:
`logs/input-sid0-boot-20260906/console.log` and
`logs/input-sid0-launch-20260906.log`. See PROGRESS.md for exact current
operational cautions. In particular, old claims below that guest exit always
recovers without a physical restart are **not true in these tests**.

Fedora/systemd is running from RAM; no internal SSD is exposed by this
input-only DT, no target SSD writes have occurred, and SSD/standalone boot
remain unfinished. Preserve the existing Linux partition and macOS.

## ✅ FIRST LIGHT — 2026-08-15

**m1n1 boots on the M5 Pro (T6050).** Installed as the boot object of the
"Linux" volume group via 1TR (`bputil -nc` + `kmutil configure-boot -c m1n1.bin
--raw --entry-point 2048 --lowest-virtual-address 0`). Reached `Running proxy...`
— MMU + caches on, AIC3 up, pmgr up, framebuffer console live.

So the SPTM wall does **not** block a macOS-style kernelcache boot on M5, matching
the asahi_neo finding. Confirmed from the real boot log:

| Derived blind from ADT (this repo) | Hardware reported |
|---|---|
| `interrupt-controller@280400000` | `AIC: Version 3 @ 0x280400000` |
| `watchdog@28836c000` | `Primary WDT register @ 0x28836c000` |
| 661 pmgr devices | `pmgr: initialized, 661 devices on 1 dies` |
| `compatible = "apple,j714s"` | `Devicetree compatible value: apple,j714s` |
| `dart,t8110` | `dart-usb0 ... is a t8110` |

Other facts from first light:
- `AIC3 with 1/4 dies, 3104/4096 IRQs, reg_size:40004, config:10000`,
  `cfg_stride/intmaskset_stride/intmaskclear_stride = 0x4a00`
- Internal display already initialized by iBoot: **3024x1964**, stride 3024,
  fb @ `0x10fd310c000`
- USB0/1/2 (DART t8110) initialize fine → **proxy over USB-C works**
- Secondary WDT @ `0x288330008`

## ✅ PROXY SESSION — 2026-08-15 (M1 Pro host over USB-C)

`proxy-kit/collect.py` connected on `/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED`:

```
AIC version reg @0x280400000 = 0xb      (matches ADT aic-rev = 11)
MIDR_EL1 = 0x611f0641  part = 0x64      = MIDR_PART_T6050_SOTRA_MCORE ✓
WDT   @0x28836c000 = 0x2fcd4d67         (counter ticking)
u.base = 0x10005f60000                  (m1n1 load base; RAM @ 0x10000000000)
REAL ADT dumped: 737280 bytes -> adt-real-t6050.bin
```

### Reconstruction accuracy (ioreg-derived vs. real ADT)
- real 624 nodes / reconstructed 640
- **only 28 nodes missing**, ALL of them `/arm-io/error-handler/*` (IOKit hides
  them; irrelevant to Linux)
- **pmgr devices 661 == 661** → the generated `t6050-pmgr.dtsi` is correct
  against ground truth.

### T6050 CPU topology + clocks (from the real ADT)
| cluster | type | cpm-impl-reg | cpufreq base | cores | L2 |
|---|---|---|---|---|---|
| 0 | M | `0x210e40000` | `0x210e00000` | 6 | 8 MiB |
| 1 | M | `0x211e40000` | `0x211e00000` | 6 | 8 MiB |
| 2 | P | `0x212e40000` | `0x212e00000` | 6 | 16 MiB |

P-state tables (`/arm-io/pmgr`):
- **P cluster** (`voltage-states5` + `-sram`): 20 states, 1.308 → **4.608 GHz**,
  625–1125 mV
- **M clusters** (`voltage-states22`/`23` + `-sram`): 15 states, 1.344 →
  **4.380 GHz** (the two M clusters are binned slightly differently)

### cpufreq patch — WRITTEN AND BUILDS
`src/cpufreq.c`: added `T6050`/`T6051` to `pstate_reg_to_pstate()` and a
`t6050_clusters[]` table (bases above, `{apsc, default}` following the
T6030/T6031 pattern). Rebuilt clean. **Not yet flashed/tested on hardware** —
next boot should no longer print "Chip 0x6050 is unsupported".

### Known gap seen at boot
```
cpufreq: Chip 0x6050 is unsupported
```
`src/cpufreq.c` has no T6050 table, so cores stay at boot frequency. Harmless
for bring-up; a small, self-contained upstreamable patch.


## Session 2026-08-15 (evening): Linux boot attempts

### Confirmed working
- m1n1 boots reliably from disk on T6050 and reaches `Running proxy...`
- USB proxy over USB-C works (chainload + register access from an M1 Pro host)
- m1n1 **accepts our hand-written device tree**, prepares it, and jumps to the kernel
  (`FDT prepared`, then `Preparing to boot kernel`)
- Patches written and running: skip `pcie_init()`/`dapf_init_all()` on T6050
  (they SError), `t6050_clusters[]` for cpufreq, keep fb console active across
  payload boot, halt-instead-of-reboot on unhandled exception

### The blocking bug (new T6050 finding)
```
Starting secondary CPUs...
Starting CPU 1 (0:0:1)... Failed!     <- all 17 secondaries fail
FDT: CPU N is not alive, disabling...
FDT: Pruned .. CPU references in [AIC]/affinities/...
```
m1n1 cannot start any secondary core. `smp.c` maps T6050 to
`CPU_START_OFF_T6031` (0x88000) — evidently wrong for this SoC. m1n1 then
disables every dead CPU in the DT and prunes cpu-map/PMU affinities.

### Linux status: enters, then silent
Kernel is entered (m1n1 prints `Preparing to boot kernel`, then `fb_shutdown()`
clears the console leaving the logo — normal handoff). No kernel output ever
appears. Tried and ruled out:
- `console=tty0` + `ignore_loglevel debug` (fbcon chain is all =y: DRM,
  DRM_FBDEV_EMULATION, SIMPLEDRM, FRAMEBUFFER_CONSOLE)
- `maxcpus=1`
- a single-CPU device tree with no cpu-map and no AIC affinities (nothing for
  m1n1 to prune) — still silent
- AIC3 is NOT the problem: the kernel computes die_stride =
  0x10000 + 4*4096 + 5*128 = 0x4a00, exactly what m1n1 reports for T6050

Conclusion: the kernel dies before its console initialises. Diagnosing further
needs real serial output.

### Serial console: blocked
`macvdmtool` (M1 Pro host, DFU port both ends, correct cable) reports
`Putting target into serial mode... VDM failed (reply: 0x05ac80d2)`.
The M5's Type-C port controller rejects the debug VDM. Suspect macvdmtool
predates this port controller. Without serial we are blind past the handoff.


### CPU-start offset hunt (attempted, blocked)
Upstream commit "Initial support for T6050/T6051" (2026-06-29) reuses
`CPU_START_OFF_T6031` (0x88000) for T6050 — evidently untested on real silicon.
Tried to locate the real block by scanning PMGR reg[0] (0x280600000) over the
USB proxy with 32-bit reads.

**Result: reads beyond the first page fault the machine.**
```
sanity: word at 0x280600000 = 0x000001f0      (OK)
read fault at +0x4000                          (M5 dies)
on-screen: SError, L2C_ERR_ADR 0x...280604000  (= BASE+0x4000)
```
PMGR is NOT freely readable on T6050 — likely powered-down or SPTM-protected
sub-regions. Blind register scanning is not a viable technique here.

### Also newly seen in the full boot log (`m1n1-boot-full.log`)
- `MCC: Unsupported version:mcc,t6050` — memory cache controller has no T6050
  support either (`mcc_init()` has no `mcc,t6050` branch)
- m1n1 uses the **dockchannel UART @ 0x288e28000**
- boot_args: phys_base `0x10003af8000`, mem_size `0xfc7008000`,
  mem_size_act `0x1000000000` (64 GiB), video 3024x1964 @30bpp stride 0x2f40
- **The USB proxy relays m1n1's whole console** (`TTY>` lines) — no serial
  console needed to capture m1n1 itself (but it cannot capture the kernel,
  since the proxy dies at handoff)

### Serial console via macvdmtool: does not work on M5
`Putting target into serial mode... VDM failed (reply: 0x05ac80d2)`, both while
macOS and m1n1 run on the target. The M5's Type-C port controller rejects the
debug VDM; macvdmtool predates this hardware. Note this also *breaks the USB
proxy* on that port until a full power cycle.


### CONFIRMED T6050 BUGS IN m1n1 smp.c (evidence below)

**Bug 1 — cpu_start_off points outside the register block.**
PMGR block 0 (`0x280600000`) decodes only **0x4000 bytes**; reads at +0x4000
SError the machine. Upstream uses `CPU_START_OFF_T6031 = 0x88000`, i.e. an
address that does not exist on this SoC. Dump of the whole 16 KiB shows it
contains nothing but the power-state array (non-zero only up to ~+0x460).

**Bug 2 — the enable-bit formula assumes 4 cores per cluster.**
`smp.c` computes `write32(base + 0x4, 1 << (4 * cluster + core))`.
T6050 has **6 cores per cluster**. The ADT states the correct bit for every CPU
in `/cpus/cpuN/function-enable_core` (phandle = pmgr, name 'Core', args[0]):

| cpu | cluster:core | ADT arg | m1n1 computes | |
|---|---|---|---|---|
| 0-5 | 0:0-0:5 | 1<<0 .. 1<<5 | 1<<0 .. 1<<5 | ok |
| 6 | 1:0 | **1<<6** | 1<<4 | WRONG |
| 12 | 2:0 | **1<<12** | 1<<8 | WRONG |
| 17 | 2:5 | **1<<17** | 1<<13 | WRONG |

12 of 18 CPUs get the wrong bit. The arg is simply `1 << cpu_id`; m1n1 should
read `function-enable_core` from the ADT instead of computing it.

**Evidence: CPU power states** (PMGR block 0, 18 CPUs at +0x00..+0x88, stride 8)
```
+0x00 MCPU0_0 = 0x1f0   PS_ACTUAL=0xf  -> core 0 RUNNING
+0x08..+0x88            = 0x100   PS_ACTUAL=0x0  -> other 17 cores POWERED OFF
+0x90,+0x98,+0xa0       = 0x1f0   -> all 3 clusters powered on
```
So the secondaries are genuinely parked and unpowered — not starting and
crashing.

**Also:** the per-cluster CPM block (`cpm-impl-reg`, e.g. `0x210e40000`) is not
freely readable either — reads fault at +0x68.


### DECISIVE TEST: CPU power registers ignore writes from EL2

Ran a controlled experiment over the USB proxy (`pwr2.log`):

```
CONTROL: RAM 0x10010428240 <- 0xdeadbeef, read back 0xdeadbeef   WRITES WORK
CPU PS : 0x280600008 (MCPU0_1) = 0x00000100
         wrote 0x0000000f  (m1n1 pmgr_set_mode semantics: clear
                            AUTO_ENABLE|WAS_CLKGATED|WAS_PWRGATED, TARGET=0xf)
         immediately after   = 0x00000100     <-- UNCHANGED
         15 polls            = 0x00000100     actual stays 0x0
```
Bit 8 (`PMGR_WAS_PWRGATED`, a sticky status bit that clears on write) did not
clear either — the write never landed. Meanwhile m1n1's own
`pmgr: Cleaning up device states...` completes with no timeouts, so PS writes
work for ordinary devices.

**Two possible readings (we cannot yet distinguish them):**
1. CPU power/start on T6050 is gated by firmware (SPTM/GL) and simply cannot be
   driven from EL2 — in which case *no* `cpu_start_off` value can ever work and
   m1n1 needs a different mechanism entirely. This matches the class of wall
   that M4 bring-up is publicly stuck behind.
2. CPU PS registers are read-only status mirrors (possibly on all Apple SoCs),
   and real control lives in the CPU-start block, whose location on T6050 is
   still unknown (it is NOT in PMGR block 0, which decodes only 0x4000).

Distinguishing them requires locating the start block, which cannot be done by
probing: PMGR beyond +0x4000 and the cluster CPM block beyond +0x68 both SError
the machine.

**This is the current end of the road for the SMP bug without outside input.**

### Best next leads
1. Find the correct CPU start register offset for T6050 (pokeable live over the
   working USB proxy — no reboots needed to experiment)
2. Ask the Asahi community why a kernel would go silent post-handoff on a new
   SoC; the ADT + device trees here are the evidence they'd want

## What works today (done in this repo)

| Artifact | What it is |
|---|---|
| `adt-m5pro-mac17,9.plist` | Full Apple Device Tree dump (`ioreg -alp IODeviceTree`) |
| `plist2adt.py` | Converts the ioreg plist back into raw binary ADT format |
| `adt-m5pro.bin` | Reconstructed binary ADT — parses with m1n1's own `adt.py`; validated (uart0 phys `0x505200000` matches m1n1's hardcoded T6050 `EARLY_UART_BASE` exactly) |
| `m1n1/build/m1n1.bin`, `m1n1.macho` | m1n1 bootloader built from upstream `main` on this machine. Upstream already has T6050: Sotra MIDR parts, chickens entries, AIC3 driver, early UART base |
| `t6050-pmgr.dtsi` | 2,777-line power-management tree, generated with Asahi's official `pmgr_adt2dt.py` from the reconstructed ADT (661 pmgr devices). Split into `-nodes`/`-refs` for include structure; refs to 22 always-on (`no_ps`) parent domains stripped |
| `t6050.dtsi` | Boot-minimal SoC device tree (cpus/cpu-map, AIC3 @ `0x280400000` + event @ +`0x40000`, wdt, 3× pinctrl, 5× i2c, s5l-uart @ `0x505200000`, all reg/IRQ values from the ADT) |
| `t6050-j714s.dts` → `t6050-j714s.dtb` | Board file; **compiles clean with dtc** |

## What's still missing before Linux boots (in order)

1. **A way to install m1n1.** The stock installer hard-refuses chip `0x6050`
   (`main.py` `CHIP_MIN_VER`) and the OS packages only support macOS 12.3/13.5
   firmware. Manual path: the stub container already exists on disk4
   ("Linux", 256 GB). Deploying m1n1 as a custom kernel requires booting into
   1TR (hold power), `bputil` reduced security + permissive mode, and
   `kmutil configure-boot -c m1n1.macho` — physical presence + admin password.
2. **Unknown: does m1n1 even start on M5?** M4 bring-up stalled on Apple's
   changed non-macOS boot mode + SPTM (Secure Page Table Monitor). Whatever
   blocks M4 likely blocks M5 the same way. This is the actual research
   frontier — track `AsahiLinux/m1n1` commits mentioning t8132/t6040/t6050.
3. **Kernel support:** `apple,sotra-m`/`-p` cpufreq + CPU-start (spin-table via
   `cpu-impl-reg`, present in the ADT), AIC3 binding for t6050, then the long
   tail: NVMe (ANS, `iop,ascwrap-v6`), USB, SMC, display. The dtb here covers
   the serial-console-boot subset only.
4. **Dev loop:** the Asahi way is m1n1 proxy mode — second Mac connected over
   USB-C running `proxyclient` against m1n1. No display/NVMe needed to start.

## Good news found along the way

- Upstream m1n1 already names this exact chip (M5 Pro Sotra) — the Asahi team
  has silicon in hand; public bring-up has begun.
- UART/GPIO/WDT/DART are all old IP blocks (`uart-1,samsung`, `gpio,t8101`,
  `dart,t8110`) — existing drivers apply.
- AIC3 (`aic,3`) driver already exists in m1n1 and has a t8122 kernel binding.

## Reproduce

```sh
python3 plist2adt.py adt-m5pro-mac17,9.plist adt-m5pro.bin
# venv with construct+pyserial:
python m1n1/proxyclient/tools/pmgr_adt2dt.py adt-m5pro.bin > t6050-pmgr.dtsi
cc -E -nostdinc -I <dt-bindings> -I . -undef -x assembler-with-cpp \
   t6050-j714s.dts | dtc -I dts -O dtb -o t6050-j714s.dtb
# m1n1: make USE_CLANG=1 RELEASE=1 (needs brew lld + rustup aarch64-unknown-none-softfloat)
```

---

## 2026-08-16 — status after the probe campaign

**Where we are.** Bare-metal chainload reaches past `tick_init` and then goes
silent forever (Apple logo, no text). Confirmed by coloured-band probes:
kernel entry OK, `paging_init` OK, `init_IRQ` OK, `tick_init` OK *after* two
`aic_init_cpu` patches.

**Image patches in `Image-q-fiqfix.bin`** (all byte-verified; base is the
pristine `Image-asahi`):

| file offset | value | site |
|---|---|---|
| 0xbbc0ac | d503201f | `aic_init_cpu+0x3c` — nop `b.eq` into the EL2 block |
| 0xbbc0c4 | 14000004 | `aic_init_cpu+0x54` — skip UPMCR0 read |
| 0x010530 | d503201f | `aic_handle_fiq+0x48` — nop `b.eq` into EL02 block |
| 0x010544 | 14000005 | `aic_handle_fiq+0x5c` — skip UPMCR0 uncore check |

**Corrections to earlier assumptions.**

- The FIQ-handler patches are *not* self-defeating. At EL2 with VHE (E2H=1),
  `mrs cntp_ctl_el0` reads the **EL2** physical timer — the kernel's own tick.
  That check sits at `aic_handle_fiq+0x20`, before the `CurrentEL` test, and
  routes to hwirq 0 = `AIC_TMR_HV_PHYS` = the DT's `"hyp-phys"` PPI, which is
  exactly what a VHE kernel requests. The nopped EL02 block serves *guest*
  timers only. `aic_fiq_clear_mask` (0xbbbc48) writes VM_TMR_FIQ_ENA only for
  hwirqs 2/3; the HV timers have no mask bits. The ack path is intact.
- "UPMCR0 and VM_TMR reads are fatal" was never isolated — both `aic_init_cpu`
  patches were applied together. Supporting evidence for UPMCR0 specifically:
  `features_m4` (chickens.c:112, used for Sotra at :164) sets
  `uncore_version = UNCORE_NONE`, i.e. m1n1 deliberately never touches UPMCR0
  on M4-class cores. The other fatal register in that block may be ICH_HCR
  (plausibly no vGIC), not VM_TMR.
- The "SError in a driver initcall" class is nearly empty: `PINCTRL_APPLE_GPIO=m`
  and the boot images carry **no initramfs**, so no `=m` driver ever probes.
  The whole initcall surface is apple-pmgr pwrstate, wdt, simpledrm, fbcon.
  m1n1's `pmgr_init` already reads all 661 non-virtual PS registers without
  dying, so the 301 Linux pwrstate probe reads are proven safe.
- Framebuffer plumbing is correct: `dt_set_fb` (kboot.c:180-253) fills reg/
  geometry, sets format `x2r10g10b10`, and **deletes** `status`, enabling the
  node. `fbcon=nodefer` correctly counters `FRAMEBUFFER_CONSOLE_DEFERRED_TAKEOVER=y`.
  The fb at 0x10fd310c000 is outside m1n1's declared memory fence — required.

**Leading hypothesis: timer FIQs are never delivered to EL2 at all.** Nothing
on this machine has ever demonstrated FIQ delivery — m1n1 polls `CNTPCT` and
never uses timer interrupts. A machine that already firewalls the CPU-start
registers from EL2 gating FIQs too is entirely in character. Symptom matches:
boot continues past `time_init` on wakeup-driven scheduling until the first
timer-based wait in an initcall, then parks in WFI forever.
Runner-up: the `IPI_SR_EL1` **read** at `aic_handle_fiq+0x18` — the one sysreg
in the patched path that m1n1 only ever *writes*, never reads.

`proxy-kit/fiqtest.py` settles both with **no reboot**: it arms the EL2 phys
timer for 1ms over the live proxy and reads back `CNTP_CTL_EL0`.
7 = delivered and handled by m1n1's `exc_fiq`; 5 = fired but no FIQ taken
(hypothesis confirmed, and the bug is below EL2). `exc_fiq` prints
"Exception: FIQ" at exception.c:400 *before* it reads IPI_SR (:434) and PMCR0
(:427), so a death mid-test with that line printed isolates the runner-up.

## The hypervisor channel (the real fix for the debugging loop)

Debugging at one bit per reboot is what made the last twenty boots worthless.
m1n1's **hypervisor mode** replaces it: m1n1 stays resident at EL2, Linux runs
as an EL1 guest, and m1n1 traps the whole uart0 MMIO page
(`hv_map_vuart`, src/hv_vuart.c:144) to emulate a Samsung/s5l UART, streaming
the guest kernel log back over the same USB proxy link. Guest exceptions are
decoded with ELR/FAR and symbol names. This also sidesteps the EL2 grief
wholesale — UPMCR0, VM_TMR_FIQ_ENA and KVM init are what a hypervisor is for —
so the guest uses the **unpatched** kernel.

Verified against `adt-real-t6050.bin` before first run:

- uart0 base `0x505200000`, IRQ 1359 — matches our `serial0` node exactly
- chip-id `0x6050`; PMGR `UART0`, `ATC0_USB`, `ATC0_USB_AON` all present
  (`map_essential` hooks them, so `power-domains = <&ps_uart0>` is safe)
- `/defaults` node present, uart0 `AAPL,phandle` = 0x285
- hv is compiled into our m1n1 build ("HV: ECV enabled", `P_HV_MAP_VUART`)
- proxyclient `m1n1.hv` imports with only the vendored deps in `proxy-kit/lib`

One source change was needed: `proxyclient/m1n1/hv/__init__.py` had no T6050 in
its CPUSTART table. Added `0x6050` to the `0x88000` tuple, mirroring
src/smp.c:299-301. `hv.sh` reapplies this idempotently.

Artifacts: `t6050-j714s-hv.dts`/`.dtb` (serial0 enabled, `stdout-path`,
`earlycon=s5l,0x505200000 console=ttySAC0 keep_bootcon debug ignore_loglevel
maxcpus=1`), `guest-hv.bin` = m1n1.bin + bootargs line + hv DTB + gzipped
`Image-asahi`, `proxy-kit/hv.sh`.

**Do not chainload before running the hv.** On locked-sysreg chips RVBAR still
points at the 1TR-installed image, so secondaries would reset into a stale m1n1.

---

## 2026-08-16 (later) — VM_TMR_FIQ_ENA is WRITE-ONLY-UNDEF on T6050

**The headline hardware finding of the project so far.** On Sotra,
`SYS_IMP_APL_VM_TMR_FIQ_ENA` (`S3_5_C15_C1_3`) accepts **reads** and rejects
**writes**. `MRS` returns `0xf`; `MSR` raises an undefined-instruction
exception (ESR `0x2000000`, EC=0, IL=1, FAR=0).

Evidence is direct and unambiguous, from the running m1n1 image dumped off the
machine over the proxy (`m1n1-fault.bin`, window starts at rel 0x14000):

```
0x0155b4: d53df16a  MRS s3_5_c15_c1_3, x10   <- read, executed fine
0x0155b8: 540000a1  b.ne 0x155cc             <- taken
0x0155c0: d51df169  MSR s3_5_c15_c1_3, x9    <- write, branched over
0x0155cc: 2a1f03e9  mov w9, wzr
0x0155d0: b27f014a  orr x10, x10, #2
0x0155d4: d51df16a  MSR s3_5_c15_c1_3, x10   <- FAULTED
```

Same register, same exception level, twenty bytes apart: read continues, write
dies. Caveat: only the one write was actually attempted (the `0x155c0` write
was branched over), so "all writes UNDEF" vs "only some values/states" is not
yet distinguished — that needs a guarded proxy test.

### Corrections this forces

- **"Reading UPMCR0 / VM_TMR_FIQ_ENA is fatal on Sotra" is FALSE.** Probed all
  21 IMP-DEF registers `hv_start` touches with `GUARD.SKIP`: every one reads
  cleanly. `UPMCR0` = 0, `VM_TMR_FIQ_ENA` = 0xf, `SPRR_CONFIG`, `GXF_CONFIG`,
  `AMX_CTL`, `APVMKEY*`, `APSTS` all present. The four Image patches were built
  on a false premise and must be re-derived around *writes*, not reads.
- The one patch that ever changed observable behaviour — nopping the `b.eq`
  into the EL2 block of `aic_init_cpu` (0xbbc0ac) — happens to remove a
  **write** to VM_TMR_FIQ_ENA. Right fix, wrong reason.
- Timer FIQ delivery to EL2 works (see previous section). Not the bug.
- Earlier symbol attribution of rel 0x155d4 to `hv_start+0x148` was made
  against the local *dirty* build and is **invalid**: the M5 runs stock
  `88a9821`, and the bytes at that address differ between the two binaries.
  Always resolve running-image addresses against `m1n1-running.bin`.

### Method note that made this possible

Debugging by coloured band was costing one bit per reboot. Two things fixed it:
`GUARD.SKIP` + `p.get_exc_count()` lets the proxy probe unknown registers
without killing the machine, and `iface.readmem` can pull the *running* binary
back for disassembly. Both are free and repeatable within one m1n1 session.
Chunk bulk reads at 64 KB — a single 2 MB `readmem` drops the CDC link
("Device not configured"); the ADT's 720 KB fetch is fine, so the ceiling is
somewhere between.

### Operational reality

The machine running Claude **is** the M5. Every proxy session costs the
operator a full reboot cycle (macOS -> m1n1 -> run -> macOS to report). Batch
every diagnostic into ONE script per trip. Host access for staging and log
retrieval: `ssh -i ~/.ssh/id_ed25519_azahi PRIVATE-USER@PRIVATE-LAN-ENDPOINT-REMOVED`, tree `~/azahi/`.

### Open

- Is the write UNDEF unconditional, or value/state dependent?
- The hv fix must live in the **host** m1n1, which is the stock 1TR-installed
  boot.bin — so either a 1TR trip, or chainload-then-hv (RVBAR/secondaries
  caveat, src/smp.c:127-131).
- **CNTFRQ_EL0 = 1 GHz** (measured: 208325047 ticks in 0.208 s), not the
  24 MHz of every prior Apple chip. Effect on `arch_timer` unanalysed.

## 2026-08-16 (later): VM_TMR_FIQ_ENA is write-UNDEF — analysis + prepared fix

**The hv UNDEF is decoded.** rel 0x155d4 = the `reg_set(SYS_IMP_APL_VM_TMR_FIQ_ENA_EL2,
ENA_P)` write in `hv_update_fiq` (src/hv_exc.c:158), reached from `hv_exc_exit`
(:429) on the first guest exception. The faulting MSR wrote back 0xf|2 = the SAME
value it read (reg reads 0xf) — so the UNDEF is value-independent. MRS works, MSR
UNDEFs: read-only register. One datapoint, taken with E2H=1 (hv active);
`proxy-kit/vmtmrprobe.py` (NEW) sweeps all write values + neighbours in one session.

**Fix built and compile-tested:** `m1n1-vmtmr-ro.patch` (hv_exc.c only) — on
T6050/T6051 hv_update_fiq masks pending guest timers by injecting IMASK into
CNTP/CNTV_CTL_EL02 (architectural, works from EL2) and the trapped guest CTL
reads/writes hide/drop the injected bit. Artifacts: `m1n1-vmtmrfix.bin`
(zero-padded for clean bare chainload) + `.macho`. Runner: `proxy-kit/hv-fixed.sh`
(chainload fixed m1n1, then hv.sh — no 1TR trip needed; the stale-RVBAR chainload
warning is moot while CPU-start writes are ignored, smp.c:127 only warns).

**Kernel Image (77398016 B): ALL VM_TMR_FIQ_ENA sites** (MSR = fatal if RO):
aic_init_cpu+0xa4 (file 0xbbc114, MSR), aic_fiq_set_mask+0x2c/0x44 (0xbbb63c/0xbbb654),
aic_fiq_clear_mask+0x28 (0xbbbc70), reads at aic_handle_fiq+0x7c, aic_init_cpu+0x94,
set_mask+0x20/0x38, clear_mask+0x1c/0x34. Patch verdicts:
- **0xbbc0ac KEEP** (new reason: skips the EL2 block whose VM_TMR *write* 0xf→0xc
  UNDEFs, plus untested ICH_HCR_EL2 access — not the reads, which are fine)
- **0xbbc0c4, 0x010530, 0x010544 REVERT** (premise dead: UPMCR0/VM_TMR reads are
  safe; UPMCR0=0 means the guarded writes are naturally skipped)
- unmask (clear_mask) never writes while reg=0xf (bits already set); first KVM
  guest would hit set_mask → UNDEF. Bare metal: boot-safe, KVM-unsafe.

**1 GHz CNTFRQ: benign.** ARMv8.6 mandates CNTFRQ=1 GHz; arch_timer takes the rate
from CNTFRQ (no DT override — decompiled t6050-j714s-hv.dtb/serial.dtb: timer node
has NO clock-frequency; the 24 MHz is the `clkref` fixed-clock for the UART).
Evtstream divider clamps at 15 (2^15/1e9≈33 µs, fine); sched_clock/udelay scale.
Not the silent-death cause. (Check later: is the s5l UART really fed 24 MHz on
this SoC — only matters for bare-metal ttySAC, not the hv vuart.)

### Confirmed: the faulting statement is hv_exc.c:158

Rebuilt pristine m1n1 at 88a9821 in a scratch git worktree with the same flags
(`make USE_CLANG=1 RELEASE=1`). The build is **byte-for-byte reproducible**.
Compared against `m1n1-running.bin`: 98.9% identical over the 960 KB dumped,
differences confined to data/relocation regions, and the three instructions of
interest match exactly. So the pristine build is the running binary for symbol
purposes — use `scratchpad/m1n1-pristine/build/m1n1.elf` to resolve any address.

```
0x155a8 -> hv_start + 0x188      (NOT +0x148; that came from the dirty build)
0x155b4 -> hv_start + 0x194
0x155d4 -> hv_start + 0x1b4      <- the UNDEF
```

The code is `hv_update_fiq()` (src/hv_exc.c:149) inlined into `hv_start`:

| addr | insn | source |
|---|---|---|
| 0x155a8 | `MRS HCR_EL2` | hv_exc.c:151 |
| 0x155ac | `MRS CNTP_CTL_EL02` | hv_exc.c:154 |
| 0x155b4 | `MRS VM_TMR_FIQ_ENA` | read half of the `reg_set` RMW |
| 0x155b8 | `b.ne` | else-branch taken |
| 0x155c0 | `MSR` (`reg_clr`) | hv_exc.c:156 — branched over |
| 0x155d0 | `orr x10, x10, #2` | OR in `VM_TMR_FIQ_ENA_ENA_P` |
| 0x155d4 | `MSR VM_TMR_FIQ_ENA` | **hv_exc.c:158 `reg_set(...ENA_P)` — FAULTS** |

**The write was a no-op.** `reg_set` is read-modify-write; the read returned
`0xf` (matching the standalone probe on a different boot), `ENA_P` is already
set in `0xf`, so the faulting `MSR` wrote the register's own current value.
A write that changes nothing still UNDEFs — strong evidence the register is
wholly write-rejecting rather than value- or state-dependent.

This is not a one-off path: `hv_update_fiq()` is called on **every exception
exit** (hv_exc.c:429), so the hypervisor cannot work on this SoC until it is
resolved.

---

# 2026-08-16 — LINUX BOOTS ON APPLE M5 PRO

```
[    0.000000] Booting Linux on physical CPU 0x0000040000 [0x611f0641]
[    0.000000] Machine model: Apple MacBook Pro (14-inch, M5 Pro, 2025)
[    0.000000] arch_timer: cp15 timer running at 1000.00MHz (virt).
[    0.142988] 505200000.serial: ttySAC0 at MMIO 0x505200000 is a APPLE S5L
[    0.148552] [drm] Initialized simpledrm 1.0.0 for 10fd31e6880.framebuffer
[    0.178420] Console: switching to colour frame buffer device 378x118
[    1.240665] Kernel panic - not syncing: VFS: Unable to mount root fs
```

Full boot to the root-filesystem panic, 1.24 s. Kernel
`7.0.13-400.asahi.fc44.aarch64+16k`, 59 GB RAM detected, framebuffer console
live on the internal panel. Boot log: `logs/first-boot.log`.

Booted as an m1n1-hypervisor guest (host m1n1 = `m1n1-vmtmrfix.bin` chainloaded;
guest = `guest-hv.bin`). The kernel is the **pristine** `Image-asahi` — no Image
patches at all. Every fix lives in m1n1 or the device tree.

## The four T6050 problems that had to be solved

1. **`SYS_IMP_APL_VM_TMR_FIQ_ENA` writes UNDEF while the hv runs a guest**
   (reads fine; writes also fine in plain proxy context — state-dependent).
   Killed `hv_update_fiq()` (src/hv_exc.c:158) on the first guest exception.
   Fixed by `m1n1-vmtmr-ro.patch`: mask guest timers with `CNTx_CTL_EL02` IMASK
   instead. This is the real M5 silicon divergence.
2. **Secondary CPUs never start.** Guest CPUSTART write → `hv_start_secondary`
   blocks forever. Fixed with `run_guest.py -C 0` (guest sees only cpu0).
3. **PMGR power-state writes SError the host.** The hv replays guest PMGR writes
   onto real hardware (`map_essential` `wh()`), and upstream's replay *forces the
   domain on* — the fatal one was `ps_atc0_common`, parent of the ATC0 USB tree
   carrying the proxy link. Fixed by shadowing writes on chip 0x6050/0x6051.
   Also deleted the whole pmgr tree from the guest DTB: genpd's late sweep would
   otherwise have powered off display, SEP, ANS and the host's own console.
4. **Nobody was reading the guest console.** m1n1 exposes *two* CDC-ACM ports;
   the emulated uart0 comes out on the **second** one (src/hv_vuart.c:97-99) and
   `hv.sh` only opened the first. Run 2 was never silent — the entire kernel log
   went to an unopened device node. `hv.sh` now tees it to `guest-console.log`.

Also disabled for the guest: MTE/SME (`arm64.nomte arm64.nosme` — every
`GCR_EL1`/`TPIDR2_EL0` access traps to a host Python round-trip, one per context
switch) and cpuidle (`cpuidle.off=1` — the hv reads `CYC_OVRD` bit0 as "CPU
shutting down" and would tear down cpu0).

**1 GHz timer confirmed in Linux**: `cp15 timer running at 1000.00MHz`. ARMv8.6
mandates it; no DT override needed. Every prior Apple chip is 24 MHz.

## Next

Root filesystem. Fastest path to a shell: append `initramfs-asahi.img` to
`guest-hv.bin` (magic `m1n1_initramfs` + le32 size + cpio, see
`proxyclient/tools/run_guest_kernel.sh`) — note the image is zstd and may need
re-gzipping, and an initramfs re-opens the `=m` driver probe surface. Then a real
rootfs, then KDE.

---

# 2026-08-16 (later) — INTERACTIVE ROOT SHELL

```
Run /init as init process
systemd[1]: Running in initrd.
Booting initrd of Fedora Linux Asahi Remix 44 (Forty Four) dracut-108-7.fc44
...
:/root# uname -a
Linux fedora 7.0.13-400.asahi.fc44.aarch64+16k #1 SMP PREEMPT_DYNAMIC aarch64 GNU/Linux
:/root# cat /proc/meminfo | grep MemTotal
MemTotal:       59273024 kB
:/root# ls /sys/class/drm/
card0  card0-Unknown-1  version
```

systemd running as PID 1, full Fedora dracut initramfs, **interactive root shell**.
Log: `logs/userspace-shell.log`.

## What unlocked it

`kboot_set_initrd()` (src/kboot.c) now relocates the initrd to `0x10A00000000`.
m1n1 unpacks payloads into its heap, which sits BELOW the carveout-free window
advertised to the OS — Linux checked the initrd against the linear mapping,
found it outside, and **silently discarded it**:

```
initrd not fully accessible via the linear mapping -- please check your bootloader
```

then panicked with no root fs, looking identical to the no-initramfs case. The
kernel (0x10800000000) and FDT (0x10900000000) already had this treatment; the
initrd never did because we had never loaded one.

## The console is bidirectional — we can type into the guest

m1n1's vuart injects RX from the **second CDC port**, so writing to it drives
the guest's console:

```sh
printf 'uname -a\n' > /dev/cu.usbmodemPRIVATE      # the SECOND port
```

Guest output arrives on the same port (hv.sh tees it to guest-console.log).
This is a full interactive shell, not one-way logging — no keyboard driver
needed. `aic_set_sw` RX injection works fine on T6050.

## Where it stops

`initrd-switch-root.service` fails (no root device — no storage driver yet) and
dracut drops to its emergency shell. Expected. The initramfs is minimal dracut:
no coreutils, so `nproc`/`free`/`head` are absent. Use `/proc` and `/sys`.

## Next: KDE without a storage driver

59 GB of RAM and `CONFIG_RD_ZSTD=y` mean a full root filesystem can be shipped
as a giant initramfs and run entirely from RAM — skipping NVMe/ANS/SART/RTKit
completely. `fedora-minimal.zip` is in the project root. KDE would render on
simpledrm with software GL. The genuinely hard remaining piece is **input**
(built-in keyboard/trackpad), not storage or display.

---

## Input hardware: dockchannel MTP, not SPI HID

From `adt-real-t6050.bin`:

```
/arm-io/dockchannel-mtp/mtp-transport/keyboard
/arm-io/dockchannel-mtp/mtp-transport/multi-touch
/arm-io/spi2            reg=0x505108000  irq=[1369]
/arm-io/pwm0/kbd-backlight
```

The built-in keyboard and trackpad are behind the **MTP coprocessor over
dockchannel**, not SPI HID. Drivers already exist and ship in the initramfs —
`dockchannel-hid.ko` and `apple-dockchannel.ko` — so this is device-tree work,
not driver work. Caution: the host m1n1 uses dockchannel for its own console
("Initialized dockchannel UART at 0x288e28000"); check for contention.

**Everything needed is already a module.** `find /lib/modules -name "*apple*"`
in the guest lists spi-hid-apple, nvme-apple, apple-sart, apple-rtkit-helper,
apple-dart, appledrm, dwc3-apple, phy-apple-atc, apple-dockchannel,
pinctrl-apple-gpio and more. Nothing probes because the guest DTB is 4.4 KB and
describes only CPU/AIC/timer/serial/framebuffer. **The remaining work is mostly
device-tree authoring against the ADT.**

## Driving the guest shell from the host

`~/azahi/gsh.py 'cmd'` (one-shot) and `~/azahi/gshell.py` (interactive REPL).
Both write to the **second** CDC port a character at a time — bursting a whole
line duplicates ~1 char per line, because the vuart RX injection races the
guest draining its FIFO. Replies are read out of `guest-console.log` by byte
offset (holding the file open sits on a stale EOF while `tee` appends).

## THE GOAL, restated

The user wants the M5 to boot Linux **standalone — no second Mac, no cable** —
and show a KDE desktop. They accept that wifi, sound, GPU acceleration, SMP and
suspend are broken. So the priority order is:

1. **Bare-metal boot** — the blocker for everything untethered. Working theory:
   bare metal Linux runs at EL2 and `aic_init_cpu` writes VM_TMR_FIQ_ENA at
   Image-asahi offset `0xbbc114`, which UNDEFs on this SoC. Under the hv Linux
   runs at EL1 and never does. Fix is either entering the kernel at EL1
   (kills every EL2-only landmine at once, keeps the kernel pristine) or
   patching the 3-4 MSR sites (0xbbc114, 0xbbb63c, 0xbbb654, 0xbbbc70).
2. **Input** — dockchannel/MTP DT nodes.
3. **RAM rootfs** — 2-3 GB desktop image baked into boot.bin; no storage driver
   needed. Install once via 1TR, boots by itself thereafter.
4. **KDE** on simpledrm with software rendering.

Note bare metal has **no vuart** — observability drops back to text on the M5's
own panel (console=tty0 + fbcon works). Develop and test bare-metal images while
still tethered by chainloading them, and only do the 1TR install once one boots.

**Not realistically fixable by us:** the GPU. Asahi's driver is a multi-year
per-generation effort and M5's GPU is undocumented. KDE will be software
rendered.

---

# 2026-08-16 — FULL FEDORA BOOTS FROM RAM

```
Welcome to Fedora Linux Asahi Remix 44 (Forty Four)!
[  OK  ] Reached target multi-user.target - Multi-User System.
[  OK  ] Reached target graphical.target - Graphical Interface.
[root@fedora ~]# 
== Fedora Linux Asahi Remix 44 (Forty Four) ==
/dev/loop0      3.9G  1.4G  2.2G  38% /
Mem:              56 total    51 free
systemctl is-system-running -> running
card0  card0-Unknown-1
```

A complete Fedora system on the M5 Pro: real btrfs root mounted rw from a
loop device backed by RAM, systemd fully up, **no failed units**, root shell
via serial autologin. **No storage driver involved at all.**
Log: `logs/full-fedora-boot.log`.

## How the RAM root works

`guest-hv-ramroot.bin` (980 MB) = m1n1 + bootargs + DTB + gzipped pristine
Image-asahi + `m1n1_initramfs` + [stock dracut initramfs (zstd) ++ ramroot
cpio (zstd)]. The kernel unpacks **concatenated zstd cpio streams**, so the
second archive overlays the first — no repacking of the Fedora initramfs
(whose metadata cannot survive a round trip through macOS).

`ramroot/ramroot-setup.sh` runs as `ramroot.service` inside the initrd:
modprobe loop → losetup /dev/loop0 on `/ramroot/root.img` → probe for the
btrfs subvolume `root` → mount `/sysroot` → graft `sysroot-overlay` → systemd
switch-roots into it.

Build: `sh ramroot/build-guest-ramroot.sh [path/to/root.img]` (~9 s with a warm
`work/`). `ramroot/mkcpio.py` streams a newc cpio with uid/gid forced to 0 and
splits members over 4 GiB (`m1n1_initramfs` size field is le32, so the
compressed blob must stay under 4 GiB; patchable in payload.c if needed).

## Two autologins matter

The overlay installs `agetty --autologin root` drop-ins for **both**
`getty@tty1` (the panel — gives logind a seat0 + VT, which any Wayland
compositor requires) and `serial-getty@ttySAC0` (the vuart — how the host
drives the machine). Without the serial one the boot ends at `fedora login:`
and the image ships no known root password, so it is unreachable from the host.

## Iteration is now fully unattended

Killing `run_guest.py` makes the M5 reset and return to `Running proxy...` by
itself, so build → boot → read → fix cycles need no human. One transient seen:
`P_HV_START` dropped the CDC link once; a straight retry worked.

## Next: KDE

This image is Fedora **Minimal** — `fedora-minimal.zip` contains `root.img`
(3.9 GB btrfs, 1.28 GB used) and no desktop. KDE needs the Fedora Asahi Remix
44 **KDE** image fetched over the network (same release ⇒ same 7.0.13-400
kernel ⇒ modules match), then the same build with that `root.img`.
Then: `startplasma-wayland` on simpledrm with `LIBGL_ALWAYS_SOFTWARE=1`,
autologin on tty1, and `ramroot/uinject.py` (uinput keyboard/mouse driven from
the vuart) to give kwin a real seat without the MTP coprocessor.

---

## KDE attempt: the 4.24 GB image does not boot

Fedora Asahi Remix 44 **KDE** (`fedora-44-kde-202607221600.zip`, from
`https://alx.sh/installer_data.json`; same build stamp as the minimal image, so
the kernel matches) has a 14.2 GB `root.img`. Packed as a RAM disk that is a
3.93 GiB zstd blob — 77 MB under the 4 GiB ceiling the `m1n1_initramfs` le32
size field imposes.

**Two failures, in order:**

1. **`cat: write error: No space left on device`**, 14 s in. The image exceeds
   the 4 GB cpio member limit so it ships as 5 chunks, and
   `ramroot-setup.sh` reassembled them in `/run` — a small tmpfs, despite
   56 GB of free RAM. Everything after that was systemd waiting forever on
   `dev-loop0.device` (21 minutes of a dead machine, which I misread twice as
   slow progress — **grep for errors before believing a spinner**).
   Fixed: the join now gets its own tmpfs sized at half of MemTotal.

2. **The machine dies the instant the guest starts.** Upload completes 100%,
   then `Jumping to entrypoint at 0x10018984800` and the CDC link drops; the
   guest console produces zero bytes. Reproduced twice at this size. The
   980 MB minimal image boots fine from the same base, so it is size-related.

   Concretely, `hv.load_raw` puts the guest at `u.heap_top`:
   `Guest region start: 0x10018984000`, size `0xfd1a4000` → ends
   `0x10115B28000`. That **overlaps the memory window we advertise to Linux**
   (`0x1010A960000..0x10F4AB00000`, see `dt_set_memory` in src/kboot.c) by
   ~180 MB. Root cause not yet isolated — the death is at guest entry, before
   Linux allocates anything.

## Better architecture: virtio-9p instead of a giant RAM disk

Everything needed is already present, so the rootfs need not be in the boot
image at all:

- `src/hv_virtio.c` in m1n1, `Virtio9PTransport` in
  `proxyclient/m1n1/hv/virtio.py`, and `run_guest.py -v <hostpath>:<tag>`
- guest kernel has `CONFIG_NET_9P=m`, `CONFIG_NET_9P_VIRTIO=m`,
  `CONFIG_9P_FS=m`, `CONFIG_VIRTIO_MMIO=m` — all shipped in the initramfs

Plan: keep the boot image small (dracut initramfs + setup script, ~90 MB, fast
to upload), export the host directory holding `root.img` over 9p, then in the
guest mount 9p and `losetup` the image directly off it. That removes the 4 GiB
size cap, the chunk-and-rejoin step, the RAM ceiling, and the oversized-guest
crash in one move. Cost: root I/O crosses USB at ~11 MB/s, so it will be slow
to start, but it is lazy — only what is read gets transferred.

Note this is a **tethered-only** option (9p needs the host), so it is a route to
proving KDE, not to the standalone goal. Standalone still needs bare-metal boot.

---

# NEXT SESSION — start here

State: Linux boots fully under the m1n1 hypervisor; full Fedora (minimal) runs
from RAM with a root shell. KDE image built but does not boot (see above).
Standalone boot not yet attempted.

## Ready to run, in priority order

**1. Bare metal (the standalone blocker).** `Image-baremetal.bin` is built:
pristine `Image-asahi` with the four `MSR VM_TMR_FIQ_ENA` sites NOPed
(0xbbc114, 0xbbb63c, 0xbbb654, 0xbbbc70 — each verified as that exact
instruction before patching). Needs a bare-metal DTB — `t6050-j714s-bare.dts`
exists but **does not compile yet**: it references `ps_uart0` while the pmgr
tree is deleted. Fix by adding `/delete-property/ power-domains;` to the
`&serial0` block, as `t6050-j714s-hv.dts` does. Then assemble
m1n1 + bootargs + dtb + gz(Image-baremetal) + initramfs and chainload it.
Observability is the M5's own panel only (`console=tty0`, no vuart bare metal),
so read it off the screen or photograph it.

**2. KDE via virtio-9p** (tethered, but small and fast to iterate). Export the
host dir holding the KDE `root.img` with `run_guest.py -v <dir>:kde`, mount 9p
in the guest, `losetup` the image straight off it. Removes the 4 GiB cap, the
chunking, and the oversized-guest crash. All pieces already present — see the
virtio-9p section above. KDE `root.img` is at
`ramroot/work-kde/root.img` (14.2 GB, already extracted).

**3. Input** — `uinject.service` is wired into the KDE overlay already
(synthetic keyboard/mouse via /dev/uinput on seat0). Drive it from the host with
`~/azahi/ginput.py move|click|key|type`. Real keyboard needs dockchannel/MTP DT
nodes; drivers already ship as modules.

## Running things

```bash
ls /dev/cu.usbmodem*                      # two ports = m1n1 is up
GUEST=~/azahi/guest-hv-ramroot.bin sh ~/azahi/hv-fixed.sh   # known-good Fedora
python3 ~/azahi/gshell.py                 # interactive guest shell
```

Known-good image: `guest-hv-ramroot.bin` (980 MB, Fedora minimal from RAM,
boots to a root shell). Use it to sanity-check the rig before trying anything new.

## Hard-won process lessons

- **Grep the log for errors before believing a progress spinner.** A dead
  machine spun on `Job dev-loop0.device/start running` for 21 minutes while
  `cat: write error: No space left on device` sat 14 s into the same file.
- Killing `run_guest.py` usually makes the M5 reset back to `Running proxy...`
  by itself — but not always; sometimes it needs a physical power cycle.
- Don't run a proxy connection test immediately before `hv-fixed.sh`; it leaves
  the port mid-handshake and the chainload then times out.

---

# 2026-08-29 — the internal SSD is reachable without kernel patches

Goal changed this session: **KDE running from the internal SSD**, using the
Linux partition that already exists. The user's constraint is explicit —
*"do not wipe it i need to use the linux partition my mac install should not be
touched"*. No repartitioning, ever. Verify the target by identity before any
write, and read before writing at all.

## The finding that unblocks storage

The Fedora Asahi rootfs ships **Apple's official device trees for every SoC up
to M3** in `/usr/lib/modules/$(uname -r)/dtb/apple/` (104 files). Pulling
`t6030-j514s.dtb` — the **M3 Pro 14"**, the closest structural analogue to
j714s — gives a complete, known-good NVMe template.

Better: asked the running kernel for its own match tables (`modinfo -F alias`).

| driver | binds |
|---|---|
| `nvme-apple` | `apple,t8103-nvme-ans2`, `apple,nvme-ans2` |
| `apple-sart` | `apple,t6000-sart` |
| `apple-dart` | `apple,t8110-dart` |
| `apple-dockchannel` | `apple,dockchannel` |

**Nothing requires a `t6050-` compatible string.** The SSD *and* the built-in
keyboard are reachable with a pristine kernel — device-tree work only. This was
the single most likely blocker and it is gone.

## T6050 ANS/NVMe address map

From the real ADT (`adt-real-t6050.bin`): `/arm-io/ans` reg[3] = `0x21dcc0000`
(nvme), `/arm-io/sart-ans` = `0x21dc50000`, `compatible = iop,ascwrap-v6`,
`sart-version = 4`, `nvme-interrupt-idx = 4` → IRQ 2338, mailbox IRQ set
{1347..1350}.

The ADT does **not** expose the ANS mailbox. It is derived from an offset that
is identical on five generations:

| SoC | nvme | sart | mbox | nvme − mbox |
|---|---|---|---|---|
| t8103 | 0x27bcc0000 | — | 0x277408000 | 0x48b8000 |
| t6000 | 0x393cc0000 | 0x393c50000 | 0x38f408000 | 0x48b8000 |
| t6020 | 0x34bcc0000 | 0x34bc50000 | 0x347408000 | 0x48b8000 |
| t6030 | 0x38dcc0000 | 0x38dc50000 | 0x389408000 | 0x48b8000 |
| t6031 | 0x34dcc0000 | 0x34dc50000 | 0x349408000 | 0x48b8000 |

→ **T6050 mbox = 0x219408000**, coproc window = `0x219400000`. Derived, not yet
measured. `sart = nvme − 0x70000` holds and IS confirmed by the ADT.

Power domains, all in pmgr0 (`0x280600000`), offsets from the ADT-generated
`t6050-pmgr-refs.dtsi`: `fab6_soc` @0x138 (always-on) → `ans` @0x140;
`apcie_st0` @0x128 + `ans` → `apcie_sys_st0` @0x150. Same shape as t6030.

## ANS is power-gated — and the hv shadow blocks the guest from fixing it

`nvmeprobe.py` read `nvme+0x1300` (BOOT_STATUS) cold and took an **SError**
(`FAR 0x21dcc1300`, `ESR 0xbe000000`) that wedged m1n1 into a reboot loop and
cost a physical power cycle. The address was not wrong — the block was not
powered.

Two lessons:

- **`GUARD.SKIP` does not cover SErrors**, and it does not apply at all once
  m1n1 is sitting in hv context after a killed guest. Never read a possibly
  power-gated MMIO address "just to see". Check the PMGR PS_ACTUAL nibble
  first — PMGR is always-on and safe to read cold.
- The guest cannot power ANS itself. `map_essential` hooks only UART0 and the
  ATC USB domains, and for chip 0x6050 those hooks **shadow** writes. Every
  other PMGR register passes straight through to hardware.

Fix: power ANS on **host-side** before the guest starts, via m1n1's own
`pmgr_adt_power_enable` (walks the ADT parent chain). `run_guest.py -c` runs
code in the hv namespace immediately before `hv.start()`, which is exactly the
right window — no m1n1 rebuild needed. Wired into `hv.sh` behind `ANSPOWER=1`.

## New tooling

- **`~/azahi/gpull.py`** — pull a file out of the guest over the vuart,
  sha256-verified. The guest's stdout is full USB speed even though RX
  injection is 4 ms/char, so base64-to-console is the fast direction. Two traps
  it handles: the guest **echoes the command**, so end markers must be split
  (`==EO""F==`) or they match instantly; and the shell wraps output in OSC 3008
  sequences, so markers are not at line start.
- **`~/azahi/anspower.py`** — power ANS up and confirm the derived MMIO layout,
  refusing to touch ANS unless PMGR reports the domain active.
- **`~/azahi/waitboot.sh`** — retry the boot until the M5 answers. Device nodes
  can exist while m1n1 is wedged; only a completed proxy handshake is liveness.
- `build-guest-ramroot.sh` now takes `DTB=<name>`.

## Artifacts

`t6050-j714s-hv-nvme.dts/.dtb` (6336 B) and `guest-hv-nvme.bin` (979.8 MiB) —
the known-good RAM image with **only** the device tree swapped, so a failure
implicates the DT and nothing else.

## The ASC base: trust the ADT, not the cross-generation pattern

The `nvme_base - 0x48b8000` mailbox offset is exact on t8103, t6000, t6020,
t6030 and t6031 — and **wrong on T6050**. m1n1's own NVMe driver settles it:

- `src/nvme.c:309` — NVMe registers are ADT `/arm-io/ans` **reg[3]**
  → `0x21dcc0000` (agrees with the pattern, and with the DT of every reference SoC)
- `src/nvme.c:335` — `asc_init("/arm-io/ans")`, and `src/asc.c:41` takes
  **reg[0]** as the ASC base, `src/asc.c:53` puts the mailbox at `base + 0x8000`
  → ASC `0x219600000`, mailbox **`0x219608000`**, not `0x219408000`.

Searching the raw ADT for `0x219400000`/`0x219408000` finds **zero** hits, while
`0x219600000`, `0x219050000`, `0x21dcc0000` and `0x21dc50000` are all present.
The ASC genuinely moved on this SoC. `t6050-j714s-hv-nvme.dts` corrected.

## SART is version 4 — new, but v3 ops are accepted

`p.nvme_init()` failed cleanly with:

    sart: SART /arm-io/sart-ans has unknown version 4

m1n1 (`src/sart.c:186`) and Linux (`drivers/soc/apple/sart.c`) both top out at
**v3**; every SoC from t6000 through t6032 reports 3. T6050 reports 4.

Patched `src/sart.c` to route `case 4` to the v3 ops (local bring-up only,
never for upstream). Rebuilt as `m1n1-nvme.bin` — `make USE_CLANG=1 RELEASE=1`
works on the M1 Pro. The SART error is gone, so **v4 accepts the v3 register
layout**. This matters far beyond m1n1: our DT already declares the
`apple,t6000-sart` fallback, which selects `sart_ops_v3`, so **Linux needs no
change** — provided nothing later depends on a v4 difference.

## Why nvme_init() then wedged the machine (twice)

After SART passed, `nvme_init()` went silent — no exception, no recovery, dead
UART, physical power cycle required. The cause is structural:

    src/rtkit.c:637   while (rtk->iop_power != RTKIT_POWER_ON) { ... }

an **unbounded** wait. If ANS never answers on the mailbox, m1n1 spins forever.
So the hang means precisely "the coprocessor did not reply" — most likely the
mailbox base or the ANS boot state, not a fault. (`nvme_ensure_shutdown()`,
which would clean up an ANS left running by iBoot, is commented out at
`src/nvme.c:482`, so it never runs.)

**Process lesson, and it cost two reboots:** run the read-only survey BEFORE
the bring-up. `anspower.py` reads PMGR (always-on, safe cold), powers ANS only
if gated, re-checks PS_ACTUAL, and only then reads ANS MMIO — never attempting
the RTKit handshake. That probe was already written and sitting unused when
`nvme_init()` was called. Order of operations is the whole discipline here:
**PMGR read → power → PMGR verify → MMIO read → only then handshake.**

## ROOT CAUSE: the ANS fabric parent is CLOCK-GATED

The read-only survey finally caught it. After a fresh boot, with ANS powered by
iBoot and no PMGR write attempted:

    fab6_soc   0x280600138 = 0x00000244   target=0x4  actual=0x4
    ans        0x280600140 = 0x000000ff   target=0xf  actual=0xf
    apcie_st0  0x280600128 = 0x0f0000ff   target=0xf  actual=0xf

`ans` itself reports **ACTIVE**, yet reading `nvme + 0x1300` STILL faults.
`src/pmgr.h:13-15` gives the states:

    PMGR_PS_ACTIVE  0xf
    PMGR_PS_CLKGATE 0x4      <-- fab6_soc is here
    PMGR_PS_PWRGATE 0x0

**`fab6_soc`, the fabric ANS hangs off, is clock-gated.** A device domain can
read ACTIVE while the bus that reaches it is not clocked, so every access to
the ANS/NVMe MMIO window dies — which explains all three failures in one go:
the original SError, and both `nvme_init()` wedges (the coprocessor could never
answer the mailbox because its fabric was not clocked).

It also explains why m1n1's `nvme.c` never powers anything on: on t8103..t6031
`fab6_soc` is already ACTIVE at this point, so nobody ever needed to.

**The fix to try next:** call `p.pmgr_adt_power_enable("/arm-io/ans")`
UNCONDITIONALLY rather than only when `ans` reads gated — it walks the ADT
parent chain (`src/pmgr.c:151 pmgr_set_mode_recursive`) and will bring
`fab6_soc` to ACTIVE. `anspower.py` currently skips the call when `ans` already
reads 0xf, which is exactly the wrong test: **check the whole parent chain, not
the leaf.** Then re-read `nvme+0x1300`; if it returns `0xde71ce55` the entire
address map is confirmed and Linux can be pointed at it.

Note for the DT: `ps_fab6_soc` is marked `apple,always-on` in
`t6050-pmgr-refs.dtsi`, which tells Linux never to touch it. If it is genuinely
clock-gated at handoff, that property may be wrong for T6050 and the guest may
need to be allowed to raise it.

---

# 2026-08-29 (session 2) — RAM-root confirmed healthy; NVMe run trapped on a timer

## M1 DONE — full Fedora from RAM, verified over the vuart

`GUEST=~/azahi/guest-hv-ramroot.bin sh ~/azahi/hv-fixed.sh` reached:

```
Reached target multi-user.target - Multi-User System.
Reached target graphical.target - Graphical Interface.
login:
[root@fedora ~]# systemctl is-system-running
running                       <-- not "degraded"
7.0.13-400.asahi.fc44.aarch64+16k
/dev/loop0      3.9G  1.4G  2.2G  38% /
```

`/proc/partitions` = loop0 + zram0 only (no NVMe, as expected — no DT node).
`/sys/class/drm/` = card0 (simpledrm). No KDE (this is the minimal image).
The gpio fix is confirmed present: the DTB embedded in `guest-hv-ramroot.bin`
is byte-identical to `t6050-j714s-hv.dtb` with pinctrl/i2c disabled.

**Correction to the previous report:** the deployed `guest-hv-ramroot.bin` is
sha256 `288bc6d3c866f457…`, NOT `a172072800354b50…`, and it was never rebuilt —
but it does not matter, because the fix lives in the embedded DTB, and
`modprobe.blacklist=pinctrl_apple_gpio` is absent from the bootargs and is
redundant anyway (a disabled node cannot bind). Verify images by extracting
what is actually embedded, not by trusting a reported hash.

## M2 attempt — guest trapped writing CNTV_CTL_EL0

`HOSTM1N1=m1n1-nvme.bin ANSPOWER=1 GUEST=guest-hv-nvme.bin` died with an
unhandled trap from the guest:

```
Exception taken from EL1h
ESR: 0x6232f826  -> EC 0x18 (trapped MSR/MRS), MSR (write) x1, s3_3_c14_c3_1
```

`s3_3_c14_c3_1` = **CNTV_CTL_EL0** — the guest's virtual timer control. The hv
trapped the write and could not emulate it. This is precisely the path the
`m1n1-vmtmr-ro.patch` rewires (guest timer CTL accesses trap because
CNTHCTL.EL1TVT is set), so a regression there is the prime suspect.

**The run changed TWO variables at once** — host m1n1 (`m1n1-nvme.bin`, 15.1%
different from the known-good `m1n1-vmtmrfix.bin`) *and* the guest image. The
ramroot guest boots fine under `m1n1-vmtmrfix.bin`, and a DTB difference is
unlikely to cause a timer trap, so suspicion falls on the host binary.

**Next test, isolated:** `ANSPOWER=1 GUEST=~/azahi/guest-hv-nvme.bin
sh ~/azahi/hv-fixed.sh` with the DEFAULT host m1n1 (`m1n1-vmtmrfix.bin`). The
host does not need m1n1's SART v4 patch — m1n1's own `nvme_init()` must never
run (`src/rtkit.c:637` wedges forever); Linux's `apple.c` does the handshake.
`hv-fixed.sh` now takes `HOSTM1N1=<path>` to select the host image.

## Process note: a crashed guest can wedge the proxy

After that exception the two CDC ports still enumerated but the proxy stopped
answering (`UartTimeout: Expected 1 bytes, got 0`), so the next `hv-fixed.sh`
could not chainload. m1n1 was sitting in hv exception context. **This needs a
physical power cycle** — it is the one failure mode the host cannot clear.
Also: `sh run.sh -c "print(...)"` does NOT test the proxy, it just runs python
locally. Use a script that imports `m1n1.setup` (see `/tmp/pping.py`).

## ROOT CAUSE #2: `pmgr_adt_power_enable` can never power ANS on T6050

The `ANSPOWER=1` path reported success-shaped output that was actually total
failure:

```
ANS power: 18446744073709551615 18446744073709551615      <-- (u64)-1, twice
ps_ans = 0xff
```

`18446744073709551615` is `-1`. **Both calls failed**, and `ps_ans = 0xff`
(target 0xf / actual 0xf) made it look fine because the *leaf* was already
ACTIVE — the same trap as before: the leaf is not the thing that is gated.

Why it fails, verified offline against `adt-real-t6050.bin`:

```python
/arm-io/ans        clock-gates present=False
/arm-io/sart-ans   clock-gates present=False
```

`p.pmgr_adt_power_enable(path)` → `pmgr_adt_devices_set_mode` →
`pmgr_adt_find_devices` (src/pmgr.c:210-227), which reads the node's
**`clock-gates`** property and returns -1 if it is missing or empty. On
t8103..t6031 those nodes have it; **on T6050 they do not**. So that API can
never power ANS on this SoC, and it fails before touching any hardware.

**Fix:** drive the PS registers directly, mirroring `pmgr_set_mode`
(src/pmgr.c:85-96) — `mask32(addr, AUTO_ENABLE|WAS_CLKGATED|WAS_PWRGATED|
PS_TARGET, PS_TARGET=0xf)` then poll `PS_ACTUAL == 0xf`. Parent fabric first:

| domain | PS reg | note |
|---|---|---|
| `fab6_soc` | 0x280600138 | the one actually CLKGATEd (0x4) |
| `apcie_st0` | 0x280600128 | |
| `ans` | 0x280600140 | leaf; already reads ACTIVE |
| `apcie_sys_st0` | 0x280600150 | |

Implemented in `~/azahi/anspower_inline.py`, exec'd in the hv namespace by
`hv.sh`'s `ANSPOWER=1` branch immediately before `hv.start()`. It reads all
four (safe cold), powers parents first, verifies `PS_ACTUAL`, and only then
reads `nvme+0x1300` — expecting `0xde71ce55` to confirm the address map.

## The CNTV_CTL_EL0 trap was the host binary, not the guest

Re-running the SAME `guest-hv-nvme.bin` against the known-good
`m1n1-vmtmrfix.bin` produced **no exception at all** — Linux booted normally.
So the `Exception taken from EL1h / ESR 0x6232f826 / CNTV_CTL_EL0` seen earlier
came from `m1n1-nvme.bin` (15.1% different from the known-good build), not from
the NVMe device tree. **Do not use `m1n1-nvme.bin` as the hv host.** The host
does not need m1n1's SART v4 patch — m1n1's own `nvme_init()` must never run.

Method note: that run changed two variables at once (host binary AND guest
image) and cost a power cycle to untangle. Change one thing per boot.

## Where run 3 actually stopped

With ANS unpowered, the guest booted, systemd started, then froze mid-userspace
(last line `systemd-journald: Successfully sent stream file descriptor`).
`dmesg` showed **no nvme/ans/sart/rtkit lines at all** — the driver never got
far enough to print. The DTB is not at fault: the embedded one has proper
`sart@21dc50000`, `nvme@21dcc0000` (`apple,t6050-nvme-ans3`,
`apple,t8103-nvme-ans2`), a resolvable `mboxes` phandle and
`power-domains = <ans apcie0>` whose providers exist.

**A wedged guest wedges the proxy.** Both times the ports still enumerated but
`bootstrap_port` timed out, and only a physical power cycle cleared it.

---

# 2026-08-29 — THE SSD ANSWERS. The blocker was ADT address translation.

```
0x41dcc0000 = 0xf00100fd   <-- NVMe CAP register: the controller responding
0x419600000 = 0x00000001   coproc window alive
0x419601300 = 0x00000000   BOOT_STATUS (0 = coproc not booted; Linux does that)
0x41dc50000 = 0x000000ff   SART
```

Four reads, zero faults, with `fab6_soc` powered.

## The bug: every ANS address was missing the /arm-io translation

`/arm-io` applies a **+0x200000000** ranges translation. The ADT *stores* raw
addresses; the real ones come from `adt["arm-io"].translate(reg.addr)`:

| node | ADT raw | REAL | what we used |
|---|---|---|---|
| ans reg[3] (nvme) | 0x21dcc0000 | **0x41dcc0000** | 0x21dcc0000 ✗ |
| ans reg[0] (coproc/ASC) | 0x219600000 | **0x419600000** | 0x219600000 ✗ |
| sart-ans | 0x21dc50000 | **0x41dc50000** | 0x21dc50000 ✗ |
| uart0 (control) | 0x305200000 | **0x505200000** | 0x505200000 ✓ |

uart0 is the proof the method was known and applied correctly — the console
works precisely because it was translated. The storage map was recorded raw.

**Everything blamed on power was this.** "ANS is power-gated", the SErrors, the
two `nvme_init()` wedges, "the ASC moved on T6050" — all of it was reading
addresses that do not exist. `fab6_soc` genuinely was CLKGATEd (0x4 -> 0xf via a
direct PS write) and that still needs doing, but it was never the blocker.

**Rule: never use an ADT `reg` value without `adt["arm-io"].translate()`.**

## Correction: BOOT_STATUS lives in the coproc window

`reg-names = "nvme","ans"`; Linux's apple-nvme reads `APPLE_ANS_BOOT_STATUS`
(0x1300) off the **"ans"** reg (mmio_coproc), i.e. 0x419601300 — not nvme+0x1300.
Confirmed against the M3 Pro reference DT (`refdt/`), same structure.

## Guard notes (cost two power cycles)

- `p.set_exc_guard()` from a script is **pointless for read32/write32**:
  `src/proxy.c:157` sets `exc_guard = GUARD_MARK` itself for every P_READ*,
  overriding it. That is why `GUARD.SILENT` never suppressed anything.
- A faulted proxy read therefore returns **0xabad1dea** (low half of
  GUARD_MARK's `0xacce5515abad1dea`). Detect faults by value, not by guard.
- Each fault still prints a full `print_regs` dump over the UART, which desyncs
  the link and reboots the M5. It self-recovers to `Running proxy...` (m1n1 base
  changes each time, which is how you can tell it rebooted) — no power cycle
  needed, but probe ONE address per run.

## Fixed and deployed

`t6050-j714s-hv-nvme.dts`/`.dtb` now carry translated addresses
(`sart@41dc50000`, `mbox@419608000`, `nvme@41dcc0000`). The DTB was spliced into
`guest-hv-nvme.bin` in place (same 6336-byte size) and deployed to `~/azahi/`.
`~/azahi/anspower_inline.py` powers `fab6_soc` by direct PS write and probes the
translated addresses.

**Next:** `ANSPOWER=1 GUEST=~/azahi/guest-hv-nvme.bin sh ~/azahi/hv-fixed.sh`
with the DEFAULT host m1n1. Expect `nvme0n1` in `/proc/partitions`. Then, before
anything else, identify the Linux partition **read-only** by UUID/label.

# 2026-08-29 — "ANS did not boot" root-caused: SART v4 moved PADDR/SIZE. Hv shim written.

With translated addresses, apple-nvme got a real RTKit HELLO ("protocol
version 12") then `apple_rtkit_boot` timed out (-62 = -ETIME) and teardown
printed `apple-sart ... entry [paddr: 0x1010c800000, size: 0x8000] not found`.

## Evidence chain (all from the still-running guest, no reboot)

- `/proc/interrupts`: mbox-recv (hwirq 1350) fired exactly **4** times,
  mbox-send (1347) 0. No storm → 1350 really is recv-not-empty; the mailbox
  DT (ascending 1347..1350 name order) is **correct**, suspect closed. The
  message flow demonstrably reached the coproc's buffer-request phase.
- Unbound apple-sart (`echo 41dc50000.sart > .../unbind` releases the
  IO_STRICT_DEVMEM claim), dumped the SART block from the guest via /dev/mem
  with aligned 32-bit reads. Result at 0x41dc50000:

```
+0x00: ff ff ff ff ea ff ff ea      <- flags, entries 0-7 (entry 6 = Linux's write)
+0x40..0x5f: all zero               <- v3 PADDR window: RAZ, dropped Linux's write
+0x60: 286700 28cdc0 28c614 28c634 288374 10fff260 0 10000028   <- v4 PADDR (<<12)
+0x98: 8                            <- Linux's v3 SIZE(6) write, landed as v4 PADDR(14)
+0xc0: 1ff 3f 3 33 3 33 0 24f      <- v4 SIZE (<<12)
```

## The v4 layout (verified by three independent consistencies)

FLAGS @0x00+4i (unchanged from v3), **PADDR @0x60+4i**, **SIZE @0xc0+4i**,
0x40..0x5f is a hole. Proof: (1) iBoot's entries only pair up this way —
entry 7 = paddr 0x10000028000 (just above DRAM base 0x10000000000), size
0x24f000, flags 0xea; entry 5 = 0x10fff260000 (top-of-DRAM carveout);
(2) Linux's three v3 writes for entry 6 landed exactly where the layout
predicts (flags stuck at 0x18, paddr lost in the hole at 0x58, size landed
at 0x98 = v4 PADDR(14), inert because FLAGS(14)=0); (3) the teardown
"entry not found" is the v3 readback of that wreckage (paddr 0, size 0x8000).

So the coproc was handed a syslog/crashlog buffer at 0x1010c800000 that SART
never actually allowed; its first DMA blocked; it stalled; rtkit boot timed
out. Everything else (RTKit v12, mailbox, hv MMIO replay — guest writes
demonstrably reached the hardware) is fine.

## The fix — in the hv, kernel stays pristine

No existing kernel compatible matches this layout (v2: config|size@0x00,
paddr@0x40; v3: 0x00/0x40/0x80) — a DT-only fix is impossible, but a kernel
patch is NOT needed: `map_essential` in `proxyclient/m1n1/hv/__init__.py`
(same place as the T6050 PMGR shadow) now traps guest accesses to
sart+0x40..0xbf and replays them at the v4 offsets (+0x20 for PADDR, +0x40
for SIZE). Guest DT keeps `apple,t6000-sart`; FLAGS accesses stay
passthrough. Patched in BOTH trees (project + ~/azahi), logged as "SARTv4".

Also settled from the real ADT: /arm-io/ans iommu-parent = 633 = sart-ans's
own AAPL,phandle — no DART involved. sart-ans has sart-power-managed,
sart-power-reg-offset=0x13e8 (reads 0 in reg[0]) and two more reg windows
(0x41dd44000/0x4000, and 0x41dcc0000/0x4000 = the nvme base) — unused so far.

New read-only probe: `sh ~/azahi/run.sh ~/azahi/sartv4dump.py` (refuses to
run if fab6_soc isn't ACTIVE; decodes entries in the v4 layout).

**Next:** `ANSPOWER=1 GUEST=~/azahi/guest-hv-nvme.bin sh ~/azahi/hv-fixed.sh`.
Expect in hv log: `SARTv4 W v3+0x58 -> v4+0x78 = ...` lines; in dmesg: RTKit
init, then `ANS booted!`-path silence, `nvme nvme0: allocated 64 MiB host
memory buffer`-style lines, `nvme0n1` in /proc/partitions. Then identify the
Linux partition READ-ONLY by GPT UUID/label before anything else.

Residual unknowns, none blocking: the send-empty/send-not-empty pair is
still unverified (0 interrupts — only matters if the send FIFO ever fills);
the five low PADDR entries 0x286700000-ish look like non-DRAM windows
(coproc-side?); the 0x13e8 "power reg" semantics are unknown.

## Why the operator must power-cycle, and how to stop needing it

**There is no remote reset for the M5.** The only hardware path on Apple
Silicon is a USB-C Vendor Defined Message (what `macvdmtool` uses), and this
machine's Type-C port controller **rejects it**: `VDM failed (reply:
0x05ac80d2)`. macvdmtool predates M5. Worse, attempting it also kills the USB
proxy until a power cycle. No network exists on the M5 while m1n1 runs, and it
is a laptop on a battery, so there is nothing else to actuate. The physical
power button is the only actuator — always ask the operator explicitly.

**Most power cycles were self-inflicted.** `pkill`ing `run_guest.py` strands
m1n1 in hypervisor context: the two CDC ports still enumerate but the proxy
stops answering (`bootstrap_port` → `UartTimeout`), and only the button clears
it. There is a clean path that was sitting there unused —
`hv.run_shell()` installs (proxyclient/m1n1/hv/__init__.py:397-402):

```python
SIGUSR1 -> ExitConsole(EXC_RET.HANDLED)      # resume the guest
SIGUSR2 -> ExitConsole(EXC_RET.EXIT_GUEST)   # unwind the guest cleanly
```

So **stop guests with `sh ~/azahi/gstop.sh`** (SIGUSR2, falling back to SIGTERM),
never `pkill`. m1n1 returns to `Running proxy...` and stays usable.

Note an unhandled guest exception does NOT hang a detached run: `run_shell`
gets EOF on /dev/null stdin, returns None, and the caller maps that to
`EXC_RET.HANDLED` (:999). A guest SError *storm* therefore loops forever
printing register dumps — which is what looked like a hang. Use gstop.sh.

# 2026-08-29 — "ANS did not boot" fixed; next wall was M4+ NVMe register split (T8132). Fixed too.

The SARTv4 hv shim worked: RTKit boots, BOOT_STATUS reaches 0xde71ce55, "ANS
did not boot" gone. The guest then took 189 identical SErrors (L2C_ERR_STS
0x82, L2C_ERR_ADR **0x...41dce4908**, x22=0xde71ce55, x23=0x1300) — the driver
had just passed the BOOT_STATUS poll and hit APPLE_ANS_LINEAR_SQ_CTRL
(nvme_base+0x24908). Every AP access to ans reg[3] (0x41dcc0000) at offset
>= ~0x1210 bus-errors; base-page regs (CAP/CC/CSTS 0x0/0x14/0x1c) are fine.

## Root cause: M4+/T8132 split the NVMe register file (NOT a security lock)

Proven three ways:
1. **Hardware** (answin2.py): with all PS domains active, ans reg[9]
   (raw 0x25dcc0000 -> **0x45dcc0000**) reads clean at +0x0 (CAP 0xf00100fd),
   +0x1210, +0x1200/+0x1208, +0x24908 (=1), +0x2490c; ans reg[3]
   (0x41dcc0000) reads clean at the NVMMU block +0x28100/+0x28120 but ABORTS
   at +0x1210/+0x24908. So the two register files were physically separated.
2. **Upstream m1n1** commit `53f8ee9b54ba` "nvme: support T8132": *"M4 and later
   have additional regs and use a different mmio base for NVMMU ops. ans[3]
   becomes the reg for NVMMU ops while NVME ops move to ans[9]. Additionally,
   write ioq_{cmd,cqe}s to nvme+0x120{0,8} as otherwise IO cmds fail and ANS
   crash logs indicate the IOSQ base is 0."* Selected by ADT prop
   **nvme-secure-bar** (present on our /arm-io/ans). SARTv4 in the same tree
   (`9bfdf8aeca30`, *"As seen on M5 Pro/Max (T6050)"*) is CONFIG@0x00 /
   PADDR@0x60 / SIZE@0xc0 — **byte-identical to the layout we reverse-derived**.
3. **Linux**: series `apple-nvme-t8132` (lore, 2026-08-11, Yureka/Sven) adds
   compatible `apple,t8132-nvme-ans2` with reg-names "nvmmu","nvme","ans" and
   the same two deltas (separate NVMMU base + IOQ_CMDS/CQES writes). Still
   ANS2. Our Fedora kernel (7.0.13-400.asahi) predates it.

So: reg[3] = NVMMU only; reg[9] = the real NVMe BAR; M4+ additionally needs the
IO submission/completion buffers registered at nvme+0x1200 / +0x1208, which the
old t8103-flow driver never writes (ANS then DMAs from IOSQ base 0 -> the
teardown/SError we saw).

## Fix — DT + hv shim, kernel still pristine

- **DTB** (`t6050-j714s-hv-nvme.dts`): nvme node "nvme" reg now points at reg[9]
  (`nvme@45dcc0000`, reg <0x4 0x5dcc0000 0x0 0x60000>). Rebuilt (6336 B, 2 bytes
  changed) and spliced into `~/azahi/guest-hv-nvme.bin` at offset 0x110186
  (byte-verified).
- **hv shim** (`map_essential`, both trees identical): guarded by
  `nvme-secure-bar` on /arm-io/ans. (a) HW-remaps the guest's NVMMU page
  0x45de8000 -> real reg[3] 0x41de8000 (full speed, RESERVED tracer). (b) Hooks
  nvme9+0x28 (NVME_REG_ASQ, to learn the admin SQ buffer) and nvme9+0x2490c
  (linear admin SQ doorbell); on each admin doorbell it scans the 2-deep admin
  ring for Create-IO-CQ (op 0x05 -> IOQ_CQES 0x1208) / Create-IO-SQ (op 0x01 ->
  IOQ_CMDS 0x1200) and mirrors their PRP1 into the ANS IOQ regs before
  forwarding the doorbell. The hot-path IO doorbell (+0x24910) and NVMMU
  invalidate (+0x28118/+0x28120) stay untrapped/native.

## Status: BUILT + STATICALLY/PROBE-VERIFIED, hardware boot NOT yet run

The M5 proxy wedged on a mid-transfer CDC drop during the m1n1-nvme chainload
(two attempts; the 2nd loaded kernel+SEPFW+ADT then dropped at "Copying stub").
Not code-related — a flaky-link transfer failure that leaves the resident m1n1
unresponsive (ports enumerate, NOP times out) and does NOT self-recover.
**User: re-enter m1n1 on the M5 (fresh 'Running proxy...'), then re-run**
`sh ~/azahi/runnvme.sh` (or `HOSTM1N1=~/azahi/m1n1-nvme.bin ANSPOWER=1
GUEST=~/azahi/guest-hv-nvme.bin sh ~/azahi/hv-fixed.sh`).

Expect in hv.log: `SARTv4 W ...`, then `T8132 IOQ_CQES = ...` / `T8132 IOQ_CMDS
= ...` on admin-queue creation; in guest dmesg: RTKit init, NO SError, admin +
IO queue setup, and **nvme0n1 in /proc/partitions**. THEN identify the Linux
partition READ-ONLY by GPT PARTUUID/label before any write.

Probes added: `~/azahi/answin2.py` (t8132 model confirm), `~/azahi/sartv4dump.py`
(v4 layout), `probe/anscfgprobe.py`. All read-only, PMGR-verified, fault-safe.

## The infinite register scroll = m1n1's OWN nvme driver, not the guest

Photographed the M5 mid-storm and resolved the PC against our build:

```
(rel: 0x26c04)  ->  nvme_exec_command + 0xd8      "Exception taken from EL2h"
```

**EL2h = m1n1 itself**, not the guest. m1n1's built-in NVMe driver uses the
pre-T8132 register layout (nvme ops on ans reg[3]), which does not decode on
T6050, so every command SErrors; `src/rtkit.c:637` has no timeout, and the
exception handler recovers via GUARD_MARK and immediately re-faults — an
infinite loop of register dumps with nothing listening. Only a physical power
cycle clears it.

`nvme_init()` is reachable as proxy opcode `P_NVME_INIT` (src/proxy.c:587) and
from `proxyutils.get_gigalocker()`. Probe scripts that call it have been
renamed `DANGEROUS-*` in ~/azahi/. **Never call `p.nvme_init()` on this SoC.**

The normal boot path is clean: `runnvme.sh` -> `hv-fixed.sh` -> chainload.py +
hv.sh -> run_guest.py, plus anspower_inline.py which only does read32/mask32.
None of them touch m1n1's NVMe driver. Linux's `apple.c` does the handshake.

## KDE over virtio-9p: mounted successfully, compositor did not paint

Reached, on hardware: guest boots with virtio attached, mounts the host
directory over 9p, loop-mounts the 14.2 GB KDE `root.img` read-only, and the
KDE binaries are all present (`kwin_wayland`, `plasmashell`,
`startplasma-wayland`, `konsole`). No multi-GB upload involved.

**Three T6050 bugs in m1n1's virtio helper had to be fixed first**
(`proxyclient/m1n1/hv/virtutils.py`):

1. `collect_aic_irqs_in_use()` crashed with `AttributeError: interrupts` —
   several T6050 ADT nodes carry `interrupt-parent` but no `interrupts`, and
   `adt.__getattr__` raises rather than returning None. Guarded.
2. `usable_aic_irq_range()` had no entry for **`aic,3`** (T6050 is AIC v3), so
   `.get()` returned None and `alloc_aic_irq` iterated None. Added
   `range(0, 3104)` (m1n1 reports "AIC3 ... 3104/4096 IRQs").
3. **The real killer: allocation from the BOTTOM of the range.** The 9p device
   got **irq 1** — timer/FIQ territory — and MMIO at `0x200000000`, the base of
   /arm-io's translation window. The guest then died the instant it was
   entered: upload 100%, "Jumping to entrypoint", CDC link dead, zero guest
   output. **This is the same signature as the 4.24 GB all-in-RAM KDE image
   failure**, so that may well have been an IRQ/MMIO collision too rather than
   anything to do with size. Both allocators now take the TOP of the range
   (`virtio0 @ 0x586000000, irq 3103`), after which the guest booted normally.

`u9fs` is required by `Virtio9PTransport` (spawned over pipes, speaks 9P2000 —
mount with `version=9p2000`, NOT `9p2000.L`). Not in Homebrew; built from
source (github.com/unofficial-mirror/u9fs) into `~/.local/bin`.

**Where it stopped:** `ramroot/work-kde/kde-start.sh` (delivered *through* the
9p mount, since pushing a long script through the vuart one character at a time
is far too slow) overlays a tmpfs on the read-only rootfs, binds /dev /proc
/sys, unbinds fbcon to free DRM master, and chroots to run
`kwin_wayland --drm ... -- konsole` with llvmpipe. The framebuffer console did
go dark (fbcon released), but nothing painted, the guest console went silent,
and the M5 subsequently reset.

**Assessment:** even if the compositor starts, a desktop paging its files over a
USB-speed 9p link on ONE core with software rendering is likely unusable. The
faster route to a real KDE desktop is to finish the SSD: the corrected
`nvme@45dcc0000` DTB is built and deployed but has still never had a clean run.
