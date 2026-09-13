# Progress — 2026-09-13

This is the public, privacy-reviewed checkpoint. Historical private notes may
contain superseded plans; the state below takes precedence.

## Latest user report and expanded publication

FIRST ATTENDED LIVE TEST NEXT: user confirms the phone is connected and its
USB tethering toggle is greyed out. The host controller has not yet been enabled,
so this alone is not evidence of a phone/cable failure. All four delivered
checksums and the five-domain power preflight have passed.

The user is instructed to save work, run `sync && bash usb-tether-test.sh minimal`
from the courier directory, and enable phone tethering when it becomes available.
This is an experimental first hardware test, not a claim that PHY/SID/VBUS
uncertainties have been eliminated. It may hang and require an attended power
cycle. The runner does not install boot files; it may create a Linux log and
a temporary NetworkManager profile. Do not retry or unload an applied overlay.
Outcome pending; no root hub, phone enumeration or networking success claimed.

FIRST NATIVE DRY PREFLIGHT PASSED: user photo shows all five required PMGR
domains (FAB5_SOC, ATC2_COMMON, ATC2_USB_AON, ATC2_USB, ATC2_PHYMXWRAP)
at target/actual ACTIVE. The module reports dry mode, no overlay applied;
the runner unloads it and prints diagnostic complete. No host controller or
network interface was enabled by this check.

Follow-up source review: the exact kernel's apple_dart_of_xlate accumulates
multiple SIDs for the same DART; four references to two DARTs are not inherently
a four-DART slot overflow. This does not prove the candidate's physical SID
routing. The kernel config defaults to DMA translation, not passthrough.
The isolated loader source confirms its SIG write; the candidate's host-mode
clear-mask remains a deliberate, hardware-unverified deviation. Power ACTIVE
does not settle PHY behaviour or Type-C VBUS sourcing.

Next physical preparation: disconnect the inter-Mac USB cable, connect the
unlocked phone to the target's right-hand USB-C socket with a data cable.
Tethering may remain unavailable until host enumeration. No `minimal` command
has been issued and no live host-overlay result is claimed.

DELIVERED CHECKSUMS VERIFIED: user reports all four manifest checks returned
OK. Next is the runner's explicit `dry` mode: it temporarily loads only the
diagnostic overlay module, reads five PMGR power states, applies no device-tree
overlay, and unloads its diagnostic module. This is not a USB host/network test.
The script also writes a diagnostic log on the Linux root. Outcome pending.

V6 COURIER DELIVERY CONFIRMED: the user-provided photo shows KDE Konsole
listing all five expected files in `/run/azahi-usb-20260913`: three modules,
`SHA256SUMS`, and `usb-tether-test.sh`. An initial missing-hyphen typo was
corrected; the correct path succeeds. The photo remains private.

Next verify the delivered manifest in that directory before any module load.
File presence establishes delivery, not working USB hardware or networking.
No target checksum result or live USB preflight has been reported yet.
Persistent v4 remains installed; this successful boot used the v6 RAM handoff.

V6 RAM HANDOFF SENT: after the user restarted into the installed v4 fallback
proxy, a fresh read-only identification found changed RAM addresses. The new
session was verified rather than reusing the old pins. A guarded v6 test checked
the old header/function and all 91,819,821 payload bytes before any replacement.
All 70,698,084 new initrd bytes were written and read back in 64 KiB chunks,
then the corrected header was published last. The original loader returned
success, expected next-stage pointers were verified, and the Linux handoff was
sent. No persistent boot image or daily macOS partition was changed.

The target desktop/courier result is still pending. Next Konsole command:

```sh
ls /run/azahi-usb-20260913
```

No USB candidate driver has been loaded yet. The installed boot object remains
v4 and needs a separate permanent correction; do not casually reboot.
`proxy-test-v6.py` is published as a session-pinned reference with its private
serial identifier removed. Do not run it on a different session. Its one new
path was explicitly reviewed/enrolled; publication hooks remain enabled.

LATEST CORRECTION READY (not installed): `/run/initramfs` contained only `log`,
so the old courier assets were not available for in-place recovery.
`boot-stage-v2.sh` now uses explicit static BusyBox mktemp/cp/sha256sum/mv and
absolute findmnt, with PATH deliberately set to `/nonexistent`.

The new v6 image preserves the exact 70,698,084-byte initrd and 92,651,520-byte
aligned outer image, original loader/kernel/DT/boot arguments, all original CPIO
bytes, and unchanged driver/runner assets. Only the courier script changes.
Five offline image invariance/corruption tests pass.

A host-local QEMU ARM64 VM used the exact pinned kernel, Bash, findmnt and
BusyBox from the v5 initrd, with no disks, network or USB passthrough. It:

- reproduced the old `mktemp: command not found` failure;
- ran the corrected courier successfully despite empty PATH;
- verified all delivered checksums;
- preserved an existing destination and rejected corrupt payloads, source
  symlinks and a non-tmpfs destination mount.

All six test markers and `COURIER_VM_ALL_PASS` were observed. An initial test
harness archive-encoding mistake was caught in the VM and corrected before
the successful run. This tests courier userspace, not M5 USB hardware.

V6 private image SHA256:
`324822de14a43ab164d0ec6257d50d9dd6be1b17fd063faf24b0d571e41096ee`.
No boot image or firmware is uploaded. No target reboot or persistent write
has occurred in this correction. Next: controlled restart into the existing
v4 fallback proxy, freshly identify the session, then a guarded v6 RAM test.
Do not reuse the previous live-session addresses without re-verification.

NEW PHOTO: the current boot journal explicitly reports
`/azahi-usb-stage.sh: line 11: mktemp: command not found`.
The initrd courier did execute but stopped before creating its staging directory.
This explains the missing `/run/azahi-usb-20260913`; KDE Konsole was not the
problem. No corrected courier image has been built or installed yet. The next
implementation must account for tools actually available in the early boot
environment (including validating any BusyBox applet option differences).

Publication hardening is being added: default-deny ignores, exact-path allowlist,
independent installed index/history scan hooks, and synthetic regression tests.
No private photo is uploaded; only this transcribed diagnostic is recorded.

The user reports that KDE is accessible and that listing
`/run/azahi-usb-20260913` returned a cannot-access error. Konsole within KDE is
the correct place to run the command; a separate text terminal is not required.
Courier delivery is therefore **not established**. Need the exact error/log;
do not infer the running image identity solely from the desktop appearing.

Read-only inspection of the fixed host image confirms the courier script,
systemd drop-in, all five payload files, findmnt and static BusyBox are present.
The next target diagnostic is:

```sh
journalctl -b -u initrd-switch-root --no-pager -n 15
```

Do not reboot or reinstall yet. No target changes were made during publication.

At the user's request, publication now also includes 284 historical project
source/configuration/note files. Personal/private data remains excluded, with
identifying details redacted from 89 files. See the research archive manifest;
this is not a 56 GB binary workspace backup.

## Current boot incident

The known-working **aligned v3** booted native KDE from the SSD without a helper
Mac. The later **USB courier v4** was installed and its bytes read back correctly,
but the packaging was incompatible with the loader. Correct copying did not
mean correct boot behavior.

The loader requires an initrd of exactly **70,698,084 bytes**. Appending the USB
file courier increased v4 to **70,980,667 bytes**. A live proxy check confirmed:

```text
AZAHI_STANDALONE_STOP: bundle bounds/version; no kernel handoff
```

This is a packaging mistake, not a KDE failure or a USB-driver crash. No USB
candidate module had been loaded. The server distributing v4 was stopped.

### Correction and evidence

The **v5-fixed** builder recompresses the original concatenated CPIO bytes with
zstd -19, appends the same courier archive, and zero-pads the initrd to the
loader's exact size. Original CPIO bytes, metadata and ordering are preserved;
loader code, kernel, boot arguments and device tree remain unchanged.

- Original CPIO recompressed size: 67,531,064 bytes.
- Courier frame: 282,583 bytes.
- Final initrd: 70,698,084 bytes.
- Full aligned image: 92,651,520 bytes.
- Four new offline regression tests passed, including compiling the actual
  loader bounds condition: v3/v5 accepted, v4 rejected.

Through the already-running proxy, a guarded **RAM-only** correction verified
the entire old bundle, wrote/read back the corrected initrd in 64 KiB chunks,
published the corrected header last, then called the byte-verified original
loader function. No persistent storage was changed by this test.

Observed markers:

```text
AZAHI_KERNEL_READY
AZAHI_ANS_WARM_READY
AZAHI_STANDALONE_HANDOFF
```

The next-stage kernel/FDT pointers were checked and the handoff sent. **This is
not yet confirmation of a running desktop or successful courier delivery.**
The persistent boot image remains v4. Another reboot may return to proxy until
the fixed image is installed with a fresh validated backup and readback.

## USB candidate

Three exact-kernel modules are built privately for
`7.0.13-400.asahi.fc44.aarch64+16k`:

- eUSB2 host PHY for T6050.
- DWC3 glue with its own compatible, optional reset and forced-host support.
- Runtime DT overlay loader with a read-only power-state preflight.

The target is the **right USB-C socket**, ADT USB instance 2 / port number 3.
The default runner is diagnostic-only. Its live PMGR variant is withheld.
Five power domains must report target and actual ACTIVE; there is no force
bypass. The dry path avoids gated peripheral reads and unloads only its own
diagnostic module. Applied overlays cannot safely be unloaded.

Host validation: 11 artifact/ADT checks, 19 runner mocks and 3 glue/overlay
checks passed in the private workspace. The runner/glue suites are included
and can run without private firmware. Hardware behavior is still unverified.

Outstanding risks: PHY register sequence, DART stream mapping, gated reads,
Type-C role/VBUS sourcing, then actual phone enumeration and network traffic.
No claim of working USB tethering, Internet, or persistent network configuration.

## Earlier milestones and unresolved issues

- Input: board-specific v2 OFF/ON interface-power requests worked under the
  hypervisor and on native boots. Native success logs show `Touch MT ready`.
  Other boots fail AFE attach/boot and time out. Firmware presence was verified;
  replacing it or adding guessed delays is not an established fix.
- Storage: split NVMe/NVMMU mapping and corrected SART exports enabled native
  SSD access. A separate guarded policy restricts writes to the audited Linux
  root range; it does not make experimental DMA/firmware risk disappear.
- KDE: clean per-launch XDG configuration and software-rendering settings
  restored responsiveness and automatic desktop startup. Saved documents remain
  on SSD. Ephemeral configuration is not a RAM-root operating system and is not
  proof that every freeze is a session-restore problem.
- CPU: one core is running. Prior secondary starts did not reach the expected
  entry markers; M4 fixes cannot be assumed to solve this T6050 condition.
- GPU: software rendering only; native acceleration is not implemented here.
- Wi-Fi: host-side metadata identified N1/Centauri control/Alpha/Beta endpoints
  and ACIPC tables. No native scan/association or packet path exists yet.
- Shutdown: reaching poweroff.target with the screen still on was observed.
  That message alone does not prove every filesystem was safely unmounted.

## Next verification

On the target Linux terminal, **without another reboot**:

```sh
ls /run/azahi-usb-20260913
```

If present, list detailed file sizes and then validate the local manifest before
considering a diagnostic-only USB preflight. First obtain the actual result;
do not infer successful delivery from host build tests or handoff markers.
