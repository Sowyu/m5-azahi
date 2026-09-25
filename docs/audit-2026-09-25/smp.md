# Secondary CPU startup on T6050 (M5 Pro)

Linux runs on CPU0 only. The other 17 cores never come online, and that is the
biggest daily problem now. This report is the offline diagnosis: why the stock
loader path does not start secondaries on this SoC, the smallest change with a
real chance of fixing it, and the one attended boot that tells the two live
hypotheses apart. No hardware was available. Evidence is the Mac17,9
kernelcache (build 26A428), the J714s ADT, the m1n1 source, the M4 Pro project
(damsleth/wallace), and the repo's own V1..V5 live checkpoints
(`research-archive/probe/CPU-CHECKPOINT.md`).

## What is already known, restated with sources

The M5 secondaries power on but never run loader code. iBoot and PMGR report
the core active: the recorded PS_ACTUAL goes 0x100 to 0x1f0, yet the core never
stores its reset-trace marker, across five loader builds (V1..V5,
CPU-CHECKPOINT.md). The person who added the initial T6050 port saw the same
thing: "the cores turn on (as can be seen in pmgr), but never start executing
our code" (AsahiLinux/m1n1 PR #610, commit `b2d3f5e`).

The stock start path is unchanged from what works on older chips. In m1n1
`src/smp.c`, `smp_start_cpu()` does two MMIO writes to the PMGR CPU_START bank
at `pmgr_reg + 0x88000`:

```c
write32(cpu_start_base + 0x4, 1 << (4 * cluster + core)); // "system enable"
write32(cpu_start_base + 0x8 + 4 * cluster, 1 << core);   // start the core
```

The private loader's `smp.c` is byte-identical to upstream here (it only adds
an early `AZAHI_ONE_CORE` return for T6050). The `0x88000` offset is right for
T6050: it is `CPU_START_OFF_T6031`, and the offline ApplePMGR analysis confirmed
T6050 `initRegGroups` maps this group at offset `0x88000`. The live addresses
line up exactly: ADT `/arm-io/pmgr` reg[0] is `0x80600000`, which resolves to
`0x280600000` with the arm-io parent range applied, so `cpu_start_base` is
`0x280688000` and the recorded live register `0x280688004` is `+0x4`.

The M4 result does not transfer. On the M4 Pro (T6040, also an SPTM SoC),
the same bare PMGR write starts all 14 secondaries: they enter m1n1, return
per-core heartbeats, and later enter Linux
(`scratch/pcie/wallace/evidence/2026-07-10-t6040-smp-writeup.md` and
`2026-07-29-t6040-SMP-14-CORES-UP.md`). So SPTM being resident is not by itself
the blocker, and the M4 fixes (park in WFE, reserve the CTRR SMP-RO region,
`idle=nop`) address a different failure: on M4 the cores execute and then lose
state at WFI, which is not what happens on M5.

## How macOS starts a core on this SoC (26A428)

The XNU path on this kernelcache is a chain of virtual calls that ends in a
PMGR register write, the same family of write the loader already does:

- `AppleARMCPU::startCPU` at `0xfffffe0008c89c6c` invokes the ADT
  `function-enable_core` platform function (the `/cpus/cpuN` `function-enable_core`
  property, function tag "Core", arg 1).
- That resolves to `ApplePMGRFunctionEnableCPUCore::callFunction` at
  `0xfffffe000988483c`, which tail-calls `ApplePMGR::enableCPUCores` at
  `0xfffffe000985bafc`.
- `enableCPUCores` calls `ApplePMGR::configMiscCores` at `0xfffffe000985b3d4`,
  which does the actual per-core register programming through the PMGR RegMap
  writer `writeReg32` (T6050 override `AppleT6050PMGR::writeReg32` at
  `0xfffffe0009cc60f8`, vtable slot 0x1060).

So the OS does not start a core through a magic secure call here: it writes
PMGR registers, like m1n1 does. Two things stand out, though:

- `PE_cpu_start_from_kext` at `0xfffffe000c40c484` is a panic stub
  ("PE_cpu_start_from_kext unimplemented", `AppleARMSMP.cpp`). The classic
  kext-driven CPU-start entry is gone from this build; core bring-up is wired
  through the platform-function and SPTM machinery instead.
- The kernel is an SPTM kernelcache (segments `__DATA_SPTM`,
  `__TEXT_BOOT_EXEC.__bootcode`, and a large `sptm_*` symbol set). The reset
  entry and exception-level bootstrap of a starting core run in the guarded
  domain, not in the OS.

`configMiscCores` writing PMGR is necessary but may not be sufficient on its
own once SPTM owns the reset vector. That is the crux below.

## Ranked diagnosis

### 1. The CPU_START "+0x4" enable register is not a plain RW latch, and the stock write clears the bit it needs. Loader-fixable. Medium confidence.

iBoot leaves `cpu_start_base + 0x4` holding `0x3fffe`, which is bits 1..17, one
per secondary (all 17 pre-enabled). The stock `smp_start_cpu()` then overwrites
`+0x4` with `1 << (4*cluster+core)`. For CPU1 that is `0x2`. The one recorded
live read of this register went from `0x3fffe` before the attempt to `0x3fffc`
after (CPU-CHECKPOINT.md, V1). That is the target core's own bit (bit 1) coming
back cleared, not set. The upstream comment calls `+0x4` "some kind of system
level startup/status bit. Without this, IRQs don't work." If that bit must stay
set for the core to run and the register latches or is write-1-to-clear on
T6050, then the stock write disables the very core it then tries to start with
the `+0x8` write. On older SoCs the same overwrite is harmless, which is why
this only bites here.

This is the one hypothesis a loader can act on. Candidate fix, in
`src/smp.c` `smp_start_cpu()`, gated on `chip_id == T6050 || chip_id == T6051`:
do not overwrite `+0x4`. Preferred form is to skip the write entirely and rely
on iBoot's `0x3fffe`, because if `+0x4` is write-1-to-clear then even an
`|=` of the target bit clears it. Second form is a read-modify-write OR. It is
about two lines behind a chip check.

Confidence is medium, not high: the evidence is a single recorded read pair.
`0x3fffe -> 0x3fffc` is also consistent with the hardware acking or consuming
the start request rather than the write breaking it. The attended test below
is designed to settle exactly this.

### 2. The secondary reset entry is owned by SPTM/firmware, not the per-core Apple reset vector. Not loader-fixable. Medium confidence.

The core may reset into a firmware-owned vector and park in a WFI loop, so the
PMGR power-on turns the domain on but nothing ever fetches loader code. Support:

- The CTRR-locked, secondary-only 48 KiB region is filled entirely with WFI
  (`0xd503207f`), verified across its whole range through `0x10004bbc000`
  (CPU-CHECKPOINT.md). Upstream identifies this same region on M4/A18/M5 as
  read-only to secondary cores (`s3_0_c11_c0_0/1`, PR #657) with unknown
  purpose. A WFI-filled RO region is what an unassigned core would park in.
- The recorded cluster doorbells read 0, and no secondary ever set its flag.
- The architectural reset vector on the boot core reads `RVBAR_EL2 =
  0x1fc08c000`, a firmware region, distinct from the per-core Apple reset
  register that holds the loader base. If secondaries fetch from the firmware
  vector rather than their impl register, no loader poke redirects them.
- `PE_cpu_start_from_kext` is a panic stub in 26A428; the OS starts cores
  through SPTM-mediated machinery.

Counter-evidence, which is why this is not ranked first: on M4 (also SPTM) the
bare PMGR write works, and on T6050 the checkpoints report CPU1's impl reset
register reads the loader base and is locked, i.e. iBoot did point it at the
loader. If that value is honored on reset, hypothesis 1 or 4 explains the
failure without SPTM. If it is shadowed by SPTM, this hypothesis holds.

If this is the cause, secondaries need Apple secure-monitor cooperation that
Linux cannot get from outside SPTM. A Linux-side workaround would need one of:
an SPTM CPU-boot call with a known ABI and accepted caller provenance (the
wallace SPTM work shows the SPTM dispatch ABI is reachable for NVMe/SART but
its caller-domain checks are not understood, `2026-07-23-sptm-three-soc-structural-diff.md`);
or a boot flow where SPTM does not hold the cores, so the impl reset register
wins as it does on M4. Neither is available offline, and the second may be
disallowed by the M5 boot policy.

### 3. WFI/WFIT loses architectural state. Real, but downstream, not the cause. High confidence it is not the CPU1 blocker.

On M4/M5 a secondary can lose most of its register file at WFI unless
`CYC_OVRD_DISABLE_WFI_RET` is cleared, which m1n1 only does when
`apple_sysregs_unlocked` is true (false on T6050). Upstream mitigates by
reserving the 48 KiB SMP-RO region (PR #657) and appending `idle=nop
arm64.nowfxt` (yuka `feature/wfi-bootarg`). But this only matters after a core
executes and reaches WFI. It cannot explain zero reset-trace stores on M5, so
it is a real follow-up once cores run, not the reason they do not.

### 4. The "+0x4" global-bit mask is wrong for 6-core clusters. Real bug, but not the CPU1 blocker. High confidence.

`1 << (4*cluster+core)` assumes at most 4 cores per cluster. T6050 clusters
have 6 cores each (ADT: cluster 0 M-cores id 0..5, cluster 1 M-cores id 6..11,
cluster 2 P-cores id 12..17). So cores in cluster 1 and up get the wrong global
bit. This is the known "aliases starting at ADT id 6" issue. It does not
explain CPU1, which is cluster 0 core 1 and maps to bit 1 either way. It should
be fixed alongside hypothesis 1 (use `6*cluster+core`, or drop `+0x4` entirely).

## Candidate fix and why the diagnostic does not apply it directly

The smallest change with a real chance is hypothesis 1's `+0x4` change in
`src/smp.c`. It cannot live in a new file: the reset landing needs `smp.c`'s
own `target_cpu` and `_reset_stack`, which are file-private, so only `smp.c`
can start a core in a way the loader can observe. The rules for this audit do
not allow editing existing loader files, so the change is specified here for
the private tree, and the new default-off loader file gathers the evidence that
licenses it. Exact change, private `standalone-loader/m1n1-20260911/src/smp.c`,
inside `smp_start_cpu()`:

```c
    // Some kind of system level startup/status bit
    // Without this, IRQs don't work
    if (chip_id != T6050 && chip_id != T6051)
        write32(cpu_start_base + 0x4, 1 << (4 * cluster + core));
    // T6050/T6051: iBoot pre-sets +0x4 to 0x3fffe (all secondaries). The
    // overwrite cleared the target bit in the one recorded live read
    // (0x3fffe -> 0x3fffc), so leave iBoot's mask in place. See smp.md.
```

Remove the private `AZAHI_ONE_CORE` early return for T6050 to reach this code.

## The loader diagnostic (default-off)

New files, compiled but default-off:
`standalone-loader/m1n1-20260911/src/azahi_smp.c` and `.h`. No `azahi.smp=`
cmdline token means it does nothing, so default boots are unchanged.

- `azahi.smp=probe`: read-only. Logs each secondary's Apple reset register
  (`cpu-impl-reg[0]`), its lock bit, and whether it equals the loader entry
  `_vectors_start`, plus the whole CPU_START bank (`+0x0/+0x4/+0x8/+0xc/+0x10`)
  on die 0. It reads only the reset register (offset 0), which
  `smp_start_cpu()` also reads before starting, so it is safe on a powered-down
  core. It never reads `impl+0x100` (the CPU status register, only safe on a
  running core) and never writes.
- `azahi.smp=start`: logs CPU_START, runs the stock `smp_start_secondaries()`
  (its own 100 ms per core bounded wait), logs CPU_START again, then reports
  `smp_is_alive()` per core. The before/after of `+0x4` shows whether the stock
  write clears the enable bit (hypothesis 1). All secondaries reporting not
  alive while the reset register is correct and locked points at hypothesis 2.

How it is called from the loader. The same way `azahi_pcie_init` already is:
inside the `T6050` branch of `kboot_boot` in `kboot.c`, right after the
`azahi_pcie_init(pcie_cmdline, dt)` call, reusing the resolved bootargs pointer:

```c
        azahi_smp_diag(pcie_cmdline);
```

with `#include "azahi_smp.h"` next to the existing `azahi_pcie.h` include. That
call is not added here (it would edit `kboot.c`); it is a one-liner the private
tree adds.

### Compile and test results

- `azahi_smp.c` compiles clean against upstream m1n1 headers with the aarch64
  cross gcc 16.1 from `env.sh` and the required freestanding flags
  (`-ffreestanding -fno-builtin -nostdinc -isystem ... -mgeneral-regs-only
  -I<m1n1>/src -I<m1n1>/sysinc -Wall -Wextra -Werror`). No warnings. The only
  defined symbol is `azahi_smp_diag`; everything else resolves against m1n1.
- `python3 smp/test-smp-diag.py`: 4 host checks pass. They compile the token
  parser out of the C and confirm it is default-off and word-bounded (a longer
  token never trips a shorter mode, and `start` never fires for `probe`), and
  statically confirm probe mode contains no `write32`/`write64` and that
  `smp_start_secondaries()` is called from exactly one place.

## Attended test plan

Goal of the first session: decide hypothesis 1 vs 2 before changing any start
code. Read-only first.

Step 1, probe (no install, no writes).

- Build the loader with the `azahi_smp_diag(pcie_cmdline)` call added, or with a
  temporary unconditional `azahi_smp_diag("azahi.smp=probe")` for a proxy run.
- Chainload it over the proxy exactly like the V1..V5 diagnostics, on a fresh
  physical cycle with no other proxy client. Do not start secondaries first.
- Expected log lines:
  - `AZAHI_SMP: pmgr_reg = 0x280600000, cpu_start_base = 0x280688000`
  - `AZAHI_SMP: loader entry _vectors_start = 0x... boot MPIDR = 0x... boot_cpu_idx = 0`
  - one `AZAHI_SMP: cpuN ... impl=0x210N50000 rvbar=0x... lock=1 ==entry` line
    per core (rvbar should equal the loader entry; lock should be 1)
  - `AZAHI_SMP: die0 CPU_START @0x280688000: +0=... +4=0x3fffe +8=... ...`
- The load-bearing line is `+4`. If it reads `0x3fffe`, iBoot pre-enabled every
  secondary and hypothesis 1 is in play. If any `rvbar` line reads `!=entry` or
  `lock=0`, the reset register is not pointing at the loader and hypothesis 2
  (or an RVBAR problem) is confirmed instead.

Step 2, start (reproduces the failure with before/after evidence).

- Same build, plus the private `smp.c` `AZAHI_ONE_CORE` early return removed
  (otherwise `smp_start_secondaries()` returns before starting anything and
  this step shows nothing). Keep the stock `+0x4` write for this step so it
  reproduces the recorded failure. Then boot with `azahi.smp=start`.
- Expected:
  - `CPU_START before ... +4=0x3fffe`
  - after `smp_start_secondaries()`, `CPU_START after ... +4=0x3fffc` (or the
    target bit cleared) and `AZAHI_SMP: 0/17 secondaries alive`.
- Reading: `+4` going `0x3fffe -> 0x3fffc` with the reset register still correct
  and locked and zero alive confirms hypothesis 1 is worth the `smp.c` fix. If
  `+4` is unchanged and cores are still not alive, hypothesis 2 (firmware/SPTM
  reset ownership) is the more likely story and a loader-only fix will not help.

Step 3, only if step 2 supports hypothesis 1: apply the `smp.c` `+0x4` change,
rebuild, chainload, and run `azahi.smp=start` again. Success is any
`AZAHI_SMP: cpuN alive=1`, which would be the first secondary ever to execute
loader code on this machine. Even one alive core settles the question.

Abort criteria. Any SError, any hang, or a watchdog reset: stop, physically
cycle, do not retry the same step. Never call unbounded `smp_call`/`smp_wait`,
never chainload again after a failed start, and never boot Linux from a
diagnostic build. Do not read the CoreSight or debug blocks (a prior read of
`0x210010ff0` SErrored the machine).

Rollback. Probe and start install nothing; a physical cycle returns the machine
to the installed v7 image. If a fixed loader is ever installed to test step 3
persistently, the installed v7 image is the rollback through the private
Recovery procedure, exactly as for the PCIe and shutdown work.

## Honest confidence

I cannot prove which hypothesis is right without the machine. My best read is
that hypothesis 1 is the most likely thing a loader can fix and is cheap to
test, but hypothesis 2 is close behind and, if true, means secondaries need
SPTM cooperation Linux cannot get offline. The probe in step 1 is read-only and
decides most of this in one boot, which is why it comes first.

## Orchestrator review changes (2026-09-25)

- The probe dumped a second CPU_START bank at `pmgr + 0x2000000000`. Nothing
  places a die-1 PMGR there on this SoC (the repo's other die-level PMGR
  nodes sit at `+0x2100000000`), and the J714s has all 18 CPUs on die 0.
  Reading an unmapped address can SError, which would defeat a read-only
  probe. The dump is now die 0 only, and CPU nodes on other dies (the
  restore-image template lists die-2 CPUs) are skipped with a log line.
- Step 2 now states that the private `AZAHI_ONE_CORE` early return must be
  removed first, and the call site is `kboot_boot`, where `azahi_pcie_init`
  already runs.
- One more observation for the diagnosis: iBoot's `+0x4` value `0x3fffe` is
  bits 1 to 17, one bit per CPU in linear order. The stock
  `1 << (4 * cluster + core)` formula only matches that for cluster 0, so on
  these 6-core clusters it would name the wrong CPU for cores 6 to 17 even
  if hypothesis 1 is fixed. CPU1, the core actually tried, maps correctly.

## Follow-up: macOS core-start sequence compared (2026-09-25)

Traced in the Mac17,9 kernelcache (26A428): `IOPMGR::enableCPUCore(cpu,
entry)` (0xfffffe000c2d50dc) drops the entry argument and calls
`ApplePMGR::enableCPUCore(cpu)` (0xfffffe000985bf4c), which calls
`enableCPUCores(1 << cpu, true)` (0xfffffe000985bafc). That reaches
`ApplePMGR::configMiscCores` (0xfffffe000985b3d4) through vtable slot
`+0xd20`, which `AppleT6050PMGR` does not override.

`configMiscCores` builds, from the requested cores only, one value for
CPU_START `+0x4` per die and one value per cluster for `+0x8 + 4*n`, then
writes them in that order. It writes `+0x4` even for a die with no requested
cores (value 0), so `+0x4` behaves as a trigger register, not a plain enable
mask.

Consequences:

- **Hypothesis 1 is unlikely.** For CPU1, macOS writes the same values the
  stock loader writes (`0x2` to `+0x4`, then the cluster-0 bit to `+0x8`).
  The recorded `0x3fffe -> 0x3fffc` readback fits the hardware accepting the
  start request, which also fits CPU1's power domain reaching ACTIVE. The
  failure happens after a start request that looks correct. Skipping or
  OR-ing the `+0x4` write is not expected to help and is withdrawn as the
  candidate fix.
- **Real but secondary bug.** macOS takes each core's `+0x4` bit from
  per-core data, and iBoot's `0x3fffe` is one bit per CPU in linear order.
  The loader's `1 << (4 * cluster + core)` only matches that for cluster 0,
  so cores 6 to 17 would get the wrong bit (earlier notes recorded the same
  mask problem). Once a core can start at all, use the linear CPU index
  (`6 * cluster + core` on this 6-core-cluster layout) for `+0x4`.
- The remaining explanation is outside the PMGR start sequence, in how a
  released core reaches its first instruction. This session does not
  investigate that further. The read-only probe (step 1 above) is still the
  right first hardware step: it records the reset-vector state per core
  without starting anything.
