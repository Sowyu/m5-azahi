# Recovery / direct CPU diagnostic checkpoint — 2026-09-06

## Current target and next action

**Newest override:** PRIVATE-USER approved one-core native SSD work next, daily macOS
strictly excluded. Fourth clean V5 was replaced in RAM only by the unchanged
native prefix; SSD read-only transfer and native handoff completed. Panel text
is unreadable at current webcam distance; awaiting closer view, not a cycle.
Installed V5/original
backup unchanged. See `NATIVE-SSD-CHECKPOINT.md` for current live state.

**Newest — fourth direct boot CLEAN:** V5base**0x100043a4000**. PRIVATE-USER's physical
cycle and read-only checks verified original loader bytes, zeroCdiagnostic
state, CPU1/6/12off, originalAPSC and restored all-WFI firmware48KiB at
**0x10004bb0000..0x10004bbc000**. Logs cycle4-preflight and cycle4-clean-ram
with cpu-direct-v5- prefix/date. Proxy alive, clientclosed. **No more cycle
needed currently; all older RAMpatch/retainedstack cautions below are history.**
No new CPUstart/power/control/SSD writes this boot. CPUrelease still unresolved;
no new evidence-backed test ready. Asking PRIVATE-USER about moving one-core SSD work
ahead of all-core bring-up. Do not interpret as formatting/repartition approval.
InstalledV5/originalbackup unchanged, no commits.

**Newest — third direct boot tested:** PRIVATE-USER's cycle verified clean V5 at
**0x100055e0000**, previous patches gone, APSC restored. Research-driven
diagnostic now patches only **firmware RAM0x10005dec000..0x10005df8000** from
all-WFI to repeatedSEV/B(-4). CPU1 bounded start and localIPI both negative:
tracezero, noevents, power1f0, proxyalive. Loader reset/main-entry unmodified.
CPU1 Ctarget1/failed1 and allocatedstack retained. Others not requested.
**Next: physical shutdown, then hold power for startup options and choose
Linux** to clear the temporary firmware RAM patch. No additional installation
or Recovery commands. Never chainload/software-reset/restore/reuse this session.
Installed V5/backup intact, no SSD writes/commits this turn; APSC untouched.
Read CPU-CHECKPOINT.md for exact results and CPU-ONLINE-RESEARCH.md for sources.
All second-boot state below is historical, not current.

**Latest:** CPU1 local fast-IPI wake and CPU5 full-bank writes executed in one
on-target call (no USB delays) both gave no secondary SEV events. CPU1–6 now
requested; all existing reset/main-entry patches, traces and disabled cluster1
APSC remain retained. Proxy alive, client closed; no SSD writes/commits.
Logs cpu-direct-v5-local-ipi-20260906.log and
cpu-direct-v5-fast-bank-20260906.log. **Next user action: physical shutdown,
then hold power for startup options and select Linux**, clearing accumulated
volatile diagnostics. Not Options/Recovery; installed V5 remains unchanged.
After boot, fresh preflight must derive the new base and verify original image
bytes/APSC state before any new test. Still only the primary core proven.

**Latest:** cluster1 APSC disabled by one source-resolved bit23 RMW at
**0x211e20020**, now**0xc00102**. CPU6 event test still negative; proxy alive,
client closed. Primary cluster, frequency/voltage values and SSD untouched.
Keep control and all stubs retained until physical cycle, mandatory before
SMP/chainload/Linux/reuse. Evidence cpu-direct-v5-apsc-start-20260906.log.

**Newest RAM state:** first16 reset branches AND main entry at base+0x800
now target **0x10005d97000** (base+0x3000), a two-instruction SEV loop.
CPU3 and CPU4 event-based entry tests both stayed at quiet baseline despite
power1f0. This test does not depend on secondary RAM stores. Proxy alive,
no client; all earlier stubs/traces retained. **Physical cycle before SMP,
chainload, Linux, restoring entry branches or memory reuse.** No further SSD
writes/commits. See CPU-CHECKPOINT.md and cpu-direct-v5-event-*.log.

**Current — second direct boot:** PRIVATE-USER cycled again; fresh V5 boot at
**0x10005d94000** verified. Full-bank CPU1 start and PC-relative in-image
CPU2 entry-marker tests both remained zero despite power status 0x1f0.
All three separate cluster-enable controls at **0x280620000/4/8** already
read **0xf**. No writes to those controls. Still only one proven CPU.

Current reset branches target **0x10005d96000**, trace **0x10005e7c000**
(unused EL3 stack). Old stateless stub **0x10008bb4000** and high-RAM trace
**0x10800012000** retained too. Primary runtime vectors unchanged. C SMP
target/failed flags remain zero because these starts bypassed C: do not
mistake that for fresh hardware. **Physical cycle before SMP initialization,
chainload, restoring branches, reusing allocations, or booting Linux.**
Offline investigation needs no user action; no proxy client is running.

Logs: `cpu-direct-v5-cycle2-preflight-20260906.log`,
`cpu-direct-v5-full-bank-20260906.log`, `cpu-direct-v5-inimage-20260906.log`,
`cpu-direct-v5-cluster-control-read-20260906.log` in logs/. Last check ended
with proxy alive. Installed V5 and original backup unchanged; artifact server
stopped. No further SSD writes, partition changes, or commits. The older
base addresses and next-action instructions below are historical.

Latest read-only RAM check copied the ADT preoslog at 0x1000655c000+0x40000
to `logs/cpu-direct-v5-preoslog-20260906.bin`; proxy alive, client closed.
No additional core starts or MMIO writes since the cluster-control check.
See CPU-CHECKPOINT.md for offline firmware extraction and remaining caveats.

**Newest — direct boot tested:** PRIVATE-USER physically shut down and selected
Linux. V5 booted directly at **0x10005200000**, Running proxy. Verified
first 0x840 reset/entry bytes and 0x800 runtime-vector bytes against the
pinned V5 file, VBAR_EL1=base+0x2a800, MPIDR=0x80040000, EL2, unused
diagnostic state and locked CPU0/1/6/12 RVBAR addresses matching base.

CPU1 bounded WFE startup failed at stage 0, all five trace words zero.
Late observation remained zero; CPU1 power=0x1f0, global start=0x3fffc,
cluster0 doorbell=0, retained reset stack **0x10008030000**. CPU6 and CPU12
follow-up stateless parking tests also reported power=0x1f0 but all trace
words zero. No newly proven CPU in any cluster. This rules out RAM
chainloading as the sole cause, not all firmware/entry/trace-store causes.

**Current live RAM is patched:** first16 reset B instructions target a
native retained stub at **0x10008034000**, trace **0x10800012000**. Primary
runtime vectors unchanged, CPU1 target=1 and retained stack untouched.
Never reuse/free this stub, restart SMP, restore branches, chainload, or
boot Linux in this session. **Physical cycle into Linux proxy is required
before new hardware tests.** No current proxy client. Installed SSD V5
file is unpatched; these follow-up changes were RAM only.

Evidence: `logs/cpu-direct-v5-screen1-20260906.jpg`,
`logs/cpu-direct-v5-preflight-20260906.log`,
`logs/cpu-direct-v5-start-20260906.log`,
`logs/cpu-direct-v5-postcheck2-20260906.log`,
`logs/cpu-direct-v5-cpu6-park-20260906.log`,
`logs/cpu-direct-v5-cpu12-park-20260906.log` (ends CPU12_PARK_PROXY_ALIVE).
First postcheck helper had a host AttributeError for dc_ivac_range, stopped
before any cache op; corrected to existing dc_ivac/u.exec APIs and passed.

Artifact server PID 39462/session7708 was stopped after boot, not running.
Start `python3 -u probe/recovery-loader-server.py --bind PRIVATE-LAN-ENDPOINT-REMOVED` only
when Recovery install/restore downloads are needed. Original backup intact.
No further SSD writes after diagnostic installation; no commits.

Offline comparison: current Asahi/Yureka SMP code uses the same CPU1 start
sequence and T6050 offset. Neo fork avoids RVBAR writes and defaults WFE;
our test already avoids those writes and sets WFE before startup.
Sources: https://raw.githubusercontent.com/AsahiLinux/m1n1/main/src/smp.c
and https://raw.githubusercontent.com/MiyakoYakota/m1n1/main/src/smp.c .
No demonstrated T6050 fix was found in that comparison. Next work remains
firmware reset/handoff investigation; do not guess additional MMIO writes.

**Latest:** PRIVATE-USER ran the guarded helper, typed INSTALL, confirmed kmutil,
and authenticated locally. Webcam
`logs/recovery-webcam-20260906-diag-install1.jpg` shows
`KMUTIL_COMPLETED mode=diag`, with policy-after output saved in Recovery
/tmp. Linux Preboot was remounted writable and kmutil installed the V5
custom boot object and updated its local boot policy. **Target boot-file
writes have now occurred.** No partition changes or commits. Direct boot
is not yet verified; next step is shutdown, hold power for startup options,
choose Linux, and inspect Running proxy before any bounded CPU test.
Older 'not installed' statements below are superseded by this paragraph.

M5 Mac17,9 is in paired Linux Recovery, Terminal open. Earlier V5 RAM
session ended with a physical cycle. **No diagnostic installation yet.**
Only one CPU remains proven. No commits, partition changes, or macOS edits.

PRIVATE-USER's current boot object is backed up and verified. Prepared direct
installation of the same V5 diagnostic to eliminate RAM chainload as a
variable. This is a diagnostic-only proxy loader, **not persistent KDE**.
No Linux payload may run with its high-RAM CPU trace.

Read-only artifact server is running on host PRIVATE-LAN-ENDPOINT-REMOVED, exec session
**7708**, `probe/recovery-loader-server.py`. It exposes only `/loader.sh`,
`/diag.bin`, `/original.bin`. Previous backup receiver PID 39378 stopped.
Downloaded bytes for both binaries verified against SHA256 locally; helper
syntax and M1-model refusal checked. Helper not yet run on M5.

User next commands on M5:

```sh
curl -f PRIVATE-LAN-ENDPOINT-REMOVED -o /tmp/loader.sh
bash /tmp/loader.sh diag
```

The helper validates model and exact Linux/Preboot identities, existing
paired permissive policy and original coih, and both download CRC/sizes.
Requires user to type INSTALL, then remounts **only Linux's Preboot** writable
and runs kmutil for /Volumes/Linux. Administrator authentication stays local.
No bputil policy downgrade, partition actions, or automatic reboot. Stop on
any error; inspect webcam after KMUTIL_COMPLETED before asking for reboot.

Source method: https://asahilinux.org/docs/sw/m1n1-user-guide/

## Verified disk and policy identities

- Linux system: disk4s3, `/Volumes/Linux`, read-only, UUID
  **PRIVATE-UUID-REMOVED**.
- Linux volume group / Data UUID: **PRIVATE-UUID-REMOVED**.
- Preboot: disk4s4, `/Volumes/Preboot`, currently read-only, UUID
  **PRIVATE-UUID-REMOVED**.
- Same container disk4 UUID **PRIVATE-UUID-REMOVED**,
  physical store disk0s3. Never format or repartition this APFS container.
- Paired 1TR, Permissive, kernel CTRR disabled, SIP and SSV enabled.
- Original active coih:
  `84EBA1015DBA2FE2D992D8161B2540F2ECBE1F895CE82EAC3A05B100EBDB39C8E2A815BADB88CD38ABC3388EC91E8269`.
- Full exact original path in backup `manifest.tsv`; basename matches coih
  and boot directory matches nsih. This is filename/policy matching, not a
  claim that a locally recomputed IMG4 hash equals coih.

## Backup evidence and recovery path

Host folder: **logs/recovery-backup-20260906.eTn0av**. Contains archive,
receipt, validated/extracted regular files, and `original-loader.bin`.

- archive: 228804 B, CRC 277424912, SHA256
  `a514bcc05acc8b0d8507e3a6ee9f576afa30538d4f2d256f4b0d4bb0c4fd8e83`.
- original wrapped IMG4 `custom-01.bin`: 1117034 B, CRC 1531755257,
  SHA256 `fed0eb4d7ea1eaf6ba10d0487840bb59f4940edcc986b029b3b5753630bf7e31`.
- extracted original raw loader: 1114112 B, CRC 330887840, SHA256
  `f2f234d99be7bdd0181366ec16c055ac14bdfa48cb2774c238836462521d2505`.
- diagnostic V5 raw: 1114112 B, CRC 901225419, SHA256
  `7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef`.

Recovery helper compared source/copy CRC and sizes, then compared archive
CRC/size with host receipt. Host independently recomputed source CRC from
received bytes and SHA256. Recovery lacks OpenSSL and cmp; no cryptographic
hash or byte-for-byte comparison on target is claimed. Earlier cmp failure
was missing-command, not detected corruption. Photo confirming BACKUP SENT:
`logs/recovery-webcam-20260906-backup-result1.jpg`.

`probe/extract-recovery-loader.py` pinned wrapped SHA256 and strict DER,
verified fuos payload and raw SHA256, and decoded original PAYP:
entry kcep=2048, kclo=0, kclf=1114112, kcwf=0, kcwz=1114112,
kclz/kcrf/kcrz=0. Extraction refused overwrite.

To restore the original loader, boot paired Linux Recovery again, ensure
Linux is mounted at /Volumes/Linux, start the host artifact server if needed,
download /loader.sh as above, and run:

```sh
bash /tmp/loader.sh restore
```

This reinstalls the exact backed-up raw loader with original entry/mapping,
using kmutil to generate the local policy. It does not restore the prior
signed IMG4/policy byte-for-byte. Keep both original IMG4 and raw backup.
Do not blindly copy signed boot files or change bputil security settings.

After diagnostic installation and physical boot into Linux's Running proxy,
verify V5 image identity/base before any CPU start. Use bounded CPU1 WFE
test first, retain failed-core stack on timeout, and obey CPU-CHECKPOINT
forbidden debug/MMIO rules. No further cores are claimed working yet.
