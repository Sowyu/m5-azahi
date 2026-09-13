# Private T6050 CPU startup diagnostic — 2026-09-06

**Current-state override:** one-core native KDE now runs from the internal SSD
with host-assisted kernel boot. All-core startup remains unresolved. The
live-session addresses and name references below are historical, not current
identity/state. No TTS; do not address the user by name. Read
[current handoff](../CURRENT-STATE.md) before any further CPU work.

**Priority/live-state override:** PRIVATE-USER approved one-core native SSD work next.
CPU research is paused; the fourth clean V5 RAM loader has now been replaced
by the unchanged native prefix for an SSD RAM test. Do not run CPU helpers.
See `NATIVE-SSD-CHECKPOINT.md`. Daily macOS untouched; no commits.

Priority: all 18 CPU cores, then persistent internal Linux boot; GPU later.
PRIVATE-USER explicitly approved overriding the local m1n1 AI-work restriction for
his private copy, with **no commits**. No upstream submissions. Existing
dirty changes in the tree are preserved. No storage-layout authorization
is inferred and this test performs no SSD operations.

## Current state

**Newest — fourth direct boot CLEAN:** base**0x100043a4000**. PRIVATE-USER's cycle
cleared the third-boot firmwareRAM patch. Verified originalV5 reset/mainentry
and runtimevectors, target0/failed0/alive[], CPU1/6/12power100,
globalstart3fffe/allclusterdoorbells0, APSC400106/400102/400102.
CTRR lower**0x10004bb0000**, finalpage**0x10004bbb000**, control0;
entire48KiB range through exclusiveend**0x10004bbc000** verified originalWFI,
SHA256bc4a4e3073dfa66ac5ea39867e4c18866e96b396f32b9479b1499b9744b81871.
Logs cpu-direct-v5-cycle4-preflight-20260906.log and
cpu-direct-v5-cycle4-clean-ram-20260906.log both end CPU_CHECK_PROXY_ALIVE.
No CPU starts, firmware/control/SSD writes this boot; client closed.
**No cycle is required now. Earlier retained-state cautions are historical.**
No new source-backed CPU-release fix was found. Ask PRIVATE-USER whether to reorder
priorities toward one-core native SSD work; do not infer a priority change
or permission to repartition/format. InstalledV5 and backup unchanged.

**Newest — third direct V5 boot:** base**0x100055e0000**. PRIVATE-USER's physical cycle
verified clean original V5 reset/runtime vectors, unused C SMP state, CPU1/6/12
power100, globalstart3fffe, and APSC400106/400102/400102. Earlier second-boot
patches and disabled APSC are gone. Log cpu-direct-v5-cycle3-preflight-20260906.log.

**Current retained diagnostic:** upstream PR657 register reads at EL2 gave
CTRR_M4_LWR=**0x10005dec000**, UPR=**0x10005df7000**, CTL=0. Snapshot of the
inclusive final4KiB page, exclusiveend**0x10005df8000**, was exactly49152bytes
of WFI encoding7f2003d5. SHA256
bc4a4e3073dfa66ac5ea39867e4c18866e96b396f32b9479b1499b9744b81871,
saved logs/cpu-direct-v5-cycle3-ctrr-20260906.bin. Entire range now patched
through RWalias, cleanPoC/readback, to repeated **SEV;B(-4)** bytes
9f2003d5ffffff17. Every instruction-aligned entry parks in a SEV loop.
Loader reset/main-entry bytes and runtime vectors were NOT patched this boot.

V5 bounded normal startup then requested CPU1, failed stage0, and stopped;
CPU1power1f0, ten20msWFET observations returned1/ISR0, traceallzero/alive[].
One localCPU1IPI follow-up with range still patched gave the same result.
No secondary execution proven, and this does not establish firmware PCs or
prove the protected block is the actual parking area. Ctarget1/failed1 and
CPU1 allocated stack retained. **Do not restore the firmware block, reuse
allocations, initialize/restart SMP, chainload, or boot Linux before physical
cycle.** APSC unchanged this boot. No client remains; last log ends
CTRR_PARK_PROXY_ALIVE. Installed V5 unchanged, no SSD operations/commits.

Helpers cpu-ctrr-snapshot.py, cpu-ctrr-park-check.py already executed; park
defaults offline, guards reject fresh-mode rerun. Logs cycle3-ctrr-snapshot,
cycle3-ctrr-park, cycle3-ctrr-ipi in logs/ with cpu-direct-v5- prefix/date.
Online source review and next-use caveats are in CPU-ONLINE-RESEARCH.md.
Older current-state paragraphs below are historical.

**Latest follow-ups:** one local fast IPI (`S3_5_C15_C0_0=1`) to already
requested CPU1 had no observed effect. Local encoding follows hv_exc.c
(Aff0 target, current Aff1/Aff2); do not use smp_send_ipi with the uninitialized
spin table. Ten20ms WFET observations returned1, ISR0, CPU1power1f0.
Then CPU5 used the complete bank32,32,0,0 in one on-target assembly call,
DSB between writes, no USB gaps. Same quiet result, CPU5power1f0.
Neither test proves delivery/firmware PC; neither produced a new executing CPU.
Logs `cpu-direct-v5-local-ipi-20260906.log` and
`cpu-direct-v5-fast-bank-20260906.log` both end LOCAL_IPI_PROXY_ALIVE.
Helper `probe/cpu-local-ipi-check.py` defaults offline; both live modes have
already run. CPU1–6 now requested this boot; no primary power writes, further
APSC writes, SSD writes or commits. Retain all RAM patches/allocations and
cluster1 APSC disabled until physical cycle. Client closed. Request a physical
cycle into Linux proxy to clear accumulated diagnostics before further boot
experiments; do not software-reset/chainload this session.

Upstream main940439b9 comparison against local88a9821 showed no smp.c changes;
no tree update performed. Offline iBoot48-bit-mask candidates at offsets
1f5000/1f6508/1f65e8 were page-table routines, not resolved RVBAR setters.
No new firmware-reset register write is justified by that investigation.

**Latest control change:** cluster1 APSC is now deliberately disabled at
**0x211e20020 = 0xc00102** (was0x400102; only bit23 changed). Source-resolved
64-bit write matched AppleT6050PMGR::enableAPSC(false,1,0), immediate settle
with busy7/pending31 clear. CPU6 full-bank start64,0,1,0 still yielded quiet
WFET baseline through ten20ms windows, ISR0, power1f0. No new executing CPU.
Primary cluster and all voltage/frequency values were untouched. Leave this
control as-is until physical cycle; do not blindly restore during a pending
CPU start. **Cycle required before any SMP/chainload/Linux/reuse.**
`logs/cpu-direct-v5-apsc-start-20260906.log` ends APSC_START_PROXY_ALIVE;
client closed. `probe/cpu-apsc-start-check.py` defaults to offline validation;
--run already executed and state guards prevent rerun. Read-only predecessor
`cpu-apsc-read.py` found cluster0=0x400106, cluster1/2=0x400102.

ACC mapping evidence: table pointers at KC0xfffffe0008166bb0 resolve three
11-entry maps. Offsete20020 uses mapping IDs2c/37/15, ADT regindices10/1a/24,
bases210e20000/211e20000/212e20000, length12e8; subtractlogicalbasee20000.
This is not a write to ADT acc-impl-reg+e20020. No debug-block access.
One corrected offline hypothesis: enableCPUComplex's vtable+cf0 resolves
restoreACC, **not enableAPSC**. Do not claim disabling APSC is Apple's normal
per-core startup prerequisite; this was an explicit isolation experiment.

**Newest live state — RAM-independent event tests:** still direct V5 base
**0x10005d94000**. First16 reset branches AND main entry branch **base+0x800**
now target **base+0x3000 = 0x10005d97000**, containing only `SEV; B` (8 bytes,
`9f2003d5ffffff17`). All earlier stubs/trace allocations remain untouched.
CPU3 reset-slot-only and CPU4 main-entry-inclusive starts both yielded no
event increase: ten 20ms WFET windows each returned once at timeout, exactly
matching five baseline windows; ISR_EL1 stayed0, each core power became1f0.
The CPU advertises FEAT_WFxT (ISAR2 low nibble2); primary WFET worked without
timer-control writes. No stack, RAM store or MRS needed in secondary stub.
This weakens the failed-trace-store hypothesis; event delivery itself isn't
independently proven between cores, so do not claim a definitive CPU PC.

Logs `logs/cpu-direct-v5-event-{preflight,baseline,cpu3,cpu4}-20260906.log`.
Helper `probe/cpu-event-entry-check.py --offline` passes, live modes already
run and must not be rerun. Proxy alive, client closed. **Cycle before any
SMP initialization, chainload, main/reset-entry restoration, Linux or RAM
reuse.** C target/failed flags still do not represent fresh hardware.
No SSD writes/commits. Older current paragraphs below describe earlier tests.

**Current — second direct V5 boot:** base **0x10005d94000**. Fresh preflight
passed after PRIVATE-USER's cycle. Full-bank CPU1 start (2,2,0,0 at PMGR
0x280688004/8/c/10) still yielded zero markers and power 0x1f0. Then CPU2
used a PC-relative marker entirely inside the loader: code **base+0x2000**,
trace **base+0xe8000** (unused EL3 stack; PFR0 confirms no EL3). Its full-bank
start (4,4,0,0) likewise yielded zero markers and power 0x1f0.

Current first16 reset branches point to **0x10005d96000**. Retain old CPU1
stub **0x10008bb4000** and trace **0x10800012000** too. Primary runtime
vectors unchanged. No C SMP was initialized: target_cpu=0 and failedflag=0
are **not evidence of fresh hardware** after these stateless starts. Never
restore branches, free/reuse either stub/trace, initialize SMP, chainload,
or boot Linux before a physical cycle. No client remains connected.

New source-resolved CPU-cluster controls **0x280620000/4/8** all read **0xf**
(MACC0/MACC1/PACC). ApplePMGR::enableCluster uses this low-nibble enable
value; no missing enable request was found and no cluster-control writes
were made. These are distinct from per-device CPU/CPM power-status registers.
Live ADT soc-clusters records map CPU logical IDs 1/2/3 to physical 0/1/2.
Source: local AppleT6050PMGR initRegGroups 0xfffffe000987f094, configCPUComplexPowerState
0xfffffe0009880a64, ApplePMGR enableCluster 0xfffffe000949e47c,
getPhysicalClusterID 0xfffffe000949dd44. No firmware execution.

Evidence: `logs/cpu-direct-v5-cycle2-preflight-20260906.log`,
`logs/cpu-direct-v5-full-bank-20260906.log`,
`logs/cpu-direct-v5-inimage-20260906.log`,
`logs/cpu-direct-v5-cluster-control-read-20260906.log` (proxy alive).
Helpers `probe/cpu-full-bank-check.py` and `probe/cpu-inimage-check.py`
passed offline instruction/guard checks; already run, not safe to rerun.
Only one CPU proven. Installed V5 unchanged, backup intact, server stopped,
no further SSD writes or commits. Older live-state paragraphs below are history.

Additional read-only investigation: `probe/cpu-preoslog-read.py` copied the
live ADT-declared preoslog RAM range **0x1000655c000+0x40000** into
`logs/cpu-direct-v5-preoslog-20260906.bin`, ending PREOSLOG_READ_PROXY_ALIVE.
No startup/MMIO writes. POSL header, Stage1 mBoot-20457.1.29 and Stage2
mBoot-18000.161.9 banners present; most entries are opaque hash/line records,
not a readable CPU startup failure. Do not treat them as decoded diagnostics.

Extended `probe/extract-kernelcache.swift`'s explicit type allowlist to ibdt.
Strict IM4P/LZFSE extraction produced local analysis-only
`probe/firmware-analysis/ibootdata.j714s.bin`, 459150 bytes, SHA256
`b43f7a31f6d980c6205f029dd80b2dc5ec0a2a52d7d3d801019736d9dcb5d11b`.
It contains named MCPS/SCPS CPU power-transition entries, but their semantics
are not decoded and no test/fix follows from the names alone. Host restore
version 18000.161.10 differs from target Stage2 .9; never install this file
as an assumed compatible replacement. No Apple firmware was executed.

Offline m1n1 pmgr_init review: cleanup enables parents of already-active
devices, not CPU shutdown; this direct preflight logged no such parent enables.
T6050 enableTVM changes ACC voltage-management state, not a demonstrated
missing core-reset release. Do not copy those writes onto the target.

**Newest:** direct V5 boot verified at 0x10005200000. CPU1 failed stage0;
CPU6/12 corrected-mask stateless follow-ups also power on with zero markers.
Still one proven CPU. Current first16 reset branches point to retained RAM
stub **0x10008034000**, trace0x10800012000; CPU1 stack **0x10008030000**,
target1. Proxy alive, no client; physical cycle before restart/chainload/
Linux/reuse. Installed V5 unchanged; original backup intact; server stopped.
See RECOVERY-CHECKPOINT.md and logs/cpu-direct-v5-*-20260906.log. All older
base addresses, pending-install claims and running-server notes are stale.

**Direct-install update:** webcam confirmed `KMUTIL_COMPLETED mode=diag`.
V5 is now installed in Linux's custom boot slot, with its original loader
backed up and restorable. M5 still in Recovery; shutdown/boot Linux next.
No direct-boot CPU result yet. See RECOVERY-CHECKPOINT.md. This supersedes
the no-target-boot-writes / not-installed statements below.

**Newest, supersedes pending backup notes below:** backup succeeded and was
verified on host; original raw loader extracted with entry/mapping checked.
M5 remains in Recovery, no diagnostic installation yet. Backup receiver
stopped. Read-only install/restore artifact server now on PRIVATE-LAN-ENDPOINT-REMOVED,
exec session 7708. See **RECOVERY-CHECKPOINT.md** for current exact details
and user commands. The earlier missing-cmp error was not corruption.

**Recovery update (later):** PRIVATE-USER physically cycled into Options, selected
Linux in Recovery, and opened Terminal. The V5 live-RAM session below is
gone. Webcam-verified inventory: Linux system disk4s3 at /Volumes/Linux
(read-only), same-container Preboot disk4s4, mounted read-only by PRIVATE-USER at
/Volumes/Preboot. `bputil -d` selection 1 matched the displayed Linux volume
group and showed Permissive Security. Display only; no policy changes.
`find /Volumes/Preboot -type f -name '*custom*'` found a custom boot path,
but exact long path/UUIDs await machine-readable collection. Do not rely
on transcribing the webcam UUIDs or old notes for install targets.

Prepared `probe/recovery-backup.sh` (M5/model, mount and container guards;
RAM-temp copies, POSIX checksum/size comparisons, bounded backup upload only;
receiver calculates SHA256, and helper verifies returned archive checksum/size).
Receiver `probe/recovery-backup-server.py` is currently running on host
PRIVATE-LAN-ENDPOINT-REMOVED, exec session 31552 (restarted; old PIDs 39262/39335 stopped). Serves /check.sh only and
accepts one token-scoped upload into
`logs/recovery-backup-20260906.eTn0av/backup.tar.gz`. No backup received yet.
Stop this receiver after transfer. Shell/Python syntax checks passed;
helper correctly refused to run on the M1 host. First Recovery attempt
stopped before temp copies because OpenSSL is unavailable. Updated helper
uses cksum instead; waiting for PRIVATE-USER to download/run again. Local receiver
test passed exact upload bytes, checksum/size receipt, SHA256, and duplicate
upload rejection. No successful target backup yet.
Second Recovery attempt stopped after a RAM-temp copy: `cmp: command not
found`, not an observed content mismatch. Photo
`logs/recovery-webcam-20260906-backup-compare-error1.jpg`. Replaced missing
cmp with cksum CRC/size comparison (not cryptographic on target), kept host
SHA256, and preflighted all remaining external command dependencies before
copying. Local checksum match/change rejection and receipt parsing tests
passed. Updated helper served/checked, awaiting PRIVATE-USER's retry. Original
Preboot files unchanged; failed temporary backup retained in Recovery /tmp.
No target boot-file writes, installation, repartitioning, or commits.

**Latest, supersedes the V4 state below:** PRIVATE-USER cycled; V5 was loaded at
**0x1000495c000**. CPU1 again timed out at stage 0, slot 0, proxy survived.
Then a stateless assembly parking stub was installed in native-allocated
RAM **0x1000768c000**, with trace **0x10800012000** (256 bytes). Only the
16 reset-slot branch instructions were redirected to it, through the
existing writable RAM alias; the primary runtime vectors were unchanged.
CPU1's retained target/stack were verified and never changed. Any delayed
core entering a patched slot parks without touching shared C startup state.

CPU6 start used ADT-correct global mask **0x40** at 0x280688004, then
cluster mask 1 at 0x28068800c. CPU12 follow-up reused/verified that exact
stub without code/trace writes, using global **0x1000**, cluster mask 1
at 0x280688010. Both changed power status 0x100 -> 0x1f0, but all five
trace words stayed zero through one-second observations. Thus no newly
proven core in any of the three clusters, even with corrected masks and
stateless entry. No SSD writes or commits. **Do not initialize SMP,
chainload, restore the reset branches, free/reuse the stub, or boot Linux
in this state. Physical cycle required before a new loader session.**

Latest log `logs/cpu-diag-v5-cpu12-park-20260906.log` ends
`CPU12_PARK_PROXY_ALIVE`; no client remains running. Also see
`logs/cpu-diag-v5-preflight-20260906.log`, `logs/cpu-diag-v5-chainload-20260906.log`,
`logs/cpu-diag-v5-start-20260906.log`,
`logs/cpu-diag-v5-cpu6-park-alias-20260906.log`.
The first CPU6 helper attempt tried writing the RX code mapping and got a
**recovered synchronous permission fault**, ESR 0x9600004f, FAR base+4.
It stopped before any branch changed or CPU-start writes occurred. The
corrected attempt used REGION_RW_EL0 as defined by memory.c; not MMU bypass
or an MMIO experiment. Earlier failed log: `logs/cpu-diag-v5-cpu6-park-20260906.log`.

Next discriminating test under consideration: boot an instrumented loader
directly through Apple boot, eliminating RAM chainload/code replacement.
This requires Recovery access and a verified backup of the Linux custom
boot object before any change. No installation operation has been done.
Never alter partition layout, macOS, or erase APFS volumes for this test.

Native KDE previously reached graphical Plasma first-run setup in RAM.
It is no longer running: the webcam showed a fresh Running proxy before
the first diagnostic. V1 and V2 have both timed out on CPU 1 with stage 0.
V3 also timed out at stage 0. Its primary proxy survived the startup test,
but a subsequent read-only CoreSight ID access caused an SError and proxy
timeout. PRIVATE-USER physically cycled after that fault; never retry that debug
block. V4 was then loaded at **0x10005a0c000** and also timed out at stage 0.
Its proxy survived. A guarded CPU1-only ACTIVE request (0x280600008,
0x1f0 -> 0xff) read back unchanged at 0x1f0; trace and alive flag stayed zero.
Latest log `logs/cpu-diag-v4-active-20260906.log` ends
`CPU1_ACTIVE_CHECK_PROXY_ALIVE`. No proxy client remains running. Preserve
the retained CPU1 stack/target; no further SMP initialization or chainload
on this session. Still only one proven CPU.

Current work is offline analysis of AppleT6050PMGR from the host restore
cache, extracted read-only to `probe/firmware-analysis/kernelcache.mac17j.macho`.
Original source is the mac17j restore cache under host Preboot, not the
running host kernel. `probe/extract-kernelcache.swift` verifies IM4P/LZFSE
and Mach-O; `probe/inspect-kernelcache.py` uses isolated Capstone 5.0.9 in
`/tmp/azahi-cpu-disasm.zPmZfJ`. No firmware execution or installed-file writes.
T6050 initRegGroups confirms group 8, map 0, offset 0x88000. Common
configMiscCores (0xfffffe0009495968) is the actual virtual startup method.
Its newer topology path uses die-cluster-id/cluster-core-id and the
acc-cores global enable bit. CPU1's mapping appears unchanged; the old
six-core mask bug still applies at CPU6. This is evidence, not an SMP fix.

Boot-CPU architectural-only check succeeded with no MMIO/SMP writes:
`ID_AA64PFR0_EL1=0x1101000010110111`, `RVBAR_EL2=0x1fc08c000`.
This is a firmware-region reset address, distinct from the implementation
register containing our loader base. It is **not** proof of CPU1's PC or
the cause of failure. Do not read/scan the firmware address on hardware.
Log: `logs/cpu-diag-v4-architectural-reset-20260906.log`, proxy alive.
Read-only local analysis copies of iBoot j714s (4,102,280 bytes) and SPTM
t6050 (1,376,288 bytes) are also in `probe/firmware-analysis/`; not executed.

## V5: tested, stage 0; subsequently RAM-patched for stateless CPU6/12 tests

Binary `probe/m1n1-smp-diag-v5-20260906.bin`, SHA256
`7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef`;
matching raw `.elf` preserved. Build and diff checks pass. Offline Capstone
validation checked all 16 reset-slot branches, all 16 unchanged runtime
exception destinations, and raw-entry trampoline at 0x800 -> `_start` 0x804.
The first 0x800 bytes now route every 128-byte slot to `cpu_reset` at 0x940,
recording slot offset in trace word 4. Runtime exception initialization uses
separate aligned `_smp_runtime_vectors` at 0x2a800; primary registers aren't
clobbered by a diagnostic guard in exception handlers. No power-sequence
changes. Existing user exception halt behavior is preserved.

This tests alternate firmware entry/vector selection only, not a diagnosed
fix. CPU1 timeout still stops and retains its stack. High-RAM trace remains
diagnostic-only: **no Linux payload on V5**. No commits or SSD writes.
Build evidence: `logs/cpu-diag-v5-build-20260906.log`.

V5 reproduction only: physical cycle into fresh Running proxy, verify boot MPIDR 0x80040000
without starting SMP, then chainload V5 with `--raw` (entry default 0x800).
Run `probe/cpu-proxy-check.py --read-core-power --read-start-status --start-existing`
with new V5 log names. Never use the V2/V4-pinned write/wake helpers on V5.
All retained-stack symbol offsets and `_bss_end` happen to match V4, but
reset instructions/image hash differ; do not infer helper compatibility.

## V4: tested, same stage-0 result

`probe/m1n1-smp-diag-v4-20260906.bin`, SHA256
`3fe03928a82d5a32f515eeb6f0668f0a2a80810691a6fe43e85ff81d27d3a185`;
matching `.elf` preserved. Build/diff checks pass, and `_start` disassembly
was inspected. It preserves V3's PoC clean and reset trace. The new guard
at main image entry (offset 0x800) passes the verified boot-core affinity
0x40000 unchanged. A different affinity records stage 0x80, MPIDR, CurrentEL,
SCTLR_EL1 in the existing high-RAM trace and parks in WFE before stack/BSS
initialization. This tests alternate entry selection without new MMIO writes.
It is a private T6050 diagnostic only, not a general bootloader or SMP fix.

V4 reproduction only: run the inventory **without --start-existing** first
and confirm `BOOT_CPU_MPIDR 0x80040000` before chainloading V4. Then use the
same bounded startup test with new log paths. Do not use the V2-pinned wake
helper on V4 (its code offsets/hash differ). Never boot Linux from these
fixed-high-RAM diagnostic builds. Completed evidence:
`logs/cpu-diag-v4-preflight-20260906.log`,
`logs/cpu-diag-v4-chainload-20260906.log`,
`logs/cpu-diag-v4-start-20260906.log`,
`logs/cpu-diag-v4-active-20260906.log`.

Evidence: `logs/cpu-diag-precycle-20260906.jpg`,
`logs/cpu-diag-v1-chainload-20260906.log`,
`logs/cpu-diag-v1-start-20260906.log`,
`logs/cpu-diag-v1-power-read-20260906.log`.

The V1 loader was at 0x1000469c000 and locked RVBARs matched. Before the
attempt, 0x280688004 read 0x3fffe; afterward it read 0x3fffc. Cluster request
registers +8/c/10 read zero. A read-only check of ADT-identified power state
registers reported CPU0/CPU1 actual state 15 (0x1f0), CPU6/CPU12 state 0
(0x100), and all three cluster devices state 15. This means CPU1's power
state is reported active, not that instruction execution is proven. Stage
0 is compatible with multiple causes, including failure of the first trace
store itself. No power-state writes were added.

## V3: tested, same stage-0 result

`probe/m1n1-smp-diag-v3-20260906.bin`, SHA256
`de111ba02eddfb0e71425818191f1b73da6388b71b4b53e6066c8621fd1985c6`;
matching `.elf` preserved. Build and diff checks pass. This adds an explicit
clean-to-PoC of the resident loader code/shared globals, from `_vectors_start`
through `_bss_end` (0xe6c08 bytes), followed by DSB, IC IALLUIS, DSB, ISB,
immediately before the original CPU-start writes. The range is bounded to
4 MiB and starts at the current loader base. No power-register changes.

Rationale is a hypothesis, not a diagnosed fix: chainload cleans code to PoU
and the old SMP path publishes only `_reset_stack`. A reset core without
our MMU/cache setup may need explicit visibility of the new code/shared
state. The [arm64 boot protocol](https://www.kernel.org/doc/html/latest/arch/arm64/booting.html)
requires PoC-clean kernel code and coherent CPU entry; it does not prove
this is the cause on T6050. V3 remains a diagnostic-only, no-Linux-payload
build because its trace scratch overlaps the usual kernel RAM region.

After a physical restart, sequentially chainload **V3** then run
`python3 -u probe/cpu-proxy-check.py --read-core-power --read-start-status --start-existing`
with fresh logs. Expect `T6050_SMP_DIAG_V3` and `T6050_POC_CLEAN`.

The above is V3 reproduction, not the next test. Hardware logs:
`logs/cpu-diag-v3-chainload-20260906.log`,
`logs/cpu-diag-v3-start-20260906.log`,
`logs/cpu-diag-v3-status-20260906.log`. Loader base 0x100057cc000;
PoC range 0xe6c08 bytes. CPU1 remained trace stage 0. Power readback was
0x1f0, as before. Existing stop-path impl+0x100 reads succeeded:
CPU0 0x210050100 = 0x80802aef201102;
CPU1 0x210150100 = 0x118080caef20d102. No undocumented bit meanings inferred.

**New forbidden-access checkpoint:** standard CoreSight CIDR0 at the
ADT-named CPU0 coresight base +0xff0, **0x210010ff0**, caused SError and
proxy timeout on its first read. No subsequent debug register was accessed,
no unlock/halt/injection was attempted, and no debug writes occurred.
`probe/cpu-debug-identify.py` is now explicitly disabled before opening USB.
Do not retry or scan this block. Evidence:
`logs/cpu-diag-v3-debug-identify-20260906.log`,
`logs/cpu-diag-v3-debug-fault-20260906.jpg`.

## V2: tested, same stage-0 result

`probe/m1n1-smp-diag-v2-20260906.bin`, SHA256
`9f37a3f65f64fce68db37a144148bb4a9679fd0cb28241b3eb02279ce5800163`;
matching `.elf` preserved. Build and diff checks pass; disassembly verifies
the address is constructed with MOVZ/MOVK before any stack/data reads.

Only change from V1 is moving the 256-byte trace from loader BSS to fixed
0x10800010000, inside the known native RAM fence. This tests whether low-RAM
trace access itself hides reset progress. Startup writes/stack/C sequence
are unchanged. The new private `smp_diag.h` records this scratch reservation.
**Diagnostic-only T6050 build: never load a Linux payload while it runs**;
the fixed scratch overlaps the RAM region normally reserved for the kernel.

Hardware evidence: `logs/cpu-diag-v2-preflight-20260906.jpg`,
`logs/cpu-diag-v2-chainload-20260906.log`,
`logs/cpu-diag-v2-start-20260906.log`. CPU1 was power-state 0 before startup,
then 15 afterward; trace remained all zero. No secondary flag was set.

`probe/cpu-reset-wake-check.py` verified V2 reset-vector instructions by
exact target RAM readback and checked locked CPU1 RVBAR against the current
loader base. It invalidated the high-RAM trace on the primary, issued one
SEV on the primary (no power/start writes), and observed for one second.
Trace stayed zero, CPU1 stayed 0x1f0, no CPU became alive. Proxy survived.
Evidence: `logs/cpu-diag-v2-wake-20260906.log`. This helper is pinned to V2;
do not run it on V3 without updating its image/code checks.

## Baseline evidence

`logs/cpu-wfe-original-20260906.log`: all 17 secondary starts timed out on
the original installed loader with WFE selected before its first SMP start.
RVBAR addresses match the loader base. Boot physical MPIDR is 0x80040000;
ADT reg values are not physical MPIDRs. All 18 ADT nodes form three six-core
clusters. The legacy global enable-mask calculation aliases CPUs starting
at ADT ID 6. That does not explain failures for IDs 1–5.

Exact legacy start registers at 0x280688004/8/c/10 were readable in previous
tests; their semantics on T6050 are not established. Do not scan registers.

## V1 diagnostic build (tested baseline)

- `probe/m1n1-smp-diag-v1-20260906.bin`, SHA256
  `1d461270bf5de3c45e64033e9285e7c99bb4f6650066ef1ee79e47352d67f86c`.
- Matching raw ELF: `probe/m1n1-smp-diag-v1-20260906.elf`.
- Original build output preserved in `probe/m1n1-before-smp-20260906.bin`
  and `.elf`; original binary hash
  `3ca38299f547ec792f343aa0b0604ba54a462587ac9cace701360c30a9879cd3`.
- Known native loader prefix and all known-good Linux images are unchanged.

Local changes this test: `m1n1/src/smp.c`, `smp.h`, `start.S`, `startup.c`.
The startup addresses/masks remain unchanged. A 256-byte aligned RAM trace
records reset entry before stack usage, MPIDR, CurrentEL, SCTLR_EL1 and C
initialization stages. Primary cleans the trace before reset, invalidates
without cleaning after the attempt. Trace stages:

| Stage | Last checkpoint |
| --- | --- |
| 0 | No reset-entry store observed; not proof the core stayed powered off |
| 1 | Entered reset assembly before stack setup |
| 2 | Stack loaded, about to enter C |
| 3 | Entered reset C routine |
| 4 | Initial console output completed, before init_cpu |
| 5 | init_cpu returned |
| 6 | exception_initialize returned |
| 7 | Entered secondary spin-table initialization |
| 8 | Published startup flag |

T6050 stops on the first timed-out CPU and preserves its stack/target for
possible delayed entry. Further startup calls refuse until physical restart.
RVBAR mismatch also refuses without start writes. Even on success, this
diagnostic stops before CPU ID 6, where the known enable-mask mismatch begins.
It is not an all-core fix or an execute-and-return heartbeat test.

Build passed: `make -C m1n1 USE_CLANG=1 RELEASE=1 -j8`; offline inventory and
`git -C m1n1 diff --check` passed. Reset disassembly verified stores precede
stack access. Existing Makefile grouped-target and payload printf warnings
are unrelated. No commits were made.

## Hardware test after PRIVATE-USER confirms fresh proxy

Ensure no guest or proxy client is active. Do not start secondaries before
chainloading this image. Chainload replaces the RAM loader at its existing
base, preserving locked reset addresses; it does not install to storage.
Use fresh log paths, sequential clients only:

```sh
sh /PRIVATE-USER/azahi/run.sh /PRIVATE-USER/azahi/proxyclient/tools/chainload.py -r /PRIVATE-USER/azahi-port/probe/m1n1-smp-diag-v1-20260906.bin
python3 -u probe/cpu-proxy-check.py --read-start-status --start-existing
```

Look for `T6050_SMP_DIAG_V1` and `T6050_RESET_TRACE`. Do not call unbounded
`smp_call`/`smp_wait`, boot Linux or chainload again after a failed reset.
Capture the panel and retain the proxy log, then plan the next test from
the observed stage rather than guessing new MMIO addresses.
