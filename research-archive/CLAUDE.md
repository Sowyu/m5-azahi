# Asahi Linux on Apple M5 Pro — start here

## Current operational override — 2026-09-06

**Newest direct-boot result:** V5 booted directly at0x10005200000. CPU1,
CPU6 and CPU12 tests still produced no entry markers, despite power-on
status. Current reset branches are RAM-patched to retained parking stub
0x10008034000; CPU1 target1/stack0x10008030000 preserved. Proxy alive, no
client. Physical cycle required before new hardware tests/chainload/Linux.
Artifact server stopped. Original loader backup intact; no further SSD
writes or commits. Details: probe/RECOVERY-CHECKPOINT.md. Supersedes below.

**Newest:** V5 direct installation completed in Linux's custom boot slot;
webcam confirmed KMUTIL_COMPLETED mode=diag after PRIVATE-USER's local approval and
authentication. Original loader is backed up. M5 still in Recovery; next
shutdown and select Linux from startup options, then verify direct proxy
and bounded CPU test. No repartitioning or commits. Still one proven CPU.
This supersedes 'not run yet' below. See probe/RECOVERY-CHECKPOINT.md.

**Recovery update supersedes the live-RAM state below:** M5 is in paired
Linux Recovery Terminal. Original custom loader backed up, CRC/size verified,
SHA256 recorded, and exact raw restore loader extracted. Direct V5 install
helper prepared but **not run yet**; no target boot-file writes. Host serves
only loader.sh/diag.bin/original.bin at PRIVATE-LAN-ENDPOINT-REMOVED, exec session 7708.
See **probe/RECOVERY-CHECKPOINT.md** for identities, backup, install/restore
commands, and next action. No commits. Still one proven CPU.

**Latest hardware state:** V5 at 0x1000495c000, with 16 reset-slot branches
now redirected to stateless parking stub 0x1000768c000; separate trace at
0x10800012000. CPU1 V5 test failed at stage 0. Correct-mask CPU6 (0x40) and
CPU12 (0x1000) tests also powered up to 0x1f0 but produced no entry marker.
Proxy survived; latest log `logs/cpu-diag-v5-cpu12-park-20260906.log`. No
client running. No new proven core, SSD writes or commits. Do not chainload,
restart SMP, free/reuse stub, restore branches or boot Linux in this session.
Next discriminating test needs direct Apple boot of an instrumented loader,
requiring Recovery access and verified backup first; nothing installed yet.
See newest `probe/CPU-CHECKPOINT.md`; older V4/live-state text below is historical.

Latest request: **all CPU cores first, then persistent internal-partition
boot for tinkering; GPU afterwards**. Native KDE now reaches graphical
Plasma first-run setup, confirmed by PRIVATE-USER, who reports severe lag. Evidence:
`logs/native-kde-boot-20260906.log`, `logs/native-kde-screen4-20260906.jpg`.
Normal native desktop completion and physical input remain unverified.
That RAM session has since ended: webcam showed Running proxy, and the
private V1/V2/V3 CPU diagnostics were loaded/tested. CPU 1 timed out at
trace stage 0 in all three. Post-start SEV and explicit PoC clean did not
help. A subsequent read-only debug CIDR0 access at **0x210010ff0** caused
SError/proxy timeout; that helper is disabled. Do not retry that block.
PRIVATE-USER cycled after the debug fault. V4 alternate-main-entry diagnostic was
tested at base 0x10005a0c000: stage 0 again, proxy survived. Guarded CPU1
ACTIVE request also made no difference; latest log is
`logs/cpu-diag-v4-active-20260906.log`. No client remains running. Keep its
retained CPU1 stack/target intact; do not reinitialize SMP or chainload.
Current work is offline AppleT6050PMGR restore-cache analysis. Its startup
register group confirms map 0 + 0x88000; topology translation under review.
V5 is now built/verified, not loaded: all 16 reset-vector slots instrumented,
normal exception table separate. Requires a fresh physical cycle before
testing. Architectural RVBAR_EL2 on primary reads 0x1fc08c000 (firmware),
not the separate Apple implementation RVBAR; this does not identify CPU1 PC.
See `probe/CPU-CHECKPOINT.md`. No SSD writes have occurred.

The previously
verified KDE guest was stopped cleanly for these tests. Fresh proxy SMP
startup still fails on all 17 secondaries. A minimal native image reached
initramfs userspace output, but the full native input/RAM-root image panicked.
The panic was isolated to an accidentally omitted SMC client blacklist;
restoring it reached Fedora automatic root login natively. All-core
operation is still unverified; all 17 secondary starts failed. See PROGRESS.md
and the current `probe/boot-native.py` logs; do not infer current running state
from older PID or leave-running instructions.

Read the live update at the top of `PROGRESS.md` before using historical
commands below. We are on the M1 Pro host; the USB-tethered target is T6050.
PRIVATE-USER authorized reversible local kernel/module work and prioritizes built-in
input. Keyboard and trackpad are now physically verified using the local
dockchannel-HID replacement module; `Image-asahi` remains pristine.

Never repartition or alter macOS. The SSD queue-wrap fix now passes 8,192
direct reads; no target disk data has been written. The 250 GB "Linux" space
is APFS with boot/recovery volumes, not a Linux root filesystem. Installation
needs an explicit storage-layout decision; see `probe/SSD-CHECKPOINT.md`.
The current runner is `probe/boot-input.py`, not old `hv-fixed.sh`/`gstop.sh`.
ANS PMGR belongs at **0x280900000**, not older banks; never execute the old
`anspower_inline.py`. Guest exit does NOT reliably permit reconnection;
request a physical cycle when needed, and never open a second proxy client
while the guest runs. PRIVATE-USER explicitly overrode the local `m1n1/` AI-work
restriction for this private copy on 2026-09-06, with **no commits**. Local
RAM-only CPU diagnostics are now permitted; do not submit anything upstream.
See `probe/CPU-CHECKPOINT.md`. This does not authorize disk-layout changes.
Historical hardware addresses and recovery claims below are superseded by
the verified current notes.

Porting Linux to a MacBook Pro 14" M5 Pro (Mac17,9, SoC **T6050 "Sotra"**,
chip ID 0x6050). **Read [BRINGUP.md](BRINGUP.md) first** — it is the complete
findings document and is kept current.

## Status

Linux **boots** as an m1n1-hypervisor guest; full Fedora runs from a RAM rootfs
with an interactive root shell (`guest-hv-ramroot.bin`, known-good). Bare metal
still dies after `tick_init` — unsolved.

**Current goal: KDE running from the internal SSD.** The user's constraint is
absolute — *use the Linux partition that already exists, never repartition,
never touch the macOS install*. Read before writing; verify the target
partition by identity first.

Storage needs **no kernel patches**: `nvme-apple`, `apple-sart`, `apple-dart`
and `apple-dockchannel` all bind on generic/older-SoC compatible strings
(checked against the running kernel's own `modinfo -F alias`). It is pure
device-tree work. See the 2026-08-29 section of BRINGUP.md.

The kernel is the **pristine** `Image-asahi` — no kernel patches. Every fix
lives in m1n1 or the device tree. Keep it that way.

## The two machines

The Mac running Claude **is the M5** — the machine under test. Booting it into
m1n1 kills your session. A second Mac (PRIVATE-USER's M1 Pro, borrowed) drives m1n1
over USB:

```bash
ssh -i ~/.ssh/id_ed25519_azahi PRIVATE-USER@PRIVATE-LAN-ENDPOINT-REMOVED   # user is PRIVATE-USER, NOT PRIVATE-USER
```

Its working tree is `~/azahi/`. Deploy with `sh deploy.sh`. Logs come back over
the same link — never ask the user to paste them.

**Every proxy run costs the user two reboots.** Batch every diagnostic into ONE
script per trip. This was the single biggest early mistake.

### If you are running ON the M1 Pro (`PRIVATE-USER@Alexs-MBP`)

Then you ARE the host — no ssh, no deploy step, and **the reboot tax is gone**.
The user boots the M5 into m1n1 once and leaves it; you run tests, read logs,
fix and re-run as often as you like without involving them. The M5 reboots
itself back to `Running proxy...` after a guest crash, so even a failed run
needs no human.

Run things directly out of `~/azahi/` (the live kit — proxyclient, vendored
`lib/`, images, logs). This project tree is the source of truth; copy built
artifacts into `~/azahi/` rather than running from here. Check the M5 is
present with `ls /dev/cu.usbmodem*` — two ports means m1n1 is up: the first is
the proxy, the second is the guest console.

Use this freedom to iterate, but tell the user what you are doing periodically —
silent work is invisible work.

**The M1 Pro can build everything** — verified 2026-08-16. Homebrew, `dtc`,
`clang`, `ld.lld` and `cargo` are all installed (a non-interactive `ssh` shell
has a bare PATH and will wrongly report them missing — check locally). Both
builds are byte-for-byte reproducible and match what the M5 produced:

```bash
cd ~/azahi-port/m1n1 && make USE_CLANG=1 RELEASE=1 -j8      # m1n1
cc -E -nostdinc -I. -Idt-bindings -undef -D__DTS__ -x assembler-with-cpp \
   t6050-j714s-hv.dts | dtc -I dts -O dtb -o t6050-j714s-hv.dtb
```

ADT parsing works here too:
`PYTHONPATH=m1n1/proxyclient python3 -c "from m1n1.adt import load_adt; ..."`.
So nothing needs the M5 except being the target. Note `~/azahi-port/` is the
source tree and `~/azahi/` is the live kit — copy artifacts across, do not run
from the tree.

## How to run

M5 → boot into m1n1 → `Running proxy...`, then on the M1 Pro:

```bash
GUEST=~/azahi/guest-hv-ramroot.bin sh ~/azahi/hv-fixed.sh        # known-good
ANSPOWER=1 GUEST=~/azahi/guest-hv-nvme.bin sh ~/azahi/hv-fixed.sh  # + NVMe
sh ~/azahi/run.sh ~/azahi/anspower.py                            # read-only survey
sh ~/azahi/waitprobe.sh                                          # retry until alive
sh ~/azahi/gstop.sh                                              # STOP a guest CLEANLY
```

`m1n1-nvme.bin` is the current chainload image (vmtmr fix + SART v4).

Guest kernel log lands in `~/azahi/guest-console.log` (the **second** CDC port),
hypervisor trace in `~/azahi/hv.log`. The M5 self-recovers to `Running proxy...`
after a guest crash, so repeated runs need no user action.

## Hard-won facts — do not re-derive

- **`SYS_IMP_APL_VM_TMR_FIQ_ENA` (s3_5_c15_c1_3) writes UNDEF while the hv runs
  a guest.** Reads are fine; writes are fine in plain proxy context. It is
  state-dependent. This is the real M5 silicon divergence. Fixed in
  `src/hv_exc.c` by masking guest timers via `CNTx_CTL_EL02` IMASK.
- **Secondary CPUs never start on T6050.** Guest CPUSTART → `hv_start_secondary`
  blocks forever. Run with `-C 0` (guest sees only cpu0).
- **PMGR writes SError the host.** The hv replays guest PMGR writes onto real
  hardware and upstream's replay *forces the domain on*. Shadowed for 0x6050 in
  `hv/__init__.py map_essential`. The guest DTB has the whole pmgr tree deleted.
- **Protected carveouts are never unmapped** (no MCC support), so the OS is
  fenced to `0x1010A960000..0x10F4AB00000`. Anything handed to Linux must live
  inside it: kernel `0x10800000000`, FDT `0x10900000000`, initrd `0x10A00000000`
  (all pinned in `src/kboot.c`). Outside it, Linux silently discards the initrd
  and panics.
- **CNTFRQ is 1 GHz**, not 24 MHz. Truthful, ARMv8.6-mandated, benign.
- Reading `UPMCR0`/`VM_TMR_FIQ_ENA` is **not** fatal — an early theory that cost
  a dozen boots. All 21 IMP-DEF regs `hv_start` reads exist and read fine.
- **ANS/NVMe addresses come from the ADT, not from cross-generation patterns.**
  `/arm-io/ans` reg[3] = nvme `0x21dcc0000`, reg[0] = ASC `0x219600000`
  (mailbox = +0x8000 = `0x219608000`), `/arm-io/sart-ans` = `0x21dc50000`.
  The `nvme - 0x48b8000` mailbox offset is exact on t8103..t6031 and **wrong
  here** — the ASC moved on T6050.
- **SART is version 4** on T6050; m1n1 and Linux both only know 0/2/3. Treating
  it as v3 works (patched `src/sart.c`), so the `apple,t6000-sart` fallback in
  our DT should be enough for Linux unmodified.
- **`src/rtkit.c:637` waits for the coprocessor forever** — no timeout. If ANS
  does not answer, m1n1 wedges and the machine needs a physical power cycle.
  Linux's `apple.c` is far more careful (handles crashed/running/stopped, and
  times out), so a failed m1n1 `nvme_init()` does NOT predict a failed Linux
  probe.

## Debugging technique that works

- **Order of operations around powered-down blocks, non-negotiable:**
  PMGR read (always-on, safe cold) → power on → PMGR verify PS_ACTUAL == 0xf →
  only then read the block's MMIO → only then attempt any handshake. A cold
  read of a gated block is an SError that wedges m1n1 and costs the user a
  physical power cycle. This cost two reboots on 2026-08-29.
- `GUARD.SKIP` + `p.get_exc_count()` probes unknown registers without killing
  the machine — but it does **not** cover SErrors, and does not apply at all
  once m1n1 is sitting in hv context after a killed guest.
- `~/azahi/gpull.py` pulls a file out of the guest over the vuart, sha256
  verified. The guest's stdout is full USB speed; only RX injection is slow.
- The Fedora rootfs ships **Apple's official DTs for every SoC up to M3** in
  `/usr/lib/modules/$(uname -r)/dtb/apple/`. `t6030-j514s.dtb` (M3 Pro 14") is
  the closest template to j714s; decompiled copies are in `refdt/`.
- `iface.readmem` pulls the running binary back for disassembly. **Chunk at
  64 KB** — a single 2 MB read drops the CDC link.
- Resolve running-image addresses against a **pristine rebuild** of the exact
  commit, byte-compared to the dump. The M5 runs stock m1n1; the local tree is
  patched, so local offsets lie.

## Rules

- `m1n1/CLAUDE.md`: upstream **forbids AI-assisted contributions**. Read the
  sources freely, never propose patches for upstreaming.
- Consult a **fable** subagent at every decision point, in the background — then
  verify what it returns. It has been wrong and self-reversed several times.
- Verify artifacts (checksums, disassembly, decompression) before telling the
  user to boot anything. A wasted boot costs them ten minutes.
