# J714s trackpad interface-power experiment

## Sep13 CURRENT: successful native boot sequence photographed

User-provided photo of `dmesg | grep -iE 'afe|touch mt|azahi_v2'` shows:

```text
1.769702 AZAHI_V2_POWER iface=1 state=0 accepted
1.876061 New AFE[0] cbor image received
2.013180 Touch MT ready
2.013191 AZAHI_V2_POWER iface=1 state=2 accepted
```

Together with user-reported working trackpad and the verified on-disk firmware
hash below, this establishes successful native initialization on this boot.
Earlier failed-boot photo had OFF1.785445, CBOR1.893409, attach/boot failure
around1.9963, ON1.996471, timeout4.003073. Both accept v2 power requests; only
the successful sequence reaches Touch MT ready. Timing differences alone do
not prove a missing delay or a specific reset cause. No reproduction matrix,
loaded-initramfs hash or raw-event comparison yet. This is an intermittent
early AFE startup failure, separate from KDE's saved settings. Do not declare
input stable across boots or change/reload drivers in this working session.

## Sep13: installed trackpad firmware hash verified; startup still intermittent

User photo confirms `sha256sum /lib/firmware/apple/tpmtfw-j714s.bin` returns
`03a6d272deae424cd4a8e8ca75161079e4da11ffebc012d8b8088b35f1ad719d`, exactly
the expected file. Earlier missing-file report was a typo (`tmptfw`). This
verifies the current on-disk file, not the bytes loaded by every prior boot.
Do not replace firmware merely because an earlier AFE startup failed.

User reports trackpad works after another reboot. Previous failed-boot photo
showed state0/state2 AZAHI_V2_POWER accepted, AFE attach failure (-6), AFE Chip
Boot Failure / No HINT_L, AFE bootload failed1, and interface start timeout.
Current successful-boot log comparison is next; not yet captured. No driver
unload/reset or new reboot requested. KDE fresh-config launcher installation
separately confirmed by photo; that is not a fix for intermittent AFE startup.

## Latest Sep12: user reports working native trackpad in clean-config session

FOLLOW-UP: user immediately reports severe trackpad and keyboard lag plus
doubled keys in Konsole-only GUI. Movement is present but not usefully stable;
do not label native input fixed. Need active GUI load and later raw input
timing evidence to distinguish compositor delay from driver behavior.

After userspace-only KWin restarts and temporary clean XDG_CONFIG_HOME test,
user says trackpad works. native-kde-clean-config-success-20260912 webcam shows
graphical Konsole and pointer. No intervening reboot/module/firmware/DT edit.
Movement reported by user, not established from still image; no new firmware
SHA or AFE log readback. Preserve working session; earlier AFE failure remains
real evidence and cold-start input reliability is NOT yet established.

## Sep12 native SSD KDE: AFE startup failure, not just a hidden cursor

Latest photo `logs/native-trackpad-power-check-20260912.jpg` confirms
`AZAHI_V2_POWER iface=1 state=0 accepted` and `state=2 accepted` in the native
boot (about1.78/1.99s). The patched power-request path is running; this is not
the older rejected-v1-request failure. Firmware checksum still pending.
User had joined the earlier two commands onto one line, passing sha256sum
as arguments to tail, and mistyped dmesg on some tries. Corrected one-line
power check succeeded. Give ONE command at a time for subsequent manual work.

Autonomous aligned-v3 cold boot reaches KDE and keyboard works. User reports
no mouse pointer/trackpad response. Photo
`logs/native-trackpad-diagnostic-screen1-20260912.jpg` shows both Apple MTP
device names; kernel logs show firmware send/reset around1.77s, a new AFE CBOR
image received, then `Failed to attach to AFE`, `AFE Chip Boot Failure`,
`AFE[0] bootload failed: 1`, interface start timeout around4s, and repeated
`Interface multi-touch is already starting`. No native ready/event proof.
The requested log filter omitted AZAHI_V2_POWER lines (they don't contain
mtp/touch/dchid), so their absence in this photo is NOT evidence the patch
wasn't loaded. Next check explicitly includes those markers and firmware SHA.
Expected `tpmtfw-j714s.bin` SHA256:
`03a6d272deae424cd4a8e8ca75161079e4da11ffebc012d8b8088b35f1ad719d`.

Compared earlier HV PASS: firmware send21.434s, OFF accepted21.449s, CBOR
received21.559s, Touch MT ready21.703s, ON accepted21.708s. Different timings
are an observation, NOT proof a delay fixes native boot. Current public M4
v2-power patch has no extra settling delay; no direct AFE-failure fix found.
Keep standalone boot baseline intact. No live unbind/unload: BUG_ON(1) remains
in transport remove callback. No GPIO writes/new module/hardware reset in this
diagnostic turn; native root isRW and requires orderly shutdown if needed.

User authorized a reversible local driver patch on 2026-09-06. The stock
`Image-asahi` and the working keyboard-only SID0 image are preserved. This
directory does not modify m1n1 sources or target SSD contents.

## Hardware result — PASS, 2026-09-06

`guest-hv-input-v2power.bin` accepted both OFF/ON request pairs, consumed the
trackpad firmware and reached `Touch MT ready` at 21.7 seconds. Physical
testing captured 826 SYN reports, X/Y and pressure updates, two-finger
detection, five click press/release pairs, and keyboard A/B/C. DART faults:
zero. Evidence: `logs/input-v2power-boot-20260906/console.log`. Desktop gesture
policy and haptic feel are separate from these raw-input checks.

## Provenance

- Fedora Asahi Copr, `kernel-7.0.13-400.asahi.fc44.src.rpm`, SHA256
  `b9b505704a9ae9cfa00caff49f4cc206f1d5d407217ff32b56659738cef7befb`.
  `dockchannel-hid.c` is the 1213-line new-file addition in its
  `patch-7.0-redhat.patch`; unmodified copy is in `vendor/`.
- Matching `kernel-16k-devel-7.0.13-400.asahi.fc44.aarch64.rpm`, SHA256
  `ad835398b8d443619030c5baccc79246fc97d175fc2d17633738d35fd0319c0a`.
- Package SHA256s checked against HTTPS Copr primary metadata. These are
  checksum checks, not an independent RPM signing-key verification.
- Protocol reference: [Project Wallace's patch](https://github.com/damsleth/wallace/blob/main/patches/t6040-dockchannel-hid-reset-contract.patch)
  and [J614s hardware result](https://github.com/damsleth/wallace/blob/main/evidence/2026-08-04-t6040-trackpad-v2-power-request-accepted.md).
- `host-include/elf.h` is the musl libc ELF header, downloaded from
  `https://git.musl-libc.org/cgit/musl/plain/include/elf.h`; used only by the
  host module-metadata generator, not by the target module.

## Change

Only on `apple,j714s`, replace report `{0x40, 1, iface, state}` with the two
9-byte requests `{0x40, 2, iface, state, phase, 0, 0, 0, 0}`, phase 0 then 1.
Propagate power-request errors instead of ignoring them. Older board requests
are unchanged. This is an experiment, not a generic upstream-ready driver.

## Build and deployment

`bash input-driver/build-module.sh` cross-compiles with Homebrew LLVM/LLD
against the exact extracted Fedora headers. Linux's matching modpost sources
are compiled for macOS using the two tiny host-only compatibility headers.
The standard `scripts/module-common.c` supplies vermagic. BTF is omitted
because there is no matching vmlinux. The module is unsigned and out-of-tree;
the kernel does not enforce module signatures. No force-load option is used.

`python3 ramroot/add-input-module.py guest-hv-input-sid0.bin
input-driver/build/dockchannel-hid.ko guest-hv-input-v2power.bin`
(one shell line) appends a compressed cpio overlay at the original indexed
module path, in both initramfs and the RAM sysroot overlay. It verifies the
existing payload is unchanged except for the initramfs-size field.

Current module SHA256:
`1b4bd27679416faacca50831cb47bd112bb5931a397f8641c2cb1642b7b49837`.
The stock and replacement `.gnu.linkonce.this_module` sections both have
size `0x540`; vermagic matches the running kernel exactly. This checks some
ABI prerequisites, not hardware correctness.

Boot with the existing one-shot runner and `--prepare-mtp --trace-input`.
Do not unload/unbind the dockchannel driver: the inherited remove callback
contains `BUG_ON(1)`. To roll back, physically restart into proxy and boot the
preserved `guest-hv-input-sid0.bin`.
