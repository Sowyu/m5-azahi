# Resume safely

## Current status: v7 cold boot verified; audit repairs in progress

This section supersedes the chronological checkpoints below. One v7 cold
boot was verified: simpledrm 3024x1964 at 60 Hz, user-selected 175% scaling
persisted, root on SSD Btrfs, USB tethering and pinned SSH active, and
interface-bound certificate-validated HTTPS returned 200. No APFS mounts.
Keep every USB-C socket empty during boot; connect the phone after KDE.
CPU0 only, software graphics, shutdown power-cut hang, Wi-Fi and native
Codex installation remain unresolved. This is not a production-ready system.

PR #1 is an unmerged audit, not 300 independently confirmed bugs. Confirmed
input receiver interface bounds and allocation-failure rearm bugs are fixed
in source; extracted actual-function tests pass with ASan/UBSan and an exact
kernel module cross-build succeeds. The replacement module is NOT installed;
never unload the live input driver to test it. Stage a rollback-backed boot
test separately. Do not apply the audit's suggested ACK mutex fix: the sender
holds that mutex while waiting for the ACK. The loader cache-flush allegation
also ignores the existing initrd relocation and is not a verified defect.

Privacy remediation removes a flattened private directory path from an
archived patch and adds a regression-tested publication rule. Approved Git
history cleanup preserves a private backup and the audit branch. Existing
clones must be refreshed after the rewrite; do not push old history back.
No evidence of exposed credentials or compromise has been established.

## Historical checkpoints (not current status)

## Latest: v7 full-height candidate installed; first cold boot pending

Fresh backup confirmed the selected working v6 image before installation.
Recovery installation readback now matches v7 SHA256
2eaea0bc1503c2ac74a1b11dbb88423675f324a61db3da6db1aa88392672f5ba,
size92651520, raw entry2048. v6 is preserved as rollback. This supersedes
the not-installed state below, but NOT the hardware-test warning: no v7
Linux boot/display result yet. Next boot with every USB-C socket empty;
connect phone after KDE loads. Check full display mode, settings persistence,
USB/SSH/HTTPS before declaring success. Private recovery server remains up.

## Newest: opt-in full-height framebuffer candidate built, NOT installed

User explicitly overrode local bootloader AI restrictions for this personal
project. The private candidate retains original firmware framebuffer geometry
instead of the default 74-row notch crop. It requires an explicit chosen
azahi,full-height-framebuffer u32 value1 plus exact J714s/T6050/board8 and
3024x1964, stride12096, depth30/32 checks. Default/mismatch stays cropped.
No display-register writes or new framebuffer allocation are introduced.

Actual C guard tests pass (10 cases); cross-build and offline image checks
pass. v7 preserves working v6 args/kernel/initrd; only DT opt-in and loader
change. Image size92651520; SHA256
2eaea0bc1503c2ac74a1b11dbb88423675f324a61db3da6db1aa88392672f5ba.
NOT installed or hardware-tested; v6 remains the booted image. Need a guarded
backup/test/install workflow pinned to current v6 before requesting Recovery.
Do not reuse old repair server pins. Full height also exposes the physical
notch, so desktop notch avoidance is a separate usability consideration.

## Latest: persistent KDE preferences configured, reboot test pending

The installed launcher created a new /run/kde-clean directory each launch,
explaining lost preferences despite the SSD root. A backup-backed migration
now keeps current preferences under /root/.config/azahi-kde and redirects the
active session's old config path there. The launcher uses the persistent path
on subsequent starts. Software-rendering flags and direct KWin/Plasma startup
are preserved; session restoration is disabled with loginMode=emptySession.

Live checks confirm 200% scaling (1512x945 logical), Breeze Dark, and matching
saved configuration on Btrfs. KDE was not restarted; USB and SSH remained active.
No APFS mounts, partition or boot changes. Persistence is configured but not
yet verified across a reboot; do not claim the earlier freeze issue resolved.
Only 3024x1890 is exposed; the notch strip remains a separate display issue.
Private backup directories and preferences stay on the native laptop. Restore
the backed-up launcher to return to per-launch clean settings if needed.
Codex CLI installation is still pending; don't assume native agent access.

## Latest: v6 SSD cold boot + automatic USB tethering + SSH VERIFIED

After booting with every USB-C socket empty and connecting the phone only
after KDE loaded, the user reported USB tethering working. The helper then
reconnected using the existing pinned SSH keys WITHOUT a new bootstrap,
proxy payload, manual module command or network-profile creation.

Direct native checks confirm:
- Root is the intended SSD Btrfs filesystem.
- azahi-usb.service started at boot and reported USB_HOST_READY at ~8 seconds.
- Native HPM mode=awake, result=0, ready=Y, poisoned=N.
- The saved azahi-usb-tether profile is active on the USB interface.
- Both persistent SSH services are active; all three task units and chronyd enabled.
- Interface-bound certificate-validated HTTPS GET returned HTTP200.
- Clock synchronized; no failed systemd units and no APFS mounts.
- CPU online remains only CPU0; Wi-Fi and native GPU still unresolved.

This establishes ONE successful cold boot with automatic Linux-side USB and
SSH startup, not general reliability or arbitrary hotplug support. Working
procedure: leave every USB-C socket empty while starting Linux; MagSafe may
remain. Connect the phone after KDE loads and enable tethering on the phone.
Boot/internet no longer require a helper payload. Remote SSH still requires
the same private helper relay running and reachable on the configured network.

Preserve this working session. Do not reload minimal, unload the live overlay
or repeat DWC3 live reload: that failed with -110 on the earlier boot. Boot
with a cable present can trigger the deliberate connected-state HPM refusal.
Shutdown can still hang at poweroff.target; do not claim it is fixed.
No kernel/runtime update, new power-role task, disk resize, or daily-macOS
change accompanied this successful boot verification.

## Earlier: native HPM wake works; DWC3 live reload fails with -110

On the v6 cold boot, unplugging USB-C cables and loading the native helper
in awake mode yielded result=0, ready=1, poisoned=0, state=0. Phone charging
returned. A connected read-only probe matched the prior working session's
power/data-role tuple, but the phone still had no USB data enumeration.

The isolated DWC3 removal returned quietly; its subsequent probe FAILED:
controller soft reset timed out (-110), leaving no USB buses. A successful
insmod exit did not mean the device probe succeeded. Do not repeat this live
reload as a recovery recipe or unload the applied overlay. PHY/clock/reset
reinitialization remains a driver limitation to investigate, not a proven fix.
Four host glue tests pass, including a new actual-remove-function control-flow
test; these do NOT establish successful physical controller reinitialization.

Next attended test: save work and power off normally, then boot Linux with
EVERY USB-C socket empty (MagSafe may remain). This avoids the initial
connected-state refusal and lets the saved service attempt HPM wake before
first USB-controller initialization. Wait for KDE before plugging the phone.
No further reset-register experiment or Recovery enrollment is needed for
this test. Cold-boot tethering is still unverified; prior working-boot proof
must not be presented as reliable automatic startup.

## Earlier: v6 cold boot reaches KDE; USB startup FAILED

User reports KDE booted after the attended v6 shutdown/startup test, without
a new helper payload. This is the first reported cold boot of installed v6.
However, the phone does not charge and USB tethering is unavailable. The user
also tried the minimal driver command; its detailed result is not yet known.

Native SSH is currently unreachable (reverse-forward listener absent).
Prior working-boot tethering/SSH evidence remains valid, but automatic USB
initialization across cold boot is NOT working. Do not call this a successful
autonomous network setup. Need azahi-usb service journal and azahi-hpm kernel
messages before assigning a cause. No repeated minimal command, driver unload,
blind HPM retry, power-register write or reboot. Preserve KDE and obtain logs.

## Earlier: corrected v6 installed and readback verified; cold boot NEXT

The attended Recovery repair passed its fresh snapshot gate and installed
the corrected v6 loader. The uploaded readback matches the exact previously
RAM-booted v6 SHA256 and 92651520-byte size. Linux volume identities and
policy transition passed; final Linux Preboot is read-only. The v3 rollback
image and pre-install v4 backup remain preserved. No daily macOS change.

Cold boot is NOT yet tested. Next: orderly Recovery shutdown, unplug phone
and helper data cables (keep charger), select Linux from startup options.
Wait for KDE before reconnecting the phone and enabling tethering. The native
USB startup helper needs its first state-7-to-S0 boot test; saved SSH tunnel
should reconnect once tethering is active and the same helper is reachable.
Do not send a proxy payload: this test must use the newly installed loader.

## Earlier: native SSH and guarded startup installed; cold boot still pending

USB tethering is verified by direct native SSH: DHCP/DNS and interface-bound,
certificate-validated HTTPS GET and HEAD succeed. The earlier TLS failure
cleared after clock synchronization. The helper now has task-key-only SSH
access through a pinned, loopback-only reverse tunnel; no public/LAN root
listener or global sshd change was made.

Dedicated persistent SSH services were installed, enabled and live-switched
successfully with rollback protection. A reconnect and HTTPS GET passed.
The dedicated USB NetworkManager autoconnect profile is saved; the existing
working connection was not interrupted. chronyd remains enabled. make was
installed; GCC/toolchain upgrades were deliberately held because the solver
also wanted core runtime upgrades. No kernel or core runtime upgrade occurred.

A narrow native HPM helper was built against the exact running kernel.
Live status-only and logical read-only probes both passed; HPM is already in
S0 and networking remained usable. Its SSPS path is guarded to the previously
observed disconnected state-7 tuple, with fault latching and no reset/role
override. Native state-7-to-S0 execution is NOT yet live-tested. Three groups
of protocol tests pass, including all 32 status-bit deviations and faults.

azahi-usb.service is installed and enabled. Its live already-loaded branch
preserves the working USB controller and passed; eight mocked startup tests
cover clean load, partial load, hash/root refusal, poisoned/no-ready state,
clean refusal recheck, driver failure and missing root hub. Four real
loopback SSH tests pass on isolated ports. No failed native systemd units;
all three saved services active and HTTPS GET 200 after installation.

CRITICAL remaining issue: installed boot object is still bad v4, which stops
in proxy. This Linux session came from corrected v6 RAM handoff. Do not claim
standalone cold-boot success. The v6 loader needs Linux-paired Recovery
enrollment, fresh verified backup, user authentication and an attended boot
test. Do not run the old transfer server unchanged: it targets bad v4.
For first native HPM cold-boot test, phone should initially be unplugged;
a connected state-7 partner causes clean refusal rather than unsafe writes.

Preserve the current KDE/USB session. No reboot, APFS mount/write, partition
change or daily-macOS access was performed for these native installations.
Photos, generated SSH keys/state, addresses, device IDs and private receipts
must never be published. Only reviewed source/tests and sanitized results
belong in the public repository.

## Earlier: native remote-access relay prepared; user bootstrap pending

User approved secure remote access and automatic boot/network startup.
Phone is confirmed on the same Wi-Fi as the helper. A dedicated SSH relay
has been prepared, with task-specific keys and a fingerprint-verified,
one-use password bootstrap. The native script checks kernel/model/Linux-root
identity and creates a loopback-only key-authenticated sshd plus a fixed
reverse tunnel, using unique runtime state and transient systemd services.
It does not alter global sshd config, existing keys, firewall or boot files.

Four real loopback SSH integration tests pass: wrong credentials/host key,
one-use bootstrap, arbitrary command and local-forward refusal, exact
loopback remote-forward restriction, host-key pinning and actual tunnel data.
Pinned helper-only dependencies are in remote-access/requirements.txt.
The helper listener is running; no native connection or installation is yet
verified. The user has the short setup commands and fingerprint. Do not infer
that simply having internet makes an inbound SSH route available.

Next: verify native connection and fresh read-only inventory; preserve the
working USB session. Then plan/install native startup components with scoped
backups. Persistent loader correction and HPM initialization are still
unfinished; no reboot, power cycle or macOS write was performed here.
Generated keys, passwords, setup payloads and private host addresses must
never be exported. Only the five reviewed remote-access source files were
enrolled in both publication allowlists; all privacy checks remain enabled.

## Earlier: certificate-validated HTTPS over USB confirmed

User screen evidence shows chronyd restart, chronyc makestep returning
200 OK, and UTC date corrected to September 13, 2026. A subsequent curl
HEAD request with --noproxy '*' and --interface enu1 to the Asahi HTTPS site
returned HTTP/2 200 with certificate verification enabled (no insecure flag).
Together with prior DHCP, DNS, external ping and browser evidence, native
USB tethering is confirmed working for this boot. The earlier certificate
error cleared after clock correction. This is a successful HEAD test, not
a rerun of the original runner's GET test or a bandwidth/stability benchmark.

Next efficiency improvement: establish authenticated native remote access
so commands/logs can move directly, rather than user typing/photos. No SSH,
remote agent or inbound reachability is configured/verified yet; phone NAT
may require a deliberate connection route. Network access also permits native
downloads. Do not assume autonomous or reboot-persistent operation: current
HPM setup was from proxy and permanent loader still needs correction.
No reboot, new driver load, remote-access setup or macOS change was performed
for this milestone. Photos and raw request/device identifiers remain private.

## Earlier: native USB tethering works; HTTPS clock error remains

User-provided screen evidence shows the preserved candidate loaded on native
Linux and a unique right-port USB network interface, enu1, was identified.
NetworkManager activation succeeded and DHCP assigned a private IPv4 address.
DNS resolution and repeated external ping replies succeeded; Firefox loaded
Google search results. User confirms USB tethering is enabled on the phone.
This establishes working native tethering for this boot.

The runner's stricter interface-bound HTTPS test failed with curl error60:
"certificate is not yet valid", HTTP000. Do not misreport this as HTTPS-test
success or bypass certificate validation. The previously incorrect Linux
clock is the leading explanation; correct/synchronize it and rerun only the
HTTPS check, NOT the driver-loading script. No current target date output has
yet confirmed the clock diagnosis.

Do not reboot or unload/reload the applied overlay. Permanent boot remains
bad v4, current Linux used the verified v6 RAM handoff, and HPM awake setup
was performed from proxy. Network profile is temporary and this is NOT a
reboot-persistent networking fix. Next: clock/TLS verification, then native
remote access and deliberate persistent initialization work. Daily macOS
remains untouched. Photos, private IP/MAC/connection identifiers and raw logs
are excluded from publication.

## Earlier: system-awake task succeeded; phone charging and host/source confirmed

Cable correlation passed: unplugging only the phone cleared attachment,
power and data status on the audited right-port HPM. The phone was left
disconnected for a separately gated SSPS(S0) startup experiment, following
the pinned upstream SN201202x initialization path. This mode requires the
exact observed empty-port tuple; the general S0 guard remains unchanged.
It does not assert that the persistent status bit28 is electrically harmless.

The single task returned zero and system-state readback changed 7 to 0;
the port remained disconnected. No reset, power-role-swap, forced-device
task, IRQ-mask write or persistent boot change was issued. After reconnect,
the user reports charging. Readback: status 0x108280fd, power 0x0f0d,
data 0x80000073, system state0, task result0. Pinned role definitions now
confirm host/source. This is physical charging + role evidence, NOT yet
USB device enumeration, DHCP or working tethering.

Nineteen offline HPM/FFI tests pass, including all 32 one-bit deviations
from the narrowly permitted disconnected status, incorrect power/data/state,
and preservation of the default refusal behavior. The fresh-address,
hash-verified v6 RAM handoff completed for the native tethering test.
Full original payload hash and every replacement chunk's readback passed;
the original loader returned success and the expected next stage was verified.
User was asked to run the preserved SSD candidate and enable phone tethering.
Permanent v4 boot remains unchanged. Daily macOS remains untouched.

## Earlier: attached-port roles conflict with phone UI; SWDF rejected

An attachment snapshot now reports status 0x1000b41d, power status 0x0f3f,
data status 0x800000f3 and system state 7. With the pinned tipd definitions,
these indicate a connected sink/device rather than source/host. However,
the phone reports "USB controlled by Connected device" already selected.
Physical cable-to-controller correlation must therefore precede further tasks;
do not treat the interpretation as a confirmed phone-role diagnosis.

One SWDF data-role request completed with task result 3 (rejected), leaving
roles/state unchanged. No retry, power-role swap, SSPS, forced-device-policy
command, reset, IRQ-mask write, disk write or boot change was issued.
A fresh snapshot confirmed the same values. Proxy remains parked and healthy.
USB tethering is NOT working or verified.

The host diagnostic now has a separately gated one-shot data-role mode,
captures task status/result, and passes 16 offline tests. Existing S0 guards
remain unchanged. Saved firmware contains a forceUSBDeviceMode(false) path
using UFPf with zero payload, but applicability and active policy are unproven;
no UFPf command was sent. Do not infer that this justifies bypassing guards.

Fresh RAM layout differs from the old v6 script pins. Loader prefix/function
verification passed, next-stage entry is zero and no live secondaries were
found. Do not run the old RAM handoff script unchanged. Daily macOS is untouched.

## Earlier: live SPMI4/HPM reads succeed; power-state change withheld

The helper proxy appeared. Fresh loader/ADT/right-HPM identity passed.
Controller power 0x0f0000ff and FIFO 0x40004000 were read before bus commands.
WAKEUP, selector polling and logical-register reads completed successfully
using the shared C transport. Two snapshots: APP mode, VID0x28,
status0x10000000, system state7, power/data status zero.

No SSPS/S0 task, IRQ mask, reset, disk write or boot change was issued.
State7 and status bit28 require interpretation; the older driver labels the
latter a voltage warning. Existing S0 guard rejects this combination and
must not simply be removed to make a test proceed. USB remains unverified.

User was asked to connect the Nothing phone to the right socket (if free),
leaving the helper cable connected, and report charging. The physical check
is pending. Target is parked in proxy. Continue with cable/attach observation
and documented state semantics; then an appropriate controlled test. Prior
v6 boot address pins are stale until checked against the current session.

## Latest: attended HPM proxy diagnostic prepared; live connection required

Added proxy-hpm.py and a host-only FFI bridge to the already-tested C transport.
Thirteen offline tests pass. Explicit status-only mode verifies current loader,
ADT, right-HPM identity, controller power and FIFO state. Probe adds wake and
logical selections; a separately gated S0 mode permits only the documented
SSPS system-awake task with safety checks and completion/result/state readback.
No disk writes, boot changes, controller resets or IRQ-mask writes are present.
The original USB delivery bundle and Linux modules remain unchanged.

No live HPM command has been issued. Helper currently has no proxy serial port.
User has been asked to save Linux work, reconnect the known helper cable/socket
and boot the Linux entry to Running proxy. Do not boot Recovery or touch daily
macOS. Do not reuse stale v6 RAM addresses: inspect fresh identity/layout first.
Next: status-only proxy check, then controlled HPM probe if power/FIFO healthy.
If S0 is needed and verified, test whether it survives the corrected RAM boot
and enables phone attachment. This is an untested hypothesis, not USB success.
USB tethering remains unverified; no user network interface/DHCP/HTTPS result.

## Latest: SPMI4 polling prototype passes host tests, not live-ready

Implemented a shared C FIFO transport plus a Linux SPMI controller adapter in
usb-driver/pd-backport. Right-HPM SID only, no reset/shutdown/flush, bounded
polling, strict reply checks, no partial read output and latched failure.
Both probe and transactions default disabled. No IRQ domain or DT overlay.

Four host test groups pass under AddressSanitizer/UndefinedBehaviorSanitizer:
independent command encodings; all extended lengths/address boundaries;
invalid requests with no IO; and timeout/malformed-reply/failure-latch cases.
Controller compilation, combined linking and modpost pass against the exact
target kernel headers. No loadable module, target write or delivery change.

This does NOT fix tethering yet. Next: audit HPM selector/wake completion and
implement justified polling or IRQ integration, with ownership/power/lifecycle
review before any live test. Upstream PD probe cannot just bind to this adapter
and is not read-only. Do not unload the USB overlay or request a casual reboot.
Current KDE remains v6 RAM handoff; persistent loader remains bad v4. The old
four-file candidate is checksum-verified on Linux SSD. Daily macOS untouched.
No new user typing or power cycle is needed at this checkpoint.

## Latest: native inventory and generation-4 controller gap

User reports /sys/class/typec missing and SPMI devices listing "0", interpreted
as total 0. No registered SPMI peripheral is evidenced. This is not a measured
VBUS diagnosis and does not establish the physical connection's failure cause.

Host audit confirmed target nub-spmi-a1 is generation 4. Existing 7.0.13
controller source uses old FIFO offsets and lacks command/IRQ support; both
Fedora patchsets leave drivers/spmi unchanged. Even the newer pinned Asahi
IRQ-capable controller retains the old register layout. Do not bind it by
simply adding a compatible string. Saved Apple initialization confirms gen4
FIFO offsets 0x200/0x210/0x220, RX-empty bit30, IRQ banks0x400/0x600 stride4.
Seven hash-pinned offline checks pass; no MMIO or target driver changes.

A separate compile-only compatibility patch removes the newer dedicated
Thunderbolt-switch hooks, preserving generic Type-C/mux code and unchanged
SPMI transport. Patched core+transport+trace compile/link and pass modpost;
unmodified control still fails as expected. No fake-success stubs or loadable
module. This is NOT a complete USB2-only driver or hardware success.

Next engineering: implement/audit actual generation-4 controller ownership,
commands, bounded FIFO handling and interrupts (or justified polling); then
PD role integration and safe delivery. Do not unload current overlay or reboot.
No new user command is requested. Candidate copy remains verified on Linux SSD;
persistent boot remains bad v4, current KDE from v6 RAM correction. macOS untouched.

## Latest: SSD copy verified; PD backport audit

User reports four checksum OKs for /root/usb-candidate after the guarded
new-directory copy from /run. The original candidate is now preserved on
Linux's SSD; this is NOT a persistent boot fix. Do not reboot or unload.

New host-only feasibility check lives under usb-driver/pd-backport. Seven
unmodified, hash-pinned Asahi source/config files were fetched. Against the
exact target headers, SPMI transport and trace compile; shared core fails on
15 diagnostics for newer Type-C/Thunderbolt switch APIs. No compatibility
stubs, loadable module, target writes or delivery changes. Modpost not reached.

Saved Linux DTB contains no SPMI/USB-PD nodes. Saved right-port HPM interrupt
types are 0/2/3 for IRQs 11/17/19; upstream needs four named IRQs. Its example's
select IRQ13 remains unverified for this target. Probe issues WAKEUP and core
changes S0/interrupt masks, so a PD probe is not a read-only test.

Next native read-only inventory: ls -l /sys/bus/spmi/devices /sys/class/typec
Send exact output, including missing-directory messages. No reboot needed.

## Latest: live test timed out before phone networking

The next user photo shows the runner's failure: no unique right-port USB
network interface. Kernel messages at about 590.5 seconds show PHY host init
completion, xHCI USB2/USB3 root hubs (Linux IDs 1d6b:0002 and 1d6b:0003),
one port on each, and "host mode up (state 2)". These are controller root hubs,
not the phone. No child-device attach or descriptor error appears in the
displayed tail. The shell prompt returned; no kernel hang is shown.

The user previously reported no phone charging and grey tethering. Whether
the requested reconnect was performed is not separately confirmed. VBUS /
Type-C role handling remains a hypothesis, not an electrical measurement;
cable and PHY issues remain possible. No networking, DHCP or HTTPS success.
Do not rerun or unload the applied overlay. Persistent boot remains bad v4;
this session used the v6 RAM correction. No reboot requested.

Next: preserve the checked courier directory from /run to a fresh directory
under /root on the already verified Linux SSD root, then verify its manifest.
Do not overwrite an existing destination or touch daily macOS. Copy outcome
is pending. Subsequent engineering should audit the missing SN201202x SPMI
transport/PD integration, especially actual target IRQ mapping; upstream probe
issues a wake command and is not a read-only diagnostic.

## Immediate state

LATEST LIVE PHOTO: the runner reached the right-controller root hub
`/sys/devices/platform/soc/382280000.usb/xhci-hcd.0.auto/usb1` after loading
dependencies and all three candidate modules. User says phone is not charging
and tethering remains grey. No phone/interface/Internet proof yet. Photo shows
the script still waiting; final exit result pending.

Do NOT rerun or unload. Allow its bounded wait to finish, unplug/replug the
phone once, then request `dmesg | tail -n 30`. VBUS/role negotiation is suspected,
not confirmed. A powered hub or PD changes must not be assumed to solve it.
Remember the files remain under /run: preserve a verified copy on the guarded
Linux root before a future reboot if needed, never on the macOS partition.

LATEST: phone connected, tethering grey (controller not enabled yet). First
attended `minimal` test is being requested after save-work/hang warning:

```sh
sync && bash usb-tether-test.sh minimal
```

User should enable tethering as soon as available during the script's wait.
Allow up to about three minutes for host/interface/DHCP/HTTPS stages. Request
the output if it fails or stays grey; do not rerun/unload manually. This is an
explicit experimental hardware test under the user's ongoing USB bring-up
authorization, not proof that remaining physical SID/PHY/VBUS risks are solved.
No result has yet been received. Persistent v4 remains unchanged.

LATEST PHOTO: dry preflight PASSED, all five PMGR target/actual states ACTIVE;
diagnostic unloaded, no overlay applied. User is being asked to disconnect
the inter-Mac USB cable and connect an unlocked phone to the target's RIGHT
USB-C socket. No live/minimal command issued yet. Allow the phone tethering
toggle to remain grey until enumeration; do not interpret it alone as failure.

Exact-kernel source supports combining SID bits per DART (so the four overlay
references do not consume four DART slots), but physical SID routing, PHY
clear-mask behaviour and PD/VBUS remain experimental. Do not equate dry success
with full hardware validation. Save user work before a later live test, warn of
possible hang/power-cycle, and do not auto-retry/unload an applied overlay.

LATEST: user reports four checksum OK results, cwd is the courier directory.
Next explicit diagnostic-only command (trim output, retain full script log):

```sh
bash usb-tether-test.sh dry 2>&1 | tail -n 20
```

This loads/unloads only the dry diagnostic module and applies no overlay.
Inspect actual output; pipeline completion alone does not establish success.
Do not proceed to `minimal` without evaluating the PMGR result and outstanding
PHY/DART/VBUS audit risks. Dry result is not yet available.

LATEST PHOTO: KDE Konsole shows all five courier files at the correct path.
Delivery succeeded. Next target command (one line):

```sh
cd /run/azahi-usb-20260913 && sha256sum -c SHA256SUMS
```

Wait for four OK checks before considering diagnostic-only preflight. No USB
module load or network success yet. Do not reboot; persistent v4 is unchanged.

NEWEST: the user restarted into proxy, fresh session identity/RAM layout was
verified, and the guarded v6 RAM handoff completed successfully. All old payload
bytes were checked and all replacement bytes read back. Native desktop/courier
confirmation is pending; ask for `ls /run/azahi-usb-20260913` from KDE Konsole.
Proxy access was consumed by handoff. No native network transport is established.
Persistent v4 remains installed; permanent correction is still a separate task.

LATEST: courier v2/v6 built and tested in a no-disk/no-network ARM64 VM with
the actual initrd executables. Old failure reproduced; new courier and five
image checks pass. Target still running KDE from prior RAM boot, no new image
installed. `/run/initramfs` only held `log`, not the courier assets.
Next controlled shutdown/restart should reach existing v4 fallback proxy.
Read fresh identity/base/bootargs, verify old bundle and memory bounds before
any v6 RAM write. Permanent v4 replacement is still outstanding.

NEWEST PHOTO: `initrd-switch-root` journal reports the courier stopped at line11
because `mktemp` is absent. The hook did run. Fix/test the courier's early-boot
tool dependencies before building another candidate. Do not ask the user to
repeat the same log command; no new image or permanent fix has yet been installed.

LATEST: user reports KDE accessible but the courier directory cannot be
accessed from Konsole. Konsole is a valid target terminal. Host image inspection
finds the courier hook and assets present; inspect the current boot journal:

```sh
journalctl -b -u initrd-switch-root --no-pager -n 15
```

Do not treat the older listing request below as a successful result or ask for
a reboot merely to get a text terminal. The actual service output is pending.

A RAM-corrected v5 Linux handoff was sent. The target's current screen and the
presence of `/run/azahi-usb-20260913` are awaiting confirmation. Persistent v4
still fails the loader's initrd-size check. Do not ask for a casual reboot.
No native networking or SSH is established; host commands do not execute on
the target after the USB proxy is consumed by handoff.

Ask for this short target command, one line at a time:

```sh
ls /run/azahi-usb-20260913
```

Expected entries are `SHA256SUMS`, `usb-tether-test.sh`,
`phy-apple-t6050-usb2.ko`, `dwc3-apple-t6050.ko`, and
`azahi-usb-overlay.ko`. If available:

```sh
ls -lh /run/azahi-usb-20260913
```

Do not treat missing files as a reason to repartition or format anything.

## Hard boundaries

- The daily-driving macOS partition is out of bounds: no writes, repair,
  resizing, formatting, boot-policy changes or staging there.
- Public disk identifiers are intentionally invalid. Do not guess replacements
  or enable the historical root-write bounds on another disk.
- No automatic module loading, boot-image installation or firmware replacement.
  Recovery work needs exact target identification, a validated fresh backup,
  appropriate user authentication and verified readback.
- Do not restart the obsolete v4 delivery server or retry its installer.
- Do not unbind/unload DockChannel HID: its remove path contains `BUG_ON(1)`.
- Do not use random MMIO writes, NVMe reset/init, broad register scans or
  speculative power-control changes. Do not relax guards to make a test pass.
- When the user is absent, limit work to safe host-side development and offline
  tests. Persistence does not authorize autonomous power cycles or new risks.
- Webcam previously helped read the target screen, but the latest preference
  was **no webcam**. Use supplied photos; obtain renewed permission for capture.
  Never upload captures or images of the user.
- Prefer short commands and audio prompts when user interaction is needed.
  Never claim an audible prompt was heard merely because playback succeeded.

## Order of work

1. Confirm native boot and RAM courier delivery; verify file hashes.
2. Review/run diagnostic-only USB preflight on the verified private candidate.
3. Resolve hardware audit concerns before a live minimal host overlay test.
4. If the phone enumerates, prove an interface under the right USB controller,
   DHCP and interface-bound certificate-validated HTTPS. A root hub is not enough.
5. Separately replace the bad persistent boot bundle through the guarded private
   workflow. v3 is the known-working fallback; no corrected persistent install
   has yet been verified.
6. Wi-Fi, secondary CPUs and native GPU remain distinct research tasks.

## Public/private split

This repository is for reviewed source and progress, not target-specific
operational secrets. The full private workspace retains recovery receipts,
firmware and boot artifacts. Do not seek or publish the private identifiers in
order to make this reference snapshot immediately executable.
