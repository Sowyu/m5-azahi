# Native root-only write test — HARDWARE PASS (2026-09-06)

**Current-state override:** actual SSD-root v3 has now reached KDE. The target
was last seen with root mounted read-write, guard armed; do not apply the
historical post-padding-test disarmed/RO state to it. See
[current handoff](../CURRENT-STATE.md) and [SSD boot result](SSDROOT-BOOT-CHECKPOINT.md).

## Next candidate now prepared

Actual SSD-root KDE candidate built/offline tested after user asked what next:
`probe/SSDROOT-BOOT-CHECKPOINT.md` is the current handoff. User asked to poweroff
then select Linux proxy; target has not yet booted this new candidate. Existing
rootguardv1 hardware success below remains the storage-driver evidence.

## LIVE OVERRIDE — test finished successfully, target is native RAM Linux

**Latest webcam — corrected mount SUCCEEDED:**
`logs/rootguard-user-bug-screen2-20260906.jpg` shows corrected
`ro,rescue=nologreplay,subvol=root` command, Btrfs enabling nologreplay, then
installed /etc/fstab printed. The user repeated the command (possibly stacked
mounts; inspect mountinfo before any later unmount). Root SSD filesystem is
now mounted read-only at /mnt/ssd; running OS / remains the minimal RAM root.
No arming or RW mount was requested. The visible systemd "fstab has been
modified ... daemon-reload" hint is not a mount failure; no reboot needed.
Visible fstab contains Btrfs / and /home subvolumes, separate ext4 /boot,
vfat /boot/efi. Do not assume these stock boot partition UUIDs match new GPT;
boot/EFI mounts will need deliberate configuration for eventual SSD boot.
OCR of this photograph was unreliable; refer to image, not OCR fragments.
This supersedes the previous mount-not-yet-successful note below.

**Correction after user-reported mount error:** Webcam
`logs/rootguard-user-bug-screen1-20260906.jpg` shows btrfs rejecting the plain
`nologreplay` mount parameter from our suggested command. Exact local
linux-7.0.13/fs/btrfs/super.c confirms only `rescue=nologreplay` (or legacy
`norecovery`) is accepted. This is our command error, NOT a failed write test.
Mount did not succeed. Correct next command, still read-only/no log replay:
`mount -t btrfs -o ro,rescue=nologreplay,subvol=root /dev/nvme0n1p5 /mnt/ssd && cat /mnt/ssd/etc/fstab`.
The /mnt/ssd directory already exists from the prior successful mkdir. Do not
enable writes, repair the filesystem, or reboot to address this parser error.
Bare `nologreplay` references in historical prose below mean the intended
no-log-replay behavior; actual commands must use `rescue=nologreplay`.

After userdone, both USB CDC nodes present. Read-only V5 preflight passed:
`logs/rootguard-v1-proxy-preflight-20260906.log`; base10004114000, unusedV5
state verified, secondary alive[], CTRRWFI10004920000..1000492c000, proxyalive.
Unchanged native prefix chainload passed:
`logs/rootguard-v1-chainload-20260906.log`. Native boot runner completed all
RAM transfers/ANS/DAPF preparations and handoff, exit0:
`logs/rootguard-v1-native-boot-20260906.log`.

Webcam boot first `logs/rootguard-v1-boot-screen1-20260906.jpg` shows startup.
Second `logs/rootguard-v1-boot-screen2-20260906.jpg` explicitly shows native
test success: GPT primary/backup/root-prefix verified, identities verified,
root-only arming, WRITE_FLUSH_READ_PASS, PADDING_RESTORED, disarmed, repeated
region verification, `ROOTGUARD_TEST_PASS` and `ROOTGUARD_CHECK_DONE`.
The pass marker requires original protected partition headers unchanged within
this boot, other namespaces0 written sectors, main exactly64 written sectors
(16KiB test plus16KiB restore), and all namespacesRO. Driver parameterN again.
NVICLOG-not-yet-written/ERR_ABSENT RTKit messages still appeared, as before;
they did not prevent this test from completing. No panic/IO failure observed.

This is proof of this bounded native write/flush/read/restore test, NOT general
SSD stability or power-loss durability. No SSD filesystem was mounted by test.
KDE image remains14.25GB inside158.78GB root partition, unchanged prefix.
No EFI formatting, loader installation, filesystem grow, or new CPU/GPU work.
No daily macOS filesystem mutations targeted. No commits.

Leave M5 running; USB proxy is now gone, no native remote shell/input transport.
Next user command requested: mount ONLY new root read-only with nologreplay
and subvol=root, then display /etc/fstab to prepare disk-root initrd/config.
Use exact root PARTUUID or verified native nvme0n1p5; not Recovery disk names.
Do not arm/mountRW manually or powercycle until a next candidate is prepared.
Play audible cue at handoff. Old sections below are build/procedure history.

Host inspection for next initrd: stock `initramfs-asahi.img`66MiB includes
bash,cat,cp,blkid,btrfs,mount,findmnt,partx,modprobe,depmod,udevadm but NOT
python3,dd,sha256sum,cmp,blockdev. Need deliberately add required utilities/
dependencies or a reviewed small verifier; do not assume old RAM Python test
can execute directly in the stock initrd. Proven input-v2 composition is
stock initrd +893MiB minimal RAM cpio +small input overlays. New SSD initrd
should omit RAM cpio, retain needed input overlays, provide root-mount unit
and copy its configuration into mounted SSD root before switch-root. Nothing
for that next candidate implemented yet in this turn.

## Immediate handoff

M5 is still in Recovery. Webcam `logs/rootguard-ready-recovery-screen-20260906.jpg`
confirms successful root installer final marker and shell prompt. Root transfer
serverPID54038 stopped normally AFTER completion. Do not rerun installer.
User is being asked to shut down via Apple menu, then hold power for startup
options and choose **Linux**, not Options, reaching **Running proxy**.
No host proxy serial device exists before that physical action.
Play sound at EVERY final/handoff, and don't address user by name. No commits.

This is NOT standalone boot. Only one CPU proven. All17 other cores remain
unresolved. GPU remains software. Installed SSD KDE root is fully verified,
but disk-root initrd/config and permanent loader still need implementation.
Daily macOS partition2 is explicitly out of scope for filesystem mutations.

## Candidate / checks

`native-rootguard-v1-20260906.bin`,1027838716B, SHA256
`fbb7c705d7f8741e1debd84b973254fdf24b37ba53d7822177d4ae4aaa82fb4e`.
Manifest same basename.json records module/asset/region hashes.
DT `t6050-j714s-native-rootguard.dtb`, SHA256
`ddd855503c88b8b3b0afe64b4f3862dee2ec328c347b6c7eca5664bdf1fee5f8`.
Root NVMe module `nvme-driver/build-rootguard/nvme-apple.ko`, SHA256
`696d0fded6a47bb9929e1f49b1a38d166d6c539e573696c3c206b84c13c6708c`.
Uses PROVEN SART `nvme-driver/build/apple-sart.ko`, SHA256
`58ba58e4a6dd0b4574751d224772d9bfe447fa3f4e8bdba8cfa9e7c52b80305d`;
do not substitute newly compiled rootguard-directory SART (different build
metadata/hash, not used). Original RO NVMe module/hash/payload untouched.

Builder `probe/build-native-rootguard.py` refuses overwrite, validates pinned
source input-v2 image and completed Recovery after-report. Base RAM initrd is
byte-for-byte unchanged, appended archive carries new modules/test overlay.
Actual appended cpio validated by `probe/verify-rootguard-archive.py`:
10 exact asset hashes, one service symlink, uid/gid0, no unsafe archive paths.
Both new `--rootguard-test --offline` and old `--ssd-readonly --offline` pass.
New candidate with no SSD mode deliberately fails before any hardware access.
Mutually exclusive modes preserve old driver/boot guards.

`bash nvme-driver/test-root-write-policy.sh`:525366 assertions of exact shared
C policy with address/undefined sanitizers. Every65536 NVMe transfer length
at both boundaries/overflow, every control pattern/opcode/flags, wrong NSIDs,
payload lengths, geometry, metadata, passthrough and flush misuse.
`python3 probe/test-native-rootguard.py`:11 tests (some subtests), covering
filesystem identity/geometry/test extent, hashes and padding restoration on
successful write, failed flush, failed read-back and failed restoration.
First test run exposed bytearray-vs-bytes UUID test incompatibility; fixed and
rerun passes. Initial builder expected20KiB backup file; real collector stores
24KiB (including Recovery final data LBA). Fixed to hash only final20KiB GPT,
NOT Recovery data which may legitimately change during Apple boot. No failed
builder invocation wrote a candidate image. Archive inspection initially used
unbounded marker search (loader string); persistent verifier now locates after
DT/kernel as builder does and passes. These were host checks, no target writes.

## Driver restrictions

Private `nvme-driver/apple.c` builds rootguard only with AZAHI_ROOT_WRITES.
`build-modules.sh rootguard` writes separate `build-rootguard/`; default RO
mode still exists but do not rebuild over pinned old artifacts unnecessarily.
New root build has ONLY `azahi,j714s-nvme-rootguard` DT alias, no stock/RO
fallbacks. Retains established .j714s_readonly hardware quirks: warm firmware,
NVMMU separate BAR, IOQ registers/63 queue depth, cold/runtime reset refusal.
Requires apple,j714s model and fixed DT root UUID/start/exclusive-end properties.

`nvme-driver/root-write-policy.h` shared with host C tests. Compile-time only:
NSID1,4096-byte LBAs, root UUIDPRIVATE-UUID-REMOVED,
allowed LBAs[204034123,242798667). No runtime range parameters. Every final
non-read I/O command checked after nvme_setup_cmd and BEFORE DMA mapping/
submission. Only non-passthrough ordinary block WRITE with exact payload
length, no metadata/PI/directives/fused flags, FUA/LR only, wholly inside range.
Ordinary zero-payload FLUSH on NSID1 allowed only armed; it has namespace-wide
scope but only drains already queued writes. No discard/write-zero/format/
sanitize/vendor media commands. Existing admin read/setup allowlist retained,
including volatile set-features with Save bit forbidden.

`/sys/module/nvme_apple/parameters/root_write_armed` is0600, defaultN. True at
module-load time refused (probe not yet bound). Probe success leaves disarmed;
userspace must verify disk/GPT/root before writingY. Disarm writesN. Remove
clears state. This is an accidental-write guard, NOT protection against a
malicious root process replacing kernel/module. Hardware write behavior remains
experimental; offline testing is not proof of correct NVMe media behavior.

Read exact upstream7.0.13 core.c from local tar: nvme_setup_flush zeroes command;
nvme_setup_rw initializes checked fields, FUA/LR bits. Fedora delayed-flush patch
reviewed; it completes flush early and defers actual operation. NOT copied:
experiment tests actual synchronous flush, no early acknowledgement.

## What runs on next RAM boot

`native-rootguard-check.service` runs after input check, before tty1 getty, with
fallback `.bash_profile` once marker. `/run/native-rootguard.log`, tty1 output;
Timeout240sec. Uses proven `probe-ssd-readonly.py`: require masks, stop udev
execution, explicitly load module, set all namespacesRO, resume udev.

`native-rootguard-test.py` requires targetaarch64/J714s, explicit boot argument,
RAM root loop0, parameterN, unique main namespace1000555581440B/NSID1/4K,
all namespacesRO/zero written sectors, root PARTUUID/parent/exact extent,
no mounted or swap NVMe volumes. Direct I/O checks current GPT against pinned
Recovery after-report and first16MiB installed root against source SHA256
21f2d2b6d658fc729b2c6fbe802ae0e5c150f754736032657160bb122417ea3b.
Superblock requires fsUUIDPRIVATE-UUID-REMOVED,
total_bytes14248030208,one device,4Ksector/16Knode. Captures all four original
partition first4KiB within this boot for before/after comparison (read only).

Test target ONLY root block device, root-relative offset34359738368(32GiB),
16384bytes, outside current14.25GB filesystem and inside158.78GB partition.
Before arming, namespaceblockRO cleared, non-root partitions setRO. Kernel
guard independently stays fixed range. Open ONLY root O_RDWR|O_DIRECT|O_SYNC|
O_EXCL. Save old16KiB to `/run/rootguard-padding-before.bin` (RAM), write
deterministic pattern, fsync, direct read exact compare, restore oldbytes in
finally, fsync, direct compare. No negative writes to protected addresses.
Always attempt disarm/resetnamespaceRO. If NVMe dies and restore cannot run,
only16KiB padding beyond filesystem may retain pattern. Do not mount RW or
retry blindly on errors; inspect exact failure/driver status through webcam.

After test, repeat direct GPT/root-prefix/protected-header comparisons, require
all namespacesRO, other namespaces0 written sectors, main exactly64 sectors
(two16KiB writes). Success marker `ROOTGUARD_TEST_PASS` and
`ROOTGUARD_CHECK_DONE`. **No SSD filesystem mounted by this test.**

## After user has booted Linux proxy

First inspect fresh serial/webcam, then read-only installed V5 preflight:

```
python3 -u probe/cpu-proxy-check.py --verify-v5 --read-core-power --verify-ctrr-wfi > logs/NEW-rootguard-proxy-preflight.log 2>&1
```

Use new unique log names, inspect results before continuing. Installed V5
diagnostic trace overlaps native kernel load address: NEVER boot kernel via V5.
Chainload unchanged native prefix FIRST:

```
M1N1DEVICE=/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED sh /PRIVATE-USER/azahi/run.sh /PRIVATE-USER/azahi/proxyclient/tools/chainload.py -r /PRIVATE-USER/azahi-port/native-loader-prefix-20260906.bin
python3 -u probe/boot-native.py native-rootguard-v1-20260906.bin --rootguard-test > logs/NEW-rootguard-native-boot.log 2>&1
```

Runner validates pins, activates established ANS link preparation, fixed RAM
fence, loads image, applies DAPF MTP preparation, then native handoff. USB will
disappear. Webcam physical panel; no target remote typing/network transport.
Only after real hardware test success should disk-root mount/config/boot work
proceed. Permanent loader still requires translating ANS/DAPF preparation into
its native startup; EFI partition not yet formatted; installed V5 not standalone.
