# Unattended long-running networking task — agent handoff, 2026-09-12

## Read this first

Latest user instruction supersedes the earlier stop-and-document instruction
for the **receiving agent**: make this a long-running task while the user is
out shopping and watching movies today. **No questions, no reboot/power cycles,
and keep working until the goal is reached.** Do not wait for another “continue”
once assigned this handoff. The authoring turn only updates documentation;
it does not itself launch a background run or another agent.

## Unattended execution contract — highest-priority handoff instructions

**Goal:** get usable networking on the existing native SSD Linux/KDE setup,
prioritising USB tethering with the Nothing Phone (3a) Pro. Preserve autonomous
KDE boot, input functionality and the daily-driving macOS partition. Built-in
Wi-Fi is the preferred eventual destination, but is not a prerequisite for
the immediate tethering goal. SMP/native GPU are not this run's scope.

**Completion requires target evidence:** a real non-loopback interface,
successful address/route configuration, DNS resolution and outbound HTTPS
from native Linux, with a documented repeatable connection procedure. No
reboot test is allowed during this run. Explicitly leave reconnect/reboot
persistence unverified unless observed without violating that restriction.
A compiled module, static test pass or xHCI root hub alone is NOT completion.

- Work autonomously and persistently. Continue through research, implementation,
  builds, tests, debugging and documentation without asking the user to choose
  routine options. Do not end at a plan, first failed build, or partial milestone
  while meaningful safe in-scope work remains. Use the runtime's supported
  long-running task/goal mechanism if available; no invented background promise.
- **No questions or requests for user action while they are away.** Do not ask
  for passwords, typing, photos, phone settings, cable moves or approvals.
  Non-blocking written progress notes are fine; they must not need a reply.
- **No reboot, shutdown, forced poweroff, recovery/proxy transition, bootloader
  enrollment or cold-boot cycles.** This applies to agent-operated actions too,
  not just requests to the user. Do not use audio to summon physical help.
- Do not simulate permission by interpreting “do anything” or “don't stop” as
  authority to bypass the storage, firmware, MMIO or recovery safeguards below.
  Do not load an experimental driver that could strand this SSD-root session
  with no attended recovery. Do not alter the working enrolled boot image.
- First use saved artifacts and any already-established safe transport. **At
  handoff there is no established native shell/network transport.** Do not
  assume one appeared or claim local host commands ran on the target. A newly
  discovered transport must be verified and within existing authority.
- If live testing cannot proceed without physical intervention, keep doing
  all useful independent work: exact M5 RE, upstream/backport review, isolated
  module builds, offline DT validation, dependency/symbol checks, regression
  tests, and a staged delivery/rollback package. Prepare future attended steps
  in documentation; do not execute them or request attendance today.
- Avoid endless repeated searches or busy polling to appear persistent. When
  every meaningful safe alternative is exhausted and target completion truly
  requires unavailable access or a forbidden cycle, **record the exact blocker
  and leave the goal incomplete, never report success**. Follow the runtime's
  blocked-goal rules if using that mechanism. Do not ask a question to unblock
  it during the unattended period. Persistence cannot create missing access.
- Save incremental progress and reproduction commands in this handoff and
  NETWORK-CHECKPOINT so context loss does not restart the investigation.

The user explicitly wants sustained work, not repeated handoffs. An unavoidable
access/safety blocker is the only non-completion exception after exhausting
safe work; a routine failed test is a reason to debug and continue.

Immediately preceding task: user approved prioritising USB tethering with
their **Nothing Phone (3a) Pro**. Built-in Wi-Fi remains their preference,
but no supported Apple N1 driver was established. They leave for Japan in
about a day and want a usable, independently bootable development laptop.
Do not repeat the fixture question or ask whether tethering is acceptable.

Workspace: `/PRIVATE-USER/azahi-port`, macOS host, zsh. Target is M5 Pro
Mac17,9 / J714sAP / T6050 / board 8, 18 cores, 64GB. Current native Linux
kernel: `7.0.13-400.asahi.fc44.aarch64+16k`.

## Non-negotiable boundaries

- **No commits, no upstream submissions.** Preserve existing work.
- **CRITICAL: daily-driving macOS partition 2 is out of bounds for writes.**
  This overrides urgency, convenience and “do anything/don't stop”. Do not
  mount it read-write, resize, format, repair, restore, erase or use it for
  staging. Do not change its files, APFS container/volumes, boot policy,
  Preboot or Recovery assets. Do not issue whole-disk writes or partition-table
  changes that could affect it. Do not select a disk by a guessed /dev name;
  verify exact identities and ranges below before any permitted storage action.
  A Linux-looking label is not sufficient identification. If identity/scope
  is uncertain, do not write; continue safe offline work without asking the
  absent user. Existing Linux rootguard must remain intact. Linux-paired APFS
  is distinct from daily macOS, but boot enrollment/transitions are still
  forbidden during this unattended run. No shortcut may weaken this boundary.
- User does not want their name used. Manual typing/reboots have been very
  exhausting; batch verified instructions and establish transport if possible.
- Prior audio preference: `/usr/bin/say -a 95 'short message'` (default output
  previously inaudible). During this unattended run do not summon the user or
  request physical actions; the no-interruption/no-cycle contract above wins.
- **Webcam use is important and explicitly, absolutely OK with the user.**
  Use the host webcam proactively to observe the facing target laptop's actual
  screen, identify its current mode, read errors and verify visible outcomes.
  Do not ask permission again or ask the user to take a photo. Inspect a frame
  at the start of a resumed live session and after meaningful observable state
  changes; do not repeatedly photograph an unchanged screen just to stay busy.
  Available capture: `/opt/homebrew/bin/imagesnap -w 1 logs/UNIQUE-NAME.jpg`,
  then inspect the resulting image with view_image. Use unique filenames.
  Keep captures focused on the target screen; avoid password entry, faces and
  unrelated private material. Earlier requested face photos were moved to Trash;
  permission to inspect the screen does not undo that privacy preference.
  If framing is unusable, record the limitation and continue offline rather
  than summoning the user. Webcam observation is not a keyboard/control or
  network transport, and cannot prove a command executed unless visible.
- No agents/delegation unless user or applicable instructions explicitly asks.
- Use apply_patch for edits. Do not set sandbox_permissions (approval never).
- `m1n1/AGENTS.md` forbids AI work. Prior user override applies only to private
  isolated `standalone-loader/m1n1-20260911`, not original `m1n1/`.
- No random MMIO, ANS/NVMe resets, `get_gigalocker`, legacy NVMe init,
  macvdmtool reset, guessed PHY compatible, or SMC blacklist changes.
- **Do not unload/unbind dockchannel transport:** its remove has BUG_ON(1).
- Saved ioreg/ADT contain private data. Only print allowlisted hardware fields;
  never dump broad ioreg (user/session IDs, MAC addresses, serials, etc.).

## Known-working target state to preserve

### Recommended mode during today's no-cycle absence

**Leave the currently working native Linux/KDE session running.** A visible
terminal is useful for screen observation if already available; no user action
is required by this note. Keep the facing webcam arrangement available. Do not
replace the working autonomous boot with proxy merely to increase access.

Proxy is useful for low-level bringup because it exposes a host control path,
but it is not an always-on native Linux shell. Existing native handoff loses
the proxy, and a crash may require a physical cycle; therefore proxy alone
cannot promise unattended repeated native tests. The enrolled image currently
boots autonomous Linux, not proxy: restoring V5 would be a boot change and
sacrifice autonomous boot until restored. That is not allowed today.

If the initial webcam unexpectedly shows **Running proxy already**, do not
assume the saved KDE state is current or change modes to match these notes.
Record the observed state and use only reviewed safe operations compatible
with the no-cycle/storage contract. No blind startup script or native handoff
that consumes the only control channel without a safe recovery path.

With KDE running there is still no established remote native shell/network;
expect offline RE/build work to be the immediately available route. Do not
promise end-to-end hardware completion from webcam access alone. Proxy may be
a better fixture for a future attended diagnostic session, not a requirement
or a safe unattended-reboot workaround for this run.

User reported automatic SSD boot directly into KDE after the launcher repair:
“it booted straight into kde yayy”. The earlier clean-config runtime test was
“holy crap soo much more responsive”; webcam showed wallpaper/panel/Konsole.
First post-repair boot passed per user, not sustained reliability proof.
No host-supplied payload was used for that boot. Host cable disconnection was
instructed but not independently observed.

- **One CPU, software graphics**; not SMP/native GPU success.
- Built-in keyboard/trackpad usable after compositor repair; no new input
  driver fix in these networking turns. Underlying input/suspend stability
  not established.
- Last native interface check showed **only lo**. No SSH or native remote shell.
- Installed minimal DT has no native USB/PCIe/Wi-Fi controller nodes.
- **Poweroff hangs at reached target poweroff.target**; user then long-presses.
  Do not claim that message proves filesystems are flushed/unmounted or hard
  poweroff safe. Cause not diagnosed; preserve macsmc power blacklists.
- Root password was set privately by user; unknown to agent.
- Root tty1 auto-login starts KDE after a 5-second countdown; Ctrl+C during
  countdown can get shell. Do not reuse old KWin PID2238 or stale tty numbers.

Installed `/usr/local/bin/basic-kde-session` now matches reference
`probe/native-kde-clean-session-20260912.sh` in behaviour:

```sh
#!/bin/sh
set -eu
export HOME=/root USER=root LOGNAME=root SHELL=/bin/bash
cd /root
export XDG_RUNTIME_DIR=/run/user/0 XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe LP_NUM_THREADS=1
export QT_QUICK_BACKEND=software KWIN_COMPOSE=Q KWIN_FORCE_SW_CURSOR=1
export QT_QPA_PLATFORM=wayland
export XDG_CONFIG_HOME=/root/kde-good
unset DBUS_SESSION_BUS_ADDRESS DISPLAY WAYLAND_DISPLAY
exec dbus-run-session kwin_wayland --drm --no-lockscreen \
  -- "plasmashell --no-respawn" konsole
```

Working config saved at `/root/kde-good`; original config preserved. Previous
launcher backed up in unique `/root/kde-backup.XXXXXX`, exact random suffix
not confidently read. Old shell variables `b`/`k` do not survive reboot.
Installed file comparison and sync photographed in
`logs/native-kde-clean-installed-20260912.jpg`.
Parent `/usr/local/bin/native-ssd-kde-start` retains Btrfs root UUID guard,
disables selected KDE plugins, logs to `/run/native-ssd-kde.log`.
“USB-loaded kernel” text in wrapper is stale, not actual boot dependency.
Full regression history: `probe/native-kde-regression-20260912.md`.

## What changed in the interrupted USB turn

**Host-only changes, no target connection, MMIO, driver load, boot-image edit,
installation or reboot. No USB candidate has been built. No tether test.**

1. Read current network checkpoint, cross-build recipe, existing DT and stock
   DWC3 glue; reviewed pinned online USB/PD sources below.
2. Extended `probe/inspect-kernelcache.py` with repeatable `--entry` for exact
   Mach-O fileset selection. Providing it REPLACES default entry list; missing
   entries now cause argparse error. Defaults remain kernel, ARMPlatform,
   PMGR, T6050PMGR. No firmware execution. SHA256 after change:
   `0bb1d0e48d0b5f41f0c0d4bfeb470e23ab87112c6ac9fb5c6d29eedeb988e539`.
3. Earlier CPU disassembly venv `/tmp/azahi-cpu-disasm.zPmZfJ` no longer exists.
   Created **`/tmp/azahi-usb-disasm.G380qX`**, installed Capstone **5.0.9**.
   New exact-entry symbols-only invocation completed successfully. No unit
   tests added for this small inspector extension; full M5 disassembly not
   yet performed. Temp environment may disappear; recreate with mktemp+venv.
4. User stopped while the install/symbol command was running. Collected its
   completed exit-0 result for handoff. Exec sessions **36414 and 64180 are
   complete**; no pending task build/inspection process remains from this turn.
   Older receipt receiver might still be alive; see below, not task-active.

Existing networking artifacts from prior turn:

- `probe/network-hardware-audit.py`: read-only saved ADT + allowlisted PCI IDs.
  SHA256 `be7fc64a1c7fd494cf7774f974a9be3ec777fc27ed342f0a9bb3b0f900adb9d6`.
- `probe/test-network-hardware-audit.py`: **8 tests previously passed** (board
  linkage, wrong board/PHY/mapper/vendor, missing endpoint, privacy exclusion).
  SHA256 `2415e7eb564f9815809aa0c51fc4e2da7a96df6ce32f6f4b8c88ac86618119e9`.
- `probe/NETWORK-CHECKPOINT.md`: detailed inventory and source conclusions.
  Audit tests were not rerun after stop; no audit implementation edits this turn.

## New M5-specific RE foothold (not a verified init sequence)

Existing `probe/firmware-analysis/kernelcache.mac17j.macho` contains:

| Fileset | VA | fileset offset |
| --- | --- | --- |
| com.apple.driver.AppleTypeCPhy | fffffe0007714580 | 710580 |
| com.apple.driver.AppleT6050TypeCPhy | fffffe0007717620 | 713620 |
| com.apple.driver.AppleSPMI | fffffe00075dfb60 | 5dbb60 |
| com.apple.driver.usb.AppleSynopsysUSB40XHCI | fffffe0007aed330 | ae9330 |
| com.apple.driver.usb.AppleSynopsysUSBXHCI | fffffe0007afcf90 | af8f90 |

Symbols successfully located:

| Exact symbol | VA |
| --- | --- |
| __ZN18AppleT6050TypeCPhy13eusb2phy_initEbb | fffffe0009a3b744 |
| __ZN18AppleT6050TypeCPhy17eusb2phy_shutdownEv | fffffe0009a3ce54 |
| __ZN18AppleT6050TypeCPhy16usb2PhyPortResetEP22AppleTypeCPhyInterfaceb | fffffe0009a3d780 |
| __ZN18AppleT6050TypeCPhy18eusb2phy_s2r_enterEb | fffffe0009a3dcb8 |
| __ZN18AppleT6050TypeCPhy17eusb2phy_s2r_exitEb | fffffe0009a3dfd0 |
| __ZN18AppleT6050TypeCPhy8initUSB2Ej | fffffe0009a76e98 |

Successful command used (symbols only):

```sh
/tmp/azahi-usb-disasm.G380qX/bin/python probe/inspect-kernelcache.py \
  probe/firmware-analysis/kernelcache.mac17j.macho \
  --entry com.apple.driver.AppleT6050TypeCPhy \
  --entry com.apple.driver.AppleTypeCPhy \
  --symbol 'eusb|usb2|USB2' --symbols-only
```

On resume, use anchored exact method regex to exclude similarly named log
strings. Increase --size for full function, default is only 0x180. Inspector
caps at next selected-entry symbol; verify function boundaries before treating
output as complete. Need prove register-bank mapping in M5 start(), actual
host caller mode, ordered RMWs/delays, reset/shutdown and role interactions.
**No claim M4 sequence matches M5 yet.**

## USB path and pinned sources

Target config enables stock DWC3/DWC3_APPLE, XHCI, APPLE_DART, SPMI_APPLE,
PHY_APPLE_ATC, TYPEC_TPS6598X and RNDIS/CDC Ethernet modules. Config does not
prove all .ko files are installed. It lacks PHY_APPLE_T6040_USB2 and
TYPEC_SN201202X. USB host tether needs controller + PHY + DART + clocks/reset
+ Type-C/PD/VBUS + network driver, not just `modprobe rndis_host`.

Stock full glue read from `input-driver/build/srpm/linux-7.0.13.tar.xz`,
`linux-7.0.13/drivers/usb/dwc3/dwc3-apple.c`:

- Only compatible apple,t8103-dwc3; exclusive reset asserted during probe.
- Resource names dwc3-core and dwc3-apple; waits PROBE_PENDING for role event.
- Calls USB2 phy_set_mode before initial core probe has populated PHY pointer;
  experimental M4 provider defaults HOST to cover initial power_on ordering.
- No force-host/device property in stock. M4 force-host patch depends on an
  earlier force-device fork; cannot apply alone.
- Normal glue writes Apple CIO tuning, switches modes and tears PHY/core down
  on disconnect. Comment documents eUSB repeater reset and possible watchdog
  resets if sequence wrong. Don't assume fixed-host reconnect is safe.

Asahi Linux pin **236788cd2602a24c703fe7bdaddaf73ef77d2027** (asahi-wip-7.2):

- New source is `drivers/usb/typec/tipd/spmi.c`, **NOT sn201202x.c** (404).
  Full spmi.c read this turn. Module built as sn201202x via Makefile; siblings
  core.c, i2c.c, tps6598x.h, trace.c/h. No files downloaded to workspace yet.
- [SPMI driver](https://github.com/AsahiLinux/linux/blob/236788cd2602a24c703fe7bdaddaf73ef77d2027/drivers/usb/typec/tipd/spmi.c):
  select-register uses SPMI zero-write + completion IRQ, then reads register0;
  data read window0x20/write0xa0, chunks <=16B, total <=0x40. Probe requests
  irq/select/sleep/wake, issues WAKEUP, then tipd_init. **Probe is not read-only.**
- [Binding](https://github.com/AsahiLinux/linux/blob/236788cd2602a24c703fe7bdaddaf73ef77d2027/Documentation/devicetree/bindings/usb/apple%2Csn201202x.yaml)
  compatible apple,sn201202x, SPMI USID, connector graph. Example selectIRQ13
  is not directly in M5 ADT's three-entry HPM list; derive, don't copy blindly.
- Backport core dependencies/API compatibility against 7.0.13 not assessed
  fully or built. New core has TYPEC_TPS6598X_CORE separate from transport.
- Existing atc.c supports t8103/t8122, not native T6040/T6050. No full drop-in
  M5 USB stack established in checked tree.

Wallace pin **2d0753bff8f02e89add2800b1a2019d0555100c8**:

- `patches/0001-phy-apple-add-experimental-T6040-USB2-only-slice.patch`:
  239-line experimental M4 host PHY, defaults HOST, no inverse power_off.
- `patches/t6040-dwc3-apple-force-host.patch`: depends on prior fork.
- `dts/t6040-j614s-dcuart-usb2-native-right.dts`: USB2 fixed-host only.
- `evidence/2026-08-19-t6040-usb2-v2phy-rerun-root-hubs-restored.md`:
  root hubs worked >=107s, **no child device/network success**, VBUS/fixture
  unresolved. M4 test did not bind NVMe; not proof safe with our SSD root.
- [M4 exact eUSB2 evidence](https://github.com/damsleth/wallace/blob/2d0753bff8f02e89add2800b1a2019d0555100c8/evidence/2026-07-24-t6040-eusb2-init-sequence.md):
  host false,false inputs; B0+8 separate set bits14,13,12,0,1; 10ms;
  B0+4 clear3; 10us; clear0 then1; B1+0 |=9; B0+4 set2;
  B0+1c clear29 then30; 30us; read B1+20; 5ms; B0+0 bits2:0=2.
  **These are M4 evidence only, not authorised M5 writes.**
- [VBUS gap/correction](https://github.com/damsleth/wallace/blob/2d0753bff8f02e89add2800b1a2019d0555100c8/evidence/2026-08-04-t6040-usb-vbus-gap-analysis.md):
  read correction! M4 uses SPMI SN201202x, not I2C CD321x. Self-powered phone
  alone doesn't bypass attach/VBUS requirements. New Asahi driver postdates
  that report's no-driver finding.
- [Yuka branch review](https://github.com/damsleth/wallace/blob/2d0753bff8f02e89add2800b1a2019d0555100c8/evidence/2026-07-29-t6040-yuka-usb-branch-review.md):
  t8122 PHY fallback known broken on T604x/CIO4. Wrong event bank and probe-time
  writes; don't add a compatible merely to see whether it probes.

## Exact saved M5 hardware / build route

See NETWORK-CHECKPOINT and audit for all three ports. Candidate ADT port3
(physical exterior socket not independently verified): USB core382280000
size11800, glue382200000 size4000, reg2 38228c000 size5800; PHY banks
382a90000/382800000 each4000; DART382f00000/382f80000 eachc000.
IRQs USB1483..1486,856; DART1487. Mapper SID1, vm-base10000004000,
sizeffff0000. Do not confuse with input MTP SID0. Extra DART regs shared,
not generic write targets. USBclock267; PHYclock586,61,268,246..249.
USB compatible usb-drd,t6050/t8142; PHY atc-phy,t6050/t6040.
SPMI HPM2 is under nub-spmi-a1, USID0xc, ADT IRQ11,17,19; other HPMs on a0.
No SPMI access done. Port3 PMGR61 common,266 AON,267 USB,268 PHYMXWRAP;
parent/reset relationships require proper review, not raw pokes.

Saved ADT `adt-real-t6050.bin` SHA256
`5a87c2ee23c945694303a4396fbbf197918220f87441a41505838a3c37277a24`.
Saved ioreg `adt-m5pro-mac17,9.plist` SHA256
`82f39f12aac5806de5f60daa0c17007223ca8c7e2672ba9f7275e6e7c631a836`.
ADT parser imported from proxy-kit/proxyclient with pylib. For full walk use
explicit recursion over children; parser walk_tree was insufficient for an
earlier deep scan. Use get_reg for translated physical addresses.

Exact kernel headers at
`input-driver/build/headers/usr/src/kernels/7.0.13-400.asahi.fc44.aarch64+16k`.
Existing working macOS ARM64 module cross-build recipe:
`input-driver/build-module.sh`, clang `/opt/homebrew/opt/llvm/bin/clang`, lld
`/opt/homebrew/opt/lld/bin/ld.lld`, modpost `input-driver/build/modpost`, exact
Module.symvers and stack guard from generated asm-offsets.h.
**Reuse in isolated USB directory; don't overwrite working input artifacts.**
Full source tar exists but only a few files extracted. tar streaming takes
~15 seconds; batch requested paths. No USB .c/.ko/DT candidate staged yet.

## Native Wi-Fi conclusion / alternative debug transport

Saved populated ioreg confirms Centauri control/alpha/beta **106b:1901/1902/1903**,
classes ff0000/0d2000/0d1100. Exact model specs identify Apple N1. No matching
N1 driver found in exact Fedora wireless source scan (2,135 files) or checked
Asahi development tree. Search absence isn't proof no unpublished driver.
Do not force brcmfmac, M4 BCM4388 firmware, RF calibration or random PCI IDs.
Saved KC AppleCentauriManager exists as future RE foothold, not ready driver.

Potential development-only alternative: AsahiLinux/kisd README reports
M5Pro/T6050 DebugUSB protocol4, dockchannel base2c8d00000. This is **not**
MTP's294b* transport or proof Linux console/network exists. No native DC UART
driver/PPP/Android-host path implemented or tested here. Could reduce manual
development transfers later; don't promise it as working Internet.

## Autonomous payload / storage / rollback

Preserve installed **standalone-ssdroot-v3-aligned-20260912.bin**:
92,651,520 bytes (5655 x16KiB), cksum750659463, SHA256
`397a0e4125087c63b83c09b35cd44fe6bc35508d7d54613bd9a2bf4d9aff46fc`.
v3 is exact previously RAM-tested v2 +170 zero padding bytes. v1 unsafe
chainload overlap; v2 unaligned rejected at coldboot. Neither is rollback.
Installed coih:
`B422A78B3E396F05C3C08A7AD9ADD7D406EBF641225BAEACCA3D95F5AF24F3FEE89D3A7A87D0B614BF2EAD97C9C5F1ED`.
Sep12 09:59 enrollment receipts: `logs/standalone-aligned-enroll-20260912.n8zyi1`.
Old receiver8766 was session94451/PID29583, hostPRIVATE-LAN-ENDPOINT-REMOVED; may persist,
check read-only before use. **Do not rerun old installer: expected coih stale.**

Rootguard DTB `t6050-j714s-native-rootguard.dtb` SHA256
`ddd855503c88b8b3b0afe64b4f3862dee2ec328c347b6c7eca5664bdf1fee5f8`.
Code has no NVMe/cpufreq/secondaryCPU init; preserve warm ANS/rootguard design.
Rootguard allows p5-only writes, other partitions read-only, no discard/vendor
commands. Keep SMC core/GPIO but existing power/input/hwmon/rtc blacklists.

| Partition | Identity / bounds in 4KiB LBAs | Rule |
| --- | --- | --- |
| p2 daily macOS | start140806 count180324745; UUIDPRIVATE-UUID-REMOVED | NEVER modify |
| p3 Linux APFS | start180465551 count23437500; UUIDPRIVATE-UUID-REMOVED | Linux paired boot only, guarded |
| p4 blank EFI | start203903051 count131072; UUIDPRIVATE-UUID-REMOVED | preserve |
| p5 Linux Btrfs | start204034123 count38764544; PARTUUIDPRIVATE-UUID-REMOVED | only authorised Linux root |
| p6 helper | start242798667 count32768 | preserve |
| p7 Recovery | start242965551 count1310709 | preserve |

p5 filesystem UUID **PRIVATE-UUID-REMOVED**, subvol/root;
byte bounds835723767808..994503340032. Partition158.78GB but filesystem14.25GB,
not grown. No resize/reformat needed for USB task.
Linux paired SystemPRIVATE-UUID-REMOVED;
VGPRIVATE-UUID-REMOVED;
PrebootPRIVATE-UUID-REMOVED;
containerPRIVATE-UUID-REMOVED.

V5 proxy rescue artifact `probe/m1n1-smp-diag-v5-20260906.bin`:
1114112B, cksum901225419,
SHA2567e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef.
Rollback archive `logs/standalone-enroll-20260911.AO0gTd/rollback-after.tar.gz`.
V5 coih F32F08BEB837A75ED540A0098F7D1A70F2BCC106364E1EE3E041F9C7C521A2BED425C146F14CB375425B6805FB429401.
Restoring proxy sacrifices autonomous boot until reinstated; prepare verified
return to v3 before any attended test. Do not overwrite baseline for an
unreviewed USB experiment.

## Execution plan for the receiving agent — no additional confirmation

1. Read this + NETWORK-CHECKPOINT + focused KDE note. Don't re-audit already
   established Wi-Fi identities or repeat phone questions.
2. Finish **offline** M5 PHY bank/init/host-caller/reset/shutdown analysis using
   exact symbols above; review PD core + SPMI dependencies and actual HPM IRQs.
3. If evidence supports implementation, stage isolated USB2/PD modules and
   guarded DT with exact kernel symbol versions. Compile/static-test before
   any target changes. Config-only NIC commands cannot substitute for this.
4. Look for an already-available safe delivery/test path without reboot or user
   action. Currently none is established. If none exists, prepare and validate
   a batched package offline, preserving v3/current KDE and p2. Recovery or a
   separate diagnostic boot are future attended options ONLY, forbidden today.
5. Perform target testing only through a verified, safe existing path and
   within the unattended contract. Do not request cable/power/phone actions.
   Otherwise continue independent implementation/verification and document
   the precise remaining live-test prerequisite; do not manufacture success.
6. Report enumeration/network success only from target evidence. Root hubs,
   successful compile, matching compatible, or a powered phone aren't enough.

No manual user command is waiting. The receiving agent should run persistently
under the unattended contract, not wait for permission already supplied here.
