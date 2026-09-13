# Linux on an Apple M5 Pro — where we got to

**Sep13 GitHub publication:** user explicitly requested ongoing publication to
https://github.com/Sowyu/m5-azahi using authenticated gh; this supersedes earlier
no-commits preference for this project. Pushed/remote-verified main commit
`9c409a4f297cf05055e08b152ed2cd1558bc5150`: 54 reviewed source/docs files.
Separate public clone `/PRIVATE-USER/m5-azahi-public`; source allowlist exporter
`publication/export-public.sh`. Do not git-add this private workspace.
Public copy strips private disk UUIDs, blocks rootguard kernel write builds,
and excludes firmware/images/captures/backups/identities/Recovery installers
and session-specific proxy scripts. No private target operational files changed.
Public host tests passed: input transport,525366 storage policy,19 USB runner,
3 glue/overlay tests. Future updates: explicit export,privacy review,tests,
public progress update,commit/push,verify. No background auto-uploader.
Target unchanged during publication; awaiting `ls /run/azahi-usb-20260913`.

**Sep13 RAM recovery handoff sent:** fixed-size v5 image verified against
actual loader bounds; original cpio preserved under stronger compression.
Using reconnected proxy, fully verified old payload then wrote/read back only
RAM initrd/header. Original loader returned0 and prepared correct Linux/FDT
entry; exited proxy. Native screen/courier evidence pending. Persistent boot
still faulty v4, so do not reboot before arranging corrected enrollment.
No native USB candidate loaded; no networking success yet.

**Sep13 boot regression identified:** transfer v4 was correctly enrolled but
loader rejected its enlarged initrd (actual hard-coded size check missed by
our offline tests). Live proxy confirms bundle bounds/version stop before Linux.
Bad-image server disabled. Fixed-size v5 reuses all original cpio bytes under
stronger compression;4 new tests pass including actual C acceptance condition.
RAM-only correction/test underway; installed bad v4 NOT yet replaced. See
usb-driver/TRANSFER-CHECKPOINT.md. Original working v3 rollback remains backed up.

**Sep13 USB files v4 enrolled successfully:** fresh v3 backup and v4 installed
readback both host-verified. Linux-paired Preboot returned RO; new image raw
SHA0ca32c0df14ce714d32029ede06a428722616da0711fc5d0b85a98f1a77d77d0.
No CPU/GPU/KDE/driver change; only a file-courier initrd append. Cold boot,
file survival and USB networking still pending. Next boot Linux without host
data cable. Working autonomous v3 rollback preserved; daily macOS untouched.
Current detailed state: usb-driver/TRANSFER-CHECKPOINT.md.

**Sep13 transfer preparation complete, not installed:** user agreed to attended
Recovery. New aligned USB-files v4 boot bundle and KDE rollback verified on
host; original kernel/DT/loader/bootargs/initrd retained, appended RAM-only
file courier does not auto-load experimental drivers or replace KDE config.
16 new transfer checks and12 existing installer regressions pass. Fresh-backup
gated server running onPRIVATE-LAN-ENDPOINT-REMOVED, session70147. Next enter Linux-paired
Recovery for read-only selected-boot backup; installation still gated. No target
writes/reboot/webcam/commits by agent. See usb-driver/TRANSFER-CHECKPOINT.md.

**Sep13 USB-first implementation:** hardened/rebuilt three USB candidate
modules and a canonical runner; 33 offline tests pass. Fixed false success
through tee, dry-run module lifecycle, checksum/kernel/root guards, right-port
interface selection, HTTPS interface binding, temporary NM profile, fixed-host
probe cleanup. Overlay dry mode now reads PMGR only; gated live reads require
all five target/actual states active; force and live PMGR fallback disabled.
Original bundle preserved in usb-driver/pre-hardening-20260913.t1WC5z/.
Still no live USB/network test, no target/boot/macOS changes, no commits.
Delivery needs a verified Linux-owned staging path; next user command is
read-only disk inventory, not a reboot or mount. Details: usb-driver/README.md.

**Sep13 native Wi-Fi:** located Apple N1's actual DriverKit components and
Apple-shipped firmware/ring-interface configuration tables on the host. This
provides a concrete reverse-engineering starting point beyond PCI IDs, but
there is still no working Linux N1 driver or target network. Detailed evidence
and next work: probe/N1-WIFI-20260913.md. KDE/input/macOS/boot untouched.

**Sep13:** photo confirms fresh temporary KDE configuration on every launch
is installed; Konsole opens explicitly from the launcher. Current KDE visible,
trackpad works after reboot per user, but previous AFE firmware-start failure
confirms input startup remains intermittent. Not a stable-boot claim. Hash
check needs corrected filename (tpmtfw, not tmptfw); no driver reload/reboot
requested. Detailed current evidence in probe/native-kde-regression-20260912.md.

**Newest Sep12 (unattended): right-socket USB2 host tether candidate built
and offline-verified, not tested.** Host-only work, no target connection,
MMIO, driver load, boot-image edit, or reboot; webcam confirms the target is
still on the unchanged native KDE desktop. New `usb-driver/` tree holds three
cross-built modules (`phy-apple-t6050-usb2.ko`, `dwc3-apple-t6050.ko`,
`azahi-usb-overlay.ko`) and two runtime device-tree overlays for the right
USB-C socket (ADT instance 2 / port 3). The eUSB2 PHY sequence is transcribed
from the saved kernelcache `AppleT6050TypeCPhy::eusb2phy_init`; the DWC3 glue
is a forked stock driver with force-host-mode; the loader applies a DT overlay
at run time after a read-only PMGR/PHY preflight. `usb-driver/test-usb-candidate.py`
passes 11 checks (addresses/IRQs/DART SIDs/tunables/PMGR offsets vs the saved
ADT, overlay merge, module ABI). **Blocker for completion:** no data path into
native Linux (only `lo`), and installing/testing needs an attended Recovery
session + reboot, both out of scope this run. VBUS remains the biggest live
unknown. Details: `usb-driver/README.md` and `probe/NETWORK-CHECKPOINT.md`.

**Handoff clarified:** proactive webcam observation explicitly approved;
daily-driving macOS p2 must remain untouched, with expanded write/identity
safeguards. Recommended state for today's no-reboot work: leave working native
KDE running. Proxy is not persistent native Linux access. Full details in
`probe/HANDOFF-20260912-USB.md`; documentation only, no mode/target changes.

**Latest Sep12 handoff directive: unattended long-running networking work.**
Receiving agent should continue while user is out shopping/watching movies,
without questions or any reboot/power cycles. Updated execution contract in
`probe/HANDOFF-20260912-USB.md`: persist through implementation and verification,
preserve KDE/macOS, no false completion if live access remains unavailable.
This supersedes the pause below for the receiving agent; this documentation
edit does not launch a background task or change the target.

**Sep12: stopped and handed off at user's request.** Full state and resume
instructions: `probe/HANDOFF-20260912-USB.md`. USB tethering with Nothing Phone
(3a) Pro was approved as next priority. No working USB/network yet: this turn
only reviewed driver sources and located the M5-specific PHY methods in saved
firmware, with a small read-only inspector extension. No module/payload build,
target writes, reboot or commits. Working autonomous KDE remains unchanged;
one CPU/software graphics and poweroff hang remain. Implementation paused.

**Newest Sep12 networking assessment:** user has Nothing Phone (3a) Pro but
prefers built-in Wi-Fi. Saved target hardware now confirms Apple N1/Centauri
PCI IDs106b:1901/1902/1903. No matching driver found in exact Fedora wireless
sources or checked Asahi development tree; this is new-driver work, not just
a missing firmware package. M5 USB fallback also needs controller/PHY/Type-C
bringup. Offline inventory/audit8 tests pass. KDE/boot baseline and macOS
unchanged; no networking success or pre-trip completion promise. Details in
probe/NETWORK-CHECKPOINT.md.

**Newest Sep12: automatic KDE boot after launcher repair PASSED (user report).**
Saved clean config and persistent fresh-D-Bus/software-rendering launcher now
boot directly into KDE after a physical power cycle. Earlier runtime test
was much more responsive. One post-repair boot is not sustained reliability.
**Shutdown remains broken:** user reports systemctl poweroff stalls at
poweroff.target and forces power off. Don't claim clean shutdown or assume
safe unmount from that message. Still one CPU/software GPU/no native network
beyond lo at last check. Next recommended focus: connectivity for local
Codex/project access, shutdown/recovery safety, then SMP/GPU. No commits or
daily macOS writes; installed kernel/standalone payload unchanged.

**Newest Sep12: responsive KDE setup made persistent; cold test pending.**
Working configuration saved at /root/kde-good. Backed up old Linux launcher to
unique /root/kde-backup.*; installed checked clean-config/fresh-D-Bus launcher,
byte comparison and sync succeeded (webcam INSTALLED). Original configs and
SSD root guard preserved. Next orderly shutdown and host-disconnected Linux
cold boot to test real automatic startup; NOT yet a repeat-boot success claim.
No commits or daily macOS changes.

**Newest Sep12: responsive full KDE recovered on native SSD Linux.** User
reports "holy crap soo much more responsive" during bounded90s clean-config
Plasma + Konsole test; webcam confirms wallpaper/panel/terminal. Known software
renderer exports were loaded in same launch shell; clean XDG_CONFIG_HOME and
fresh D-Bus used, without old scale command. This supersedes earlier uncertain
clean-config reports, including the later laggy test that lacked intended
exports. Still one CPU/software graphics/no native network. Original config
and startup untouched: preserve working config and repair persistent startup
before reboot; repeat-boot reliability is NOT yet demonstrated. No commits or
daily macOS writes.

**Newest Sep12: graphical session recovered using temporary clean settings.**
Webcam confirms KWin/Konsole and mouse pointer; user reports trackpad working.
No reboot or kernel/driver change. Clean XDG_CONFIG_HOME + private D-Bus,
software rendering, Konsole only. Next add Plasma; then preserve working
configuration and repair persistent startup before reboot. Exact prior black
screen cause not yet proven. Still one CPU and no native network interface
beyond loopback. No commits or daily macOS changes.

**Newest Sep12: first autonomous KDE boot passed, but repeat boot now black.**
User reports desktop freeze then reboot; next boot reached the five-second
KDE notice then black panel (webcam confirmed). No intervening agent boot/driver
change. Stability unresolved; do not claim reliable daily use. Next recover
text console and read KDE/kernel logs without another forced power cycle.

**Sep12 milestone: Linux now cold-boots into SSD KDE without a host-supplied
payload.** User confirms desktop and keyboard; webcam confirms KDE/Konsole.
The sole image change was170 zero padding bytes to satisfy16KiB alignment.
Preserve installed aligned v3 as working baseline. Still one CPU and software
graphics; user reports no cursor or trackpad response, so native input diagnosis
is next. Do not force power off the mounted SSD root. No commits/macOS changes.

**Latest Sep12 09:59: aligned standalone v3 INSTALLED, persisted readback
VERIFIED.** Exact RAM-tested v2+170 zero padding bytes, correct raw entry and
Linux policy, final PrebootRO. Cold boot still pending: user asked to shut
down Recovery, unplug host data cable, select Linux. One CPU remains; no
standalone-success claim yet. No commits/daily macOS writes. Receipt, current
coih and rollback instructions in [standalone checkpoint](standalone-loader/README.md).

**Latest Sep12: V5 cold-boot control PASSED; likely alignment issue found.**
Working V5 is16KiB-aligned, failed autonomous v2 is170 bytes short. A documented
M4 investigation fixed the same warning with padding only. Built v3 as exact
v2+170 zeros;3 padding tests,12 current installer tests,11 historical installer
tests and6 loader tests pass. **Not installed or M5 cold-tested yet.** New
validated helper8766 ready; target last seen at proxy, user asked with audio
to open paired Linux Recovery Terminal. Daily macOS/root untouched, no commits.
See [current standalone checkpoint](standalone-loader/README.md) for all pins,
source evidence, safe installer command and current server. One CPU remains.

**Latest Sep12 09:32: V5 rollback VERIFIED.** Exact previously working V5 raw
loader is selected again (new signed wrapper/coih); standalone v2 deselected
after failed cold boot. SSD Linux root preserved. Next: user shutdown, USB
reconnect, choose Linux and check Running proxy as controlled cold-boot test.
Do not reuse old enrollment policy pins. See standalone checkpoint.

**Newest Sep12:** read-only second report confirms paired Linux Recovery,
candidate selected, no usable iBoot failure reason. Next is a controlled
restore of the exact working V5 boot entry and proxy cold-boot check, not a
reinstall of Linux/macOS. Updated rollback helper ready/tested; not run yet.
SSD root preserved. Details/current server in standalone checkpoint.

**2026-09-12 latest:** first cold-boot diagnostic upload received and verified;
retries rejected because receipt already exists, not a dead URL. Candidate's
persisted wrapped checksum unchanged; current environment is Linux-associated
ordinary/unpaired Recovery. Specific failure reason still unknown. Read-only
retry now checks GUID-qualified boot fields, on fresh receiver8765. No new
boot or disk changes. See standalone README for exact latest handoff.

**Newest observation 2026-09-11:** first cold-boot attempt shows Apple's
"version of macOS on the selected disk needs to be reinstalled" warning,
not KDE. Webcam photo saved; exact selected entry/cause not yet established.
Do NOT reinstall/erase macOS. Return to Recovery Terminal for read-only
diagnosis; standalone cold boot is not working/proven yet. Installed artifact
readback remains verified, V5 rollback available. Webcam re-authorized.

**2026-09-11 newest: standalone loader INSTALLED and persisted readback VERIFIED.**
The installed raw payload exactly matches the RAM-tested v2 candidate. Linux
Preboot ended read-only; policy/UUID checks passed. User is being asked to
shut down Recovery, disconnect the host cable and select Linux for the first
untethered cold boot. Cold boot is NOT yet proven. One CPU/software graphics.
Readback/rollback details: [standalone checkpoint](standalone-loader/README.md).

**2026-09-11 latest: fresh Recovery backup verified; standalone install ready,
not yet run.** Target in paired Linux Recovery, UUID-verified Preboot RO.
Original and current V5 wrapped objects both backed up and checked; policy
selects V5. 13 backup tests +10 installer/readback tests pass. New bounded
helper served atPRIVATE-LAN-ENDPOINT-REMOVED requires INSTALL, verifies readback,
never reboots automatically. Details/current receiver destination and rollback:
[standalone checkpoint](standalone-loader/README.md). No webcam; no commits.

**2026-09-11: autonomous-loader RAM test PASSED, NOT INSTALLED.** A new private
self-contained loader now prepares ANS/MTP, loads the exact v3 kernel/DT/initrd
and reaches SSD KDE without the old host-side prepare/kernel-load sequence.
Tested via safe high-RAM chainload, not cold iBoot; installed V5 unchanged.
Next needs user shutdown and paired Linux Recovery to back up/replace ONLY
Linux's boot object, then an unplugged cold-boot test. Six new host tests pass.
One CPU/software graphics still. Full source/provenance/pins/current state:
[standalone-loader/README.md](standalone-loader/README.md).

Recovery backup preparation is now ready locally: UUID-pinned read-only
collector and host verifier, 11 offline tests passing. No fresh Recovery
backup or installation yet; waiting for Recovery Terminal readiness. Latest
user preference: no webcam while eating. No target commands in this step.

*A plain-English write-up of the whole project, for someone who wasn't here.*

**Start here:** [Current state and complete handoff](CURRENT-STATE.md) contains
the tested boot commands, artifact hashes, disk map, evidence, safety rules
and remaining work. **Booting without another Mac now works:** the enrolled
aligned-v3 image cold-booted SSD KDE on September12. One CPU/software graphics;
native trackpad unresolved. Earlier proxy-only status below is historical.

**Interaction preferences:** Do not address the user by name. On 2026-09-11
the user re-enabled audio cues when power cycles or other user actions are
needed (supersedes the September 6 no-TTS instruction). No commits.

**SUCCESS — KDE running from the internal SSD root:** v3 hardware boot passed
the old switch-root failure and opened the KDE desktop/panel and Konsole.
Webcam proof: logs/ssdroot-v3-screen3-20260906.jpg. Successful startup follows
an explicit root UUID check; image contains no RAM filesystem. The one-line
udev dependency correction fixed the root-unmount cascade. Fresh proxy checks,
unchanged-prefix chainload and native handoff logs saved under ssdroot-v3.
Still ONE CPU, software graphics and USB-loaded kernel/initrd: standalone boot
and all-core/nativeGPU work are NOT done. Target currently running SSD KDE RW;
use `systemctl poweroff` in Konsole for orderly shutdown, don't force power off
or disarm the active root guard. No commits; daily macOS filesystem untouched.
Full evidence/pins/next-session procedure: probe/SSDROOT-BOOT-CHECKPOINT.md.
Older pending/failure entries below are historical.

**Latest — user requests the v3 hardware boot test now:** Night wrap-up below
is superseded. Target still at v2 diagnostic shell; no USB proxy. Need orderly
poweroff and user return to Linux Running proxy, then fresh preflight and
unchanged-prefix chainload before v3 --ssd-root. No TTS.

**Night wrap-up — final local tests PASS, v3 boot test next session:** User's
journal confirms the SSD root mounted successfully and was then unmounted
before switch-root. The corrected dependency is built into v3, still NOT
hardware-booted. Final reruns:23 SSD-root tests,11 mocked rootguard tests,
525366 C write-policy checks, offline RAM layout and pinned image/module
hashes all pass. User asked to stop for sleep; no further reboot cycles.
Target last at diagnostic shell, root unmounted; asked for `systemctl poweroff`
(shutdown not yet confirmed). Resume with fresh proxy checks and v3 boot.
Only one CPU proven; nativeGPU and standalone boot remain unfinished.
No commits; daily macOS filesystem untouched. Full handoff and evidence:
probe/SSDROOT-BOOT-CHECKPOINT.md.

**Newest — switch-root dependency bug identified; v3 ready:** Diagnosticv2
booted and exposed successful SSD preflight and existing configuration marker,
then an absent /sysroot at switch-root. My prepare unit required udev to remain
running, so normal initrd cleanup stopping udev could cascade into unmounting
root. Corrected that dependency to Wants while keeping startup ordering and
all disk checks/guards unchanged. v3 built,23 offline tests and layout pass;
NOT yet hardware-booted. Target at readable ssd-initrd# diagnostic shell,
guardY, no /sysroot mount shown. Requested mount/preparation journal from user
to confirm shutdown sequence before orderly reboot and next test. No commits,
no daily macOS filesystem changes. See probe/SSDROOT-BOOT-CHECKPOINT.md.

**Newest — readable switch-root diagnostic v2 READY:** User confirms failing
switch-root service; underlying reason still unknown. Built v2 with larger
console text, RAM-only detailed setup logs, pre-handoff state report and
initrd-only emergency shell. Same disk checks/write guard/root config asv1;
22 tests + offline layout pass, no claimed root-cause fix. Target is still
failedv1, mounted/armed state unknown. Asking for ONE Control+Option+Fn+Delete
to try orderly restart, then Linux Running proxy if responsive; no forced
power-off yet. Current details/pins: probe/SSDROOT-BOOT-CHECKPOINT.md.

**LIVE — SSD-root first hardware boot stopped during startup:** Fresh proxy
checks and unchanged-prefix chainload passed; new93MB candidate loaded and
native handoff completed. Webcam `logs/ssdroot-v1-screen1-20260906.jpg` and
screen2 show a failed startup unit and apparent emergency console, not KDE.
Exact error too small to read reliably; requested close-up or SSDROOT_STOP
line. Do NOT bypass checks or reboot yet. SSD mount/config/armed state not yet
confirmed. Details in `probe/SSDROOT-BOOT-CHECKPOINT.md`. No commits.

**LIVE — actual SSD-root KDE candidate READY, NOT BOOTED:** Built
`native-ssdroot-v1-20260906.bin`92649797B (about93MB), with70.7MB initrd and
NO RAM root image. Same hardware-proven rootguard/input modules. Initrd checks
model/GPT/root UUID/extent and first-install prefix before arming; explicit
systemd mount uses only Linux root. First setup backs up changed Linux files,
installs input/desktop config and safe fstab; later boots preserve user edits.
18 offline checks pass, plus prior RO/rootguard regression checks. No target
writes/bootloader changes this turn. Rootguard test still running on M5 with
SSD root mountedRO at /mnt/ssd. Asking user to `poweroff`, then hold power for
startup options and select Linux to reach Running proxy for next native boot.
Standalone loader/all-core/GPU work remains unfinished; only one CPU, software
KDE, local root autologin for bring-up. See `probe/SSDROOT-BOOT-CHECKPOINT.md`.

**Newest — SSD root mounted READ-ONLY successfully:** Corrected
`ro,rescue=nologreplay,subvol=root` command mounted nvme0n1p5 at /mnt/ssd
and printed its fstab, confirmed via webcam
`logs/rootguard-user-bug-screen2-20260906.jpg`. The remaining systemd fstab
reload hint is not a mount error. OS / still runs from RAM; no standalone
boot yet. Leave laptop running; don't repeat mount or arm writes.

**Latest correction:** Suggested read-only mount failed because this kernel
requires `rescue=nologreplay`, not bare `nologreplay`. Confirmed in local7.0.13
Btrfs option parser and webcam `logs/rootguard-user-bug-screen1-20260906.jpg`.
Our command error; SSD filesystem has not mounted. Corrected read-only command
provided; native write/flush/read/restore success below remains valid.

**LIVE — native SSD write/flush/read/restore test PASSED:** Rootguardv1 booted
natively from RAM on one CPU. Webcam `logs/rootguard-v1-boot-screen2-20260906.jpg`
shows `ROOTGUARD_TEST_PASS` and `ROOTGUARD_CHECK_DONE`:16KiB written at unused
root-relative32GiB, flushed, read back, original padding restored. Before/after
GPT/root-prefix/protected-header checks passed; exactly64 main-namespace
written sectors, zero other-namespace written sectors (required for marker).
Driver disarmed and all namespacesRO again. KDE root is installed on SSD but
NOT yet mounted or booted from SSD; standalone loader remains unfinished.
M5 is now in native RAM Linux, NOT Recovery/proxy. Do not power-cycle yet.
Next: read-only/nologreplay mount of root to inspect fstab for disk-root boot.
Native USB/remote command transport is absent, so that command needs typing.
Only one CPU proven. No commits; no daily macOS filesystem writes targeted.

**LIVE — KDE image installed on SSD and verified:** All425 chunks,
14,248,030,208 bytes, read back with exact source SHA256
`bc33421d52f06288c53cba128ccc79b13c077fb90f957fea048a5048cd955f7b`.
Final partition/APFS metadata validation passed; after-report SHA256
`e98e09c7d47757379a0456020b6bcdf106e1d9b47ae95459a58d5417906dd9a1`.
Do NOT repeat installer. M5 remains in Recovery. Native root-only write
driver, disk-root initramfs and untethered loader are NOT yet tested/installed.
Only one CPU core proven; other17 unresolved. No commits. Older entries below
are chronological history, superseded by this live status and checkpoint.

**Next hardware step ready — native root-write test, NOT yet booted:** Separate
rootguard module built; fixed root-only LBA range, initially disarmed, ordinary
writes/flush only.525366 host C checks and11 Python tests pass. A pinned RAM
diagnostic will write/read/flush/restore16KiB at root-relative32GiB (outside
the14.25GB filesystem), then disarm; no SSD filesystem mounts. Candidate
`native-rootguard-v1-20260906.bin` passes offline boot and actual appended-cpio
asset checks; old RO payload/modules preserved and regression check passes.
Webcam confirms installer completion and Recovery shell prompt. Transfer
serverPID54038 stopped after completion. Asking user to shut down, hold power
for startup options, choose Linux (not Options), reach Running proxy. Native
write behavior still UNTESTED. Details: `probe/ROOTGUARD-CHECKPOINT.md`.

**Current — KDE root-image installer ready, NOT RUN:** Prepared a bounded
14.25GB transfer to ONLY the new Linux root UUID1646a132-28e0-43d9-ba09-
43b5e9b97f86.425 chunks, download checksum before write, synchronous writes,
local read-back checksum plus host SHA256 of every chunk and whole image.
Metadata guards before/after; no existing APFS/EFI/Recovery write targets.
8 installer tests pass. ServerPRIVATE-LAN-ENDPOINT-REMOVED serves `/install-root.sh`;
waiting for user `bash /tmp/install-root.sh install-kde-root`. Do not restart
server during transfer or blindly repeat installer. Native write-capable
driver and untethered boot still require work AFTER root copy. Details and
active receiver paths in `probe/NATIVE-SSD-CHECKPOINT.md`. No commits.

**Current — blank SSD partitions CREATED and independently verified:** User's
HTTP422 came from our root-size expectation, after diskutil completed both
adds. M5 Recovery included128MiB Apple_Boot inside the requested148GiB
allocation; host512-sector test put it outside. Actual root158779572224B,
EFI536870912B, helper134217728B, all inside freed160GB. Explicit reviewed
`includes-helper` validator mode passes the complete real report; original
GPT entries unchanged by UUID (Recovery moved to GPT slot7), both GPT CRCs
and Linux APFS checksums pass.15 tests pass. Nothing reformatted or resized
to correct this check. Do NOT rerun creation. Server stopped, Recovery open.
KDE root-image installation/native writable driver/persistent boot still
unfinished. Exact new UUIDs/devices/ranges: `probe/NATIVE-SSD-CHECKPOINT.md`.

**Current — next partition helper ready, NOT EXECUTED:** Resize is verified
complete. Prepared blank512MiB EFI +148GiB Linux root creation within the
freed160GB only. The helper validates host-received backups at before/EFI/root
stages, preserves original GPT entries by UUID (including Recovery renumber),
and allows a new128MiB Apple_Boot helper only within the same free gap.
12 partition tests and11 resize regression tests pass. Server now serves
`PRIVATE-LAN-ENDPOINT-REMOVED`; waiting for user to run it with
`create-linux-partitions`. No new target partitions or filesystem installs
yet. Exact active receiver/checkpoint: `probe/NATIVE-SSD-CHECKPOINT.md`.

**Newest — Linux APFS resize completed and verified:** Host received valid
before/after reports. Linux p3 is exactly96GB; exactly160GB free follows it.
All four original GPT entry bytes (apart from p3 ending LBA) and protective
MBR match the verified baseline. Both GPT CRCs and Linux APFS superblock
checksum pass. Daily macOS p2 extents/entry unchanged; all six Linux APFS
volume UUIDs/roles remain. KDE is NOT installed on SSD yet. M5 left in
Recovery; do not rerun resize or restore pre-resize GPT. Preparing next
partition-layout step; no new partitions/formats yet. Current checkpoint
has receipts and exact free extent. No commits.

**Newest — guarded Linux-side resize ready, NOT RUN:** User reports Linux
Data unlocked. Prepared/tested helper to retain96GB of Linux APFS p3 and
free160GB, with no formatting or changes to daily macOS p2. Before mutation,
fresh metadata must pass a host-validated upload; after, protected GPT bytes
and all partition identities/extents are verified again. Eleven offline tests
pass, including mocked successful resize, rejection cases and HTTP receiver.
ServerPRIVATE-LAN-ENDPOINT-REMOVED now serves `/resize.sh`, not old `/check.sh`.
Waiting for user to download and run `bash /tmp/resize.sh resize-linux-96gb`.
No actual resize received/observed yet. Do not restart this receiver while
the script is in use. See `probe/NATIVE-SSD-CHECKPOINT.md` for exact paths.

**Current — storage report verified:** M5 remains in Recovery Terminal.
Read-only report received and validated: both GPT header/table CRCs pass,
tables agree, all four partition UUIDs/extents match, and Linux APFS first
superblock checksum/UUID/size pass. Linux APFS is 256GB with 56.1GB used;
preferred shrink minimum is 75,916,063,539 bytes. Candidate: retain 96GB
APFS and free 160GB for Linux. NO resize or formatting performed.
Linux Data is currently locked at disk3s1 in this Recovery session; next
user step is local password unlock with `diskutil apfs unlockVolume disk3s1
-nomount`. Never request the password in chat. Do not reuse this disk number
after a reboot without resolving identity again. Metadata backup is not a
full data backup. Details: `probe/NATIVE-SSD-CHECKPOINT.md`.

**Current next action:** Native SSD controller is live; consistent reads and
zero main-namespace writes observed. Native image has no USB/network command
transport, so old remote typing cannot work in this session. Prepared one
read-only Recovery storage report (exact identity guards, APFS resize limits,
GPT backup); no resizing/formatting. User asked to enter Recovery Terminal.
Server not yet started. See `probe/NATIVE-SSD-CHECKPOINT.md` for run details.

**Latest hardware result:** Native v3 now discovers the SSD and completes
128MiB of consistent repeated direct reads, observed on webcam. The final
comparison with the older HV hashes fails; that baseline predates the loader
installation, so changed boot metadata is plausible but not yet verified.
Checking partition identities/write counters next; no writable install,
partition changes or new CPU success. Native session remains running;
no cycle requested. `probe/NATIVE-SSD-CHECKPOINT.md` has current details.

**Follow-up:** Webcam confirms all SSD namespaces read-only and the main
namespace reports zero completed writes/zero sectors written. Checking
controller state and Linux APFS container UUID next. No install changes.

**Newest SSD result:** Webcam identified a local module-build mistake:
missing SART exports prevented the native NVMe driver from loading. Fixed
modpost flag and verified the finished export table. Native read-only v3
image built/offline-validated, not hardware-tested. Current v2 native shell
left running; physical restart into Linux proxy requested for v3. No native
SSD success, partition changes or commits. Daily macOS remains excluded.
See `probe/NATIVE-SSD-CHECKPOINT.md` for exact state and candidate hash.

**User identity correction:** The user's name is **PRIVATE-USER**, not PRIVATE-USER. Earlier
notes incorrectly inferred a name from `/PRIVATE-USER`; that account path is
still the correct filesystem path and must not be renamed.

**Newest — native SSD test underway:** PRIVATE-USER approved one-core SSD work ahead
of CPU research, with daily macOS strictly protected and no commits. Native
read-only NVMe/SART modules built and offline guards passed. Unchanged native
prefix chainloaded in RAM; SSD v2 transfer/native handoff completed. USB closed
as expected; webcam text is too small to verify the result. Awaiting a closer
screen view or the last console lines; no power cycle requested. No partition
changes or persistent install. See `probe/NATIVE-SSD-CHECKPOINT.md`; its live
state supersedes the earlier clean-V5/current-state paragraphs below.

**Native shell/input confirmation:** PRIVATE-USER pressed Enter on the built-in
keyboard and confirmed the root prompt appeared. Native Linux shell and
physical keyboard response verified; native trackpad and SSD test result
remain unverified. Next is reading the RAM-resident SSD test log.

**Current — fourth direct boot, clean proxy:** V5 at `0x100043a4000`.
PRIVATE-USER's cycle cleared the previous RAM-only firmware test. Original loader
vectors/entry and all48KiB WFI filler at `0x10004bb0000..0x10004bbc000`
verified; APSC controls back at original values. No secondary CPU requested
and no target power/control changes this boot. Proxy healthy, client closed;
**no additional power cycle is needed for the current state.**
All-core operation remains unresolved before Linux, matching upstream PR610.
The latest protected-memory parking test also failed; no new evidence-backed
CPU-release fix is ready. PRIVATE-USER has approved moving one-core SSD bring-up ahead
of CPU research, with the daily-driving macOS partition strictly out of scope
and no commits. Native NVMe and writes still need verification;
the Linux-named250GB partition is APFS boot infrastructure, not a Linux root.
Original backup/installed V5 intact. No commits, SSD writes or partition
changes. Details: `probe/RECOVERY-CHECKPOINT.md`, `probe/CPU-ONLINE-RESEARCH.md`.

The chronological updates below are historical; this paragraph and the
current checkpoint take precedence over old running-state/next-step notes.

**Direct-loader update:** The guarded V5 diagnostic installation now reports
success in Linux's boot slot. Original loader backup is verified; partition
layout and macOS were not changed, and no commits made. Next is its first
direct boot, followed by a bounded CPU test. All-core operation and persistent
KDE remain unfinished. See probe/RECOVERY-CHECKPOINT.md.

**Latest — Recovery / backup:** The M5 is now in paired Linux Recovery.
Its original custom bootloader has been copied to the host and verified;
an exact raw-loader restore artifact is saved. A guarded direct V5 CPU
diagnostic installation is prepared, not yet executed. This tests direct
Apple boot instead of USB RAM chainloading; it is not persistent KDE yet.
Still one proven CPU, no commits or partition changes. Operational details
and backup/restore commands: **probe/RECOVERY-CHECKPOINT.md**.

---

## The short version

We booted Linux — and then a **full KDE Plasma desktop** — on a MacBook Pro 14"
(M5 Pro, 2025). As far as the public record goes, nobody had booted Linux on
this chip before.

It currently runs **tethered**: a second Mac drives it over USB, and the
desktop's files are streamed across that cable. It is not yet a laptop you can
unplug and use. The CPU-to-userspace boot path works, but built-in input and
SSD boot still needed hardware bring-up work (see the live update).
**Latest: built-in keyboard and trackpad both work, with physical events verified.**
**SSD reads now work too.** Installation/SSD boot is still unfinished; the
current system runs from RAM over the tether.

---

## Live update — 2026-09-06

### Latest priority and live state: all cores, then persistent internal boot

**Newest result:** V5 also missed all 16 reset-vector slots. Follow-up
stateless assembly tests used the corrected masks to start CPU6 and CPU12:
both reported power state active, but neither produced an instruction-entry
marker. This now spans all three clusters, including performance cores.
Still only one proven CPU. Proxy survives at 0x1000495c000 with diagnostic
reset-branch patches; physical cycle required before loader/Linux reuse.
No SSD writes or commits. A direct Apple-boot diagnostic (no chainload) is
the next proposed isolation test, requiring Recovery and a backup first.
See the newest section of `probe/CPU-CHECKPOINT.md` for exact live state.

**Current checkpoint (supersedes historical live-state text below):** V4
CPU diagnostic is running in proxy at 0x10005a0c000, not KDE. CPU1 again
timed out with no reset marker; a guarded CPU1-only ACTIVE request also
made no difference. Proxy survived and no client remains running. No
additional core is proven. Offline analysis of the locally available
AppleT6050PMGR restore driver now confirms the existing startup register
offset 0x88000; older claims that it is outside the PMGR block are wrong.
See `probe/CPU-CHECKPOINT.md`. No SSD writes or commits.

**Next CPU test prepared:** V5 catches all 16 reset-vector slots with a
separate normal exception table. Build and instruction-layout checks pass;
a physical cycle is required before loading it. Current hardware remains
V4 with one proven core. The primary CPU's architectural reset vector reads
0x1fc08c000, distinct from the Apple implementation register holding the
loader address; the firmware handoff is still under investigation.

PRIVATE-USER explicitly reordered the work: **all 18 CPU cores first, then booting
directly from internal storage to tinker; GPU acceleration later**.

The native KDE RAM image has now booted successfully, through systemd and
the Plasma splash to the graphical Plasma first-run setup. Evidence:
`logs/native-kde-boot-20260906.log` and
`logs/native-kde-screen4-20260906.jpg`. PRIVATE-USER confirmed seeing setup and
reported severe lag. This is not yet a verified normal native desktop or
physical native input test. Leave that session running; no reboot is needed
just to record this priority. Older "not tested" statements below are historical.

CPU blocker remains before Linux: all 17 secondary starts timed out on the
fresh installed loader, even with WFE selected first. Removing `maxcpus=1`
or adding a systemd service cannot by itself repair this. Loader changes
are currently constrained by `m1n1/AGENTS.md`, which prohibits AI work in
that tree and refers to https://asahilinux.org/slop/. No loader changes were
made in this priority update.

**Authorization update:** PRIVATE-USER subsequently explicitly approved overriding
the local AI-work restriction for this private bootloader copy, with **no
commits**. Private RAM-only diagnostic changes are now permitted; nothing
is to be submitted upstream. A diagnostic build records reset-entry stages
and stops at the first timed-out CPU, without changing CPU-start register
addresses/masks. See `probe/CPU-CHECKPOINT.md`. No storage-layout approval is
inferred, and no target SSD data writes are part of this CPU test.

**CPU diagnostic hardware result:** the webcam showed the laptop already
back at Running proxy; the native KDE session had ended. V1 was chainloaded
into RAM and CPU 1 timed out with reset-trace stage 0. The proxy stayed alive.
ADT-identified power-state reads report CPU 1 active, but there is no proof
of instruction execution. V2 moves only the trace into known-safe high RAM
to test a possible trace-access failure; built and awaiting physical cycle.
See `probe/CPU-CHECKPOINT.md` for hashes, logs and exact next test. No cores
are newly claimed working, no commits made, and the SSD remains untouched.

**V2 result:** moving the reset trace into high RAM did not change the
stage-0 timeout. CPU1 changed from reported power state 0 to 15, but no
instruction-execution marker appeared. A bounded post-start SEV check also
made no difference; target vector bytes and locked RVBAR were verified.
V3 explicitly publishes the resident loader code/shared state to PoC before
the unchanged start writes. It is built, untested, awaiting a physical
cycle; see the CPU checkpoint. Current target is the failed V2 proxy, not
KDE. No commits or disk writes occurred.

**V3 result:** the explicit PoC clean also returned stage 0. CPU0/1's
existing impl+0x100 status reads succeeded, but an attempt to identify
the standard debug component at CPU0 coresight+0xff0 (0x210010ff0) caused
SError and proxy timeout. That read-only helper is now disabled; do not
retry the block. A physical restart is required. V4 tests alternate entry
selection by catching any secondary at the main image entry before it
can clear shared state; built, untested. CPU checkpoint has hashes/logs.
Still no secondary CPU is proven executing. No commits or SSD writes.

Internal installation is not simply copying the RAM root into partition 3:
the 250 GB Linux-named container is APFS and holds boot/recovery volumes.
Native SSD operation and writes remain unverified (successful reads were
under the hypervisor with hooks). A storage-layout decision is required
before destructive installation steps; macOS and all target SSD contents
remain untouched. Do not treat this priority change as repartition approval.

### Current work: CPU startup and native boot tests

PRIVATE-USER next requested all CPUs, native operation, then GPU. The verified KDE
session below was stopped cleanly (services stopped, `sync`, runner SIGUSR2)
for these tests. **It is no longer running; the older leave-running advice
below describes the previous checkpoint, not current machine state.**

Fresh installed-loader testing with WFE enabled before the first SMP start
still timed out on all 17 secondary cores. The proxy survived. RVBARs match
the original loader base, removing stale chainload addresses as the cause
of this particular test. The live boot MPIDR is `0x80040000`, confirming the
minimal Linux DT's CPU address `0x40000` (not raw ADT `reg=0`).
`probe/cpu-proxy-check.py` validates all 18 ADT CPUs and the 3x6 topology.
The loader's legacy four-core enable-mask formula differs from the ADT's
per-CPU masks for IDs 6–17; this alone does not explain failures on IDs 1–5.
No CPU is claimed online beyond the boot core. Evidence:
`logs/cpu-wfe-original-20260906.log`, `logs/cpu-start-status-20260906.log`.

Correction to historical PMGR conclusions: ADT reg0 spans `0x1fc000` bytes,
not just 16 KiB. Exact previously used CPU-start register reads at
`0x280688004/8/c/10` succeeded (values `0x3c000,0,0,0`). This does not prove
that their legacy semantics are correct on T6050; do not scan sparse banks.

The bare-metal DT now compiles after removing serial0's dangling power-domain
reference. `probe/verify-native-candidate.py` proves the existing native
kernel differs from stock only at four documented VM_TMR_FIQ_ENA MSRs.
`probe/build-native-probe.py` assembles an unchanged existing loader prefix,
that kernel, the minimal DT and stock initramfs for a **RAM-only** test.
The minimal native test reached visible Linux and initramfs userspace boot
output (`logs/native-probe-screen2-20260906.jpg`), with no hypervisor. This is
not a full working native system: no physical-input test or rootfs there.
The fuller native input/RAM-root candidate then reached a kernel panic;
neither native input nor KDE is verified. We are arranging a QR panic-log
capture, because Fedora's default DRM panic screen hides the stack trace.
Neither script modifies m1n1 code or writes the target SSD.

`probe/boot-native.py` now loads kernel/FDT/initrd directly into the previously
established RAM fence, using existing loader APIs, with bounded transfers
and per-chunk tail readback. First chainload the **unchanged** prefix extracted
from `native-probe-20260906.bin` (SHA256
`ecffcf08622e64ad616d7b4e4bd6050cca44c9647df311ffb20efcc8f792a604`).
Do not chainload the whole 1 GB image: that path needs an extra full compressed
staging copy and hit its 1 GB heap limit before transferring the image.
The direct transfer and native handoff succeeded; evidence is
`logs/native-input-direct-20260906.log`, but the panel then showed a panic
(`logs/native-input-screen1-20260906.jpg`). `native-input-v2-20260906.bin`
retains the verified input initramfs and adds a console-check service; its
loader prefix is not the same build as the tested native prefix, and is
**not used** by this direct boot path.

GPU remains software-only. The exact shipped Fedora Asahi driver OF match
table has M1/M2 entries but no T6050/M5 hardware configuration. No GPU
registers were touched, and no older-chip compatible was substituted.

The native panic QR has now been decoded by both local Vision and ZXing:
`logs/native-input-panic-qr3-20260906.txt` and
`logs/native-input-panic-zxing-20260906.txt`. At 3.567 s, a udev worker takes
an asynchronous SError in `memcpy_fromio -> apple_smc_read ->
macsmc_power_probe`. The native builder had accidentally omitted the known
working payload's `module_blacklist=macsmc_power,macsmc_input,macsmc_hwmon,
rtc_macsmc`. This is an introduced boot-argument regression, not evidence
that the input transport cannot run natively. `probe/boot-native.py` now
restores and verifies those exclusions, while keeping the SMC core/GPIO
needed by MTP. Corrected hardware retest is pending. Its default panic mode
is now QR so diagnostics remain readable through the webcam.

**Corrected native result:** `logs/native-input-fixed-20260906.log` records
successful RAM transfer and native handoff. Webcam checks show full Fedora
boot followed by automatic root login, with no repeat of the SMC panic
(`logs/native-input-fixed-screen2-20260906.jpg`). Physical keyboard command
confirmation has been requested but is not yet observed. Native trackpad
events are also not yet verified. Native KDE is built and offline-validated
but awaiting the next physical cycle/test; details and hashes are in
`probe/NATIVE-CHECKPOINT.md`. SSD contents remain unchanged.

### Latest: basic KDE is up with built-in input

PRIVATE-USER asked to prioritize a basic desktop over SSD installation. The existing
healthy input+SSD guest now runs **KWin, Plasma wallpaper/panel/launcher, and
Konsole**, using the host's existing KDE image read-only over 9p with an 8 GiB
RAM overlay. No reboot or disk-layout change was needed. `basic-kde.service`
supervises the compositor; this live session also has a separate
`basic-kde-clients.service` after correcting an initial launch argument issue.
Future runs launch the clients from the compositor in the same service.

Webcam evidence `logs/basic-kde-screen4-20260906.jpg` shows the full desktop,
panel and Konsole, with PRIVATE-USER's physical `echo kde_ok` command and output.
KWin has both `/dev/input/event0` and `event1` open. Scale is 2, giving a
1512x945 logical desktop from simpledrm's 3024x1890 usable output. Rendering
is software-only, one CPU, and cold application startup is slow over 9p.

Startup scripts are `probe/prepare-basic-kde.sh`, `start-basic-kde.sh`,
`basic-kde-session.sh`, and `basic-kde-clients.sh`, staged under the read-only
share's `bringup-20260906/`. They disable Bluetooth, automounter, indexer and
welcome plugins only in the disposable RAM overlay. The mounted image and
all SSD namespaces stay read-only. Session logs live in guest `/run`;
see `probe/KDE-CHECKPOINT.md` for operation and limitations.

**Leave the desktop running.** This is the requested basic KDE checkpoint,
not a persistent SSD installation or an untethered boot. RAM-session files
and settings disappear on reboot. No permission to repartition is inferred.

### Latest checkpoint: SSD queue-wrap fix passes read-only tests

`guest-hv-input-ssd-ro.bin` with `--ans-zero-based-limit` passed discovery and
**8,192 direct 16 KiB reads (128 MiB total)**. Four passes over the first
16 MiB of the main namespace matched; four passes over the first 16 MiB of
partition 3 also matched. The controller remains `live`, systemd is `running`,
both input nodes are present, and the MTP DART fault count is zero. No ANS
assert, I/O error, or kernel oops appeared on this corrected boot. This is
read validation, not write, endurance, or standalone-boot validation.

The sole queue change is `0x00400040` → `0x003f003f` at `0x45dcc1210`, with
verified readback. It fixes the observed 65-vs-64 ring mismatch/first-wrap
failure in this test. The kernel and its NVMe module are stock; the hook is
in our own `probe/prepare-ans.py`. No m1n1 source changes this turn.

Evidence: `logs/input-ssd-limit-boot-20260906/console.log` and
`logs/input-ssd-limit-launch-20260906.log`. Reproduction details and disk
identities are in `probe/SSD-CHECKPOINT.md`.

**Installation blocker: all four partitions are APFS, not Linux filesystems.**
Partition 3 is a separate **250,000,000,000-byte** APFS container, PARTUUID
`PRIVATE-UUID-REMOVED`, container UUID
`PRIVATE-UUID-REMOVED`. A bounded read-only object-map lookup
using checksum-verified APFS metadata found its six current volume labels:
`Linux`, `Linux - Data`, `Preboot`, `Recovery`, `VM`, and `Update`.
Do not mistake the label "Linux" for an ext4/Btrfs root partition and format
it: it contains boot/recovery infrastructure. Partition 2 is the separate
687.9 GiB APFS container; partitions 1 and 4 are boot/recovery containers.

No guest SSD data writes, filesystem mounts, repairs, formatting, or GPT
changes have been performed. All namespaces remain block-layer read-only.
The user's no-repartition constraint still applies. Installing a conventional
writable Linux root requires an explicit storage-layout decision/exception,
preserving the Linux boot environment and leaving the macOS container intact.
No physical reboot is currently required; leave the healthy guest running.

### Current checkpoint: built-in keyboard and trackpad verified

`guest-hv-input-v2power.bin` passed its physical input test. Its locally patched
loadable dockchannel-HID module sends the v2 OFF/ON power-request pairs; all
four requests were accepted, the coprocessor consumed the firmware, and
`Touch MT ready` appeared at 21.7 seconds. The stock kernel image is unchanged.

PRIVATE-USER's 90-second capture recorded **826 trackpad SYN reports**, 1062/1072
multi-touch X/Y updates, pressure, two-finger transitions, and **five physical
click press/release pairs**. A/B/C key press/release events also passed on this
patched boot. The capture released both exclusive grabs. Systemd reported
`running`; MTP DART fault IRQ count was **zero**. Full evidence is in
`logs/input-v2power-boot-20260906/console.log`. This establishes raw input;
desktop gesture policy and haptic feel have not been independently verified.

**Next: read-only SSD bring-up.** Rechecking the saved ADT found a serious
error in the older NVMe notes: FAB6_SOC/ANS/APCIE_ST0/APCIE_SYS_ST0 belong to
PMGR group 1, **base 0x280900000**, not 0x280600000. The new combined DT and
runner validate the correct addresses; initial preparation only reads and
requires ACTIVE state, with no host PMGR writes. Guest changes to these four
states are shadowed. Do not run the old `anspower_inline.py`.

Prepared SSD test: `guest-hv-input-ssd-ro.bin` combines the verified input
image with the corrected ANS DT. NVMe automatic loading is blacklisted until
an explicit diagnostic probe; boot/home automounts and udisks2 are masked.
The guest still boots its RAM root. Run the one-shot launcher with
`--prepare-mtp --trace-input --prepare-ans` and the optional KDE 9p share.
`probe/test-prepare-ans.py` verifies the map against the saved ADT and checks
that all four guest PMGR writes remain shadows and that an inactive domain
aborts without a hardware write. The actual ANS/SSD test is not yet booted.

**SSD preflight result:** On the corrected PMGR bank, FAB6_SOC and ANS read
`0x0f0000ff`, APCIE_ST0 `0x2ff` (all ACTIVE), while APCIE_SYS_ST0 read
`0x1000030f` (auto mode, target ACTIVE but actual OFF). The default preflight
aborted before guest execution, without writes, and proxy NOP still worked.
An explicit `--activate-ans-link` option now accepts only that exact observed
gated state after the parents pass. It made one masked host PMGR write at
`0x280900150`, clearing automatic gating and retaining target ACTIVE;
readback reached `0x0f0003ff`. No additional physical restart was needed.

The combined image was tested in
`logs/input-ssd-link-boot-20260906/` with launcher log
`logs/input-ssd-link-launch-20260906.log`. The staged guest probe is
`probe/probe-ssd-readonly.py`: require automount masks, stop udev's execution
queue, explicitly load NVMe, mark discovered namespaces read-only, resume
udev, and report GPT identities. No disk data writes have occurred.

**SSD result:** ANS completed its handshake and exposed three namespaces;
the kernel read enough GPT data to report `nvme0n1: p1 p2 p3 p4`. Then its
firmware asserted `CQ (Host I/O) DB error`, head 63, and removed the disks.
The firmware dump reports 65-entry I/O queues, while Linux allocates 64.
RAM-root systemd and both input devices survived. Partition identities are
not yet established, and no SSD filesystem was mounted.

**Test preparation (now passed above):** `--ans-zero-based-limit` intercepts only the stock
driver's write of `0x00400040` to `0x45dcc1210`, substitutes `0x003f003f`, and
verifies readback. Current m1n1 source uses this zero-based pending-command
limit for 64-entry queues; Linux already uses correct zero-based sizes in
its separate Create Queue commands. This is an unproven queue-wrap hypothesis,
not yet a storage fix. Keep all disk access read-only.

### Earlier input checkpoint and implementation history

`guest-hv-input-sid0.bin` successfully boots the unchanged stock kernel and
Fedora/systemd RAM root. The decisive change was selecting **MTP DART stream
0**, not the M3-derived stream 1, for both the MTP helper and dockchannel HID
nodes. Keep the board-specific DMA range and targeted MTP DAPF preparation.
The SID1 image remains a failed experimental baseline, not a working input image.

Hardware evidence: `logs/input-sid0-boot-20260906/console.log` and
`logs/input-sid0-launch-20260906.log`. MTP completes its RTKit handshake;
keyboard, multi-touch, STM and actuator interfaces enumerate. PRIVATE-USER physically
pressed A/B/C and all four arrows: `/dev/input/event1` captured matching
key-down and key-up events for codes 30, 48, 46, 103, 108, 105 and 106.
The capture released its exclusive keyboard grab when finished.

**Trackpad remains blocked:** firmware upload reports success, but both old
reset commands return `0xe00002c2`. Opening `/dev/input/event0` times out and
later returns `EINPROGRESS` because the interface remains marked starting.
A single 10-ms active-low pulse of the board-derived AFE reset candidate
(SMC low GPIO controller, line 28) completed through the GPIO character ABI
without errors, but produced no readiness event and did not fix the open.
Do not unbind the dockchannel transport: its current remove callback contains
`BUG_ON(1)`. The ignored `tp-accel` and `mtp` firmware interfaces are additional
DT differences to investigate, not established causes.

Promising next fix: Project Wallace reports the same rejected 4-byte MTP
power request on J614s/T6040, solved with the **9-byte v2 will-change /
has-changed pair**, for OFF then ON. This is a candidate for T6050, not yet
tested here. Primary implementation and hardware evidence:
[reset-contract patch](https://github.com/damsleth/wallace/blob/main/patches/t6040-dockchannel-hid-reset-contract.patch),
[live result](https://github.com/damsleth/wallace/blob/main/evidence/2026-08-04-t6040-trackpad-v2-power-request-accepted.md).
The stock Asahi driver sends `{0x40, 1, iface, state}`. Our read-only attempt
to map the known FIFO through guest `/dev/mem` was denied by the kernel;
no FIFO writes were attempted. Do not bypass that restriction. A driver fix
is the direct implementation path, but conflicts with CLAUDE.md's explicit
"pristine kernel / no kernel patches" constraint; ask PRIVATE-USER whether to relax
that rule for a reversible local trackpad-driver patch. Keep the working
guest alive in the meantime; no power cycle is presently required.

PRIVATE-USER subsequently authorized proceeding with the local driver change
("do anything"). This overrides the stock-kernel-only constraint for this
input fix, not the no-repartition/no-macOS-writes constraints. Preparing a
replacement loadable `dockchannel-hid` module matched to the existing kernel;
the working SID0 image remains the rollback baseline.

Built `guest-hv-input-v2power.bin` with a replacement module from the exact
Fedora source/devel RPMs. Module SHA256
`1b4bd27679416faacca50831cb47bd112bb5931a397f8641c2cb1642b7b49837`;
vermagic and `struct module` section size match stock. The actual patched
power-request function passed a compiled recording-stub test for OFF/ON
payloads, phase order, both error paths, and old-board behavior. Build details
and provenance are in `input-driver/README.md`. The image builder verified
all prior payload bytes unchanged except the initramfs-size field.

After a spoken cue, webcam and wire NOP verified a fresh proxy boot. Current
test is `logs/input-v2power-boot-20260906/`, launcher
`logs/input-v2power-launch-20260906.log`. It also exports the existing host
KDE-image directory over 9p as `inputfiles`; this is not internal SSD access.
Hardware input results for this image are not yet established.

At uptime 613 seconds systemd still reports `running`. `lsblk` shows only the
RAM-root loop device and swap zram: **the internal SSD is not exposed in this
input-only image**, and no target disk writes have occurred. The working guest
is being kept alive for diagnostics. Keyboard success does not establish SSD
boot, a full desktop in this image, or standalone/untethered operation.

Known-working launch: chainload the existing live-kit `m1n1-vmtmrfix.bin` after
a physical proxy boot, then run `probe/boot-input.py` with the live-kit SID0
image, a new log directory, and `--prepare-mtp --trace-input`. Use the runner's
persistent SIGUSR1 snapshot / SIGUSR2 stop handlers, never `gstop.sh` or the
auto-retrying wrapper. Stopping has still required a physical restart before
another reliable proxy session. Use webcam verification and spoken cues to
the host speakers; the earlier Glass alert was inaudible.

### Earlier experiments (chronological; superseded by checkpoint above)

Priority is now **the built-in keyboard and trackpad first**, then the existing
Linux SSD partition. The first dedicated input image booted the unchanged
7.0.13 kernel into Fedora; `systemctl is-system-running` returned `running`.

The MTP, mailbox, DART and dockchannel nodes have been added in
`t6050-j714s-hv-input.dts`. Hardware reads confirmed the translated MTP and
dockchannel register addresses. Linux initialized the DART (42-bit addresses,
16 streams, 16-KiB pages), but **MTP wake timed out before its RTKit handshake**.
No built-in input devices registered. DART IRQ 659 fired 100,000 times while
the first bank's error register read zero; the interrupt source remains unresolved.

Exact-board firmware was fetched from Apple's 26.6.2 IPSW using small HTTP
ranges, without accessing the target's macOS filesystem. The converted
`tpmtfw-j714s.bin` is byte-identical to the upstream trackpad converter's output.
It has **not** been tested on hardware. An additional IPD firmware conversion
is experimental and has not been uploaded either.

**Stop-procedure correction:** `gstop.sh` was not safe in the running state:
SIGUSR2 killed the host process, because its special handler is only installed
inside the interactive hypervisor shell. `hv-fixed.sh` then retried the boot.
The proxy subsequently stopped responding. All host processes from this run
were stopped, and a physical power cycle was requested. The new
`probe/boot-input.py` installs a persistent stop handler and has no automatic
retries; it has passed syntax checks but still needs hardware validation.

After a physical restart, the SMC completed its RTKit handshake and exposed
the candidate input-reset GPIO keys (`logs/smc-input-probe.log`). Targeted
MTP access-filter initialization also succeeded, but MTP still did not reply
to its wake message. A subsequent read of an unverified mailbox-bank address
caused a synchronous exception and left the proxy unresponsive again. The
diagnostic client has been stopped; another physical restart is required.
Do not repeat speculative mailbox-bank reads.

The next test image, `guest-hv-input-ready.bin`, includes SMC/reset GPIO nodes
and the verified board-specific trackpad firmware in the initramfs and RAM
sysroot overlay. Its builder verified that the prior payload was preserved
apart from the initramfs size field and appended firmware archive. This image
has **not yet been booted**; reset GPIO mapping and built-in input remain
unverified. Use the one-shot runner with `--prepare-mtp`, not `hv-fixed.sh`.

The user positioned the host webcam facing the target and authorized screen
checks and an audible power-cycle cue. A webcam capture confirmed the target
is displaying exception dumps (`logs/m5-screen-20260906-a.jpg`), and the host
played the Glass sound for the restart request.

**Next hardware run (`logs/input-smc-boot-20260906/`):** The prepared image
booted Fedora to a serial root prompt and `graphical.target`. SMC negotiated
RTKit protocol 12. Importantly, **MTP also reached `RTKit: Initializing
(protocol version 12)` for the first time**, after targeted MTP DAPF setup
before guest execution. It still timed out one second later, so the complete
handshake and built-in input remain unfinished. No DART IRQ storm appeared
in this run. This narrows the problem beyond the previous no-HELLO failure.

The guest then faulted on a 64-bit shared-memory read at `0x28de8c080` while
handling SMC key `BMDN` (battery model); details are in
`logs/input-smc-launch-20260906.log`. The one-shot runner returned EXIT_GUEST
and a proxy NOP succeeded, but a subsequent independent connection timed out.
Thus guest exit is demonstrated, **reusable proxy recovery is not**. All test
clients have been stopped. A webcam capture confirmed a post-exit diagnostic
screen (`logs/m5-screen-after-guest-20260906.jpg`). Another physical restart
is needed; the earlier "no power cycle needed" update was premature.

Prepared, not yet booted: `guest-hv-input-trace-v2.bin`, also copied into the
live kit. It preserves the kernel/initramfs/FDT byte-for-byte and adds only
boot arguments to disable nonessential SMC battery/input/hwmon/RTC modules
and enable RTKit debug logging. Module names were checked against the actual
initramfs. Run `probe/boot-input.py` with `--prepare-mtp --trace-input`; tracing
covers guest accesses to known MTP CPU/mailbox/DART windows, not speculative
register scans. `probe/mtp-mailbox-status.py` now bounds connection attempts
too, since an unresponsive USB write can otherwise block the live kit.

**Traced run (`logs/input-trace-boot-20260906/`):** RTKit debug confirms
MTP reaches HELLO, endpoint map `0x517`, and system endpoint startup. It asks
endpoint 1 for a 16-KiB buffer; Linux returns IOVA **`0x3ffffffc000`** in
message `0x1043ffffffc000`. No subsequent MTP messages arrive, and startup
times out waiting for the IOP power acknowledgement. The board's saved ADT
instead specifies `vm-base=0x10000004000`, `vm-size=0xffff0000`. This is a
concrete DMA-range mismatch, although its causal role is not yet tested.

The DART fault IRQ storm **did recur** in this run, with ERROR/address reads
all zero. Full read tracing flooded the host connection and ended in an event
checksum failure. `probe/recover-guest.py` validated a USER_INTERRUPT callback
and received EXIT_GUEST acknowledgement; the target printed "All CPUs exited".
The orphaned hv_start reply remained queued (the script now accounts for it),
but a subsequent bounded NOP still timed out. Another physical restart is
required. See `logs/input-trace-launch-20260906.log` and
`logs/input-trace-recovery-20260906.log`.

**Next prepared image:** `guest-hv-input-dma-range.bin`, copied to the live
kit. The DART node now sets `apple,dma-range` to the board's exact ADT range.
The builder verified that only the FDT changed, preserving the pristine
kernel SHA256 `f1672f680082c40b8f606b5acd70f9a5ec7cef0d04abc2f63a2d26862a045999`.
Use `--prepare-mtp --trace-input`; DART tracing is now write-only to avoid
the fault-IRQ flood. This range change is **not yet hardware tested**.
Built-in keyboard/trackpad and SSD boot remain unfinished; no target disk
writes have been performed.

The user reported that the Glass alert was inaudible. Host output is unmuted
at volume 69; system sounds route through Background Music while the normal
output is MacBook Pro Speakers. For the next cue, use a spoken alert explicitly
directed to the speakers (`say -a 95` in this session; rediscover device IDs
with `say -a '?'` after audio-device changes). Audibility still needs user
confirmation; do not infer it from command success.

After the spoken cue, webcam checks showed a physical restart followed by
"Running proxy" (`logs/m5-screen-cycle-check-20260906.jpg`), and an independent
wire NOP succeeded. The DMA-range image is now being tested in
`logs/input-dma-boot-20260906/`, with launcher output in
`logs/input-dma-launch-20260906.log`. No additional "done" message was needed.

**DMA-range result:** The new buffer IOVA is `0x100ffff0000`, within the ADT
range, but MTP still stops after that buffer response and times out waiting
for IOP power ACK. The range mismatch alone did **not** explain the failure.
The DART IRQ again reached 100,000 with no error reported by its current
driver. Reduced tracing stayed intact. Fedora remained responsive for over
four minutes with `systemctl is-system-running=running`; the firmware hash
was verified inside the guest, both SMC GPIO controllers registered with 64
lines, and `/proc/bus/input/devices` remained empty. Thus the nonessential
SMC-module blacklist avoided the earlier battery fault in this test.

The new runner's SIGUSR2 handler successfully requested EXIT_GUEST from this
healthy guest. Reconnection still failed (bounded independent test expired),
so another physical restart is needed for the next experiment.

Next experiment: same DMA-range image and `--prepare-mtp --trace-input`, plus
`--prepare-mtp-tunables`. This applies the six exact ADT DART tunables at
offsets `0x20c,0x220,0x224,0x300,0x308,0x310`, with expected board/address/width
checks and before/after register readback. This setup was absent from our
earlier boot path. Its effect is **not yet hardware tested**. Do not interpret
the mere presence of these tunables as proof that they cause the fault.

**Tunable test result (`logs/input-tunables-boot-20260906/`):** Every masked
value already matched the ADT before applying it; readback was unchanged.
MTP still timed out at the same buffer/IOP-ACK stage. This rules out missing
values in that six-entry tunable set as the explanation. SIGUSR1 now takes
a bounded read-only snapshot through the existing host connection and resumes
the guest; that resume was verified with a guest-console command.

The snapshot shows stream 0 disabled (`TCR0=0`, `TTBR0=0`) and stream 1
configured (`TCR1=9`, valid TTBR). Both MTP mailbox queues are empty, so the
firmware has consumed the buffer reply; the DART error registers still read
zero. The baseline SID1 came from the M3 DT, while this board's ADT
`mapper-mtp.reg` is 0. These identifiers are not necessarily interchangeable,
but a controlled SID0 test is warranted.

Prepared **not yet booted**: `guest-hv-input-sid0.bin`, from
`t6050-j714s-hv-input-sid0.dts`, changing only the MTP/helper and HID IOMMU
stream cells from 1 to 0. The SID1 baseline is preserved separately, and the
builder verified every non-FDT byte unchanged. The test guest has been stopped
using the persistent SIGUSR2 handler. SSD contents remain untouched.

Evidence: `logs/input-first-console.log`, `logs/input-first-hv.log`, and
`logs/input-boot-20260906.log`. No target disk writes or repartitioning were
performed. SSD boot remains unfinished.

---

## What the machine is, and why it was hard

| | |
|---|---|
| Machine | MacBook Pro 14", M5 Pro, 2025 (`Mac17,9`, board `j714s`) |
| Chip | **T6050 "Sotra"**, chip ID `0x6050` |
| RAM | 59 GB usable |
| Support status | None. Asahi Linux does not support M5 |

Apple Silicon Macs don't boot Linux directly. Apple's firmware (iBoot) only
hands control to something it recognises, so the Asahi project wrote a
bootloader called **m1n1** that sits in between:

```
iBoot  ->  m1n1  ->  Linux
```

m1n1 had *initial* T6050 support upstream — it boots and initialises the
interrupt controller, power manager and display. What did **not** exist was
everything above that: no device tree describing this machine to Linux, and no
knowledge of where this chip differs from its predecessors. Finding those
differences was the project.

---

## The stack we ended up with

```
iBoot
  -> m1n1 (patched for T6050)
       -> m1n1's hypervisor (patched)
            -> m1n1 again, as a guest
                 -> Linux 7.0.13 asahi  <- completely unpatched
                      -> systemd -> KDE Plasma
```

**The kernel is stock.** That was a rule from the start and it held: every fix
lives in m1n1 or in the device tree. A standard Asahi kernel boots on this
machine as-is.

---

## How we actually debugged it

This is the part worth telling, because it's where most of the time went.

**At first we had one bit of information per reboot.** No serial port works on
this machine (`macvdmtool`'s debug protocol is rejected by the M5's USB-C port
controller), and Linux prints nothing before it has a console. So the only way
to ask "did we get this far?" was to patch a stub into the kernel that paints a
coloured stripe on the screen and halts. Boot, look at the screen, reboot.
Roughly ten minutes per bit.

**Then m1n1's hypervisor changed everything.** m1n1 can stay resident and run
Linux as a *guest* underneath it, intercepting everything — and it emulates a
serial port whose output comes back over the USB cable. That turned "was there a
stripe?" into a full kernel log plus register dumps on every fault.

**And then a genuinely humbling discovery:** m1n1 exposes **two** USB serial
ports, and the guest's console comes out of the *second* one. We'd only ever
opened the first. An entire boot we had recorded as "silent" had in fact been
printing its whole log into a port nobody was reading.

Two other techniques that paid for themselves repeatedly:

- **Probing unknown registers safely.** m1n1's proxy can be told to skip a
  faulting instruction instead of dying, so unknown registers can be read
  without killing the machine. A faulted read returns the value `0xabad1dea`,
  which is how you detect it.
- **Reading the machine's own binary back.** You can pull m1n1's memory back
  over USB and disassemble it, then resolve a crash address to an exact
  function. Twice, a **photograph of the laptop's screen** was the input to
  that: read the program counter off the photo, resolve it against a
  byte-identical local rebuild, get the exact faulting line.

---

## The M5-specific discoveries

These are the things that were actually different about this chip. Each one cost
hours, and each is now a one-line answer.

### 1. A timer register that only accepts reads

`SYS_IMP_APL_VM_TMR_FIQ_ENA` reads fine and **rejects writes** — but only while
the hypervisor is running a guest. In ordinary context writes are silently
accepted and ignored. The proof was neat: the faulting write was a
read-modify-write that put back *the value already there*, and still trapped.

Fixed by masking guest timers a different way (the architectural `IMASK` bit)
instead of writing that register.

### 2. The timer runs at 1 GHz

Every previous Apple chip runs its architectural timer at 24 MHz. M5 runs at
**1 GHz** — measured, not just read from a register. This is actually the
ARMv8.6-mandated behaviour, and Linux handles it correctly, but it looked
alarming until confirmed.

### 3. Secondary CPUs never start

The registers that start the other CPU cores ignore writes. All 17 secondaries
time out. Everything so far runs on **one core**. Unsolved.

### 4. Power-management writes crash the host

The hypervisor normally replays a guest's power-controller writes onto real
hardware — and upstream's replay *forces the domain on*. On this chip one of
those writes killed the machine outright, and the specific domain involved was
the parent of the USB tree carrying our own debug link. Now shadowed instead of
replayed.

### 5. The storage addresses were wrong by a constant

The single biggest time-sink. Apple's device tree stores hardware addresses that
must be **translated** (`+0x200000000` here) before use. We'd translated the
serial port correctly — which is exactly why the console worked — but recorded
the SSD's addresses raw. Every "the SSD is powered off", every crash, every
wedged machine, was us reading a hole in the address space.

```
what we used        what it should be
0x21dcc0000    ->   0x41dcc0000     NVMe controller
0x219600000    ->   0x419600000     its coprocessor
0x21dc50000    ->   0x41dc50000     SART (DMA filter)
```

With the right addresses the controller answers immediately.

### 6. SART version 4

The DMA address filter is a new revision that moves two register arrays. We
reverse-engineered the layout from live register dumps — and it turned out
**byte-identical** to an upstream commit annotated *"As seen on M5 Pro/Max
(T6050)"*. Nice independent confirmation.

### 7. The NVMe register file was split

On M4 and later, the NVMe registers moved: the old location is now only a
memory-management unit, and the real controller lives at a different address.
Known upstream as the "T8132" model, selected by a property this chip has.

### 8. m1n1's own NVMe driver was destroying the machine

m1n1 has a built-in NVMe driver using the *old* layout. When it failed it
entered a polling loop that faulted on every iteration — the laptop scrolled
register dumps forever with nothing listening, needing a physical power cycle.
Found by reading the program counter off a photo of the screen. Now disabled on
this chip; Linux drives the disk instead.

### 9. A virtio interrupt collision

To stream the desktop's filesystem we attach a virtual device. m1n1 allocates
its interrupt from the **bottom** of the range, which on this chip handed it
**IRQ 1** — timer territory. That killed the guest the instant it started, with
a signature we'd previously misdiagnosed as an image-size problem for three
attempts. Allocating from the top fixed it immediately.

Also needed: this chip is AIC **version 3**, which upstream's helper didn't know
about at all.

---

## Milestones, in order

1. m1n1 boots and talks over USB
2. A bare-metal payload paints the screen — handoff works
3. Kernel entry confirmed (a coloured stripe)
4. Hypervisor console working — real logs at last
5. **Linux boots** to the root-filesystem panic in 1.24 s
6. **Interactive root shell**, over the emulated serial port
7. **Full Fedora from RAM**, reaching `graphical.target`, `systemctl
   is-system-running` = `running`
8. SSD controller responds — `0xf00100fd`, the NVMe capabilities register
9. The desktop's filesystem mounted over the USB cable (9p), no upload
10. `kwin_wayland` paints its first window
11. **KDE Plasma desktop** — wallpaper, panel, launcher

For the record, at milestone 5:

```
Booting Linux on physical CPU 0x0000040000 [0x611f0641]
Machine model: Apple MacBook Pro (14-inch, M5 Pro, 2025)
arch_timer: cp15 timer running at 1000.00MHz (virt)
Console: switching to colour frame buffer device 378x118
```

---

## What still needs doing

### 1. Storage — closest

Everything is derived and verified: addresses proven on hardware, SART decoded
and cross-checked against upstream, register split identified, and the drive's
coprocessor already completes its handshake (RTKit protocol v12). The fix is
built and deployed but has **never had one clean run** — every attempt so far
died on unrelated plumbing.

*Difficulty: low-to-moderate. Risk: more M4-era differences behind the first.*

### 2. Bare metal — removes the tether

Today Linux runs as a hypervisor guest driven from another Mac. Booting it
directly is what makes the laptop standalone. This previously failed, but that
was before we understood the timer register; an image with the offending writes
removed is built and **untested**.

*Difficulty: unknown, plausibly near. This is the single highest-value item.*

### 3. More CPU cores — the difference between "works" and "usable"

One core, software rendering, 3024x1964. Plasma runs, but slowly. Secondary CPUs
have never started, and the registers ignore writes from where we're running —
which smells like a deliberate security gate rather than a bug.

*Difficulty: unknown. Could be a day or a wall. This is what stands between
"KDE appears" and "KDE is pleasant".*

### 4. Keyboard and trackpad

**Correction to an earlier assumption:** these are *not* the M1-style SPI
devices. This machine uses **MTP over dockchannel** — meaning a second
coprocessor to boot, firmware to extract from the macOS install, three new
device-tree nodes, and power domains the guest doesn't own.

*Difficulty: high — comparable to the SSD work. A USB keyboard would be
considerably easier, and there's already a synthetic input path that lets the
desktop be driven remotely.*

### 5. GPU

Everything is software-rendered. A real driver is a large, separate project.

*Difficulty: very high. Not on the near path.*

---

## Ground rules that held

- **Never touch the macOS install, never repartition.** All disk work so far is
  register reads; nothing has been written, and the partition table hasn't been
  looked at sideways. When the disk mounts, it gets identified read-only by UUID
  first.
- **The kernel stays unpatched.** Every fix in m1n1 or the device tree.
- **Nothing goes upstream.** m1n1's maintainers forbid AI-assisted
  contributions, so none of this is offered as patches. A human-written bug
  report describing the hardware behaviour would be a different matter.

---

## The honest summary

A stock Asahi kernel and a full KDE desktop run on an Apple M5 Pro. Nine
chip-specific problems were found and fixed, several of them undocumented
hardware behaviour, and the two we could check against upstream both matched
independent findings exactly.

It is tethered, single-core, has no working keyboard, and reads its filesystem
over a USB cable. It is not a daily driver.

But the machine went from "prints nothing, one bit per reboot" to "runs a
desktop" — and every remaining item is a known problem with a known shape,
rather than a mystery.
