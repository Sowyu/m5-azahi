# Progress — 2026-09-13

## Latest: native HPM wake works; DWC3 live reload fails with -110

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

This is the public, privacy-reviewed checkpoint. Historical private notes may
contain superseded plans; the state below takes precedence.

## Latest user report and expanded publication

FIRST LIVE RESULT: user photo shows all stock dependency loads and the three
candidate insmod commands completing, followed by the expected right-controller
root-hub path under `382280000.usb/xhci-hcd.0.auto/usb1`. The live host test has
therefore reached a right-port root hub. It has not established phone enumeration,
a network interface, DHCP or HTTPS. The photo was taken while the script waited.

User reports the Nothing Phone 3a Pro still has tethering greyed out and is not
charging. VBUS/Type-C role negotiation is a leading hypothesis, not a measured
diagnosis; cable/PHY problems remain possible. No reboot, unload or retry.
Let the bounded wait end, try one phone unplug/replug, then inspect the newest
kernel messages. An applied overlay may now be pinned; preserve the running
session. No automatic rollback/unload is safe here.

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
