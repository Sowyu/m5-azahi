# Handoff for the second Mac

## 2026-09-29 handoff: both Macs are available

Start here if you have no previous conversation or local project files.
This repository is an experimental Linux port for one M5 Pro MacBook.
The goal is usable Linux with all 18 cores. It currently has evidence for
only one working core. The user now has the target laptop and a second Mac
to control it. Work previously ran on a Debian home server without access
to either Mac.

The next milestone is attended validation of remote hardware reset and
serial capture, so a hung M5 no longer requires someone to hold its power
button. This takes priority over the older USB networking work below.
The second Mac's model, macOS version, connection and cable capabilities
have not been checked. Having both Macs does not establish working access.

### Get the right checkout

This handoff and the current work are on `audit-2026-09-25` in
[PR #5](https://github.com/Sowyu/m5-azahi/pull/5), not yet merged into `main`.
On the helper Mac, run these commands in a parent directory without an
existing `m5-azahi` directory:

```sh
git clone --branch audit-2026-09-25 --single-branch https://github.com/Sowyu/m5-azahi.git
cd m5-azahi
git status --short --branch
git rev-parse HEAD
```

If a checkout already exists, inspect its branch and changes before updating.
Do not reset, overwrite or discard it. Record the checked-out commit with
test results. Git may first request Apple's command-line developer tools;
finish that setup before retrying.

Give the agent on the helper this instruction:

> Continue the M5 Linux project from docs/HANDOFF.md on branch
> audit-2026-09-25. I have the target M5 Pro and a second Mac now. First
> identify the helper and establish macvdmtool serial/reset control. Follow
> the attended validation sequence before CPU-start experiments. You have
> no earlier chat context; use this repository and record new evidence.

The user authorized publishing this handoff and the accompanying research.
No new hardware operation has been performed by that publication. When the
user asks to continue on the helper, begin the session below. Older notes
saying the user is away or work is offline-only describe the previous
session; they do not override the new session's instructions. Preserve the
hardware recovery constraints. Keep updates brief and do not repeatedly ask
for permission to perform work the user already authorized.

### Project checkpoint

- Target: J714s / Mac17,9, M5 Pro / T6050, 18 physical cores. Last hardware
  evidence is the September 13 v7 SSD boot into KDE on
  `7.0.13-400.asahi.fc44.aarch64+16k`, with only CPU0 online. USB networking
  and remote access were disconnected; poweroff hung. Recheck current state.
- Repository: [Sowyu/m5-azahi](https://github.com/Sowyu/m5-azahi), branch
  `audit-2026-09-25`, [PR #5](https://github.com/Sowyu/m5-azahi/pull/5).
  The previous published checkpoint was
  `5a658b5627f3ad9839c208389883096d1972b2d6`; this handoff and the CPU trace
  follow it. Offline fixes and builds have not been installed on the M5.
- The current CPU research accompanies this handoff in
  [smp.md](audit-2026-09-25/smp.md) and
  [the offline journal](audit-2026-09-28.md). These files are in the public
  branch; no earlier chat or unpublished note is needed to read the findings.
- The public repository contains reviewed source and instructions, not a
  bootable installer. Private firmware, complete loader inputs, exact build
  fixtures and built artifacts remain on the home server. They are not
  needed to build macvdmtool and test the already installed boot. For later
  target builds, follow [BUILD-AND-TEST.md](BUILD-AND-TEST.md) and arrange
  private access to required inputs. Do not replace missing files with
  guessed fixtures or run historical installation commands blindly.
- Secondary cores previously showed powered-on status but no loader entry
  marker. Power status, compilation and CPU enumeration do not prove code
  execution. The missing ACC initialization is an untested lead, not a fix.

### First live session

1. Identify the helper Mac and establish access to it. It must be an Apple
   Silicon Mac running macOS for this tool. Start with `uname -m`,
   `sw_vers` and `sysctl -n hw.model` on the helper. The intended connection
   is home server to helper over SSH, then helper to M5 over USB-C. The
   helper needs its own network connection and must stay awake through a
   target reset. If the agent runs directly on the helper, SSH is optional.
2. Identify both machines' DFU/debug ports and connect them directly with a
   USB 3 capable USB-C cable for serial mode. Consult
   [Apple's current port table](https://support.apple.com/en-us/120694);
   do not apply the base M5 port rule to an M5 Pro. That table puts this
   target's port on the left side, nearest the hinge. These are port
   locations, not instructions to enter DFU or restore firmware.
3. Build [Asahi's macvdmtool](https://github.com/AsahiLinux/macvdmtool) on
   the helper with Xcode command-line tools and `make`. Use a separate
   checkout, not the incomplete loader tree in this repository. Record
   its commit. The helper runs macOS while the target keeps its Linux boot.
   Establish serial access with `sudo ./macvdmtool serial` and inspect the
   actual device nodes. The upstream README inconsistently spells its
   example serial path with a hyphen and an underscore; use the real node.
   Check whether the installed loader/kernel actually emits serial output.
   The current standalone image is not proven to expose an m1n1 proxy shell.
4. Save work and quiesce target writes before an attended reset. From the
   helper, the documented command is `sudo ./macvdmtool reboot serial`.
   Capture its output and fresh boot logs outside the target. Verify the
   correct Mac reset, the helper stayed reachable, and the known v7 boot
   returned. Use three attended normal resets as an initial repeatability
   check. A successful command exit alone is insufficient.
5. Validate recovery from a controlled hang only after normal resets work
   and a recoverable test environment is ready. Prefer an approved RAM
   experiment with storage idle. Record what was hung, what reset did, and
   whether boot and serial capture recovered. Check the CPU/reset baseline
   against a manual recovery before treating this as adequate recovery for
   SMP tests. USB-PD reset is not yet proven equivalent to a full power
   cycle for our failure. Stop after failed recovery instead of looping.

For step 3, run on the helper in a directory without an existing
`macvdmtool` checkout:

```sh
xcode-select -p
git clone https://github.com/AsahiLinux/macvdmtool.git
cd macvdmtool
git rev-parse HEAD
make
sudo ./macvdmtool serial
```

If developer tools are missing, use `xcode-select --install` and complete
the macOS installation prompt before building. The `serial` command sets
up the debug connection; the separate reset command in step 4 restarts the
target. Run reset commands from the helper, never from the Linux target.
The helper does not need this project's private boot artifacts or a fresh
Linux installation for the initial reset test. If the second Mac is Intel,
macvdmtool is not the documented host path; report that concrete mismatch
instead of treating it as an M5 failure.

Keep serial capture on the helper, separate from each experiment process.
After recovery is established, the intended loop is one hypothesis, bounded
test, saved logs, recorded result, reset and verified return to baseline.
Search previous results before retrying a hypothesis. Repeated normal boots
alone do not justify unattended CPU-start experiments.

Keep raw captures outside the public checkout. Record the helper model and
OS, tool and project commits, ports, cable type, commands, return status,
observed target boot, reset count and any manual intervention. Report
serial capture, normal reset and hang recovery separately as passed, failed
or untested. Publish only a sanitized result summary; a failed trial is a
result to preserve, not a reason to repeat the same loop indefinitely.

### CPU investigation to resume after reset recovery works

Read [the SMP investigation](audit-2026-09-25/smp.md) and
[the guarded startup notes](../smp/README.md) before making a candidate.
The latest static trace connects the real kernel `cpu_start` through IOPMGR
to the existing CPU_START sequence. The older proposal to skip a CPU_START
write was withdrawn.

The strongest remaining initialization difference is T6050 ACC restoration:
Apple's driver performs a write that the loader's T6050 cpufreq path skips.
Its purpose, live value and prerequisites remain unresolved. The detailed
mapping is in the investigation. Do not turn the address into a blind write
or enable older-chip frequency/voltage sequences.

Preserve `AZAHI_ONE_CORE`, reset-vector checks and timeout quarantine. The
old `azahi.smp=start` mode is refused intentionally. A new start experiment
requires a separately reviewed entry and one concrete hypothesis. Success
eventually requires each core entering the loader and all 18 executing
Linux work. The prepared `python3 smp/check-linux-cpus.py --run` checks
per-core execution once they are online; it does not bring cores online.

### Boundaries and supporting evidence

Keep v7 and its rollback artifacts. Preserve the daily macOS installation
and partition layout. No DFU restore, erase, repartition, blanket kernel
update or live USB/input driver unloading is part of this reset setup.
Follow the existing sleep precautions in
[daily-driver/README.md](../daily-driver/README.md). Never permanently
delete files; follow the current machine's recoverable Trash policy.
The server uses `trash-put`; do not assume a Debian command exists on macOS.
Identify the helper's recoverable Trash method before removing anything.
Keep serials, network addresses, logs, firmware and captures private.

[Cody Ho's firsthand development account](https://codyho.dev/blog/hypervisor-macbook-neo/#the-setup)
describes a Mac mini controlling a MacBook Neo with `macvdmtool`, timed
experiments and a persistent experiment log. It demonstrates the workflow,
not recovery from this M5 Pro's CPU-start failure. Use the
[upstream tool instructions](https://github.com/AsahiLinux/macvdmtool) for
commands and cable requirements. Both remain unverified on our two Macs.

The sections below preserve earlier hardware evidence and recovery details.
Their historical priorities are superseded by the two-Mac reset milestone
above. In particular, the old phone-based SSH connection is not a prerequisite
for establishing reset control from the helper.

## 2026-09-28 offline update

Read [the offline journal](audit-2026-09-28.md) for the newer source fixes,
tests and exact-kernel candidate builds. Source changes are collected in
[PR #5](https://github.com/Sowyu/m5-azahi/pull/5); build artifacts stay on the
home server. Nothing has been installed. Hardware state remains the
2026-09-13 checkpoint below.

The [phone cable fallback](../remote-access/PHONE-CABLE.md) now includes a
local offline ADB bundle and a tested protocol helper. It needs no tether
network interface, but requires USB enumeration and phone debugging
authorization. SSH uses a separate phone key. An optional Termux proxy can
carry laptop web traffic through the phone's internet connection. Both
hardware paths remain untested.

## 2026-09-25 offline update

Offline work only; the hardware state recorded below is unchanged since
2026-09-13. Before the next attended session, read
[the audit summary](audit-2026-09-25/README.md). Points that change what to
do on resumption:

1. On the running system, block sleep before any lid close: the installed
   NVMe build can lose its root disk across sleep. The exact commands, plus
   the other daily-use settings, are in
   [daily-driver/README.md](../daily-driver/README.md).
2. Nothing new is installed. Any rebuilt module or loader has new hashes, so
   the install-bundle pins must be regenerated first. The installer now also
   pins `start-native-usb.sh` and `azahi-usb.service`.
3. The cheapest new USB evidence is read-only: after the phone enumerates,
   read its `power/usb2_hardware_lpm` policy. This does not report actual L1
   activity or the policy of an earlier failed enumeration. See the `-71` hypothesis list in
   [kernel.md](audit-2026-09-25/kernel.md).
4. A wired USB Ethernet or USB Wi-Fi adapter removes the phone's function
   switching from the problem and would restore SSH; see
   [USB-NETWORK-ADAPTERS.md](USB-NETWORK-ADAPTERS.md).
5. Shutdown and PCIe/Wi-Fi each need a new image through Recovery, with v7
   kept as rollback. Test plans are in
   [tooling-loader.md](audit-2026-09-25/tooling-loader.md) and
   [pcie.md](audit-2026-09-25/pcie.md). Run them one at a time.

# USB tethering incident and resume handoff — 2026-09-13

## Read this first

**KDE boots from SSD, but USB internet is currently NOT working.**
Earlier successful tethering/SSH/HTTPS tests remain real historical evidence,
not proof that the current system is connected or reliable for travel.
The user requested documentation now; no additional hardware test or reboot
is being initiated as part of this handoff.

**Automatic USB startup was deliberately disabled for a diagnostic boot and
has not been restored.** A successful manual `systemctl start azahi-usb`
does not re-enable startup on the next boot. Do not lose this fact.

Latest evidence is a successful attached HPM diagnostic, not networking:
`result=0 ready=1 poisoned=0 state=0`, status `0x108280fd`,
power `0x0f0d`. The status/power values agree with the earlier successful
host/source observation. The data value wraps in the supplied photo and is
not used here as independently transcribed evidence.

## Scope, boundaries and user preferences

- Priority on resumption: reliable USB tethering, then shutdown. Native Wi-Fi,
  additional CPU cores, native GPU and native Codex setup remain later work.
- Never touch the daily macOS partition, repartition, resize, format, or
  assume a Recovery disk number identifies the approved Linux Preboot.
- Do not unload the live USB overlay, PHY, DWC3 or input transport. A prior
  DWC3 unload/reload ended in controller reset timeout; live input removal
  also has a known dangerous path.
- Do not bypass HPM poison/refusal guards, force electrical power, or issue
  speculative PD role tasks. Never interpret module-load success as working
  controller probe, enumeration, networking, or successful shutdown.
- Avoid repeated identical reboot/cable/tether-toggle instructions. The user
  tried another Thunderbolt 4 cable with the same behavior. A cable defect
  has not been demonstrated; another equivalent cable test is not next.
- Do not use the user's name. Use a short notification sound when stopping
  or requesting physical assistance; no text-to-speech.
- User-supplied screenshots are diagnostic evidence, not publishable assets.
  Earlier webcam permission does not authorize publishing captures. Honor any
  current restrictions on webcam use.
- Never publish photos, phone serials, credentials, private paths, raw device
  dumps, enrollment receipts, recovery material or private Git backups.
- Do not upgrade the kernel or core runtime as an incidental dependency fix.

## Installed system and changes actually made

| Component | State / evidence |
| --- | --- |
| Machine | J714s / Mac17,9, Apple M5 Pro / T6050 |
| Kernel | Exact `7.0.13-400.asahi.fc44.aarch64+16k` |
| Boot | Installed v7 standalone SSD-root image; earlier cold boot verified |
| Desktop | KDE, software rendering, one CPU online |
| Display | v7 full 3024x1964 at 60 Hz; user confirmed 175% scaling |
| Settings | SSD-backed `/root/.config/azahi-kde`; empty-session login configured |
| USB | Right socket, experimental USB2 host-only stack |
| Network | Latest `nmcli` only `lo`; IPv4 routing table empty |
| Phone | Nothing Phone 3a Pro; USB tethering visibly selected |
| Remote access | Previously installed dedicated SSH/tunnel/profile; last host check connection refused |
| Shutdown | Still hangs at final poweroff target on reported attempts |
| Wi-Fi / GPU / SMP | Not working / unresolved |
| Native Codex CLI | Not installed or verified |

Installed v7 image SHA256:
`2eaea0bc1503c2ac74a1b11dbb88423675f324a61db3da6db1aa88392672f5ba`,
size 92651520 bytes. The earlier working v6 rollback SHA256 is
`324822de14a43ab164d0ec6257d50d9dd6be1b17fd063faf24b0d571e41096ee`.
Hashes identify private preserved artifacts; they are not public downloads.

Native USB files are under `/opt/azahi-usb`. Older manual test files also
exist under `/root/usb-candidate`; do not assume these bundles are identical.
The saved NetworkManager connection is `azahi-usb-tether`, originally on
`enu1`. A profile cannot create a missing USB network interface.

Changes in this diagnostic sequence:

1. Root-hub `power/control=on` was tested on both USB root hubs in an earlier
   boot. It did not restore connectivity. These writes were boot-local.
2. `systemctl disable azahi-usb` was instructed and the user returned from
   the diagnostic reboot. Automatic startup has not been re-enabled or
   independently rechecked since. Treat it as disabled until verified.
3. In subsequent boots the user manually loaded the HPM helper in
   `mode=awake`, then started the USB service.
4. Only the healthy HPM diagnostic helper was later unloaded/reloaded in
   `mode=probe` to obtain fresh attached-state information.
5. USB debugging was instructed temporarily OFF on the phone. The subsequent
   interface changed from ADB to Imaging, but the exact phone toggle history
   was not independently captured. Do not assume all developer options were
   changed, or blame them for the initial failure.
6. No new driver, boot image, NetworkManager profile or package was installed
   during these latest screenshot-driven tests. No macOS storage change.

## Earlier verified success

The original right-port USB modules plus guarded HPM wake produced a USB
network interface. DHCP, external DNS/ping and Firefox worked. An initial
certificate error was traced to the wrong system date; after chronyd and
clock correction, interface-bound HTTPS succeeded with verification enabled.
Do not disable TLS verification as a networking workaround.

Dedicated pinned-key native SSH and reverse-tunnel services were then
installed and tested. A v6 cold boot, and later one v7 cold boot, reached KDE
and re-established USB networking/SSH without a new proxy payload.
The v7 test also verified the full-height display and persisted scale.
These are individual successful tests, not endurance/hotplug guarantees.

## Detailed failure/test chronology

1. **Regression after reboot/reconnect.** User reported no websites. Linux
   showed only loopback and no IPv4 route. Service restart returned quietly,
   and charging/tether-toggle availability varied.
2. **Initial enumeration failure.** Logs showed xHCI root hubs, successful
   phone descriptor reads, then `can't set config #1, error -71`, hub port
   disabled/re-enabled and disconnect/re-enumeration. USB error -71 is a
   protocol error, not proof that the cable, EMI or any one component is the
   cause. The hub's “EMI?” wording is not a diagnosis.
3. **Only root hubs at another snapshot.** USB sysfs contained just
   `1-0:1.0 2-0:1.0 usb1 usb2`; no phone node and no USB network device.
   Changing NetworkManager settings could not fix that state.
4. **Runtime PM experiment.** USB2 root-hub runtime status was suspended.
   Writing `on` to usb1 and then usb2 power/control did not restore the
   phone. Post-write runtime status was not captured. Suspension could have
   resulted from an empty bus; it was not established as the cause.
5. **Alternate cable.** Thunderbolt 4 cable gave the same behavior. Stop
   repeating cable tests without a materially different hypothesis.
6. **Delayed host-start experiment.** Automatic USB startup was disabled.
   After a cold boot with no phone, HPM awake returned result0/ready1/
   poisoned0. The phone was attached before manual USB-controller startup.
   This order resembled the earlier manual success but did NOT restore
   networking.
7. **Fresh delayed-start log.** Host mode up at approximately 205.110s;
   phone descriptors at 205.471s; configuration error -71 and disconnect.
   Another detection at 531.034s again failed configuration, followed by
   device-number4 at 531.508s. Therefore later detection events did occur:
   it is wrong to claim reconnect interrupts were completely dead.
8. **ADB-only device.** `lsusb -t` showed device4/interface0 at 480M,
   vendor-specific class, no kernel driver. Descriptor inspection gave
   class255/subclass66/protocol1, two endpoints: ADB, not NCM/RNDIS.
   VID/PID was `18d1:4e11`. The same command also reported device-status
   EAGAIN(11) and an interface-string error, so cached descriptors did not
   establish a healthy live link. Do not force-bind a network driver to ADB.
9. **Phone tether off/on.** A single toggle without unplugging was requested.
   A repeated identical photo did not independently confirm its outcome.
   A later fresh descriptor photo confirmed ADB-only at that point.
10. **Phone debugging isolation and user reboot.** Temporarily disabling
    USB debugging, then selecting tethering, was requested. User rebooted
    Linux on their own hunch. Charging/USB did not start automatically;
    startup was still disabled. The manual HPM/service sequence was given,
    and user reported no network.
11. **Latest boot, fresh Linux evidence.** HPM awake at about 85s:
    result0/ready1/poisoned0/state0, disconnected status0x10000000,
    power0/data0. Manual USB service start returned without an error.
    xHCI host mode up at 124.276s; phone descriptors at 124.639s.
    `lsusb -t` showed device2/interface0, **Imaging**, no kernel driver,
    480M. VID/PID now `18d1:4ee1`. No -71 or disconnect appeared in the
    displayed current tail; this does not prove no error elsewhere.
    The later Apple MTP RTKit oslog is not itself a phone USB error.
12. **Phone UI verified.** USB tethering was visibly selected, while
    “USB controlled by: This device” was selected and “Connected device”
    said “Couldn't switch.” The charge-connected-device option was off,
    and the phone battery icon indicated charging. Do not keep telling the
    user to choose tethering as though they had not already done so.
13. **Fresh attached HPM probe — latest result.** Only the healthy helper
    was refreshed with `mode=probe`. At about 630s it returned
    result0/ready1/poisoned0/state0, status0x108280fd, power0xf0d.
    Under the pinned driver's status definitions, plug-present, source and
    host bits are set. These match the earlier successful status/power
    values, despite the phone UI's apparent role disagreement. No network
    verification followed; the user asked for documentation.

Some photos were reused. Above, repeated images are explicitly separated
from fresh logs and user-reported outcomes. Timestamps are boot-relative,
not a continuous wall-clock sequence across reboots.

## Interpretation: what is known versus still hypothetical

Established:

- At least some attempts enumerate phone descriptors, and some expose an
  actual USB interface. “USB is completely dead” is too broad.
- The latest observed interface is Imaging, not a network function.
- Phone UI requests tethering; Linux's recorded interface does not match.
- HPM wake and the latest attached diagnostic succeeded without a reported
  transport poison. Matching HPM status does not guarantee data-plane health.
- No current network interface means DHCP/DNS/profile changes are premature.

Unproven:

- Exact cause of the earlier -71 configuration transfers.
- Whether phone UI/HAL state, role negotiation, stale USB function state,
  eUSB2 repeater synchronization, controller lifecycle or more than one
  issue explains the differing snapshots.
- Whether a USB-A intermediary would avoid problematic USB-C role changes.
  It has not been tested, availability is not confirmed, and no purchase or
  guaranteed workaround has been recommended.
- Whether a phone-only restart would help. It has not been established as
  a fix and must not become another blind reset loop.

Do not request a power/data-role swap merely because the phone UI says
“Couldn't switch”: the latest laptop-side status already reports host/source.
Reconcile the disagreement before forcing a change.

## Source findings and PR review

- [PR4 USB](https://github.com/Sowyu/m5-azahi/pull/4), head
  `6d43d571d122bb389218110edea960718fd88e40`: fully read, including the
  diagnostic note; no newer commits/comments/reviews at last check.
  Adds startup stage/error diagnostics and treats some network modules as
  optional. Ten mocked startup tests passed in an isolated private copy.
  It does not implement hotplug/PHY reset or solve the current interface
  mismatch. Its no-charging diagnosis describes older v6 evidence.
- Existing Apple glue explicitly documents coordinated PHY/DWC3 lifecycle
  around CC attach/detach and repeater resets. Forced-host mode bypasses
  the normal role-switch source. This is a real limitation, not proof of
  the exact current failure.
- Exact DWC3 core initializes PHYs, performs core soft reset, then powers
  PHYs on. This custom PHY has no init callback; hardware initialization
  is in power_on, and power_off gates clocks/asserts reset. This is a
  plausible explanation for the earlier reload -110, not a verified fix.
  Do not skip core reset or change live register ordering on this basis alone.
- Glue calls initial USB2 set_mode before handles are acquired; provider
  deliberately defaults to HOST. The null initial call is not by itself a
  demonstrated cause of -71.
- [PR3 shutdown](https://github.com/Sowyu/m5-azahi/pull/3), head
  `a873059167b7ddf0946151b7f0c62d2188088444`: proposed module loading is
  insufficient against the exact Fedora source patch, whose reboot-driver
  probe rejects devices without an OF node. Current SMC DT lacks a reboot
  child. Optional shutdown_flag behavior also needs verification; it may
  affect poweroff versus restart. No shutdown fix installed.
- [PR2 trackpad](https://github.com/Sowyu/m5-azahi/pull/2), head
  `921db7bb0a7bd814f53e9c677ef6494417801b47`: noted, not reviewed.
- [PR1 audit](https://github.com/Sowyu/m5-azahi/pull/1): relevant USB
  sections reviewed. Findings are hypotheses until validated; not all 300
  claims are confirmed. Previously confirmed input bounds/rearm fixes are
  built/tested but NOT installed. Do not use the proposed ACK mutex fix
  that conflicts with the sender's wait while holding that mutex.
- PR2/3/4 branch ancestry predates the privacy history rewrite. Do not merge
  those histories into cleaned main. Review tip changes in private and
  reapply only reviewed/redacted changes to clean ancestry with attribution.
  No PR was merged or externally commented on during these latest tests.

## Helper and service semantics that matter

`start-native-usb.sh` checks exact kernel/model/Linux root and bundle hashes.
With all three USB modules already loaded plus a right-port root hub, it
preserves them and returns USB_ALREADY_READY. This is NOT a hotplug repair
or proof of a phone/network connection. Partial load is deliberately refused.

HPM modes:

- `status`: controller power and FIFO inspection; no logical HPM snapshot.
- `probe`: bus WAKEUP plus logical selector/read transactions; not electrically
  read-only, but does not issue SSPS or power/data-role swap tasks.
- `awake`: additionally permits the tightly guarded SSPS(S0) task only from
  the known disconnected state-7 tuple. It is not a generic recovery switch.

Transport/ambiguous task failures latch and pin the helper. Do not unload
or retry a poisoned instance, drain/reset queues, or remove its protections.
The most recent refresh was of this healthy diagnostic helper only; that
does not authorize live USB/PHY/DWC3 removal.

## Resume and completion criteria

1. Preserve the current Linux session and phone state. Confirm the user is
   ready before any physical action; documentation request paused testing.
2. Read this latest section before historical “verified” checkpoints.
   Do not request all already-recorded screenshots again.
3. Last native reverse SSH attempt was refused. Check the private controller
   handoff for pinned access details if access becomes available; do not
   claim direct access exists just because SSH services were installed.
4. Focus on current phone function/role disagreement using existing evidence.
   No validated next driver patch or role-swap command has been prepared.
   Any new experiment must state its hypothesis, expected observation and
   rollback rather than repeating known-failed initialization.
5. Before declaring recovery, verify USB network-class binding, real network
   interface, DHCP/default route, DNS, synchronized time and certificate-
   validated HTTPS through that interface. Use bounded requests.
6. Then verify repeated connection/boot behavior, preserve logs privately,
   and explicitly decide whether to restore or replace automatic USB startup.
   `systemctl enable azahi-usb` restores the old boot enablement but does
   not fix its reliability; do not run it now as a networking repair.
7. Confirm dedicated SSH access works, so future work avoids manual typing.
   Native Codex still needs installation and authentication after networking.
8. Shutdown remains separate. `sync` flushes filesystem writes; it does not
   implement hardware poweroff or prove subsequent shutdown cannot hang.
   Reaching poweroff.target alone is not proof every kernel shutdown callback
   finished or a guarantee a hard power cut is safe.

## Primary references

- [Exact ADB interface identifiers in AOSP](https://android.googlesource.com/platform/system/core/+/android10-release/adb/adb.h).
- [AOSP USB data-role preference controller](https://android.googlesource.com/platform/packages/apps/Settings/+/main/src/com/android/settings/connecteddevice/usb/UsbDetailsDataRoleController.java).
- [Linux USB error codes](https://docs.kernel.org/driver-api/usb/error-codes.html).
- [Linux USB power management](https://docs.kernel.org/driver-api/usb/power-management.html).

Detailed local source paths: `usb-driver/start-native-usb.sh`,
`usb-driver/azahi-usb.service`, `usb-driver/dwc3-apple-t6050.c`,
`usb-driver/phy-apple-t6050-usb2.c`,
`usb-driver/pd-backport/hpm-once.c`, `hpm-awake.h` and the pinned tipd
headers under that directory. Exact kernel/build/private fixture locations
remain in the private workspace and are intentionally absent from public
reproduction claims.


---

The remainder is historical. Its earlier successful-boot descriptions do
not override the current disconnected state above.

## Historical baseline: v7 cold boot verified; audit repairs in progress

At this earlier checkpoint, one v7 cold
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

## Earlier: v7 full-height candidate installed; first cold boot pending

Fresh backup confirmed the selected working v6 image before installation.
Recovery installation readback now matches v7 SHA256
2eaea0bc1503c2ac74a1b11dbb88423675f324a61db3da6db1aa88392672f5ba,
size92651520, raw entry2048. v6 is preserved as rollback. This supersedes
the not-installed state below, but NOT the hardware-test warning: no v7
Linux boot/display result yet. Next boot with every USB-C socket empty;
connect phone after KDE loads. Check full display mode, settings persistence,
USB/SSH/HTTPS before declaring success. Private recovery server remains up.

## Earlier: opt-in full-height framebuffer candidate built, NOT installed

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

## Earlier: persistent KDE preferences configured, reboot test pending

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

## Older checkpoints

The checkpoints from the v6 SSD cold-boot verification back to the first
native USB inventory are kept once, in [PROGRESS.md](../PROGRESS.md) under
"Historical checkpoints". Until 2026-09-25 they were duplicated here
verbatim.

## Earlier immediate state (superseded)

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

## Earlier order of work (superseded)

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
