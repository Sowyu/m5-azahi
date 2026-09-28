# Secondary CPU startup on T6050

Status after the offline follow-up on 2026-09-25: no all-core fix is proven.
The hardware is unavailable. CPU0 remains the only core demonstrated running
Linux. No image was installed and no boot policy, disk or firmware was changed.

## Evidence that constrains the next attempt

The historical V1 through V5 experiments requested CPU starts and observed
power state `0x100` becoming `0x1f0`. They observed neither reset-trace stores
nor executing secondaries. Corrected masks, complete CPU_START bank writes,
code-cache cleaning, reset-vector variants, RAM-independent SEV loops, a local
IPI, and a secondary-cluster APSC experiment did not establish core entry.
The full record is [CPU-CHECKPOINT.md](../../research-archive/probe/CPU-CHECKPOINT.md).
Repeating those experiments without a new hypothesis adds little evidence.

The initial upstream T6050 port independently reported powered cores that did
not enter loader code on two macOS versions. The upstream start-register
sequence still has no demonstrated T6050 reset-release fix in the inspected
history. The 2026-09-27 shared-state changes are described below.
Sources: [PR 610](https://github.com/AsahiLinux/m1n1/pull/610),
[current smp.c](https://github.com/AsahiLinux/m1n1/blob/main/src/smp.c).

The M4 WFI and secondary-read-only-memory fixes address later failures. They
do not explain the absence of even the first reset marker on this machine.
Sources: [PR 657](https://github.com/AsahiLinux/m1n1/pull/657),
[PR 672](https://github.com/AsahiLinux/m1n1/pull/672).

## Upstream changes checked on 2026-09-28

Upstream merged a separate SMP refactor on 2026-09-27. Commit
[`d16a2f4e3c4d`](https://github.com/AsahiLinux/m1n1/commit/d16a2f4e3c4d)
places shared CPU state in its own aligned linker section and maps every RAM
alias of it as Device-nGnRnE. This addresses inconsistent views when one CPU
has its MMU enabled and another does not. It is more comprehensive than a
single cache clean. Commit
[`1b469fcb618f`](https://github.com/AsahiLinux/m1n1/commit/1b469fcb618f)
uses MPIDR to recover a returning CPU's stack and identity after deep WFI.
The series also moves stacks into static storage and caches ADT topology.

The changes involve both linker scripts, `memory.c`, `start.S`, `smp.c`,
headers and boot initialization. Copying the new `smp.c` into the incomplete
private snapshot is insufficient. The local guard patch still targets the
archived 2026-09-11 source. On September 29, a separate optional
[complete-loader backport](../../standalone-loader/README.md#optional-smp-shared-state-backport)
integrated all seven commits with those guards preserved. Both ELF variants
link, and four host test groups pass. This validates the integration offline,
not secondary execution or physical cache behavior.

At `c42cf43d0388`, upstream still uses the four-core CPU_START stride and the
older RVBAR mask. Keep the local T6050 corrections and timeout quarantine
when integrating newer code. These cache and re-entry fixes may matter after
reset entry works, but do not explain the RAM-independent SEV experiment's
negative result. No new hardware attempt is justified by the refactor alone.

A September 29 API recheck still identifies `c42cf43d0388` as the latest
upstream commit touching `src/smp.c`. PR 682 is closed; its merged changes
are the same series inspected above.

## The earlier skip-CPU_START hypothesis is withdrawn

The earlier report suggested skipping or OR-ing the CPU_START `+4` write
because readback changed from `0x3fffe` to `0x3fffc`. That observation does not
show that the write disabled CPU1.

The saved Mac17,9 kernelcache, build 26A428, provides a contrary trace:

- `IOPMGR::enableCPUCore` at `0xfffffe000c2d50dc` drops the entry argument and
  calls `ApplePMGR::enableCPUCore` at `0xfffffe000985bf4c`.
- `enableCPUCores` at `0xfffffe000985bafc` reaches `configMiscCores` at
  `0xfffffe000985b3d4` through vtable slot `+0xd20`. T6050 does not override it.
- That method builds the requested per-die and per-cluster masks and writes
  CPU_START `+4`, then `+8 + 4 * cluster`. For CPU1 these are the loader's
  same values. It also writes zero for a die without requested cores.

This supports trigger semantics for `+4`. Keep that write. Neither the
readback transition nor correct RVBAR values distinguish firmware reset
ownership from another pre-entry failure. The old diagnostic's claim that one
probe could settle those alternatives was too strong.

## Source fixes prepared

### The CPU driver also reaches the same PMGR sequence

A further trace in the same 26A428 kernelcache connects the CPU driver to
that mask-based path. `AppleARMCPU::startCPU` at `0xfffffe0008c89c6c`
returns immediately for the boot CPU. Otherwise it invokes its
`function-enable_core` object with arguments `1, 0, 0`; it does not forward
the supplied entry or context. The object's creation is visible at
`0xfffffe0008c88a94`, and the boot-CPU flag comes from comparing the CPU
number with `ml_get_boot_cpu_number` at `0xfffffe0008c887dc`.

The specialized `ApplePMGRFunctionEnableCPUCore::callFunction` at
`0xfffffe000988483c` forwards its stored 32-bit mask and the boolean enable
argument through PMGR vtable slot `+0xa88`. Its initializer loads that mask
from the function data at offset `+8`, at `0xfffffe0009884928`.
The T6050 vtable entry at `0xfffffe00082c3c28` resolves to
`ApplePMGR::enableCPUCores` at `0xfffffe000985bafc`, the method already
traced above. The function object's own `+0x140` slot at
`0xfffffe00081d2000` resolves to the specialized call method, not the generic
`AppleARMFunction` dispatcher.

These wrappers add no separate reset release or entry-address write. They
strengthen the case for retaining the existing CPU_START sequence, but do
not account for platform initialization before `startCPU`, nor establish
where the failed secondaries execute. No new hardware sequence follows
from this trace.

### Platform restore has an unresolved ACC difference

The 26A428 trace now also covers platform initialization. `ApplePMGR::start`
at `0xfffffe000983a14c` dispatches register maps, register groups and driver
initialization through T6050 vtable slots `+0xca8`, `+0xcb0` and `+0xcb8`.
It then calls `initAON`, `restoreHW(true)`, `lateRestoreHW` and
`initFixedFreq`. These calls are separate from `AppleARMCPU::startCPU`.

T6050 `restoreHW` at `0xfffffe0009cc0f38` first loops over CPU complexes and
calls `enableCPUComplex(complex, true)`. That method at
`0xfffffe000985bda8` calls `configCPUComplexPowerState` and conditionally
`restoreACC`. The cluster-power implementation still selects low-nibble
level `0xf`. The historical J714s readback already showed that level on all
three cluster controls, so this does not reveal a missing enable request.

That conditional call is not the only route to ACC restoration. Later in
T6050 `restoreHW`, the call at `0xfffffe0009cc11a8` enters the base
`ApplePMGR::restoreHW` at `0xfffffe0009859618`. Its loop at
`0xfffffe0009859770` through `0xfffffe00098597b0` dispatches
`restoreACC(complex, false)` through the object's `+0xcf8` slot for each
configured complex. It does not check the earlier feature gate. The
[gate trace below](#acc-restore-calls-and-feature-gate) identifies that gate
and distinguishes these two paths.

There is a separate ACC initialization detail worth retaining. T6050
`restoreACC` at `0xfffffe0009cc170c` calls the base implementation, then
dispatches `writeACCReg(complex, 0xe440f8, 1, 0)` through slot `+0x1138`.
The fourth argument selects the complex's die when zero; it does not force
every machine to die zero. J714s describes only die zero.

The mapping is now traced through `_getACCMappingAndLength`, `_getAccMapping`,
`initRegMaps` and `ApplePMGR::writeReg64`. Each physical cluster has an
11-entry table. Logical base `0xe40000` selects RegMap IDs `0x2d`, `0x38`
and `0x16`, mapped to PMGR ADT `reg` indices `0x11`, `0x1b` and `0x25`.
The saved J714s ADT translates their bus addresses through `arm-io`'s
`0 -> 0x200000000` range. This gives 64-bit writes of one at
`0x210e440f8`, `0x211e440f8` and `0x212e440f8`. All three offsets fit their
`0xc020`-byte register ranges. These are static address translations, not
hardware reads or observed writes.

The inspected complete
loader's [archived cpufreq.c](../../research-archive/standalone-loader/m1n1-20260911/src/cpufreq.c)
contains a matching `cluster->base + 0x440f8` 64-bit write of one for
older chips, but its switch omits T6050. Its cluster table names T6050 while
`cpufreq_get_features` returns NULL for it, causing `cpufreq_init` to return
before initializing any cluster.

The base ACC restore handles performance counters, CPU energy accumulators
and a feature loop before the final T6050 write. An exact operand search of
the historical `18000.161.9` iBootData found none of the logical, cluster-relative
or bus addresses above. That search cannot exclude computed addresses or
initialization elsewhere in firmware, and it uses an older build than this
kernelcache.

This remains an untested initialization difference. The register's purpose,
current value and dependency on the base ACC restore are unresolved. The
historical tests do not record a deliberate write to this offset. Do not
enable the older-chip
frequency/voltage sequence or copy the entire macOS restore routine into the
loader. No MMIO probe or write was added. The one-core guard remains.

The counter paths were checked separately. `_enablePerfCountersACC` dispatches
through slot `+0xeb8` to the T6050 vtable's `enableCPUPerfCounters` at
`0xfffffe0009cc6644`, which returns immediately. The energy enable method at
`0xfffffe0009cc2d18`, slot `+0xf00`, also returns immediately. This does not
make counter restoration a no-op: the base restore routines still call real
counter setters.

`setCPUPerfCounter` at `0xfffffe0009cc2834` forms its logical write offsets
from four bounded linear expressions or two three-by-twelve tables at
`0xfffffe0007715840` and `0xfffffe00077158d0`. Enumerating a superset of the
linear bounds and all 72 table entries gives 112 distinct offsets, none
equal to `0xe440f8`. The CPM energy and SRAM-energy setters instead write
`0xe48000` and `0xe48008` through `writeACCReg`; per-core energy restoration
uses separate setters and mappings. These traces do not identify the final
`0xe440f8` write as a counter enable, a reset control or a required startup
step. They leave its purpose and prerequisites unresolved.

The separately packaged Stage1 tables were checked too. Within each of
25G72 and 26A428, `iBootDataStage1` and `iBootData` decompress to identical
payloads despite different IM4P wrappers. Both newer wrappers match their
J714s manifest SHA-384 digests. The 26A428 payload is 455,974 bytes, banner
`mBoot-20457.1.29`, SHA-256
`70b919e3ec8b54c9d36979e11e4bc8b73180a1b842db01742dad01bef75d1a44`.
Its four code sections contain 16,088, 843, 5,439 and 59 records. The same
exact-operand ACC search has no matches in this version either.

Opcode numbers are build-specific. For example, the twelve leading records
in `SGP_CE0_ACC0_POWER_UP` have the same operands and flags in both payloads,
but their opcode changes from `0xda` to `0xe0`; the newer sequence also adds
a thirteenth record. Do not apply the older opcode-handler interpretation
to the newer table without tracing its dispatcher. The decoder intentionally
reports raw values. This comparison does not identify the tables present on
the laptop byte for byte, or prove which sequences ran.

The indexed-call trace exposed a conditional path that a sequence-name
filter alone hides. In the older
Stage2, the opcode-table entry for `0xda` points to `0x1cb0e0`, which reads
the first operand as a 16-bit index and reaches the dispatcher at `0x4a1c0`.
That dispatcher bounds its 24-byte entries to `[0x36a340, 0x371900)`, only
1,256 entries. The twelve SGP operands range from `0x5a8` to `0x5b3`, outside
that table. The parser copies their operands unchanged, and the
pre-dispatch hook does not remap them.

All twelve SGP calls are individually enclosed by opcode `0xba` with
operands `16, 0` and an `0xc8` end marker. The guard belongs to the surrounding
MGP sequence, so filtering only SGP records drops it. Handler `0x1cb560`
runs this block only when the current context's 32-bit field at `+184`
equals 16. Initialization at `0x1c524c` calls `0x8d804`, whose five-entry map
is `2, 2, 2, 16, 1`. The map index comes from `0x521bc`, which reads firmware
state registers. This review does not establish their values on the laptop.
The out-of-range indices therefore do not prove an attempted dispatch or a
missing startup operation. Never interpret bytes beyond the table as
function pointers.

Kind 2 is a real selectable input: `0x8db4c` with arguments `2, 0` selects
it through `0x8e300` and `0x1aba9c`, retaining the same opcode table. Actual
selection and nested conditions still matter. In the newer payload, all
thirteen SGP records have corresponding `0xbf` guards and `0xcd` end markers;
only their adjacency is verified here, not the newer handlers' semantics.

The valid MGP indexed routines also use another layer of register descriptors.
For example, index 374 reaches a descriptor containing `0x80e78040`.
Helper `0xa1b94` adds its low 28 bits to an initialized `0x210000000` base,
giving `0x210e78040`. This is a static address calculation, not an observed
write. Searching aligned descriptor words for low bits `0xe440f8` finds no
match in the inspected older Stage2, newer Stage2 or newer Stage1 binaries.
Computed addresses, different bases and other firmware remain outside that
search. No ACC initialization sequence follows from these negative results.

### ACC restore calls and feature gate

The conditional restore in `enableCPUComplex` reads object word `+0x2494`
at `0xfffffe000985be0c`. This is the value of feature 77, named
`acc-cluster-power-gating`, rather than a hardware status register.
`getFeatureValue` at `0xfffffe000983b3f4` uses a 24-byte feature record,
array offset `+0x1d50` and value offset `+0xc`:
`0x1d50 + 77 * 0x18 + 0xc = 0x2494`.

The base constructor copies 97 records from `0xfffffe00081ca770`.
Record 77 at `0xfffffe00081caea8` has a name pointer to
`0xfffffe000764718f`, with both its validity byte and value initially zero.
The copy stub resolves through the GOT to `_memmove` at
`0xfffffe000c40f910`; the name and zero fields were checked directly.

The feature loop in `ApplePMGR::start`, at `0xfffffe000983a510` through
`0xfffffe000983a59c`, first reads each named provider property through
`getDTProperty`. A successful lookup marks the record valid and stores its
value. Only then does it consult the override policy and try a four-byte
XNU boot argument of the same name. T6050's `+0xe10` slot resolves to
`0xfffffe0009cc65e4`, which permits the override. Failed property lookup
skips both assignments and the boot-argument lookup. The saved restore ADT
sets this property to one in four conditional PMGR children, but does not
establish the selected runtime properties or boot argument. This differs
from the separate, boot-argument-only `cpm-power-gating` policy below.

A zero feature value suppresses the restore inside `enableCPUComplex`.
It does not suppress the later base `restoreHW` loop. The T6050 call's base
vtable pointer resolves to `0xfffffe00081c9588`; entry `+0x8e0` selects
`ApplePMGR::restoreHW`. That routine dispatches through the live object's
`+0xcf8` slot, whose separately dumped target is T6050 `restoreACC` at
`0xfffffe0009cc170c`. The loop is bounded by the configured complex count,
not feature 77. Thus the feature gate alone cannot exclude the final
`0xe440f8` write from platform initialization. This establishes another
static call path, not an observed write, its register purpose or its
necessity for secondary startup. No loader option or MMIO change follows.

### ACC feature loop and separate CPM gating

The 26A428 ACC feature loop is narrower than the older loader feature tables.
`AppleT6050PMGR::isFeatureACC` at `0xfffffe0009cc2144` selects IDs
0, 18, 20, 21 and 22 using mask `0x740001` with an upper bound of 23.
The base dispatcher at `0xfffffe00098583e0` resolves as follows through the
T6050 vtable:

| Feature ID | Slot | Result in this loop |
| --- | --- | --- |
| 0 | `+0xd88` | `enableAPSC` at `0xfffffe0009cc1dac` changes bit 23 of logical ACC register `0xe20020`. |
| 18 | `+0xda0` | `enableDVMR(unsigned int, bool)` at `0xfffffe0009cc65a4` returns immediately. |
| 20, 21, 22 | `+0xdb0` | Throttler IDs 1, 11 and 12 reach `0xfffffe0009cc45ec`, which returns for exactly those IDs. |

Only the APSC entry reaches MMIO through this feature loop. Runtime feature
validity and values still gate the call. The saved restore ADT has
`cpu-apsc = 1`; historical APSC readbacks already had disable bit 23 clear.
This does not describe the whole ACC restore routine or every throttler
call. It does show why copying the older loader's throttle-register writes
is not equivalent to the T6050 implementation. The final `0xe440f8` write
remains unexplained.

A separate path, `enableCPMPowerDomainGating` at `0xfffffe0009cc34cc`, loops
over dies and CPU complexes. It preserves all but bit 31 of a 32-bit register
and sets that bit for a true argument. The logical offsets are `0x120 +
8 * complex`; wrappers at `0xfffffe0009cc625c` and `0xfffffe0009cc6268` add
`0x2c000`. The base PMGR accessors select RegMap 0, which `initRegMaps` maps
to ADT register index 0. Translating the saved die-0 ADT gives
`0x28062c120`, `0x28062c128` and `0x28062c130`, all inside the declared range.
These are separate from the previously observed cluster controls and
per-device power-status registers.

`restoreHW` calls this method at `0xfffffe0009cc11e8`, using a stored boolean.
The T6050 constructor at `0xfffffe0009cbf9b0` sets object byte `+0x738e1`
to one with a halfword store of `0x0101` at `0xfffffe0009cbf9f4`.
At `0xfffffe0009cc04fc`, `initDriver` calls
`ApplePMGR::getBootArg("cpm-power-gating", &value)` through stub
`0xfffffe0009cc8a74`. That helper at `0xfffffe000983b0c4` requests a
four-byte value from `_PE_parse_boot_argn` at `0xfffffe000c3a8084`.
If the lookup succeeds, `initDriver` replaces the byte with `value != 0`;
otherwise it leaves the default true. `restoreHW` reads that same byte.
`quiesceACC` also calls the gating method with true.

The earlier description of `cpm-power-gating` as an ADT property was
incorrect. It is an XNU boot argument consumed by this Apple driver, not a
Linux or m1n1 option. Its absence from the saved restore ADT says nothing
about the active policy. The constructor default also does not establish
the registers' state when iBoot hands control to a custom loader.

The live boot argument and register values have not been established. Exact operand
searches of both decoded iBootData versions found no matching register
offsets or bus addresses; indexed or computed accesses remain possible.

This is a newly mapped initialization control, not evidence that changing
it releases a CPU. No live values, reset dependency or recovery sequence are
known. No probe, write or loader change was added. Reproduction uses the
same kernelcache, for example:

```sh
ipsw macho disass KERNELCACHE \
  --fileset-entry com.apple.driver.AppleT6050PMGR \
  --symbol __ZN14AppleT6050PMGR26enableCPMPowerDomainGatingEb \
  --demangle --no-color --force
```

The macOS addresses above belong to the saved 26A428 kernelcache with SHA-256
`a691760372651464138779c3201c1886a385ca656397362d8e7701ba19ebf436`.
Older checkpoint addresses belong to a different image and must not be mixed
with these vtable slots. Local disassembly required `ipsw --force` because
its fileset stub parser rejected a chained pointer; relevant dispatch targets
were checked against separately dumped vtable pointers and GOT symbols.
This was a bounded static review, not an exhaustive platform call-tree audit.

### Guarded loader changes

The patch in [smp/](../../smp/README.md) fixes the six-core mask in both start
and stop paths, and adds the missing return after an incompatible locked
reset vector. It also checks T6050 RVBAR bit 11, rejects mismatched CPU IDs
and die-2 templates, handles stack allocation failure, and quarantines a
timed-out T6050 start. It leaves the one-core guard in place.

The J714s restore ADT describes die-0 CPU IDs 0 through 17 as three groups of
six. Each `function-enable_core` argument is `1 << cpu_id`. The old
`4 * cluster + core` expression overlaps groups and selects the wrong global
bit for CPU6 through CPU17. The corrected expression is `6 * cluster + core`
on T6050 only. CPU1's mask is unchanged.

The diagnostic now accepts only `azahi.smp=probe` and checks both token
boundaries. Previously `prefixazahi.smp=start` could select start mode, and
unknown modes performed PMGR reads before rejection. Duplicate requests are
now refused. The actual compiled diagnostic has no CPU-start or MMIO-write
calls.

Probe access is restricted to T6050, board 8, J714s. PMGR must resolve to
`0x280600000` and cover the CPU_START bank through offset `0x88010`. Each
CPU must have the expected die-0 ID, cluster, core and implementation-register
range. Only `impl+0` is read. It never reads the debug block or `impl+0x100`.
The restore-template die-2 nodes are skipped.

The standalone entry invokes the probe before `kboot_prepare_dt`, and refuses
handoff on a reported diagnostic error. The former proposed call inside
`kboot_boot` was after CPU-node pruning and unsuitable for startup experiments.

## New static SPTM observation

The same public 26A428 restore image contains `Firmware/sptm.t6050.release.im4p`.
Its extracted payload has SHA256
`8adf36441b2d53ad8407cea8e36c46ae3f1743340b1095e3eebbf64c77dd8e2d`.
It was disassembled locally, never executed or placed in this repository.

A path at `0xfffffff0270af400`, with a second entry at `0xfffffff0270af408`,
reads `MPIDR_EL1` and masks it to the low 16 bits. It searches 36 records at
`0xfffffff027116180`, with stride `0x1800`. A record must have a nonzero first
byte and its word at `+0x1620` must match the masked MPIDR. On no match, the
path sets `x0` to `0xdead` and remains in a WFE loop at
`0xfffffff0270af514`. A match selects stack and translation state and proceeds.

The record writer is `sptm_register_cpu` at `0xfffffff0270bcfac`. Its dispatch
entry points to that address and names `SPTM_FUNCTIONID_REGISTER_CPU`. It
finds the requested physical CPU in `/cpus` using its `reg` property, obtains
`cpu-impl-reg`, `acc-impl-reg` and `cpm-impl-reg`, then fills the record. It
stores the physical ID at `+0x1620` and publishes the first byte with a release
store at `0xfffffff0270bd204`. The initial bootstrap calls it for the boot
CPU at `0xfffffff0270e58ac`. Apple's published XNU also calls
`sptm_register_cpu(cpu->phys_id)` while building CPU topology.
Source: [Apple machine_routines.c](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm64/machine_routines.c).

This identifies a registration requirement within SPTM. It does not prove
that the failed cores reach SPTM, that the custom boot leaves it active, or
that these records are missing on the target. A matching Apple RVBAR does
not settle those questions. The next source question is which reset path
iBoot selects under the custom boot policy and whether it requires this
registration. Do not poke the table, call an assumed SPTM ABI, or copy these
virtual addresses into a hardware probe.

## iBoot reset-vector writer and WFI allocation

The public 26A428 iBoot payload was extracted and inspected, SHA256
`2f0b8037ad7163923a72214e4652baa5c0d8df65aa225cac69400393cee44b07`.
It identifies itself as `iBootStage2`; its `mBoot-20457.1.29` banner matches
the recorded Stage1 version number only. The same
hardware log records Stage2 `mBoot-18000.161.9`, which is different. These
findings do not identify the exact Stage2 code that handed off to the custom
loader. The separate historical ibootdata extraction was version
`18000.161.10`, also different from that Stage2; it is not a replacement.
The follow-up identified its reset-vector writer. Addresses in this section
are file offsets in the raw payload, not runtime addresses.

At `0x3fef0`, iBoot aligns its selected entry to 4 KiB and calls `0x170450`.
That routine constructs `(entry & 0x3fffffff800) | 1` at `0x1704c4`, then
writes it to each address from `0x4315c`. It reads the register back and checks
the same mask including the lock bit. The address-list routine constructs
`0x210050000 | (die << 38) | (cluster << 24)`, adds `core << 20`, and iterates
three clusters with a queried core count. This independently confirms the
die-0 implementation-register map used by the diagnostic.

The 42-bit address mask includes bit 11. The old loader comparison masked it
out, so a reset vector pointing 2 KiB past `_vectors_start` could pass. The
patch and diagnostic now preserve that bit. A compiled regression check
rejects both a 2 KiB mismatch and a 4 KiB mismatch before allocation or MMIO
writes. This is a comparison fix, not evidence that either mismatch caused
the historical failures.

Another path allocates `0xc000` bytes at `0x291ac` and fills them with the
WFI instruction `0xd503207f` at `0x291fc` through `0x29208`. The resulting
48 KiB buffer has exactly the SHA256 recorded for the target's CTRR region:
`bc4a4e3073dfa66ac5ea39867e4c18866e96b396f32b9479b1499b9744b81871`.
Any 48 KiB buffer filled with this instruction has that hash. It does not
identify which firmware version created the buffer.
The branch at `0x28554` separates this layout path from the call to
`0x29394`, which prepares SPTM objects. A second allocation on that latter
path fills only `0x4000` bytes with WFI, at `0x2abf8` through `0x2ac44`.
Thus the observed WFI buffer alone does not establish a live SPTM reset path.
Its allocation is now explained, but secondary execution through it is not.

These offsets can be checked without hardware using the extracted raw
payload and an AArch64 objdump:

```sh
aarch64-linux-gnu-objdump -D -b binary -m aarch64 \
  --start-address=0x170450 --stop-address=0x170554 iboot.j714s
```

## Stage versions resolved offline, 2026-09-28

The public `UniversalMac_26.6_25G72_Restore.ipsw` from Apple's update CDN
contains J714s Stage2 and iBootData with the recorded `mBoot-18000.161.9`
version. Both IM4P files match the J714s BuildManifest SHA-384 digests.
Only selected files were downloaded, and nothing was executed or installed.
Matching version strings are not a byte comparison with the target.

The decompressed Stage2 is 4,102,280 bytes, SHA256
`fa596237671bb33aa28c12dfa3f5196595f6bb4be6a3582d1f659ddedfd0c77c`.
It independently confirms the reset-vector mask: call site `0x41bd0` passes
a 4 KiB-aligned entry to `0x171808`, which applies `0x3fffffff800`, sets bit 0
and writes and checks the implementation registers. Its layout path allocates
and fills the same 48 KiB WFI region at `0x2e2e0` through `0x2e30c`.
The iBootData payload is 459,150 bytes, SHA256
`8eee86e205591907b4edfeda6ebdcf29ec9325b4bc4b4c726fe69d8d52871352`.
The table framing is now decoded below. Most operation semantics remain
unresolved; the sequence names alone do not justify a register write.

The public `UniversalMac_27.0_26A428_Restore.ipsw` from the same CDN
also supplies `LLB.j714s.RELEASE.im4p`. Its manifest digest verifies, and its
payload identifies itself as Stage1 `mBoot-20457.1.29`, SHA256
`d54f3496267002816e05e4f4f405374bfe6e755f20792d6f5362cb8d876a9353`.
The entry code loads its relocation destination from file offset `0x380`:
`0x1fc08c000`, exactly the boot CPU's historical `RVBAR_EL2` value.
This gives that address a concrete firmware association. It does not show
where a failed secondary executes, whether Stage1 remains resident, or which
reset exception level that secondary selects. Do not read or modify that
address on hardware to test this association.

These findings improve firmware provenance and preserve the existing mask
fix. They supply no new reset-release sequence, so CPU startup remains blocked
on a new hypothesis and attended evidence.

No new reset-release sequence was established. Do not execute these firmware routines
or replace installed firmware with the analysis input.

## Matching Stage2 selects SPTM from the image layout

The matching `18000.161.9` Stage2 branches at file offset `0x2d534` on the
kernel-layout field at offset `0x38`. A nonzero field calls the SPTM object
layout routine at `0x2e520`; zero continues into the alternate layout path
that contains the 48 KiB WFI allocation described above.

A separate hibernation check identifies this field more closely. At
`0x1a7ab8` it requires layout `present == 1`, and at `0x1a7ac4` tests the
64-bit field at `+0x38` for nonzero. A mismatch with its saved SPTM flag reaches
an assertion string at file offset `0x352809`. That string names the field
`kc_layout->bx_size` and compares the resulting predicate with `uses_sptm`.
This identifies an image-layout condition rather than a per-core power bit.

Asahi's [August 2026 progress report](https://asahilinux.org/2026/08/progress-report-7-2/)
independently describes SPTM setup as conditional on booting XNU, and explains
why normal m1n1 boot leaves it unloaded. The same report describes multicore
progress separately. The inference is that SPTM registration should not be
treated as a universal missing prerequisite for a raw custom loader.

This still does not reveal a failed secondary's PC or the exact live value
of that layout field. The historical raw-loader boot and the WFI buffer are
consistent with the non-SPTM path; they do not authorize probing protected
firmware or issuing SPTM calls. No CPU-start sequence or installed image was
changed as a result of this trace.

## iBootData framing and reset-register references

The offline decoder [decode-ibootdata.py](../../smp/decode-ibootdata.py) parses
the raw `18000.161.9` payload above. It consumes all four code sections exactly:
16,542, 843, 5,411 and 59 records respectively. The name section contains 416
sequence names plus the `MAX_SEQ` sentinel. These are format checks, not proof
that each operation has been understood. No firmware bytes are in the source
tree.

The header is iBootData version 1.0. A target-pointer table selects chip,
revision and a third selector. The six T6050 revision entries in this file
share one `RCfg` directory. Its five 16-byte descriptors contain a 32-bit kind,
32-bit byte length and 64-bit file offset. Kind 4 has 66-byte name entries,
each a 16-bit sequence ID followed by a 64-byte string buffer. Kinds 0 through
3 contain framed records. All integer fields are little endian.

Stage2's parser at file offset `0x1c5004` extracts the record header as follows:

```text
bits  7:0   number of following 32-bit operands
bits 17:8   opcode, ten bits
bits 27:18  sequence ID, ten bits
bits 31:28  flags, retained without interpretation
```

The firmware parser's operand buffer holds 32 words. The decoder checks that
bound, section boundaries, directory ranges, names and the observed layout.
It rejects other layouts rather than guessing. Four in-memory test groups
cover field extraction, every truncation of the synthetic input, malformed
directories/records and CLI preservation of guards with another sequence name.

Two useful register references are now distinguished from executable startup
instructions. Offsets below refer to the matching raw Stage2 or iBootData,
as specified, not addresses to use on the laptop:

- iBootData `0x50e58` and `0x50e94`, sequence `MPMGR_D2A_IBOOT2B`, contain
  opcode 0 with address words `2, 0x80688010` and `2, 0x80688008`, both with
  value 1. Stage2's handler at `0x1c7824` constructs the 64-bit address from
  the first two operands. It queues a 32-bit write through `0x1c6208`.
  The surrounding conditional at `0x50e20`, alternate branch at `0x50e68`
  and end marker at `0x50ea4` mean both writes are not an unconditional list
  to replay. The conditional's hardware meaning is still unresolved.
- The `MGP_CE0_ACC0_POWER_UP`, `ACC1_POWER_UP` and `ACC2_POWER_UP` sequences
  contain opcode `0x15` for all 18 implementation-register bases. Their first
  records are at iBootData `0x5ee34`, `0x61204` and `0x635ac`. The address map
  is `0x210050000 + (cluster << 24) + (core << 20)`, six cores per cluster.
  Stage2's handler at `0x1c8de0` calls the 64-bit read helper `0x1c63b4`, then
  passes that existing register value to `0x1c6208` for later restoration.
  The trailing operands `0, 0x100` are not a literal new reset vector.

The queue routine compiles register writes into command buffers through
`0x1ce28c`; these handlers do not directly perform those writes. Conditional
opcode `0xbe` around the RVBAR records checks the selected cluster's core
count through `0x8f174`. Its packed operand holds cluster in bits 15:8 and
core index in bits 7:0. This supports a per-present-core restoration path.
It does not establish that the historical CPU_START experiments omitted a
required operation, or that these power-transition command buffers were
executed during their reset attempts.

The CPU_START conditional is opcode `0xc0` with operands `0x4000, 0, 0`.
Its handler at Stage2 `0x1cb200` tests bit 46 of the active context's 64-bit
flags at offset `0x50`; it does not read a power register. Context setup
at `0x1c5334` calls `0x8d83c` and stores those flags at image-relative
`0x460450`. Every normal return from that initializer leaves bit 46 clear:
the three initial constants have high words `0x00308001`, and none of its
later flag additions sets that bit. This identifies the initial selection
as the cluster-0 branch. It does not prove the flag's meaning, exclude later
context changes, or turn the branch into a secondary-core release recipe.

Reproduce the structural decode using a separately extracted raw payload:

```sh
python3 smp/test-ibootdata.py
python3 smp/decode-ibootdata.py /path/to/ibootdata.j714s
python3 smp/decode-ibootdata.py /path/to/ibootdata.j714s --all-records > /path/to/full-table.json
python3 smp/decode-ibootdata.py /path/to/ibootdata.j714s \
  --sequence MGP_CE0_ACC0_POWER_UP --word 0x10050000
```

Use `--all-records` when tracing control flow. Sequence and operand filters
can hide guards carrying another sequence name; they are search results,
not self-contained instruction lists. The full view retains file order
within each section and cannot be combined with those filters.

The tool outputs raw operands and file offsets only. It has no hardware,
write, firmware-execution or upload mode. Keep the original conditional
context when interpreting a filtered record. The reset-release blocker
remains unresolved.
## Validation and remaining work

Eight host tests pass. They compile the actual diagnostic and patched start/stop
functions with UndefinedBehaviorSanitizer. They check all 18 masks, legacy
mapping, ordered register writes, incompatible reset-vector refusal, exact
mode parsing, malformed ADT refusals and die-2 exclusion. A simulated timeout
checks that a late core cannot make the boot CPU leave quarantine, change its
target, or replace the retained stack. Allocation-failure and output-directory
refusals are also checked. The tests cannot model real reset delivery, cache
coherence or firmware behavior.

The diagnostic and patched `smp.c` also compile with the aarch64 GCC 16.1
freestanding toolchain, with `-Wall -Wextra -Werror`. The public snapshot
still lacks parts of the private loader, so this is not a linked boot image.
`smp/build-offline.py` now reproduces that build with a complete local header
tree and writes a manifest alongside four objects. The build now includes
`azahi_standalone.c` and a pinned PMGR source patch providing its previously
missing read-only `pmgr_lookup_device_addr` dependency. A relocatable link
resolves the custom entry, diagnostic and lookup symbols. Three host groups
check the lookup without linking MMIO or power operations. Existing output
directories and unreviewed PMGR source hashes are refused; artifacts are
retained. This component check does not produce a complete linked boot image.

The separate [full loader link check](../../standalone-loader/README.md#complete-offline-link-check)
now links both C/assembly/Rust ELF variants with no undefined symbols. Linked
code inspection verifies the standalone entry, diagnostic order and T6050
NVMe refusal. The eighth test checks that this build refuses existing output
and a missing Rust target before preparing artifacts. The private v7 payload
is still absent; no replacement boot image was packaged or installed.

The startup patch now retains the shared reset context and stops after the
first T6050 timeout. It does not use the loader's rebooting panic handler.
A timed-out core must not be followed by another start, chainload, Linux boot
or allocation reuse until a physical cycle. The old stock-start diagnostic
is no longer available. A separate diagnostic entry and a source-backed
reset-release change remain necessary before another start experiment.

After actual loader entry works, Linux still needs the one-core argument and
alive-core refusal changed, all CPU nodes retained in the DT, accessible
spin-table release addresses, and WFI/WFIT handling reviewed. Those constraints
are intentionally unchanged while reset remains unresolved. Success requires
per-core Linux execution, beyond a PMGR power bit or a passing host test.
