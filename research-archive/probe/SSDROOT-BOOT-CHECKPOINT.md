# SSD-root native KDE — v3 hardware boot SUCCESS (2026-09-06)

**September11 override:** autonomous self-contained loader v2 also reached
SSD KDE via high-RAM test. Not installed yet. Current target KDE RW; next
paired Recovery backup/install. Audio cues re-enabled for user actions.
Read [new standalone checkpoint](../standalone-loader/README.md).

For the consolidated current-state guide, exact host-assisted boot procedure,
disk map and standalone-boot limitations, read [CURRENT-STATE.md](../CURRENT-STATE.md).

## SUCCESS — v3 reached KDE desktop and Konsole from SSD root

User returned target to Running proxy. Fresh preflight passed, installedV5
unused identity verified, RVBAR base10004820000, CTRR WFI
1000502c000..10005038000, secondaryalive[]. Exact pinned native prefix and
v3 image SHA matched. Logs:
- logs/ssdroot-v3-proxy-preflight-20260906.log
- logs/ssdroot-v3-chainload-20260906.log (unchanged prefix, proxy alive)
- logs/ssdroot-v3-native-boot-20260906.log (native handoff complete, exit0)

Webcam evidence:
- logs/ssdroot-v3-screen1-20260906.jpg: SSDROOT_PREPARE_PASS, sysroot mounted,
  SSDROOT_ALREADY_CONFIGURED, configure PASS, progressing through cleanup.
- logs/ssdroot-v3-screen2-20260906.jpg: graphical cursor.
- logs/ssdroot-v3-screen3-20260906.jpg: KDE wallpaper, panel and open Konsole
  root prompt. Actual successful graphical session, not just boot upload.

SSD root evidence: v3 has no RAM root image/service, explicit root PARTUUID
and sysroot mount; installed native-ssd-kde-start.sh refuses unless findmnt
UUID / equals PRIVATE-UUID-REMOVED. Reaching desktop through
this path proves the SSD-root handoff now works. No separate user-run findmnt
capture yet. Only change vs v2 is prepare unit Requires udev -> Wants udev;
hardware result validates correction of cleanup's root-unmount cascade.

Current target running KDE from new SSD partition RW with fixed root-only
guard armed. Do NOT disarm/unmount root or force power off. User can run
`systemctl poweroff` in Konsole when done; shutdown not yet requested/executed
by host. Native shell/input transport still unavailable to host, webcam only.
No additional target writes commanded apart from expected Linux/KDE startup.
Daily macOS filesystem not targeted; no commits or loader installation.

Limits remain: only ONE CPU online, software graphics, kernel/initrd still
USB-loaded through unchanged prefix. NOT standalone/untethered boot, not
native GPU acceleration, no repeat-boot durability/stability claim. All-core,
standalone loader, nativeGPU, filesystem grow, ordinary non-root account and
security/network setup remain future work. No TTS per latest preference.

NEXT SESSION: continue from successful SSD KDE; don't repeat installer or
first-boot config. For another cold boot fresh V5 preflight, unchanged-prefix
chainload, boot-native.py native-ssdroot-v3-20260906.bin --ssd-root, new logs.
All older failure/stop entries below are historical and superseded.

## LATEST OVERRIDE — quick v3 boot requested now; NO MORE TTS

User supersedes night stop: "nah test the boot make it quick no more tts".
No USB proxy; webcam logs/ssdroot-v3-quick-preboot-20260906.jpg still shows
v2 ssd-initrd# with the successful mount/unmount journal. Need user orderly
poweroff then hold power/choose Linux to return Running proxy. Immediately
fresh V5 checks, unchanged-prefix chainload and v3 --ssd-root when available.
Do not use spoken cues. V3 not booted yet; all final offline tests alreadypass.

## NIGHT WRAP-UP — journal confirms root mounted then unmounted; v3 unbooted

User requested final tests and wrap-up to sleep. NO more boot cycles tonight.
They ran the requested journal command. Webcam captured readable output in
logs/ssdroot-v2-final-journal-20260906.jpg. It shows prepare finished, sysroot
mount started and mounted successfully, then Unmounting sysroot.mount,
Deactivated successfully, Unmounted, and prepare stopped successfully. This
confirms the root was removed before switch-root; with the exact stock udev
cleanup conflict and Requires chain documented below, the v3 correction is
well supported. Hardware validation of that correction remains pending.

Final HOST-ONLY reruns all PASS:
- SSDROOT_TEST_IMAGE=native-ssdroot-v3-20260906.bin python3 probe/test-ssdroot.py
  23 tests,3.647s.
- python3 probe/test-native-rootguard.py:11 tests (mocked, NOT a new disk test).
- bash nvme-driver/test-root-write-policy.sh:525366 shared C policy checks.
- boot-native.py native-ssdroot-v3-20260906.bin --ssd-root --offline:layout PASS.
- v3 and both driver hashes rechecked, exact pins below unchanged.

Target last observed still at v2 ssd-initrd# prompt; root unmounted by systemd,
guardY. User is asked to run `systemctl poweroff` for an orderly shutdown.
Shutdown NOT confirmed yet; no host route to execute it remotely. If it hangs,
leave it rather than request another diagnostic cycle tonight.
Next session: user returns target to Linux Running proxy; fresh V5 preflight,
unchanged-prefix chainload, then v3 --ssd-root. Don't rerun prepare in the old
initrd and don't install a standalone loader yet. SSD-root/KDE boot not yet
proven; all-core/nativeGPU/standaloneboot outstanding. No commits, no daily
macOS filesystem mutations. Latest user request supersedes prior persistence.

## NEWEST — v2 hardware diagnosis; v3 dependency correction ready, not booted

User confirmed Running proxy. Fresh v2 preflight passed: installed unusedV5
base100041c4000, CTRR WFI100049d0000..100049dc000, secondaryalive[]. Logs:
logs/ssdroot-v2-proxy-preflight-20260906.log, unchanged-prefix chainload
logs/ssdroot-v2-chainload-20260906.log, successful USB/native handoff
logs/ssdroot-v2-native-boot-20260906.log. No standalone loader installation.

Readable v2 webcam logs/ssdroot-v2-screen1-20260906.jpg confirms:
SSDROOT_PREPARE_PASS; SSDROOT_ALREADY_CONFIGURED preserving user changes;
configure trace validates the initialized-v1 marker, exits0. Thus priorv1
DID persist its root configuration. Switch-root actual error: specified root
/sysroot does not seem to be an OS tree, os-release missing. Emergency screen
current findmnt /sysroot prints nothing; guardY. Visible handoff unit state
configure inactive/dead/resultsuccess/ExecMainStatus0. Local ssd-initrd# shell
now available. No successful switch-root/KDE claim yet.

Found concrete dependency bug: prepare Requires=systemd-udevd.service, mount
Requires=prepare, configure Requires=mount. Exact stock initrd-udevadm-cleanup-db
has Conflicts/After=systemd-udevd.service, deliberately stops udev before
switch-root. Requires propagates explicit stop into prepare and root mount.
Official systemd unit documentation confirms these semantics:
https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.unit.xml
Requires section. Explains observed successful setup then absent sysroot.
Await journal confirmation from user before further target action; asked:
  journalctl -b -u sysroot.mount -u ssdroot-prepare.service -n 20 --no-pager -o cat
No answer yet. Secondphoto logs/ssdroot-v2-journal-check-20260906.jpg unchanged.

Changed ONLY prepare unit Requires udev -> Wants udev with explanatorycomments.
After udev and required mount->prepare/configure->mount links unchanged.
Existing strict prepare script checks udev control exit before NVMe load;
ALL guard scripts, checks, modules, mount, root-files, diagnostic assets and
links unchanged. Built native-ssdroot-v3-20260906.bin92651296B,
initrd70698084B SHA256
43d9bc1fc960acefe0161c244ce942dc0af0ec42a6a5083625fec1bdc4da82a6.
Manifest diagnostic_console=2, udev_lifetime_fix=true. Builder defaultsv3.
23 offline tests pass; new test checks exact stockcleanup conflict, absence
of lifetime dependency and ONLY prepare.service asset differs versusv2.
logs/ssdroot-v3-build-20260906.log, ssdroot-v3-offline-tests-20260906.log,
ssdroot-v3-offline-layout-20260906.log. No native v3 test yet.

Next: read user journal on webcam, then orderly reboot from diagnostic shell
and fresh proxy/preflight/unchanged-prefix chainload to boot v3 --ssd-root.
Never rerun prepare within this existing session: NVMe already loaded and
guardY; its first check rightly refuses. Do not bypass checks/remount manually.
No daily macOS filesystem mutations, no commits. Sound at every handoff.

## Latest restart-key check — still no proxy

User said "i ran it" after the one-time Control+Option+Fn+Delete request.
No /dev/cu.usbmodem* on host. Webcam
logs/ssdroot-v2-restart-check-20260906.jpg shows the same failed v1 console
with several NEW green status lines at the bottom compared with the earlier
switchroot photo. Exact new lines are unreadable; do not claim clean shutdown,
unmount, or successful reboot. Analytical crop in restart-inspect PNG and OCR
did not recover text. Need a closer view of the bottom lines before deciding
whether a forced power cycle is warranted. V2 has NOT been booted; no serial
commands or target disk writes performed in this check.

## NEWEST — v2 readable diagnostic candidate ready; no root-cause fix claimed

User repeated that the switch-root service failed; accept this as the failing
stage, don't ask them to reread the same tiny line again. Underlying error
still unavailable. Built `native-ssdroot-v2-20260906.bin`92651186B, initrd
70697974B, SHA256
`525d57e29f1edaf1ecb1b8a0254b654d3d3c4bfdd9e469ea4be9988682af4f0f`.
Manifest .json has diagnostic_console=2. Same kernel/DT/modules/root-overlay
files/preflight/configure scripts/sysroot.mount as v1; NO disk checks weakened.
Oldv1 artifact preserved. Builder now defaults v2, refuses overwrite.

Added initrd-only stage wrappers: Bash -x stdout/stderr saved in
/run/ssdroot-prepare.log and configure.log; wrapper preserves actual failure
status (mock exit37 tested), reports PASS/FAILED and final log lines on panel.
ExecStartPre on initrd-switch-root.service runs read-only handoff report:
mounted/sysroot source/options, guard state, OS-release/systemd/init path
existence and three boot-stage unit states. Saved /run/ssdroot-handoff.log.
No override of stock switch-root command, no guessed ordering fix.

Initrd-only emergency.service now starts explicit local Bash console on tty1
with no password change, guarded by /etc/initrd-release. Shows stage tails,
switch-root journal error and current mount/guard state. Prompt `ssd-initrd#`.
Does NOT arm/disarm, mount/repair or alter disk. This is the same explicitly
offline/root-debug context as existing bring-up autologin, not daily macOS.
setfont -d enlarges tty1; stock initrd verified contains default8x16 and other
console fonts. Removed ignore_loglevel, set loglevel=3 to suppress info spam
on panel while retaining kernel journal/ring buffer. Diagnostic tag
azahi.ssd_diagnostics=2; boot-native --ssd-root validates these when v2 manifest.

22 tests pass with
`SSDROOT_TEST_IMAGE=native-ssdroot-v2-20260906.bin python3 probe/test-ssdroot.py`;
log logs/ssdroot-v2-offline-tests-20260906.log. New tests ensure unchanged
guards/modules/root-overlay vs v1, initrd-only shell, Bash syntax, wrapper
success/failure+log preservation. Offline layout passes:
logs/ssdroot-v2-offline-layout-20260906.log. Tests still default to v1 if env
not set (diagnostic-only test skips original). No target writes this turn.

Target remains failed v1; current root mount/armed state UNKNOWN, so avoid
forced power-off initially. Ask user to press Control+Option+Fn+Delete ONCE
to try an orderly Ctrl+Alt+Delete restart. Exact kernel hid-apple.c maps
Fn+Backspace to KEY_DELETE, and stock initrd ctrl-alt-del.target is symlink to
reboot.target. Actual input response in this failed initrd not verified. If
it responds, return to Linux Running proxy; if not, user should report rather
than force power off. Then fresh V5 preflight/unchanged-prefix chainload and
`boot-native.py native-ssdroot-v2-20260906.bin --ssd-root` with NEW log names.
Still no successful SSD-root/KDE boot or standalone loader claim.

## LIVE OVERRIDE — v1 boot attempted, failed startup, do not retry blindly

User subsequently read "starting init rd switch service" immediately above
redFAILED. This suggests switch-root stage, but is not the actual failure
message; do not equate it with confirmed successful mount/configuration.
Read exact stock initrd-switch-root/target/cleanup units: switch-root service
executes `systemctl --no-block switch-root`; switch-root target retains
initrd-root-fs.target and its dependency chain. No confirmed dependency bug
identified. New webcam `logs/ssdroot-v1-switchroot-screen-20260906.jpg` still
too blurred for exact error. Analytical crop via inspect-console-crop.swift
saved separate `logs/ssdroot-v1-switchroot-inspect-20260906.png`, original
unchanged; no additional readable error recovered. Request actual text beside
redFAILED, not preceding Starting line. No candidate/driver changes yet.

User "ok dun" returned target to fresh Linux proxy. Preflight passed:
`logs/ssdroot-v1-proxy-preflight-20260906.log`, V5 unused verified,
base10004420000, CTRRWFI10004c2c000..10004c38000, secondaryalive[], proxyalive.
Pinned candidate and native prefix hashes match. Unchanged-prefix chainload
passed `logs/ssdroot-v1-chainload-20260906.log`; runner --ssd-root completed
native handoff/exit0 `logs/ssdroot-v1-native-boot-20260906.log`.

Webcam `logs/ssdroot-v1-screen1-20260906.jpg` and screen2 show early systemd
startup, a red failed-unit line, RTKit message block and what appears to be
emergency-console text. KDE did NOT open. Exact failing unit/reason cannot be
reliably read at this font/photograph resolution. Do NOT claim root mounted,
config installed, zero SSD writes, or guard disarmed without inspecting logs.
Fixed root-only driver remains the media-write boundary; no daily macOS
filesystem write target was added. Do not reboot or bypass preflight.

Asynchronous user question sent asking for a close-up photo of lines above
redFAILED or transcription of SSDROOT_STOP. No answer yet at this update.
`probe/read-screen-bottom.swift` added for in-memory crop/scale/contrast OCR;
both attempts yielded no readable text. No modified photo was written. No
driver/initrd/boot candidate changes made in this turn. Root cause remains
unknown, not assumed to be a disk fault or a particular safety-check failure.
Next needs readable panel error (or shell if available) before selecting fix.
Potential future improvement: larger initrd diagnostic font, suppress verbose
console spam without losing journal, and an explicitly accessible emergency
shell for this offline bring-up; these are NOT implemented yet.

## Immediate next state

User asked "Okay, what now"; host built an actual SSD-root candidate. Target
still runs rootguardv1 native RAM Linux, with new SSD Btrfs root mountedRO at
/mnt/ssd (user ran mount twice, possible stack). No target writes or loader
installations this turn. Ask user to type `poweroff`, then hold power for
startup options, choose Linux (NOT Options), reach Running proxy. Need fresh
V5 read-only preflight, unchanged-prefix chainload, then new --ssd-root boot.
Do not use previous rootguard/RO modes for the new candidate. Play sound at
EVERY handoff. Don't use user name. No commits. Daily macOS p2 filesystem
mutations remain prohibited.

## Exact candidate and boot

`native-ssdroot-v1-20260906.bin`92649797B, SHA256
`abac19030ac81629ee4c98b52299cb72c6c62e0d14719e756fe9953f15a00937`.
Manifest `.json` includes all asset/overlay hashes, links, source stock/input
overlay hashes and actual initrd length70696604B. No RAM filesystem image.
`probe/build-native-ssdroot.py` refuses output overwrite. Retains stock66MiB
initramfs byte-for-byte plus input-v2 small overlays, omits893MiB RAM archive,
then appends verified new SSD setup/config/modules/desktop assets. Parses
actual archives to assert no ramroot/root.img or ramroot.service remains.
Known input dockchannel module and trackpad firmware unchanged from input-v2.

Same rootguard DT as hardware-tested test: SHA256
ddd855503c88b8b3b0afe64b4f3862dee2ec328c347b6c7eca5664bdf1fee5f8.
Same NVMe rootguard module696d0fded6a47bb9929e1f49b1a38d166d6c539e573696c3c206b84c13c6708c
and proven SART58ba58e4a6dd0b4574751d224772d9bfe447fa3f4e8bdba8cfa9e7c52b80305d.
No driver/DT changes needed for this candidate. Kernel/native prefix unchanged.

`probe/boot-native.py --ssd-root` is a third mutually-exclusive SSD mode. Pins
module hashes/DT, full candidate SHA vs manifest, initrd size<100MiB/noRAMimage,
rootPARTUUID/rootflagsnodiscard/oneCPU/explicit azahi.ssd_root=1. Keeps all
SMC exclusions and boot/EFI/repart/udisks/fstrim masks. ANS link and MTP DAPF
prep same hardware-proven path. Old --ssd-readonly and --rootguard-test work
unchanged; new candidate rejected by no SSD mode and either old SSD mode.

After fresh target Running proxy, unique logs and inspect each stage:

```
python3 -u probe/cpu-proxy-check.py --verify-v5 --read-core-power --verify-ctrr-wfi > logs/NEW-ssdroot-v1-proxy-preflight.log 2>&1
M1N1DEVICE=/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED sh /PRIVATE-USER/azahi/run.sh /PRIVATE-USER/azahi/proxyclient/tools/chainload.py -r /PRIVATE-USER/azahi-port/native-loader-prefix-20260906.bin
python3 -u probe/boot-native.py native-ssdroot-v1-20260906.bin --ssd-root > logs/NEW-ssdroot-v1-native-boot.log 2>&1
```

NEVER run native kernel directly through installedV5: its trace overlaps kernel
load address. Always chainload unchanged native prefix first. Fixed native RAM
fence/addresses same as prior tests. USB disappears on native handoff; webcam
for errors/results, no native remote command or input transport.

## Initrd design / failure handling

`ssdroot-prepare.sh/.service` precedes explicit `sysroot.mount`; default writes
off. Requires initrd/aarch64/J714s, explicitSSDboot flag, no early NVMe, exactly
3 namespaces. Explicit module probe with udev exec queue stopped, all namespaces
blockRO, verify main capacity1000555581440B/NSID1/4K and rootPARTUUID parent,
start1632272984 and size310116352 (512B units). Both GPT copies hashed against
post-install Recovery report: primary6*4K at0,
1d5f950b18f43d5b535c50e2f553464749da88d8e34713e8db56d0786fdf53ce;
backup5*4K atLBA244276260,
acd9401f19961d84ca3a3a48741325c4420d0325d72736ff5c61c34f2b22cb76.
Require Btrfs fsUUIDPRIVATE-UUID-REMOVED, no SSD mounts/swap.
Read-only inspection mount uses correct `ro,rescue=nologreplay,subvol=root`.
Require installed systemd and kwin_wayland. Until initialization marker exists,
first16MiB root must match pinned installed source hash21f2d2b6d658fc729b2c6fbe802ae0e5c150f754736032657160bb122417ea3b.
After marker exists, require its exact fsUUID instead (allow user filesystem
changes). Unmount inspect, require zero namespace written sectors, clear main
blockRO, keep every non-root partitionRO, then arm fixed kernel guardY.
Every failure attempts udev resume/disarm. Failed RO inspection can remain
mountedRO for emergency debugging; do not bypass checks.

Explicit `etc/systemd/system/sysroot.mount` Requires/After prepare; What exact
rootPARTUUID, Where/sysroot, Typebtrfs, Optionsrw,subvol=root,nodiscard.
Dracut shell mount/initqueue services masked to avoid a competing root mount.
Read actual stock systemd/dracut units to review ordering; stock cmdline only
rd.driver.pre=btrfs and xhci_plat_hcd, no stale root identity.

`ssdroot-configure.service` Requires/After sysroot.mount, Before initrd-root-fs
target and initrd-parse-etc. Target requires both mount and configure. Script
checks mounted UUID/FSROOT/rw and armed state before any config writes. Backs up
existing files/links listed by generated exact overlay manifest under
`/var/lib/azahi-ssdboot/original/` inside NEW Linux root. Rejects traversal,
symlinked destination parents and regular-file copies through final symlinks.
Copies firmware/modules/input service/KDE scripts/autologin/fstab/masks, writes
`/var/lib/azahi-ssdboot/initialized-v1` with fsUUID, syncs. Later boots with
valid marker SKIP configuration, preserving user edits. No first-boot grow.
If initial writable mount/config fails partway before marker, next pristine
prefix check may fail: inspect/recover deliberately, not blind retry/bypass.

Kernel guard remains armed while SSD root is mountedRW (only fixed root LBAs
permitted). On prepare error it disarms. On mount/config error initrd goes to
emergency target; don't disarm an actively mountedRW filesystem casually.

## Desktop / limitations

First setup replaces stock fstab with root/home Btrfs UUID entries, subvolumes
root/home, compress=zstd:1,nodiscard. Rootfs remains14.25GB in158.78GB partition;
grow later after disk-root boot verified. /home temporarily masked. Separate
stock ext4/boot and vfatEFI UUIDs are NOT reused: boot/boot-efi masked, no new
EFI formatting. Repart/udisks/fstrim/initial-setup/uinject masked persistently
as well as bootargs. No automated mounting of other partitions.

`systemd.unit=multi-user.target`; existing bring-up local ROOT AUTOLOGIN is
installed in SSD root (not secured multiuser setup). tty1 profile prints root
findmnt and CPUonline, waits5seconds, starts basic KDE via proven software-
rendered kwin/plasmashell/konsole path. This is one CPU, softwareGPU, USB-loaded
kernel with persistent SSD filesystem. NOT standalone boot or all-core fix.
`native-ssd-kde-start.sh` verifies rootUUID first, disables existing known KDE
automount/welcome/plugin files by moving them to /root/bringup-disabled-plugins,
then runs basic-kde-session. Logs /run/native-ssd-kde.log. Input check overridden
to report SSD root (not stale RAM-only text). Future security/user setup needed
before enabling network or treating this as a daily-use installation.

## Added prerequisite provenance

Stock initrd lacks Python,dd,sha256sum,blockdev. Added only self-contained
Alpine ARM64 busybox.static to /usr/local/libexec (doesn't replace Fedora tools).
Official package page: https://pkgs.alpinelinux.org/package/v3.23/main/aarch64/busybox-static
Downloaded over validatedHTTPS from
https://dl-cdn.alpinelinux.org/alpine/v3.23/main/aarch64/busybox-static-1.37.0-r30.apk
to probe/vendor/ssdboot/; only bin/busybox.static extracted.
APK SHA25644c9abdfb970f398fa72c8382fe2d8808eea16beaf82daf6ac708b92f1b8659e.
Binary SHA256198f6f675a49ac734082e054b823d3e2e947180ca2f632852ae1c09e950fd676.
APK .PKGINFO datahash matches SHA256 of third compressed gzip member:
36e8c4869c1ccf232888b291a18bd679295025b9eaaa683506b63b0b4220d875.
No independent APK signature verification claimed. ELF183/aarch64, static PIE,
no PT_INTERP, LOAD64K-aligned and16K-compatible. Applet names checked; runtime
preflight checks --list for blockdev/dd/sha256sum/stat. Not executable on macOS;
actual ARM Linux operation remains part of next hardware test.

## Verification

`python3 probe/test-ssdroot.py`:18 tests pass. Actual complete candidate cpio
assets/hashes/links, no RAM image/service, complete backup path list, guard-
before-mount order, correct no-log-replay option, static ELF/page alignment;
mocked first setup backup/marker, subsequent user-edit preservation, wrongUUID/
read-only/disarmed/path traversal/symlink refusal; region hash success/wrong/
short-read rejection with disarm; Bash syntax; all wrong boot modes reject.
Log `logs/ssdroot-v1-offline-tests-20260906.log`.
Offline new boot layout PASS, log `logs/ssdroot-v1-offline-layout-20260906.log`.
Old rootguard/RO offline boot checks still pass. Prior11 Python native-write
tests and525366 C policy assertions pass again. None of these are a hardware
SSD-root boot result; that remains pending the physical cycle and native boot.
