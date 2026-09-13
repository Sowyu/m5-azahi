# Private J714s standalone boot — ALIGNED V3 COLD BOOT TO SSD KDE PASSED

## Latest Sept12: repaired KDE auto-start boots; poweroff hangs

User confirms first automatic KDE boot after clean-config launcher repair.
Installed aligned v3/kernel/DT unchanged. Saved /root/kde-good, new
/usr/local/bin/basic-kde-session with verified software exports and fresh
dbus-run-session launching Plasma/Konsole; original backed up under unique
/root/kde-backup.*. Original SSD wrapper root UUID guard preserved. This
supersedes historical userspace experiment next-steps below; current detail
in ../probe/native-kde-regression-20260912.md.

User also reports systemctl poweroff stalls at poweroff.target, requiring
manual hold-power. This cycle is not a successful orderly shutdown. Exact
cause and filesystem final state unknown. Don't alter macsmc_power blacklist
or claim long-press safety based solely on target message. Still one CPU and
software graphics; native network last checked only lo. No host payload sent
for the post-repair boot. No bootloader or daily macOS change in KDE repair.

## Latest correction: intended clean/software test environment was absent

native-kde-live-environment-20260912 screenshot of filtered /proc/2238/environ
shows only XDG login fields (tty, VTNR4, session4, runtime dir), no KWIN/Qt/
GALLIUM/LP/XDG_CONFIG_HOME exports. The claimed clean-config control therefore
was not verified and cannot support a config-reset diagnosis. Current laggy
GUI is not equivalent to known-working scripts. Next stop test compositor,
load trusted installed script's setup/export lines into SAME tty2 shell,
verify environment, then launch without changing terminals/logging in again.
No persistent reset/fix done. Original black-screen cause remains unresolved.

## Immediate current console: tty2 ROOT text shell, GUI still running

LATEST: user says main-thread normal-scheduling test did NOT improve lag.
Do not persist it. Next return tty2 via `chvt 2`, then restore original
SCHED_RR|RESET_ON_FORK priority1 for same KWin PID2238; rollback NOT yet done.
Need targeted profiling/input timing rather than assume CPU saturation or
call real-time scheduling the culprit. No reboot or persistent changes.

Scheduling baseline now photographed: KWin PID2238 policy
SCHED_RR|SCHED_RESET_ON_FORK, priority1. Controlled test issued, not yet done:
`chrt -o -R -p 0 2238 && chvt 4` (main thread only, preserve reset-on-fork).
Compare existing GUI input latency. Exact rollback while same PID:
`chrt -r -R -p 1 2238`. No -a/global RT budget/clock/register change; runtime
only. Util-linux upstream chrt.1.adoc checked options and semantics. Recovery
text console is VT2, not VT4. No power cycle or persistent file modification.

User confirms typing normal/no doubling in tty2; GUI doubles intermittently.
Kernel tail photo native-kde-lag-kernel-log-20260912 is primarily earlier NVMe
RTKit PANICLOG ERR_ABORT/unpatched data-buffer messages and intended blacklist,
unknown oslog/overlay warning. No obvious new fault explains GUI lag in this
limited tail. No storage/reset/SMC change warranted. Next `chrt -p 2238` reads
KWin scheduler policy (PR-2 seen in top); no mutation yet. Investigate local
GUI scheduling without global RT-budget changes. KDE main_wayland.cpp upstream
calls gainRealTime; RT priority itself isn't proof of bug. Keep tty2 recovery.

`chvt 2` worked. native-console2-recovery-20260912 webcam confirms tty2
banner and logged-in root prompt. Prior chvt4 returned without error but kept
GUI, so the previous assumed GUI-on-tty3 location was likely wrong; do not
keep directing user to VT4 as recovery. No reboot needed or done. Graphical
Konsole/clean-config KWin remains live but severely laggy, Plasma not confirmed
started. Next `dmesg | tail -20` from text tty2 plus compare key doubling here
against GUI. Kernel log not yet captured. No new driver/loader/file changes.

## Latest Sep12: clean temporary settings recover graphical Konsole

LATEST active GUI top captured twice: native-kde-top-live[-second]-20260912.
KWin PID2238 ~34.3% CPU, total ~34-35% user and65% idle, no swap used, ample
memory; timestamps advance27sec. Not simply CPU fully saturated. Load~2 and
KWin PR-2 merit timing/scheduling investigation but neither proves cause.
Next Control+Option+F4 -> existing root text console -> `dmesg | tail -20`.
No more laggy GUI command-entry requests. No new signal/config/reboot.

IMPORTANT follow-up: this visible GUI is NOT usable yet. User reports severe
trackpad/typing lag and doubled keys. native-kde-lag-20260912 webcam shows
only partial unsubmitted Plasma command; don't blame confirmed Plasma startup
or mark full KDE running. Next Ctrl+C clears partial input, `top` in graphical
Konsole captures active CPU/load for webcam. Keep GUI active for measurement;
VT switch could suppress its rendering load. No new driver/clock changes.

Photo `logs/native-kde-clean-config-success-20260912.jpg` confirms Konsole
window, root prompt and pointer. User reports built-in trackpad works now.
This is Konsole-only KWin session, not yet Plasma desktop. No new power cycle,
loader/kernel/input-module change. Old failed KWin stopped, original launching
VT3 shell reused its three exports, then XDG_CONFIG_HOME set to mktemp -d
directory and `dbus-run-session kwin_wayland --drm --no-lockscreen -- konsole`
launched. Previous same minimal session without clean config was black.
Configuration is implicated but exact fault unproven, timing remains possible.
Do not claim AFE/cold-boot trackpad problem resolved without repeat/log tests.
Temporary directory path not yet recorded. Need preserve working settings and
implement/test persistent startup BEFORE reboot; current installed launch
still uses old config and fixed bus. No file deletion or .config reset done.
Next user command inside visible graphical Konsole:
`plasmashell --no-respawn > /run/plasma-clean.log 2>&1 &`.
Plasma launch result pending. One CPU and loopback-only networking remain.

## Current Sep12: ROOT SHELL RECOVERED by interrupting KDE countdown

Saved output config now visible in native-kde-output-config-20260912.jpg:
Unknown-1, enabled true, brightness1, scale2, 3024x1890@60000, position0,0,
normal transform, lidClosed false, priority1. No obvious output disabled or
zero brightness. hdrPolicy Always and highDynamicRange false both visible;
don't equate policy string with active HDR. Not a diagnosis. Next controlled
test should use fresh temporary XDG_CONFIG_HOME and preserve originals. First
request `pkill -TERM -x kwin_wayland` from current root recovery console,
then return prior launching VT (expected3) to reuse exports; new private bus
and Konsole only. Do not mutate real kwinoutputconfig.json while compositor
is active or assume default display config will fix it. No reboot.

User now confirms logged in at recovery text console after requested VT4.
No power cycle. First boot success remains valid, cause of repeat black not
known. Minimal test bypassed Plasma/client script/fixed bus, but not KWin's
saved display configuration. Next read-only
`cat /root/.config/kwinoutputconfig.json` (not yet executed). Do not delete or
claim bad settings until inspected. Source checked: KDE/kwin Plasma/6.6
src/outputconfigurationstore.cpp loads/saves this file in ConfigLocation.
New tty login won't inherit previous exports; minimal KWin may still run on
prior VT. Preserve logs/configs and stop/guard before any new test compositor.

LATEST user reports BLACK after minimal Konsole-only fresh D-Bus launch.
Three exported groups were user-confirmed, final webcam obscured, no visual
readback of environment/launch. Guarded command split across two lines was
`pgrep -x kwin_wayland ||` and then
`dbus-run-session kwin_wayland --drm --no-lockscreen -- konsole`.
Next recover VT4 with Control+Option+F4/Fn and private root login. No password
capture or reboot. This experiment has NOT established a fix or proven root
cause. Current graphical attempt likely occupies prior diagnostic VT; do not
assume VT3 remains free. tty1 getty was stopped for this boot, not disabled.

Stop handoff now returned clean-looking root prompt in native-kde-stopped-
20260912 webcam. Exact command visible; no visible error but exit status not
captured. Next minimal launch guarded against another KWin instance:
`pgrep -x kwin_wayland || XDG_RUNTIME_DIR=/run/user/0 KWIN_COMPOSE=Q QT_QUICK_BACKEND=software KWIN_FORCE_SW_CURSOR=1 LIBGL_ALWAYS_SOFTWARE=1 dbus-run-session kwin_wayland --drm --no-lockscreen -- "konsole -platform wayland"`
Fresh session bus rather than old fixed socket, software compositor, no Plasma
or client script. Existing log files preserved. If pgrep prints PID only, don't
launch again: old KWin remains. If black, recover at VT4 (Control+Option+F4/Fn),
root password privately set earlier. No persistent file change or new reboot.
Command issued, result pending. Source main_wayland.cpp checked positional
application commands, Qt platform override and SIGTERM handler on Plasma/6.6;
installed version still unmeasured, earlier installed --drm mode known works.

Newest process snapshot native-kde-process-state-20260912: KWin tty1 and
Plasma/Konsole (TTY ?) all exist; states sleeping/multithreaded, 0.0 CPU shown.
No observed D-state; black desktop is not simply missing processes. User at
separate working diagnostic console. Next one line requested to stop failed
desktop without getty restart race:
`systemctl stop getty@tty1 && pkill -TERM -x kwin_wayland`.
No enable/disable/mask or persistent file changes; stop only this boot's tty1
getty and exact compositor name with SIGTERM (not force kill). Execution
pending. Preserve diagnostic console and logs; next launch must avoid existing
fixed /run/user/0/bus conflict. No power cycle requested.

Native network runtime inventory now confirmed: native-network-interfaces-
20260912 webcam shows only lo UNKNOWN, 127.0.0.1/8 and ::1/128. No external
interface exists, agreeing with absent USB/PCIe/Wi-Fi nodes in enrolled DT.
Do not ask user to enable sshd or install Codex as if that supplies transport.
Next resume desktop diagnosis with compact process snapshot:
`ps -C kwin_wayland,plasmashell,konsole -o pid,tty,stat,pcpu,comm`.
Need process/TTY state before scoped shutdown; killing tty1 exec'd KWin may
retrigger autologin. No target modifications/reboots in this handoff.

Newest native-kde-client-logs-20260912 webcam: both requested log files exist
but tail displays no contents. No client error extracted. User leaves tomorrow
without second Mac and asks for direct agent workflow. Explained SSH needs
working native network first; Codex CLI supports Linux terminal but not tested
or installed here and requires service connectivity for hosted models. Next
read-only target command `ip -br address`. No network reconfiguration, login
credential copy, installation or new reboot done. Preserve standalone baseline;
do not present all CPU/GPU bring-up as a guaranteed next-day deliverable.

Actual launcher readback captured in native-kde-launcher-readback-20260912:
software Qt, KWIN_COMPOSE=Q, software cursor and llvmpipe exports are present.
Thus do not "fix" by blindly adding settings already there. Earlier working
ramroot/work-kde/log/kwin2.log also has DRM dev-node/EDID/PipeWire warnings.
KWin Plasma/6.6 source GLTexture::allocate/upload emits repeated message when
glGenTextures returns zero; message alone does not identify its caller/cause.
Reference: https://raw.githubusercontent.com/KDE/kwin/Plasma/6.6/src/opengl/gltexture.cpp
Actual installed KWin version not yet established. Next inspect separate
desktop/client logs: `tail -n 15 /run/plasmashell.log /run/konsole.log`.
No target software mutation, signals, restart or power cycle in this turn.

Follow-up webcam `logs/native-kde-start-lines-20260912.jpg` now shows actual
`head -n 40 /run/native-ssd-kde.log` and its beginning: accepting client
connections on wayland-0, failed open DRM node/no such file, couldn't find DRM
node for DRM device, missing EDID for Unknown-1 on /dev/dri/card0, failed
PipeWire context connection, then repeated texture errors. These warnings do
not yet establish the cause (missing EDID was seen on working simpledrm too).
Root terminal alive. Next read installed `/usr/local/bin/basic-kde-session`,
not another head/tail. No target mutation or restart this turn.

Newest webcam `logs/native-kde-opengl-error-20260912.jpg` confirms repeated
`kwin_scene_opengl: generating OpenGL texture handle failed` in session log
tail, with root text prompt usable. User corrected tail argument themselves.
This identifies KWin's OpenGL path emitting errors, not the underlying cause.
Existing local launcher requests KWIN_COMPOSE=Q and software Qt/Mesa; installed
script/runtime environment not yet independently read back. Next single
read-only command: `head -n 40 /run/native-ssd-kde.log` to see startup preceding
the repeated messages. No compositor restart, power cycle or driver changes.

Latest user reports logged in to text terminal after KDE did not start.
Manual-start outcome still needs log evidence; no repeated reboot requested.
Photo `logs/native-kde-manual-start-console-20260912.jpg` shows black visible
panel area, top edge partly outside frame, no readable error. Ask root console
`tail -n 25 /run/native-ssd-kde.log`; return VT3 if necessary and show output.
Do not infer a specific KWin/D-Bus/storage fault before seeing this log.

User now confirms `passwd` SUCCESS: private Linux-root password chosen locally,
not shared with agent. VT3 root login should now be available (not tested yet).
Next command issued: `/usr/local/bin/native-ssd-kde-start` from current tty1
root shell. This reviewed existing script checks rootFS UUID, skips already
moved KDE plugins, then captures session output at `/run/native-ssd-kde.log`.
No rebuild/driver change. If black, switch VT3 and log in root using newly set
password; inspect that log before any restart. Launch outcome pending.

Latest user reports `/run/native-ssd-kde.log` absent. No contents recovered;
do not infer a specific graphics/storage cause. Before another KDE launch,
request `passwd` from the current root shell so user can choose a private
Linux-root password locally and use VT3 for diagnostics if KDE goes black.
This affects Linux root account only; no macOS credential change. No password
requested in chat or known to agent; don't photograph password entry. Password
change NOT confirmed yet. Current boot/root shell preserved, no reboot needed.

New authorized webcam `logs/native-restart-status-20260912.jpg` shows tty1
SSD boot summary, /dev/nvme0n1p5[/root] Btrfs mountedRW, CPU online0, the KDE
five-second notice, ^C and root shell prompt. User said stopped not restarted;
do NOT claim a completed restart/third boot from this ambiguous sequence.
Root access now available without password; no more forced restart needed.
Next ONE command: `tail -n 25 /run/native-ssd-kde.log`, then inspect webcam.
If log absent, report that instead of inferring previous KDE never started.
The profile's "kernel still USB-loaded" text is stale: actual enrolled aligned
v3 cold-boot path includes its kernel/initrd. Fix wording in a later scoped
profile update, not by rewriting/re-enrolling the working boot object now.

Privacy: user requested deletion of photos showing them. Two such captures
native-trackpad-command-error-20260912.jpg and native-kde-stop-state-20260912.jpg
were moved to Trash and their workspace absence verified. User then explicitly
re-authorized webcam; newest frame is laptop screen. Preserve screen-only
diagnostic evidence and avoid capturing the person where possible.

## Latest Sep12: freeze reported, user rebooted; subsequent KDE start black

Latest user: returning tty1 still BLACK; Ctrl+C did not yield a reported
shell. Next request is return tty3 text login and press Ctrl+Alt+Delete ONCE
(Mac Fn+Control+Option+Delete) for systemd's orderly reboot target, not power
hold. Do not repeat rapidly/trigger burst forced reboot. If it restarts,
select Linux as needed and interrupt the five-second tty1 startup countdown
with Ctrl+C before KDE exec. That early-profile interrupt is not yet proven
on target. If shortcut does nothing, report that rather than force cycling.
No target password change or filesystem repair authorized/performed here.

Text VT3 DID appear by user report: kernel/display/keyboard respond to VT
switch. Root login asks password; image has no known root password (see
ramroot/build-guest-ramroot.sh), autologin configured only tty1/old serial.
Do not guess credentials or use daily macOS password. Earlier instruction
to log in root on tty3 was mistaken. Next non-destructive attempt: return
tty1 Control+Option+F1, then Ctrl+C to try interrupting foreground KDE/startup;
report whether shell appears. No evidence yet that this interrupt works.

User reports prior desktop froze and they performed a reboot cycle (orderly
versus forced not established). New boot reached the five-second KDE startup
message then black screen. Photo
`logs/standalone-v3-repeat-black-screen-20260912.jpg` confirms black panel,
not Apple Recovery warning. This does not erase the first cold-boot PASS,
but repeat-boot/desktop stability is now explicitly failing/unresolved.
No new loader/kernel/driver changes were made between these boots by agent.
Current root may be mountedRW; do not blindly force-cycle or run fsck.
Trackpad firmware SHA remains uncollected; pause that check for recovery.
Next user action: switch to text VT with Control+Option+F3 (Fn if required)
and report login/prompt/continued black. If responsive, inspect
`/run/native-ssd-kde.log` plus current kernel/storage logs before mutations.

## Latest native input diagnosis: trackpad AFE fails to start

Follow-up webcam `logs/native-trackpad-power-check-20260912.jpg` confirms both
AZAHI_V2_POWER OFF/ON accepted in native boot. Patched driver active; firmware
checksum is the next read-only check. Earlier shell error was two commands
joined as tail arguments; give one command per handoff. No target changes.

User ran read-only checks; webcam
`logs/native-trackpad-diagnostic-screen1-20260912.jpg` shows Apple MTP
keyboard/multi-touch names, firmware CBOR received then AFE Chip Boot Failure,
multi-touch start timeout and already-starting retries. This is not merely
a KDE cursor setting. First filter did not include AZAHI_V2_POWER; request
explicit power-marker log plus firmware SHA next. See input-driver/README.md.
No target mutation/reboot this turn; keep the working SSD KDE boot intact.

## Latest Sep12: autonomous cold boot PASS; native trackpad diagnosis next

After shutdown/unplug-host/Linux-selection instructions, user reports booted
into KDE, keyboard works, no visible mouse pointer or trackpad response.
Webcam `logs/standalone-v3-coldboot-kde-20260912.jpg` independently shows KDE
wallpaper/panel and open Konsole. No host RAM/payload transfer occurred during
this boot. Thus the enrolled self-contained aligned image cold-boots SSD KDE.
Cable absence during startup was not independently photographed; no boot
dependency on the host remains in this path. One successful cold boot, not
repeated-boot/daily-driver reliability validation. Preserve this baseline.

Padding-only v3 fixed the observed cold-boot failure in this tested comparison:
unaligned v2 failed; exact v2+170 zero bytes boots. Keep the16KiB enrollment
size invariant. Installed raw SHA397a0e41... / coih B422A78... below unchanged.
One CPU/software graphics still. Target NOW native KDE with SSD rootRW;
use `systemctl poweroff`, never force-cycle this live mounted root casually.

Native trackpad pointer is NOT working by user report; cause not established.
Patched input module/board firmware are unchanged from the earlier HV raw-event
PASS. Need read-only native device names/handlers and MTP/touch kernel logs to
separate firmware/interface readiness from userspace/cursor issue. Do not
unload/unbind dockchannel-HID: inherited remove has BUG_ON(1). No new driver
changes or re-enrollment for this diagnostic. Native remote control still
unavailable; user types in Konsole, webcam can inspect output. Audio enabled.


## Latest Sep12 09:59: aligned v3 install and persisted readback VERIFIED

User reports done. Received archive, receipt and JSON independently revalidated
against original preinstall and restored-V5 baselines. Selected raw image exact
SHA256 `397a0e4125087c63b83c09b35cd44fe6bc35508d7d54613bd9a2bf4d9aff46fc`,
92651520B, entry2048, lowVA0. Re-ran full bundle inspector against the uploaded
raw bytes: exact entire v2+170 zeros, all payload components preserved.
Final Linux Preboot read-only; Linux UUID/container/policy checks pass.
**Standalone aligned v3 is NOW selected; V5 no longer selected.**

Evidence `logs/standalone-aligned-enroll-20260912.n8zyi1/install-after.tar.gz`,
91283522B, cksum1439771599, SHA256
`dae8b30997e74a08aa512bd16dfeb37c58a6892bea8cbb6e9057fe279c76e7f7`.
Sibling install-verified.json and install-receipt.txt match revalidation.
Selected wrapped object92654445B, cksum1901600601, SHA256
`d354a1938aa53c7495a8fc87ad37e17a4587963d8fdd3913be5c87365c4a58b1`.
Current coih:
`B422A78B3E396F05C3C08A7AD9ADD7D406EBF641225BAEACCA3D95F5AF24F3FEE89D3A7A87D0B614BF2EAD97C9C5F1ED`.
Raw SHA validated; Apple signature/coih derivation not independently verified.

NEXT user: run `shutdown -h now` in Recovery. Once fully off unplug USB data
cable BETWEEN laptops (keep power charger), hold power for startup options,
select Linux, wait up to2min and report screen. This tests untethered cold
boot; no host payload transfer. Audio cue at handoff. Webcam permitted if
needed. Do not claim standalone/SMP success before observing actual boot.
If KDE appears, do not force power off: SSD root is mountedRW; use normal
shutdown. If Apple warning recurs, do not reinstall/erase macOS; return to
paired Linux Recovery for diagnosis/rollback. Server8766/session94451 kept
alive; install slot used, rollback slot unused. Don't rerun install mode:
its precondition intentionally expects previously selected V5 F32F08....
No GPT/root/daily macOS filesystem changes by installer; no commits.

## Latest handoff: Recovery Terminal open; aligned install command issued

User confirms Recovery Terminal open. Server8766 PID29583 still reachable at
PRIVATE-LAN-ENDPOINT-REMOVED; current rendered v3/current-V5 pins and shell syntax rechecked,
install upload slot unused. Issuing the two commands below and INSTALL prompt.
No install receipt or new target write confirmed yet. Await report in
`logs/standalone-aligned-enroll-20260912.n8zyi1`; validate before reboot.
If helper stops, inspect exact error; do not bypass identity/policy checks.

## Latest Sep12: padding-only v3 built; await paired Recovery Terminal

Restored V5 **cold boot PASS**, webcam and read-only preflight confirmed.
Still selected V5, one CPU, no new target disk writes this turn. Last photo
`logs/aligned-v3-pre-recovery-screen-20260912.jpg` still shows proxy. User has
been asked (with completed audio cue) to power off proxy, then open paired
Linux Recovery / Utilities > Terminal. Do not assume the cycle occurred.

**Strong new cold-boot hypothesis: raw object length must be 16 KiB aligned.**
The [T6040 investigation's final corrected result](https://github.com/damsleth/wallace/blob/main/evidence/2026-07-25-t6040-enrolled-payload-rootcause.md)
reports the same Apple reinstall warning with unaligned objects and a passing
padding-only control. Its earlier content/size theories are explicitly
superseded. The [milestone](https://github.com/damsleth/wallace/blob/main/evidence/2026-07-25-t6040-B0-MILESTONE.md)
confirms cold boot. This is M4 evidence, NOT yet proof on our M5.
Our working V5 length1114112 is aligned; failed v2 length92651350 is170B short.

New `standalone-ssdroot-v3-aligned-20260912.bin` is **exact entire v2 +170 zero
bytes**, length92651520 (5655 pages), cksum750659463, SHA256
`397a0e4125087c63b83c09b35cd44fe6bc35508d7d54613bd9a2bf4d9aff46fc`.
No C rebuild, kernel/DT/initrd/args/entry changes. Runtime version remains v2
because executable bytes are identical. `build-aligned.py` checks v2 SHA and
all original bundle components, refuses overwrite; JSON records provenance.
`test-aligned.py`:3 tests pass (exact bytes, corrupt payload/padding, wrong
length). `test-standalone.py`:6 tests pass incl15 actual-C ANS scenarios.
Existing v2 builder is historical RAM packaging, NOT a cold-enrollment artifact.

Updated `install-server.py` now REQUIRES `--aligned-control-backup`. It validates
original preinstall archive AND exact Sep12 rollback archive/receipt before
rendering `recovery-install.sh` with new current V5 coih F32F08... and wrapper
cksum2129482942,size1117033, plus new aligned candidate cksum/size. The unrendered
shell file is a historical-pin TEMPLATE, not for direct execution. Host now
enforces page alignment for both served artifacts and exact original-v2+padding.
`test-aligned-install.py`:12 tests pass incl full synthetic93MB IMG4 validation
and8 actual shell mock paths. Historical `test-install.py`:11 tests pass.
Actual target Apple signatures are NOT independently verified; raw SHA is.

New server **8766/session94451**; original PID26858 stopped after exact process
check, old receipts untouched. New destination:
`logs/standalone-aligned-enroll-20260912.n8zyi1`, server.log.
Both upload slots unused. HTTP exact rendered helper/syntax and both complete
served artifact SHA/length/alignment PASS. URL remains
`PRIVATE-LAN-ENDPOINT-REMOVED` but user MUST redownload (new upload token).

When paired Recovery Terminal is confirmed:
```
diskutil mount readOnly PRIVATE-UUID-REMOVED
curl -f PRIVATE-LAN-ENDPOINT-REMOVED -o /tmp/ssdboot.sh && bash /tmp/ssdboot.sh install
```
Type INSTALL. Helper checks current V5 file/policy twice before writes, scopes
mount/configure-boot to UUID-verified Linux Preboot, preserves original and
V5 objects, remountsRO, uploads selected readback. Do NOT give shutdown/untether
instructions until new install-verified.json / receipt have been inspected.
If cold boot fails, same fresh helper's rollback mode restores exact V5;
do not reuse old server tokens or erase/reinstall macOS.

## Sep12 V5 control evidence and offline iBoot investigation

`logs/v5-restore-control-screen1-20260912.jpg` shows Running proxy;
`logs/v5-restore-control-preflight-20260912.log` verifies V5 reset/entry/vector
pins, unused diagnostic state, CTRR WFI filler original. Base100046d4000,
bootargs10004edc000, top10004eec000, phys10003af8000, EL2/MPIDR80040000.
CTRR WFI [10004ee0000,10004eec000), SHA256
`bc4a4e3073dfa66ac5ea39867e4c18866e96b396f32b9479b1499b9744b81871`.
No secondary starts/RVBAR writes; alive table allfalse before initialization.

Guarded `read-control-boot.py --run` captured only ADT and declared preoslog
RAM, with normal proxy scratch allocation, no disk/MMIO startup operations.
Evidence `logs/v5-control-ram-20260912.TF7m4X/{capture.log,boot.json,adt.bin,preoslog.bin}`.
Preoslog262144B SHA256
`b31e197428d751a93dbcc8206e94ecc35b2d1a29ce4bd912f77670d115ae9aa8`;
ADT SHA256 `ed44142c9fbf3e8d46f98fbf763615eaea64681c8f28b76f143473679efb98b0`.
Log covers current successful V5 boot, not a recovered failed-v2 trace. Script
is tied to this exact base; MUST NOT reuse after another boot without review.

Offline disassembly only: saved `probe/firmware-analysis/iboot.j714s.bin`,
4102280B SHA256 `18f3644477953c4d0712ede8da5d7d1fe350d9c90c7688afd72424c4c16763c8`.
Capstone venv `/private/tmp/azahi-boot-disasm-20260912.4F58aQ` (ephemeral).
Offsets are FILE offsets, not live addresses. `Kernelcache too large` string
34de80 xref2c904 is checked against region2e, descriptor2fd528 size1e000000
(480MiB); call262c supplies rkrn tag. Proper fuos call235c ->2ce70 uses same
descriptor/capacity ->15152c ->15179c ->151174 ->261c0 image parser. Therefore
this string is NOT evidence of a93MB limit. No firmware mutation/execution.
Did not fully reverse raw-property validation; alignment lead comes from
the documented padding-only M4 test, still needs target M5 cold validation.

No commits, Linux root/GPT/daily macOS untouched. SSD KDE still requires host
until the aligned candidate is actually enrolled and passes untethered boot.

## Latest Sep12: exact V5 restore verified, proxy cold-boot test pending

User reports done. Rollback receipt received09:32 and saved archive/report
revalidated. Installed selected raw object is now EXACT V5 diagnostic loader,
SHA256 `7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef`,
1114112B, entry2048, lowVA0. Final PrebootRO, Linux identity and security/
firmware policy checks pass. **Standalone v2 is no longer the selected loader.**
Restored V5 has a new wrapper/coih from this enrollment (not old F2BB...):
`F32F08BEB837A75ED540A0098F7D1A70F2BCC106364E1EE3E041F9C7C521A2BED425C146F14CB375425B6805FB429401`.
Wrapped SHA256 `136d0424339f80cfe3d2d8a2d557a7fb3a247bd00fe630aa9554d406d2ef9a0e`.
Readback `logs/standalone-enroll-20260911.AO0gTd/rollback-after.tar.gz`,231074B,
cksum3379485293,SHA256
`8e615848c75b941c109a23ab040d639b4dcd57fc7eef7a9f68162c82410e2014`.
Sibling rollback-verified.json / rollback-receipt.txt preserved. Original
preinstall/install archives also preserved. No Linux root/daily macOS writes.

NEXT user: `shutdown -h now` in Recovery; once fully off connect USB data cable
between host and target, hold power for startup options, select Linux, report
whether Running proxy appears. This is a cold-boot control, not an SMP test.
Then webcam/read-only fresh V5 preflight before any RAM experiments. Do not
auto-run old scripts simply because USB appears. No proxy session active yet.
Do not reuse installer install mode without fresh updated pins: it expects
the OLD V5 coih and must reject this newly enrolled V5. New enrollment work
requires fresh report/pins. Server8766 still session83601 for preserved logs.

## Newest 2026-09-12: paired Recovery confirmed; V5 control-boot rollback ready

User reports done, webcam allowed. New report received and receipt/SHA checked:
`logs/standalone-coldboot-diagnose-20260912.4XhuGj/backup.tar.gz`,25232B,
cksum3129587897,SHA256
`41245c6b6ea2d608cf35be04d1c0407584dfe68e0304b79fd8ce2b7af19d6f89`.
Current environment now **one true recoveryOS / Paired**, Linux VG, valid
pairing, candidate coih still selected; security policy unchanged. Preboot
disk3s4 currently UNMOUNTED (collector leaves it alone). Filtered NVRAM includes
boot-volume identifying Linux; no usable iboot-failure fields. Chosen current
recovery-reason01000000; associated Linux VG; boot-command0b000000. These are
current Recovery observations, not a recovered error trace of failed candidate.
Photo `logs/standalone-coldboot-diagnose-screen-20260912.jpg` confirms successful
BOOT_DIAGNOSTICS_SENT and prompt. Earlier visible409 was duplicate upload.

Static review of private new loader startup and differences to V5 did not
establish the cold-load failure cause. Heap limit only applies to high-RAM
test base as intended. No random MMIO/new CPU work. Next controlled comparison
is restoring exact previously working V5, verifying readback, then checking
it still cold-boots to proxy. This narrows boot-stack versus new autonomous
loader differences; does not restore standalone Linux functionality itself.

Rollback helper updated/tested BEFORE issuing command: on rollback downloads
only1.1MB V5, not93MB candidate. Pre-write checks still require exact original
and V5 wrapped files. Post-rollback permits regenerated V5 wrapper at old name
(kmutil may re-sign) while original wrapper remains pinned; host still demands
EXACT raw V5 SHA and raw entry/properties.11 tests pass, including rewrapped
V5 host check and8 shell mock cases (new rollback-rewrap case). No change to
candidate binary, root filesystem, or source m1n1 tree this turn.

Installer server restarted with updated immutable helper, session83601,
same8766 URL and same logs/standalone-enroll-20260911.AO0gTd destination; prior
install report/archive/log preserved (log append). HTTP script/syntax and V5
SHA smoke checks PASS. New upload token means user MUST redownload helper.
No rollback receipt yet; candidate remains installed at this handoff.

Next user commands:
```
diskutil mount readOnly PRIVATE-UUID-REMOVED
curl -f PRIVATE-LAN-ENDPOINT-REMOVED -o /tmp/ssdboot.sh && bash /tmp/ssdboot.sh rollback
```
Type RESTORE. Only Linux Preboot is changed, no GPT/root/daily macOS writes.
Wait for rollback-verified.json/rollback-receipt.txt and inspect before asking
for shutdown/reconnect USB/Linux proxy test. Do not run install again blindly.

## 2026-09-12 latest: first diagnostic received; fresh qualified-field retry ready

User reported URL error. Host remainedPRIVATE-LAN-ENDPOINT-REMOVED and both servers alive.
Original diagnostic actually arrived Sep11 22:14, followed by repeated PUTs
Sep12; single-report receiver rejects duplicates409. GET/check.sh verified200.
Do not overwrite/discard first archive. SHA/receipt checked:
`logs/standalone-coldboot-diagnose-20260911.GJsJmU/backup.tar.gz`,26138B,
cksum209240360,SHA256
`b3a446274dfee1cd306fe650a8e16e8f7ee1150761baef0fd3c18d97b7729597`.
Bounded regular-file archive inspected without extraction.

Findings: associated-volume-group and boot-object path are Linux VG. Current
Recovery is **ordinary recoveryOS / Not Paired**, pairing integrity valid.
This is the post-failure Recovery environment, NOT proof the original enrolled
policy was unpaired (it was paired at installation). Candidate coih still
selected. Mounted Preboot now RW (Recovery mount state, collector did not
change it). Selected wrapped object cksum445051711,size92654276 matches the
verified post-install copy. SIP/SSV still enabled, CTRRdisabled, permissive.
Chosen recovery-reason raw03000000, boot-command0b000000 (not yet decoded).
Current iBoot1 mBoot-20457.1.29 / iBoot2 mBoot-18000.161.9. No direct failure
NVRAM keys found; /var/log/recovery.log absent. Do not claim a specific failure
cause from those absences. No rollback/new boot/target writes this turn.

Updated collector adds a read-only `nvram -p | awk` filter retaining ONLY
the eight exact boot-diagnostic key names, including GUID-qualified forms;
unrelated NVRAM values never go into report. Mock regression confirms the
qualified failure field is included and unrelated fake private value excluded.
Two tests (syntax +3 mock cases) pass again.

Old diagnostic receiver PID24720 stopped after verifying exact command.
Fresh receiver at same URL `PRIVATE-LAN-ENDPOINT-REMOVED`, session36394,
destination `logs/standalone-coldboot-diagnose-20260912.4XhuGj`. HTTP200 and
served updated helper bytes/syntax verified. No new report received yet.
Installer/rollback server8766 PID24437 still alive, preserved for recovery.
User must DOWNLOAD the updated helper before retry (old local helper carries
old upload token, not valid on new server):
`curl -f PRIVATE-LAN-ENDPOINT-REMOVED -o /tmp/bootdiag.sh && bash /tmp/bootdiag.sh`
Await report, inspect qualified fields. No reboot/install instruction yet.

## Newest observation: first cold-boot attempt shows Apple recovery warning

User now confirms Recovery Terminal open after the warning. Prepared
`recovery-boot-diagnose.sh`, read-only (no mounts/NVRAM/policy/storage writes),
and started a fresh receiver at `PRIVATE-LAN-ENDPOINT-REMOVED`, session70177,
destination `logs/standalone-coldboot-diagnose-20260911.GJsJmU`. No report received
yet. Installer/rollback server8766 remains running separately.

Diagnostic helper resolves Linux/Preboot/container UUIDs, captures current
Linux bputil report, chosen device-tree subtree, selected boot-object CRC if
already mounted (otherwise reports unmounted and leaves it alone), Recovery
version/log tail, and explicitly named NVRAM keys only: boot-volume,
alt-boot-volume, boot-args, boot-breadcrumbs, failboot-breadcrumbs,
iboot-failure-reason, iboot-failure-reason-str, iboot-failure-volume. The last
failure field names are present in our local J714s iBoot firmware strings.
No complete NVRAM dump, no other macOS filesystem read. Optional missing
fields/logs recorded with statuses; output bounded1MiB each, archive checksum
and receiver SHA receipt verified. Receiver does not interpret diagnostics.
`test-boot-diagnose.py`:2 tests pass (syntax plus3 mocked shell cases:
unmounted Preboot, missing optional NVRAM/log evidence, wrong UUID rejection).
HTTP-served script matched local reviewed bytes after capability substitution.

Next command (diagnose only, not installer):
`curl -f PRIVATE-LAN-ENDPOINT-REMOVED -o /tmp/bootdiag.sh && bash /tmp/bootdiag.sh`
Await BOOT_DIAGNOSTICS_SENT, validate receipt/bounded archive and inspect
failure-reason/volume first. No claim of iBoot rejection stage until evidence.

User re-authorized webcam. `logs/standalone-v2-coldboot-screen1-20260911.jpg`
shows Apple's warning: "The version of macOS on the selected disk needs to be
reinstalled. Use Recovery to reinstall macOS or select another startup disk."
Buttons Recovery / Startup Disk. **No KDE or m1n1 console observed.** This
does not prove which entry was selected or the exact rejection stage/cause.
Standalone cold boot has NOT passed. Do NOT reinstall or erase macOS.
Next request: click Recovery, open Utilities > Terminal (select/unlock Linux
if asked), gather read-only boot policy/failure evidence before deciding
whether to rollback V5. Do not blindly rerun install. Candidate installed and
raw readback verified, but iBoot cold-load compatibility remains unproven.
Webcam is allowed again; previous no-webcam preference superseded.

## Latest result: installation and persisted readback VERIFIED

2026-09-11 user reports "installed and host verified". Host receipt and saved
report independently re-read and validator re-run against the uploaded archive.
Candidate raw SHA256 EXACT match:
`866aea9d523152f0a0767cb7529be297f52ad4e64d94a70d0fe5bddf222a5a2a`.
Raw properties entry2048, load/write size92651350, lowVA0 as expected.
Final Linux Preboot RO; identity/security/firmware checks passed. No cold boot
has yet been observed. One CPU/software GPU still; no SMP/GPU change.

Readback archive `logs/standalone-enroll-20260911.AO0gTd/install-after.tar.gz`,
91283529B, cksum345338886, SHA256
`ec8734a0c56c0607a6437651cc52338945c26e42e9ffb9213462d3467020be02`.
Saved `install-verified.json` and `install-receipt.txt` in the same directory.
Installed wrapped object SHA256
`64e02d809ccb99b4f7e978671c20f365e4d4b1a494789eea7655c8b54db8ebdd`.
New reported coih (also selected filename suffix):
`B5238A2D3E7FFDA56DB119A8DABEE54DC409342BF9229DAAFA1D2F7A7DEECDCAE07A92BA3A9E564B5C0A3F5351E36C06`.
Apple signature not independently verified; raw payload was SHA256 verified.
Original and V5 backups preserved; no commits or daily macOS filesystem writes.

NEXT: user runs `shutdown -h now` in Recovery, waits for full poweroff,
unplugs data cable BETWEEN laptops (keep charger), holds power for startup
options, selects Linux, and reports desktop/last screen after up to2min.
No webcam; user reports manually. Audio cue for handoff. This tests truly
untethered iBoot enrollment, not the earlier high-RAM chainload.
Keep installer server8766/session74484 available for rollback if needed.
Do not rerun install mode: old-V5 policy precondition should now reject it.

Everything below describing "not installed" is historical and superseded by
this verified installation checkpoint. Build JSON installed=false is unchanged
build-time metadata, NOT the live deployment status.

Latest result: 2026-09-11. User wants independent SSD KDE before travel in
roughly a day, then additional CPU cores if feasible. Audio cues re-enabled
when user action is needed. No commits; daily macOS filesystem excluded.
Latest preference: **no webcam while user is eating**. User has now confirmed
Recovery Terminal is open ("open"); target volume/policy state still unverified.

## Latest handoff: backup verified, enrollment command ready (not yet run)

Target is now in paired Linux Recovery Terminal. Preboot was unmounted;
user mounted UUID PRIVATE-UUID-REMOVED readOnly and ran the
collector. Fresh archive: `logs/standalone-preinstall-backup-20260911.T0uKOR/backup.tar.gz`,
SHA256 `494b5e91993411b34e94b42cfc059c1694fc65ed2a494a7bf7172b3ad44e2214`.
Host validation PASS. Current Linux disk3s3 / Preboot disk3s4 (resolve afresh
in every helper), both reported RO, container96GB, paired1TR/valid pairing,
permissive with SIP/SSV still enabled and CTRR disabled (unchanged policy).

Archive contains TWO legitimate objects, not the one initially anticipated:
custom-01 is exact original wrapped/raw loader; custom-02 is exact V5 raw,
wrapped SHA `ce3151fffd46379ed093a58a15791e11af02a81533e2f5c58dfcafc54fd91e45`,
wrapped cksum `2652175684 1117034`. Current policy coih selects its filename:
`F2BB0BDC7EB3154646420C1F976F9A7AD74B9F1F80C9A2E3243A785068C8BA457F495C2F2EB1F9EF488A45449A24894E`.
Policy SHA256 `162c1faa388bc59412ece6b13640ef8359e3b5b0072829a58e58c843c86e7d4c`.
Validator now accepts exactly one pinned V5 plus optional exact original,
checks every source/hash and that reported coih selects V5; extra/unknown/
duplicate objects still fail. **13 backup tests pass**, including actual fresh
archive and rejection when policy selects the original instead. No signatures
verified or coih cryptographically derived; raw bytes are SHA256-pinned.

Active installer/readback server: `PRIVATE-LAN-ENDPOINT-REMOVED`, session74484,
destination `logs/standalone-enroll-20260911.AO0gTd`. It validates the fresh
backup SHA/structure before startup and serves immutable in-memory copies of
only reviewed script, exact candidate, and V5 rollback raw image. HTTP smoke
checks matched script and both full artifact SHAs; unrelated route returned404.
The old read-only receiver on8765 is no longer needed after backup receipt.

`recovery-install.sh` checks system/group/container/Preboot UUIDs, free space,
RO start state, paired1TR policy/chip/board/ECID/nsih and both old wrapped file
checksums. Downloads candidate+V5 to temporary files and checks exact size/CRC.
Requires explicit INSTALL (or RESTORE for rollback), repeats preconditions,
makes ONLY verified Linux Preboot RW, runs raw kmutil entry2048/lowVA0, checks
policy and preserved old files, copies selected installed object, cleanly
unmounts/remounts RO and compares persisted readback, then uploads for host
DER/raw SHA256 and policy comparison. No GPT/root/daily-macOS writes, security
downgrades or reboot commands. No target openssl/shasum dependency. HTTP/CRC
transfer is not cryptographic authentication; use only the trusted local LAN.

`install-server.py` validates returned UUIDs/RO state, all policy fields against
backup except expected local nonce/coih changes, raw entry properties and exact
candidate or V5 SHA. Successful readback writes install-verified.json and
install-receipt.txt (rollback names for rollback). Upload failure preserves
partial/archive and stops; no overwrite/retry. No automatic rollback/reboot.
**10 installer tests pass**, including full93MB synthetic IMG4 readback and
seven actual-shell mocked paths: success, wrong UUID/policy, cancellation,
corrupt download, kmutil failure, upload failure. Mock hardware commands never
touch disks; mock upload success is separate from real host-validator tests.
Synthetic IMG4 signatures are deliberately not valid. Tests are not cold-boot
evidence. Candidate raw cksum `819284573 92651350`; V5 `901225419 1114112`.

NEXT user command (not yet confirmed run):

```sh
curl -f PRIVATE-LAN-ENDPOINT-REMOVED -o /tmp/ssdboot.sh && bash /tmp/ssdboot.sh install
```

Type INSTALL; owner credentials stay local. Wait for host verification and
inspect saved report before giving cold-boot instructions. If standalone fails,
return to paired Linux Recovery and restore V5 via same downloaded helper in
`rollback` mode after remounting verified Preboot RO. This returns Running
proxy, not independent Linux; original loader backup also preserved. If old
wrapped files are missing/changed, stop and review instead of bypassing checks.

### Faster testing research, 2026-09-11

User requested Twitter/X. Searches returned no usable matching posts; direct
AsahiLinux/yuyuyureka X pages returned403. Do not claim to have read their feed.
Primary docs checked:
- https://asahilinux.org/docs/sw/m1n1-user-guide/ — USB proxy kernel loading and
  hypervisor virtual UART; nominal rapid test loops on supported setups.
- https://asahilinux.org/docs/sw/tethered-boot/ — stage1 versus EFI stage2 and
  virtual serial console. Backdoor mode needs per-OS policy change; NOT applied.
- https://github.com/AsahiLinux/m1n1/pull/610 — initial T6050/T6051 still explicitly
  describes powered secondaries not entering code. No proven new SMP fix found.
- https://github.com/damsleth/wallace — M4 Pro, not M5; self-contained enrollment
  and device-mode USB are useful workflow references, not transferable proof.

Our efficient follow-up is native USB serial/network + authenticated SSH once
transport works. Existing native handoff loses proxy; HV virtual UART is not
native USB support. Conventional EFI-stage2 would avoid repeated Recovery for
kernel changes but requires a working loader storage path; current private
T6050 m1n1 intentionally refuses legacy NVMe driver initialization. Do not copy
M4 MMIO or enable unsupported storage paths to chase faster tests.

## Current hardware state and next step

The paragraphs below describe the RAM-test milestone, superseded by the
Recovery/enrollment handoff above where they discuss current machine state.

Target last observed running KDE from SSD via the new autonomous loader.
`logs/standalone-v2-ram-screen2-20260911.jpg` shows SSD-root console autologin;
`logs/standalone-v2-ram-screen3-20260911.jpg` shows desktop, panel and Konsole.
The first photo showed an Apple logo during transition; that was NOT proof of
a reset/failure. The later Linux/desktop photos establish successful boot.

No bootloader installation has been performed. Installed custom loader is
still V5; choosing Linux on a fresh start still opens Running proxy. No new
CPU was started. Root currently RW/guard armed; don't force power off/disarm.

NEXT: ask user `systemctl poweroff` in Konsole, then hold power for startup
options and choose Options/Recovery. Ensure Recovery is paired to Linux,
unlock/select Linux if asked, open Utilities > Terminal. Need fresh read-only
Linux/Preboot UUID/policy inventory and backup BEFORE any installation.
Do not run old recovery-loader.sh diag: it pins the pre-V5 policy and is not
an installer for this image. Build a new bounded helper/receiver for the new
candidate, preserve rollback, verify installed wrapped payload, then cold-boot
without USB. Authentication stays local. No bputil downgrade or GPT changes.

### Recovery backup preparation (host-only, 2026-09-11)

New `recovery-collect.sh` is a read-only **pre-install V5** collector. It
resolves current BSD names from the fixed Linux UUID, validates system/group/
Preboot/container UUIDs and the 96GB Linux container, requires mounted Linux
and read-only Preboot, and checks paired 1TR/existing permissive policy.
It does not mount/unmount, install, change policy or write persistent storage.
Only temporary files and a checksum-verified upload are produced. If Preboot
is unmounted or writable, it stops and reports the verified device for review.
Its 32MiB bound is deliberately unsuitable for a post-install 93MB object.

Serve this script with the existing `probe/recovery-backup-server.py --script`
option only after selecting a fresh destination and checking the host LAN IP.
No receiver was started during this preparation turn; no fresh backup received.
The receiver's receipt proves transfer checksums, NOT boot object validity.

`validate-backup.py ARCHIVE` independently checks receipt, bounded archive
members (no extraction), volume identities, read-only Preboot, source/copy
checksums and manifest scope, IMG4/IM4P/PAYP structure/raw entry properties,
and the exact pinned V5 raw SHA256. Exactly one custom object is accepted;
unexpected extras stop for review. It checks reported paired/security policy
and records current coih and policy SHA256 for the future installer.
It **does not verify Apple's IMG4 signature or derive coih**. Do not claim
either; these are explicit false flags in its report.

`python3 standalone-loader/test-recovery-backup.py`: **11 host tests PASS**,
including real original IMG4 parsing, synthetic V5 fixture with renumbered
BSD devices, wrong identities/writable Preboot/policy/old-loader rejection,
receipt/checksum mismatch, manifest escape, missing/duplicate/extra/symlink
archive members and malformed DER. The synthetic wrapper deliberately does
not have a valid Apple signature. `bash -n recovery-collect.sh` passes;
the collector itself has NOT yet been run in Recovery or shell-mock tested.
Next: user confirms Recovery Terminal, fresh backup and validation, then
prepare/review install + rollback + post-install readback helpers pinned to
that backup. No installation helper for the new bundle has been run or built.

## Candidate and provenance

`standalone-ssdroot-v2-20260911.bin`: 92,651,350 bytes, SHA256
`866aea9d523152f0a0767cb7529be297f52ad4e64d94a70d0fe5bddf222a5a2a`.
Loader prefix: 1,114,112 bytes, SHA256
`57cb1b3ecb6c0f2a4cd2dcbe09cd92f6c74894cd9673381e57fa0fe25865613e`.
Raw entry 2048, lowest virtual address 0 (installation not yet tested).
Adjacent JSON pins loader and each payload component; `installed=false` is
build-time metadata, not an automatically updated deployment receipt.

`build-bundle.py` reuses the EXACT compressed kernel, DT and initrd from pinned
native-ssdroot-v3. Same SSD guard, checks, configuration and desktop. Bootargs
only append `azahi.standalone=1 drm.panic_screen=qr_code` (latter matches native
runner default). No RAM root filesystem. Kernel77,398,016B/initrd70,698,084B.
Private header AZAHI1 NUL NUL, little-endian version1, four lengths and four
CRCs. Builder and C loader bound/check content; gzip decompressor also checks
kernel length/header. CRC isn't a signature; whole artifact SHA pinned on host.

Separate source tree `m1n1-20260911` extracted with git archive from local HEAD
88a98213d55f2cbd69844762c3171b39c0cd0bf9. Copied only existing private native
kboot.c/main.c/nvme.c/cpufreq.c changes, then applied new changes in this tree.
Original dirty m1n1 tree preserved (same diff-stat after edits); no commits.
No V5 diagnostic start.S/exception/startup/smp trace code copied into this build.
User had previously overridden local no-AI restriction for private work only;
no upstream submission or claim of upstream-supported hardware.

Build uses Homebrew LLVM/LLD. Original Rust source tree is byte-identical
(`diff -qr m1n1/rust standalone-loader/m1n1-20260911/rust` clean). Existing
`m1n1/build/librust.a` reused with same RELEASE configuration because current
Rust installation lacks aarch64-unknown-none-softfloat core. No Rust source
change. Initial build had C API argument errors, corrected before testing;
new C uses dc_cvau_range/ic_ivau_range and dapf_init(path,1), matching proxy.

Build command (do not overwrite a released bundle; builder refuses):

```sh
make -C standalone-loader/m1n1-20260911 USE_CLANG=1 RELEASE=1 M1N1_VERSION_TAG=azahi-standalone-v2-20260911 -o build/librust.a -j8
python3 standalone-loader/build-bundle.py
```

## Autonomous startup

Dedicated payload_run dispatches to azahi_standalone_run, not generic storage
chainloading. Requires T6050, board8, exact target J714s, EL2 boot MPIDR40000.
Bounds payload against bootargs top_of_kernel_data and tested memory windows.
Decodes kernel directly to10800000000; initrd copied to10a00000000; FDT copied
to10900000000. Uses the proven carveout-free1010a960000..10f4ab00000 range.

SMP function initializes boot CPU index then returns BEFORE any secondary
start or RVBAR write. No frequency-init call in autonomous payload path.
ANS helper verifies ADT BARs and four PMGR names/addresses before MMIO, then
every parent state and already-running firmware before the only possible
power RMW: APCIE_SYS_ST0 280900150, clear1000030f, set15. Bounded2s poll,
no cold reset. Same MTP-only DAPF setup as native runner. No loader NVMe init;
private nvme.c continues to refuse T6050/T6051 legacy driver entry.

## RAM test safety — do not use the stock low-base whole-image chainload

A whole93MB bundle copied over resident V5 base would overlap its firmware
CTRR WFI area ~8MB above base. Caught in review BEFORE any test write there.
v1 artifact was built but NEVER hardware-tested or installed. Preserved for
history, not an approved boot candidate.

v2 RAM test uses source/stub at10300000000, destination/entry10400000000+800.
Both are inside the verified carveout-free window and disjoint from Linux
kernel/initrd/DT. No secondary RVBAR rewrites. High loader reserves the full
256MiB10400000000..10410000000 region in Linux DT and caps its heap at the
same upper bound. Payload+SEPFW+bootargs must fit first128MiB of that window.
This tests autonomous startup, but high-RAM chainload is NOT the same as an
iBoot cold load; actual installation/cold-boot validation remains required.

`test-boot.py` defaults offline; --run uses the existing host chainload tool,
SHA aebe6c30dc631b0fed366a65e40361b2e082af5812f1e3bde090e37de0fd2410,
transformed in memory with explicit assertions. Replaces low image staging
with bounded high-RAM transfer, removes RVBAR writes, sends P_VECTOR once
without waiting for a Linux proxy. Preserves SEPFW/preoslog and existing ADT
mechanics. Pinned fresh V5 identity/unused state required. Do NOT rerun while
native Linux is running; a fresh physical proxy start/preflight is required.

Fresh preflight log: logs/standalone-v1-final-preflight-20260911.log.
V5 base1000488c000, unused verified, secondaryalive[], original48KiB WFI
10005098000..100050a4000. No CPU experiments occurred this session.
Transfer/handoff: logs/standalone-v2-ram-boot-20260911.log, exited0, entry
10400000800, stub10305e54000. Expected proxy disappearance, no active client.

## Validation

Six host tests pass: valid bundle, corruption rejection, bounds/version
rejection, exact v3 payload preservation, no diagnostic secondary startup,
and compiled ACTUAL C ANS preparation with15 mocked cases (bad BAR/name,
parent/fault/firmware states, already active link and bounded timeout).
Wrapper offline compilation/input pins pass. Tests do not prove hardware
safety alone; successful native SSD KDE boot is separate evidence above.

```sh
python3 standalone-loader/test-standalone.py
python3 standalone-loader/test-boot.py
```

Logs: standalone-v2-build, standalone-v2-bundle-build, standalone-v2-tests
under logs/ with suffix -20260911.log. Previous SSD-root23/rootguard11/
Cpolicy525366 checks remain relevant; underlying drivers/initrd unchanged.

## Recovery identities / rollback to preserve

Linux SystemUUIDPRIVATE-UUID-REMOVED,
VG/DataPRIVATE-UUID-REMOVED,
PrebootPRIVATE-UUID-REMOVED,
containerPRIVATE-UUID-REMOVED (Linux APFS, not daily macOS).
Resolve fresh BSD names; don't assume old disk4s3/s4.
Original backup logs/recovery-backup-20260906.eTn0av is intact. Also preserve
current installed V5 raw probe/m1n1-smp-diag-v5-20260906.bin, SHA
7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef.
Need NEW backup of current wrapped V5 object/policy before replacement.
Previous original coih is not current V5 coih. Recovery may lack openssl/cmp;
use verified local receipt workflow, do not pretend unavailable tools ran.

References: [m1n1 user guide](https://asahilinux.org/docs/sw/m1n1-user-guide/)
supports appended direct-kernel payloads/raw custom boot entry. This private
board preparation is not upstream support. [T6050 PR610](https://github.com/AsahiLinux/m1n1/pull/610)
still documents secondary power-on without code entry; no new M5Pro CPU fix
was established in the September11 review. All cores remain a stretch goal.
