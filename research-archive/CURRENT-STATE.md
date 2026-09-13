# M5 Pro Linux handoff — 2026-09-06

**Sep13 publication authorized and done:** public source/progress repository
https://github.com/Sowyu/m5-azahi main `9c409a4f297cf05055e08b152ed2cd1558bc5150`.
Use separate clone `/PRIVATE-USER/m5-azahi-public` and explicit source exporter
`publication/export-public.sh`; never upload the whole private workspace.
Earlier no-commits preference superseded by explicit latest user request.
No firmware/photos/backups/private IDs or machine-pinned installers published.
Target state unchanged; native courier listing remains pending. Do not reboot.

**Sep13 newest: corrected v5 RAM payload passed loader; native handoff SENT.**
Whole old payload SHA checked, corrected initrd/header readback verified,
original standalone function returned0 and expected next_stage verified.
Session80482 completed; proxy consumed. Need user KDE/terminal/courier evidence.
Installed boot still bad v4—DO NOT REBOOT casually. New permanent enrollment
not done; old bad-image server remains stopped. `ls /run/azahi-usb-20260913`
is next read-only native check. Exact logs in usb-driver/TRANSFER-CHECKPOINT.md.

**CRITICAL Sep13: enrolled USB-files v4 FAILED boot, now in proxy.** Confirmed
loader STOP bundle bounds/version: our packager enlarged initrd past loader's
hard-coded70698084B. Earlier readback verification did NOT imply bootability.
Bad-image server stopped. Corrected fixed-size/recompressed v5 built and4
regressions passed; RAM-only test running session93175, no permanent fix yet.
Installed image remains bad v4. Exact live RAM base/procedure/rollback evidence
at usb-driver/TRANSFER-CHECKPOINT.md top. No CPU/USB driver changes, no commits.

**Sep13 newest: transfer-only v4 INSTALLED/readback HOST-VERIFIED.** Raw SHA
0ca32c0d…d77d0, 92946432B, reported coih E80103BF…29FAA854. Final Linux
Preboot RO, only permitted Linux enrollment changed. Working v3 rollback
preserved. Native boot/courier/network not yet tested. Next attended action:
shut down Recovery, remove inter-Mac data cable, choose Linux for cold boot;
do not load drivers on arrival. Exact receipts and rollback in
usb-driver/TRANSFER-CHECKPOINT.md; server70147 remains running. No commits.

**Sep13 fresh backup HOST-VERIFIED:** target now in Recovery; Linux Preboot
disk3s4 mounted RO after verified UUID checks. Fresh selected-image upload
matches working aligned-v3 raw SHA/coih. Installer gate on server8767 now
unlocked. Giving download/checksum and conditional install instructions for
transfer-only v4; installation/readback/boot still PENDING. See
usb-driver/TRANSFER-CHECKPOINT.md for helper checksum and receipt details.

**Sep13 latest: user approved attended Recovery file-transfer route.** Transfer-
only v4 bundle built (92946432B, SHA0ca32c0d…), preserves loader/kernel/DT/args/
old initrd byte-for-byte, appends USB files + failure-ignored tmpfs courier;
no automatic module loading. 16 transfer tests +12 enrollment regressions pass.
ServerPRIVATE-LAN-ENDPOINT-REMOVED session70147 serves read-only backup helper; installer
withheld until fresh selected-v3 backup verified. NOT installed/reboot-tested.
Next request shutdown/paired Recovery Terminal; no force-cut instruction.
Full live resume info: usb-driver/TRANSFER-CHECKPOINT.md. macOS untouched.

**Sep13 latest disk photo:** p5 Btrfs `fedora` / and expected PARTUUID confirmed;
no FAT shown, p4 FSTYPE blank. Do not infer blank data or format permission.
FAT staging unavailable as currently evidenced. Proposed next route is a
new Linux boot bundle carrying files (no auto driver load), through attended
Linux-paired Recovery with verified backup; not built/approved/installed yet.
No reboot requested now. See probe/NETWORK-CHECKPOINT.md top.

**Sep13 current priority: USB tethering first, N1 Wi-Fi second.** USB candidate
failure paths hardened and rebuilt on HOST; 33 offline checks pass (11 artifact,
19 runner mocks, 3 glue/overlay). Stage/deliver manifests agree. No target
transport, USB enumeration or network success. No target changes, reboot,
webcam, commits or daily macOS writes. See usb-driver/README.md top for exact
changes and preserved pre-edit bundle. Default runner is now PMGR-only dry;
live PMGR/force bypass withheld. DMA SID mapping/power/PHY/PD review still open.
Next requested user action: read-only `lsblk -o NAME,FSTYPE,LABEL,PARTUUID,MOUNTPOINTS`
on Linux to check whether a Linux-owned FAT staging filesystem actually exists.
No live-load/Recovery instructions supplied; do not guess or format a staging
partition, use daily macOS, or race the skipped early proxy window.

**Sep13 Wi-Fi investigation:** new concrete N1 RE sources found on HOST:
CentauriAlpha/Control DriverKit framework cache + AirshipDK ACIPC config tables.
Alpha metadata exactly matches saved106b:1902 and AppleWLANDriver. No Linux
N1 driver/network success, no target changes. Read probe/N1-WIFI-20260913.md
before repeating searches; it records offsets/source hashes and missing
protocol/PCIe work. USB candidate still has known unpatched failure-path bugs.

**Sep13 latest input evidence:** current native boot photographed reaching
Touch MT ready2.013180, immediately followed by accepted v2 power-on; user
reports working trackpad. Expected firmware hash already verified on disk.
Failed boot had AFE attach/boot failure despite accepted power requests.
Startup is intermittent, not fixed; preserve this working KDE/input session.
No new reboot or driver change requested. Details: input-driver/README.md.

**Sep13 firmware follow-up:** user photo confirms correct on-disk trackpad
file `/lib/firmware/apple/tpmtfw-j714s.bin` matches expected SHA256
03a6d272deae424cd4a8e8ca75161079e4da11ffebc012d8b8088b35f1ad719d.
No replacement needed based on this check. Trackpad working after reboot per
user; successful-boot log comparison pending. Input startup still intermittent.

**Sep13 latest verified:** user photo confirms installed basic-kde-session
uses `XDG_CONFIG_HOME=$(mktemp -d /run/kde-clean.XXXXXX)` and explicit
Plasma/Konsole startup. Fresh-config persistence is now verified in the file;
not a full stability claim. KDE currently visible; trackpad reportedly worked
after another reboot, but preceding boot had AFE attach/boot failure and
timeout. Separate intermittent input problem remains. Firmware hash attempt
used misspelled `tmptfw` rather than `tpmtfw`; correct path/hash unverified.
See top of probe/native-kde-regression-20260912.md. No webcam requested today.

**Latest handoff clarification:** webcam screen observation is important and
explicitly authorised without asking again. Daily macOS p2 protection is
critical: no writes, repair/resize, policy changes or whole-disk shortcuts.
For today's no-cycle run leave current native KDE running; proxy is useful
for attended low-level tests but disappears on native handoff and is not an
unattended remote Linux shell. See handoff's mode and safety sections.

**LATEST Sep12: receiving agent assigned unattended long-running work.** User
will be shopping/watching movies: no questions, no reboot/power cycles, persist
toward native networking with Nothing Phone tethering. Full execution contract
at top of `probe/HANDOFF-20260912-USB.md` supersedes earlier stop/ask-to-continue
instructions. Preserve working KDE/macOS; exhaust useful safe offline work if
live access unavailable. Never equate compilation with working networking.
Documentation update only; no background task launched by the authoring turn.

**STOPPED Sep12 at explicit user request.** Complete resume handoff:
`probe/HANDOFF-20260912-USB.md`. User approved Nothing Phone (3a) Pro tethering,
then asked to stop/document. No USB candidate built or target changes. Current
autonomous SSD KDE preserved; still1CPU/softwareGPU/no native network; shutdown
hang unresolved. Host-only inspector gained --entry; M5 PHY symbols located,
not yet sequence-verified. No physical action pending. Read handoff before
resuming; older next-step and pending-fixture statements below are superseded.

**LATEST network preference/evidence:** Nothing Phone (3a) Pro available;
user strongly prefers built-in Wi-Fi. Saved ioreg now confirms N1/Centauri PCI
106b:1901/1902/1903 (not Broadcom). Exact Fedora wireless source scan and
Asahi wip7.2 checks found no compatible N1 driver. Native Wi-Fi needs new
driver work as well as PCIe; don't force brcmfmac or promise tomorrow.
Offline audit now8 tests including allowlisted PCI identity/privacy. Saved
AppleCentauriManager in existing KC is an RE starting point only. Full detail
in probe/NETWORK-CHECKPOINT.md. No native changes/reboot; responsive boot kept.
Phone USB fallback is also not working yet, needs M5 controller/PHY/PD work.

**Networking investigation started; native baseline untouched.** Active note:
probe/NETWORK-CHECKPOINT.md. Offline board audit +4 tests pass; M5 USB/PHY/DART
phandles mapped from saved real ADT. Wireless endpoints are Centauri, not M4
Broadcom. PHY advertises t6040 fallback, but current kernel lacks experimental
M4 PHY and newer SN201202x SPMI Type-C support; stock glue needs a role event.
No device-tree/module/boot changes or MMIO writes. Asked which USB Ethernet
adapter/dock/phone user has; answer pending. No reboot requested. USB route
promising but not a drop-in fix, no network success claimed.

**LATEST: first post-repair automatic KDE boot PASSED, per user.** Saved
/root/kde-good and installed clean/fresh-bus launcher survived physical cycle;
user says booted straight into KDE. No new host payload supplied. But user
reports software shutdown stalls at reached target poweroff.target, followed
by manual long-press power off. DO NOT mark orderly poweroff successful or
infer filesystem unmount completed. Cause unknown; preserve SMC blacklists.
See probe/native-kde-regression-20260912.md for active checkpoint. One CPU,
software graphics, last native network only lo. Recommended next priority is
connectivity to enable target-local Codex and remove manual transfer burden,
plus shutdown/recovery hardening before SMP/GPU experiments. No extra reboot
requested and Codex not installed. Use ordinary account when deploying it.

**LATEST: responsive KDE launcher INSTALLED, compared, synced (webcam).**
native-kde-clean-installed-20260912 confirms INSTALLED; original backed up in
unique /root/kde-backup.* (current target shell b; suffix not confidently read).
Installed basic-kde-session now uses saved /root/kde-good, original known
software exports, fresh D-Bus and direct Plasma/Konsole, no timer/scale2 call.
Parent SSD root UUID guard unchanged. Next preserve runtime logs into "$b/",
orderly poweroff, unplug host data, startup picker -> Linux for real coldboot.
Coldboot outcome pending; older DO NOT reboot notes superseded once shutdown
requested. No CPU/kernel/driver changes, commits, or daily macOS writes.

**Candidate launcher readback/syntax check PASSED on screen.** Photo
native-kde-clean-launcher-readback-20260912; k is unique candidate filename
in current shell, actual suffix not printed. Next back up original to unique
/root/kde-backup.XXXXXX then install k as basic-kde-session, compare and sync.
Installation NOT yet confirmed. Preserve parent wrapper/UUID guard and old
config; no reboot until install result received. See focused regression note.

**Working config SAVED:** user confirms guarded /root/kde-good copy succeeded.
Next prepare unique candidate launcher (shell variable k), syntax-check and
readback, then back up/replace ONLY /usr/local/bin/basic-kde-session. Native
SSD wrapper UUID guard stays intact. Local candidate reference is
probe/native-kde-clean-session-20260912.sh; local creation does not install it.
Persistent startup and reboot test still pending. No reboot requested yet.

**LATEST: full Plasma clean-config test is much more responsive, per user.**
Webcam native-kde-clean-desktop-responsive-20260912 confirms wallpaper/panel/
Konsole during 90s test. Same clean config and renderer flags, no scaling
command added. No CPU/kernel/driver changes. Next preserve temp config under
NEW /root/kde-good (not yet copied), then repair persistent launcher with
backups and cold-test. DO NOT reboot yet: old auto-start is still unchanged.
Responsive runtime != reboot reliability; cause within old settings not yet
isolated. See probe/native-kde-regression-20260912.md for current detail.

**LATEST Sept12 clean-config/control test opened graphical Konsole and returned
to text console under timeout.** See probe/native-kde-regression-20260912.md
for current evidence. Webcam native-kde-clean-log-20260912 shows same-shell
source of launcher lines4..10, temp XDG_CONFIG_HOME, timeout launch and log
head. Unlike prior baseline/original-config log, NEW log's first20 lines lack
repeated OpenGL texture handle errors. Full-log cleanliness and responsiveness
are NOT yet verified. Next bounded90s same-settings test adds plasmashell,
logs to /run/kde-desktop.log. Original config/boot startup unchanged; no
reboot, kernel/driver changes, commits or daily macOS writes. Older next-step
entries below are historical and superseded by this checkpoint.

**LATEST verified-baseline launch BLACK, per user ("bleck").** Parent shell
exports were photographed before launch; guarded command should log to
/run/kde-test.log. Actual launch command/process/result not yet photographed.
Next Control+Option+F4 (Fn if needed), because test launched from tty2 and
previous tty4 shell should now be spare. If text prompt appears, run
`head -n 25 /run/kde-test.log`. No retyping exports/reboot. This means omitted
environment isn't a demonstrated complete fix; inspect new log and exact
installed KWin version before further backend/config changes. Old PID2238
was stopped; don't use that PID for new KWin. Kernel/root guard unchanged.

**LATEST actual baseline exports VERIFIED in tty2 shell.** Webcam
native-kde-baseline-env-verified-20260912 shows KWIN_COMPOSE=Q,
QT_QUICK_BACKEND=software, GALLIUM_DRIVER=llvmpipe, LP_NUM_THREADS=1,
KWIN_FORCE_SW_CURSOR=1, LIBGL_ALWAYS_SOFTWARE=1, QT_QPA_PLATFORM=wayland,
XDG_SESSION_TYPE=wayland, XDG_CURRENT_DESKTOP=KDE and VTNR2. No temp
XDG_CONFIG_HOME shown (uses original config, intentional baseline control).
Next guarded launch from SAME shell (three physical input lines):
`pgrep -x kwin_wayland ||`
`dbus-run-session kwin_wayland --drm --no-lockscreen \`
`-- konsole > /run/kde-test.log 2>&1`
No intervening login/VT change. Capture log this time; no launch result yet.
New GUI likely uses VT2 (launch shell VTNR2), so prior VT4 may be spare text
console now; don't blindly repeat VT2 recovery if GUI occupies it. Previous
KWin2238 was stopped, scheduling experiment ends with that old process; new
KWin gets its ordinary startup policy. Read current PID before any new signals.

**CRITICAL NEW EVIDENCE: minimal KWin did not inherit requested exports.**
native-kde-live-environment-20260912 webcam shows allowlisted /proc/2238/environ
output twice: only XDG login fields (SESSION_TYPE=tty, VTNR=4, session ID4,
runtime /run/user/0, seat/etc). NO KWIN, QT_, GALLIUM, LP_ or XDG_CONFIG_HOME
entries visible. Thus previous claimed clean-config test was NOT established;
do not infer config reset fixed black or blame omitted LP alone. GUI launcher
startup environment differs materially from known-working script. Likely
exports entered in another shell during console changes; exact path unknown.
Next stay in responsive tty2, stop test with `pkill -TERM -x kwin_wayland`.
Then load trusted export lines4..10 from existing basic-kde-session directly
into this same shell, verify, and launch minimal fresh-bus KWin without another
console/login between setup and launch. No persistent config modification.
Stop command now user-confirmed done; scheduler trial ceases when test
process exits. Next issued `. <(sed -n '4,10p' /usr/local/bin/basic-kde-session)`
in SAME tty2 Bash shell. Source range verified against local source and earlier
installed readback: HOME/cd/XDG/render exports only; excludes set-e, daemon,
exec. Bash syntax check passed locally. User now confirms source step done.
Next `env | grep -E '^(KWIN|QT_|GALLIUM|LP_|LIBGL|XDG_)'` verifies current shell
exports before guarded launch. Output pending. No terminal switch between
steps; no new KDE launch yet.

**Immediate next command issued:** user says "Yeah, what now" after tty2
return request; ask allowlisted environment read, split into two short lines:
`tr '\0' '\n' < /proc/2238/environ |`
`grep -E '^(KWIN|QT_|GALLIUM|LP_|XDG_)'`
Continuation > expected after line1. Read-only; inspect actual settings and
XDG_CONFIG_HOME path before baseline reproduction. No result yet. Scheduler
rollback still pending; do not mark it restored. No new GUI launch/reboot.

**LATEST user confirms earlier RAM AND SSD desktops were smooth.** Treat
today's lag as regression, not inevitable one-core performance. Compared
known-working scripts with current manually shortened launch: original
explicit GALLIUM_DRIVER=llvmpipe and LP_NUM_THREADS=1 plus desktop/session
environment were omitted from explicit minimal-test exports. Actual PID2238
environment not yet read, so omission/causality unproven; does not itself
explain original black-screen failure under original launcher. Need inspect
allowlisted runtime env then reproduce baseline, not pile on guesses.
See probe/native-kde-regression-20260912.md for comparison/next checks.
Return to tty2 via chvt2 was requested but not yet confirmed; scheduling
rollback still pending. No new target mutations in this comparison turn.

**LATEST scheduling test NO IMPROVEMENT, per user (still very laggy).**
User reports after issued `chrt -o -R -p 0 2238 && chvt 4`; don't retain this
as a fix. Actual policy readback still needed; assume main-thread OTHER may
be active until restored. Next only `chvt 2` in graphical Konsole to return
known responsive root text console. Then restore saved RR+reset-on-fork
priority1 (`chrt -r -R -p 1 2238`, after process identity remains checked) and
consider targeted tracing/tool availability instead of more blind tweaks.
No all-thread scheduling change, global RT settings, reboot or GPU claim.

**LATEST scheduler baseline verified:** native-kde-scheduler-policy-20260912
webcam confirms PID2238 SCHED_RR|SCHED_RESET_ON_FORK, priority1. Next reversible
main-thread-only test from tty2: `chrt -o -R -p 0 2238 && chvt 4`.
This sets SCHED_OTHER priority0 preserving reset-on-fork, then shows existing
GUI on VT4 ONLY if setting succeeds. No -a (other thread policies untouched),
no global quotas/sysctls or persistent startup change. User execution pending.
If no improvement, restore exact observed main-thread baseline from tty2
with `chrt -r -R -p 1 2238` after confirming PID still same KWin. Recovery VT2.
Compare pointer/typing responsiveness; no restart needed. Cause unproven.

**LATEST tty2 typing normal, kernel tail obtained.** User says keys do NOT
double in text console; GUI doubling intermittent and likely lag-related.
Webcam native-kde-lag-kernel-log-20260912 shows old (~7s) NVMe RTKit PANICLOG
element-not-written ERR_ABORT messages, nvme unpatched data buffer notice,
intentional macsmc_power/input blacklist, later unknown oslog and overlay-not-
supported message. No new obvious lag-related fault in visible last20 lines;
not proof full kernel log clean. Do NOT alter storage/SMC blacklist.
Next read-only `chrt -p 2238` for live KWin scheduling policy before considering
bounded reversible userspace scheduling test. PID2238 from recent top, query
only; if absent rediscover. No global RT quota/sysctl or CPU-frequency writes.
GUI remains on likely tty4; recovery confirmed tty2. No reboot or Plasma yet.

**CURRENT VERIFIED: root text shell on tty2.** native-console2-recovery-
20260912 webcam shows Fedora44/7.0.13 banner (tty2), completed root login and
prompt. `chvt 2` recovered without reboot; graphics likely on tty4, not tty3.
Do not repeat wrong VT4 recovery instructions; use tty2 while preserving GUI.
Next `dmesg | tail -20` and ask whether typing still doubles in this text
console. Kernel log still not obtained. No power cycle/config/driver changes.

**IMMEDIATE VT location assumption likely wrong:** native-kde-chvt-result
webcam shows user corrected initial typing errors, final `chvt 4` returned
root prompt without visible error but graphical Konsole remains. Could already
be on VT4, contrary to earlier assumption launch was on VT3. Do NOT infer
failed kernel VT switching or ask same chvt4 again. Next `chvt 2` to another
console; if text login appears log in root privately, no webcam on password.
Graphical prompt responsive enough for short commands. Previous top screen
retained KWin61.9% in its final frame (earlier two live samples~34%, so don't
claim fixed CPU ceiling). No compositor termination or reboot this turn.

**IMMEDIATE q exit succeeded:** user confirms shell prompt returned from GUI
top. Next clear any repeated q with Ctrl+U, type `chvt 4`, Enter, then check
whether existing root text console appears. This is a VT switch, not reboot
or compositor termination. Command not yet confirmed executed. Avoid further
long GUI typing; prior function-key shortcut failed. Working clean-config
graphical session remains live but unusably laggy.

**IMMEDIATE: VT4 shortcut failed even with Fn; GUI top still updates.**
native-kde-vt-switch-failed-20260912 webcam shows top clock01:31:27 (advanced),
KWin~34.3%, CPU~35user/65idle. No kernel log command executed. Don't repeat
failed shortcut or infer global kernel hang. Next ask user tap plain `q`
once, no Enter, then wait for shell prompt; confirm whether single-key input
is processed before attempting short `chvt 4` shell fallback. No power cycle,
signal, config or clock changes. GUI remains unusably laggy; no full Plasma.

**LATEST top obtained in GUI; CPU not saturated in two live samples.**
Photos native-kde-top-live-20260912 and native-kde-top-live-second-20260912:
time advances01:28:17 to01:28:44; kwin_wayland PID2238 about34.3% CPU, total
user34.3/34.7%, idle65.7/65.0%; no swap used, ample memory. No displayed I/O
wait. Load averages ~2 but not proof CPU shortage; don't blame one-core
saturation as established cause. KWin row PR -2 (possible RT scheduling;
not investigated). No matching CPUQuota/cpulimit changes found in local
scripts. Next switch Control+Option+F4 to existing text console, then short
read-only `dmesg | tail -20` for kernel/input/timing warnings. Do NOT ask for
more typing in laggy GUI. Preserve KWin/config for now; no reboot/signals.

**IMMEDIATE handoff: GUI key doubling prevents even `top` entry.** User says
cannot type; top NOT executed. Stop requesting graphical-terminal commands.
Ask only Control+Option+F4 (Fn if needed), once, to return already logged-in
recovery text console. No typing/password request unless login actually shown;
no reboot. Need establish text-console responsiveness before further commands.

**LATEST clean GUI is visible but UNUSABLY LAGGY:** user reports severe pointer
and typing latency plus doubled keys. Webcam native-kde-lag-20260912 shows
Konsole and only partially typed Plasma command (not submitted on screen).
Thus full Plasma launch NOT confirmed; lag already affects minimal GUI.
Do not call trackpad/keyboard fully working or this travel-ready. Next cancel
partial shell input with Ctrl+C, run `top` inside current graphical Konsole,
leave visible for webcam. Three letters avoids difficult manual entry and
measures load while compositor active (switching away to VT can idle it).
No process stop, reboot, saved config change or CPU frequency/MMIO action.
Delayed key-repeat/compositor saturation is a hypothesis, not established.

**LATEST SUCCESS Sep12: temporary clean-config KWin + Konsole VISIBLE.**
User reports trackpad now works. Webcam native-kde-clean-config-success-
20260912.jpg confirms decorated Konsole/root prompt and pointer on black
background. This is EXPECTED for Konsole-only test; Plasma wasn't launched.
Sequence: terminate failed KWin, return old VT3 shell with three export groups,
`export XDG_CONFIG_HOME="$(mktemp -d)"`, then
`dbus-run-session kwin_wayland --drm --no-lockscreen -- konsole`.
No reboot/kernel/module change. Saved configuration implicated, but exact
file/cause not proven and timing confound remains. No trackpad firmware/log
readback yet; don't claim driver fixed. Config directory path not captured;
current Konsole should inherit XDG_CONFIG_HOME and private DBus/WAYLAND env.
NEXT in graphical Konsole: `plasmashell --no-respawn > /run/plasma-clean.log 2>&1 &`.
Not executed/verified yet. Preserve this working session. Before any reboot,
capture temp path/config, back up persistent originals and implement tested
startup safely. Existing boot launcher unchanged; tty1 getty stopped only for
this boot. Networking only lo, one CPU/software graphics. NO reboot request.

**LATEST saved display config read:** native-kde-output-config-20260912 webcam
shows Unknown-1, brightness1, scale2, mode3024x1890@60000, normal transform;
setup enabled:true, position0,0, priority1, lidClosed:false. No obvious disabled
screen/zero brightness. Other visible fields include hdrPolicy Always alongside
highDynamicRange false, wideColorGamut false; don't infer HDR activation/cause.
File exists; no full text transfer or version readback. Next controlled test:
temporary XDG_CONFIG_HOME (mktemp -d), preserve original configuration. FIRST
user command `pkill -TERM -x kwin_wayland` now user-confirmed done.
Next return original launching VT3 with Control+Option+F3/Fn. If previous root
prompt is visible, run `export XDG_CONFIG_HOME="$(mktemp -d)"`. This step not
yet confirmed. If login screen/black instead, report before continuing; do
not assume old exports in a fresh shell. Then relaunch Konsole-only with fresh
bus. Do not delete/move/reset real .config. tty1 getty remains off this boot
only. No reboot requested. Temporary-config launch has NOT happened yet.

**LATEST root text login recovered again:** user confirms logged in after VT4
request and asks why first boot worked. Explain cause still unknown; coldboot
success != repeated graphical stability, no SSD reinstall needed. Minimal
test still reused saved KWin settings, so not a clean-config control. Next
read-only `cat /root/.config/kwinoutputconfig.json`; no delete/reset yet.
KWin upstream Plasma/6.6 outputconfigurationstore.cpp confirms this saved
display file, but installed version/config contents remain unverified. New
TTY4 login does NOT inherit earlier shell's export settings. Minimal KWin may
still run on prior VT; stop/guard before any subsequent relaunch. No reboot.

**LATEST: minimal fresh-bus Konsole launch also BLACK, per user.** This was
after three short export commands and guarded dbus-run-session KWin launch.
Actual last exports/launch not photographed (camera obscured); no new error
text captured. Do not claim root cause or working graphics. Next physical
action Control+Option+F4 (Fn if needed), expect text login, log in root with
private Linux password. Do not capture password entry. Await usable VT4; no
power cycle, no stop of current getty until ownership established. Existing
tty1 getty stopped earlier (not persistently disabled). First standalone cold
boot PASS still valid, reliable desktop/usable networking still unresolved.

**Latest handoff correction:** user objects to long minimal-launch command;
NOT reported executed. Split into short commands, one per handoff. First only:
`export KWIN_COMPOSE=Q QT_QUICK_BACKEND=software` now user-confirmed done.
`export XDG_RUNTIME_DIR=/run/user/0 LIBGL_ALWAYS_SOFTWARE=1` now user-confirmed done.
`export QT_QPA_PLATFORM=wayland KWIN_FORCE_SW_CURSOR=1` now user-confirmed done.
Webcam native-kde-minimal-env is fully obscured; no visual verification of
exports, don't request another capture solely for that. Next guarded launch
split across two physical input lines: `pgrep -x kwin_wayland ||` then
`dbus-run-session kwin_wayland --drm --no-lockscreen -- konsole`.
The shell's continuation > after first line is expected. If only PID printed,
old KWin remains; do not duplicate launch. If black recover VT4, no reboot.
Launch not yet executed. Do not interpret these exports as KDE
launch/success. No reboot or persistent edits. Avoid sending giant lines again.

**Newest Sep12 desktop stop returned:** webcam native-kde-stopped shows
requested `systemctl stop getty@tty1 && pkill -TERM -x kwin_wayland` followed
by root prompt and no visible error. No exit-status/process-absence proof yet.
Next minimal launch guarded by pgrep: if KWin still exists, print its PID and
do NOT start another. Otherwise fresh dbus-run-session + QPainter/software Qt,
software cursor/Mesa, only Konsole (explicit Wayland platform). Exact command:
`pgrep -x kwin_wayland || XDG_RUNTIME_DIR=/run/user/0 KWIN_COMPOSE=Q QT_QUICK_BACKEND=software KWIN_FORCE_SW_CURSOR=1 LIBGL_ALWAYS_SOFTWARE=1 dbus-run-session kwin_wayland --drm --no-lockscreen -- "konsole -platform wayland"`
No prior log overwrite or persistent launcher edits. This will use current
diagnostic VT, so if black use Control+Option+F4 (Fn if needed), root login.
Minimal launch NOT yet reported executed. tty1 getty stopped this boot only.

**Newest Sep12 KDE process snapshot:** webcam native-kde-process-state shows
kwin_wayland on tty1, plasmashell and konsole with no controlling tty; all
present, sleeping/multithreaded states, displayed CPU 0.0. No D state observed;
doesn't prove renderer health. Current root diagnostic console remains usable.
Next user command: `systemctl stop getty@tty1 && pkill -TERM -x kwin_wayland`.
This stops tty1 autologin from respawning then gracefully terminates exact
compositor process name. No persistent disable/mask, no reboot or boot-file
change. Issued but NOT confirmed executed yet; do not launch second KWin
until stopped. Plan fresh private D-Bus/minimal client launch afterward,
avoiding old fixed-bus socket collision and preserving existing logs.

**Newest Sep12 native networking confirmed unavailable:** webcam
`logs/native-network-interfaces-20260912.jpg` shows `ip -br address` with ONLY
lo UNKNOWN 127.0.0.1/8 ::1/128. No Ethernet/Wi-Fi/gadget interface. SSH cannot
be enabled into usefulness on current boot; controller DT support absent too.
No target changes this turn. Return to KDE recovery while preserving loader:
next `ps -C kwin_wayland,plasmashell,konsole -o pid,tty,stat,pcpu,comm` for
exact process state/TTY before scoped restart. Beware stopping tty1's exec'd
KWin may trigger getty/autologin startup again; establish current ownership.

**Newest Sep12 travel priority / client logs:** user leaves tomorrow without
second Mac; wants to remove manual typing/webcam loop and develop on target.
Webcam `logs/native-kde-client-logs-20260912.jpg` shows tail headers for both
/run/plasmashell.log and /run/konsole.log, no content. Files exist but empty;
not proof of client health or root cause. Next one command `ip -br address`
to inventory native networking before promising SSH/Codex-on-target. Native
network/USB transport unproven; compiled kernel drivers alone don't establish
hardware support. Prioritise reliable independent terminal/recovery + network
and KDE; all18 cores/accelerated GPU not promised for tomorrow. Daily macOS
untouched/no commits. Official Codex CLI Linux support verified via OpenAI
Docs: https://learn.chatgpt.com/docs/codex/cli . Not installed on target yet.
Host dtc inspection of exact native-rootguard.dtb also finds no USB, PCIe or
Wi-Fi controller nodes: network access is NOT merely an sshd-enable step on
this minimal boot configuration. `ip -br address` remains a runtime inventory
check, not expectation that enabling a service yields networking.

**Newest Sep12 installed launcher readback:** webcam
`logs/native-kde-launcher-readback-20260912.jpg` confirms software Qt,
KWIN_COMPOSE=Q, forced software cursor and llvmpipe settings present in actual
`/usr/local/bin/basic-kde-session`, matching local source. Missing DRM node/
EDID/PipeWire warnings also existed in working `ramroot/work-kde/log/kwin2.log`.
Do not claim these are root cause. Next read client logs with one command:
`tail -n 15 /run/plasmashell.log /run/konsole.log`. No runtime change/reboot yet.

**Newest Sep12 head output obtained:** webcam native-kde-start-lines shows
`head -n 40 /run/native-ssd-kde.log` completed: accepting wayland-0 clients,
DRM-node open/not-found warnings, missing EDID for Unknown-1, PipeWire context
failure, then repeated OpenGL texture failure. Root prompt remains available.
Do not request head/tail again. Next read actual installed launcher with
`cat /usr/local/bin/basic-kde-session` to verify software-rendering exports;
local source alone does not prove installed/runtime settings. No reboot/change.

**Newest Sep12 KDE evidence:** webcam `logs/native-kde-opengl-error-20260912.jpg`
confirms root text prompt and repeated `kwin_scene_opengl: generating OpenGL
texture handle failed` in `/run/native-ssd-kde.log` tail. Cause not established;
local launcher already requests KWIN_COMPOSE=Q/software Qt/Mesa. Need beginning
of actual target log: `head -n 40 /run/native-ssd-kde.log`. No reboot or runtime
configuration change performed. Standalone boot baseline remains installed.

**Current recovery step:** user reports private Linux root password set
successfully. tty1 root shell recovered by stopping KDE countdown; expected
KDE log absent in this session. Request manual `/usr/local/bin/native-ssd-kde-start`;
if black, use VT3 root login with user's new password to inspect logs. No new
loader/driver or forced reboot. Await manual launch outcome.

**Current Sep12: tty1 ROOT SHELL recovered.** Webcam native-restart-status
shows SSD Btrfs /root mountedRW, CPU0, ^C at KDE countdown and root prompt.
User says stopped not restarted; restart completion not established. Next
read `/run/native-ssd-kde.log` (one command at a time). No power cycle needed.
Old "kernel USB-loaded" console message is stale. See standalone README top.

**Newest Sep12: user reports freeze, reboot cycle, then BLACK SCREEN after
five-second KDE launch notice.** Webcam confirms black screen. First autonomous
KDE boot remains proven, repeated startup/stability is NOT reliable. No agent
driver/loader change since working boot. Current root may beRW: no blind forced
restart/fsck. Need text-VT response (Control+Option+F3 / Fn) and KDE/kernel logs.
Trackpad SHA check paused. Full state in standalone README newest section.

**Sep12 trackpad diagnostic:** webcam log confirms AFE Chip Boot Failure after
firmware CBOR receipt, then multi-touch start timeout. Not just hidden cursor.
Need explicit AZAHI_V2_POWER log and firmware SHA; original filter excluded
those markers. No unload/unbind/reset (transport remove BUG_ON), no reboot.
Working autonomous KDE/rootRW preserved; input-driver/README.md has evidence.

**Latest Sep12: STANDALONE COLD BOOT TO SSD KDE PASSED.** User confirms KDE
and working keyboard after shutdown/Linux boot; webcam confirms KDE/Konsole,
no host payload transfer this boot. Aligned v3 installed coih B422A78... is the
new working baseline. One CPU/software graphics remain. User reports absent
pointer and no trackpad response; native trackpad diagnosis next, no reboot
needed. Root currentlyRW: only orderly shutdown. See standalone README top.

**Latest Sep12 09:59: aligned v3 NOW INSTALLED and readback independently
VERIFIED.** Selected coih B422A78..., raw SHA397a0e41... exact v2+170zeros;
final Linux PrebootRO, identity/security checks pass. Target still Recovery
until user shutdown/unplug host data cable/Linux selection for first aligned
cold-boot test. No boot result yet, one CPU. Server8766/session94451 preserved,
install slot used/rollback unused. Full receipt/pins and safe next action at
top of standalone README; older "not installed" and V5-current entries stale.

**Latest Sep12: restored V5 cold boot PASS. Aligned standalone v3 READY, NOT
INSTALLED.** Exact failed/RAM-passing v2 plus170 zero bytes aligns raw image to
16KiB, following a documented M4 padding-only fix for the same warning. M5
cause/fix still unproven.12 current installer tests +3 padding tests pass,
original backup+freshV5 rollback revalidated. New helper8766/session94451,
logs/standalone-aligned-enroll-20260912.n8zyi1, unused upload slots. User asked
with audio to power off proxy and open paired Linux Recovery Terminal; last
webcam still proxy, no cycle/install confirmation. Read standalone README top
before acting; old commands/coih below superseded. No commits/macOS/root writes.

**Latest Sep12 09:32:** exact V5 restore readback verified; new coih F32F08...,
standalone v2 no longer selected. Target remains Recovery until user shutdown/
USB reconnect/Linux boot control. Await Running proxy, then read-only fresh
preflight. No root/macOS writes. See standalone README for receipt/full pins.

**Newest Sep12:** second diagnostic now confirms paired1TR Linux Recovery,
Preboot disk3s4 unmounted, candidate still selected. No useful failure reason.
Webcam confirms report sent. Preparing exact-V5 restore as controlled cold-boot
comparison; NOT executed yet. Updated rollback helper8766/session83601,
same enrollment log directory;11 tests pass. User must mount verified Preboot
RO, redownload helper, run rollback/RESTORE; await host receipt before reboot.
See top of standalone README. Linux SSD data and daily macOS remain untouched.

**2026-09-12 newest:** diagnostic was received Sep11; repeat uploads hit
single-report protection. First archive/receipt verified, candidate wrapped
CRC unchanged, Linux-associated ordinary/unpaired Recovery (not original
installation policy). Direct failure fields missing; qualified-name retry
prepared. Fresh receiver8765/session36394, destination
logs/standalone-coldboot-diagnose-20260912.4XhuGj. User must redownload helper.
No new install/rollback/cold boot. Details at top of standalone README.

**Current next action:** User is back in Recovery Terminal. New read-only
boot-failure collector served atPRIVATE-LAN-ENDPOINT-REMOVED waiting for report
in logs/standalone-coldboot-diagnose-20260911.GJsJmU. Reads specific iBoot
failure NVRAM fields/current Linux policy; changes nothing. Rollback server8766
remains available. Details in standalone checkpoint. No new boot attempt yet.

**Newest observation 2026-09-11:** cold-boot attempt reached Apple's recovery
warning that selected macOS needs reinstalling, not KDE. Photo
logs/standalone-v2-coldboot-screen1-20260911.jpg. Exact cause/selected entry
unknown; ask user into Recovery Terminal for read-only diagnosis. Do NOT
reinstall or erase. V5 rollback preserved; webcam allowed again.

**Newest 2026-09-11: standalone v2 is INSTALLED, exact persisted raw SHA256
verified, cold boot pending.** Current target remains in Recovery until user
shuts down and tests Linux with host cable disconnected. No webcam. See
[standalone checkpoint](standalone-loader/README.md) for receipt, selected coih,
rollback and cold-boot instructions. Older "not installed" text is historical.

**Latest 2026-09-11:** Fresh paired-Recovery backup received and verified,
including original +current V5 and policy selection. Target is in Recovery,
Linux Preboot RO, not KDE. Standalone installer/readback helper ready on8766;
no installation confirmed yet. 13 backup and10 installer host tests pass.
Read [latest handoff](standalone-loader/README.md) for command, exact pins,
receiver logs, rollback and research findings. No webcam or commits.

**Update 2026-09-11:** the new autonomous boot bundle passed its RAM test and
reached SSD KDE. It is NOT installed; independent cold boot is still pending.
Read [the new standalone checkpoint](standalone-loader/README.md) first.
Target currently in KDE; next requires orderly shutdown and paired Linux
Recovery. Audio cues for user actions are re-enabled. No commits.
User now confirms Recovery Terminal open. No webcam while eating. Read-only
backup receiver started at PRIVATE-LAN-ENDPOINT-REMOVED destination
logs/standalone-preinstall-backup-20260911.T0uKOR; waiting for target command
and fresh upload. Host verifier's 11 offline tests pass. No installation yet.

This is the current-state guide. Read it before the historical entries in
[PROGRESS.md](PROGRESS.md). The latest tested result is **native KDE running
from the internal SSD**, using `native-ssdroot-v3-20260906.bin`.

Documentation validation: all 14 local Markdown links resolve; the five
artifact hashes in the table were recomputed and match; v3 manifest flags and
initrd size were checked. This documentation pass made no target changes.

## Can it boot without another Mac?

**Yes: one successful autonomous cold boot on September12.** The installed
aligned-v3 boot object includes m1n1, kernel, DT and initramfs, prepares the
required hardware and mounts the installed SSD root. User reports KDE and
working keyboard; webcam confirms desktop. No host payload transfer occurred.
Repeated-boot reliability is not yet established; trackpad remains unresolved.

Current tested path:

```text
Target startup options → Linux → enrolled aligned-v3 self-contained loader
                              → prepare ANS/MTP → kernel + initramfs
                              → guarded SSD root mount → systemd → KDE
```

Once booted, Linux executes natively on the target; the other Mac is not
emulating its CPU or serving its root filesystem. The other Mac is no longer
needed for this boot path. Earlier host-assisted procedures below are historic
development/rollback instructions, not the current normal startup procedure.

## What is proven, and what is not

| Area | Latest evidence and limits |
| --- | --- |
| Native execution | Kernel and userspace boot without the hypervisor. |
| SSD root | v3 reached KDE wallpaper, panel and Konsole after mounting the installed Btrfs root. No RAM root image is in this boot candidate. |
| Persistence | Installed configuration marker survived the failed v1 boot and was recognized on v2/v3; later boots skip first-time configuration. General crash/power-loss durability is not established. |
| CPU | One core is enabled/proven. Other 17 remain unresolved. |
| Graphics | KDE uses software rendering. Native GPU acceleration is not working/proven. |
| Built-in keyboard | Physical typing worked in earlier native KDE and in the native SSD diagnostic shell. |
| Trackpad | Raw events proven under HV. Sep12 native KDE has no visible pointer/trackpad response by user report; diagnosis pending. |
| Independent startup | Aligned self-contained v3 cold-boots SSD KDE; one successful boot. EFI partition not needed for this enrolled raw-object path. |
| Networking / remote control | No working native remote shell/input transport is established. Webcam reads the panel; user types commands. |
| Daily-use readiness | Bring-up root autologin, security exclusions, one CPU and incomplete hardware support. Not a secured daily-driver installation. |

Last observed target state: KDE running with the new root mounted read-write.
No subsequent shutdown has been confirmed. Do not assume sleep/suspend works.

## Successful boot artifacts

All paths below are relative to `/PRIVATE-USER/azahi-port` on the host.

| Artifact | SHA256 |
| --- | --- |
| `native-ssdroot-v3-20260906.bin` (92,651,296 bytes; initrd 70,698,084 bytes) | `43d9bc1fc960acefe0161c244ce942dc0af0ec42a6a5083625fec1bdc4da82a6` |
| `native-loader-prefix-20260906.bin` | `ecffcf08622e64ad616d7b4e4bd6050cca44c9647df311ffb20efcc8f792a604` |
| `nvme-driver/build-rootguard/nvme-apple.ko` | `696d0fded6a47bb9929e1f49b1a38d166d6c539e573696c3c206b84c13c6708c` |
| `nvme-driver/build/apple-sart.ko` | `58ba58e4a6dd0b4574751d224772d9bfe447fa3f4e8bdba8cfa9e7c52b80305d` |
| `t6050-j714s-native-rootguard.dtb` | `ddd855503c88b8b3b0afe64b4f3862dee2ec328c347b6c7eca5664bdf1fee5f8` |

The adjacent v3 JSON manifest pins assets and links, with
`diagnostic_console=2` and `udev_lifetime_fix=true`. Do not substitute the
different `build-rootguard/apple-sart.ko`; the tested SART is the one above.
Preserve v1/v2 images and all original input/kernel/loader artifacts.

Successful-run receipts:

- [Fresh proxy checks](logs/ssdroot-v3-proxy-preflight-20260906.log).
- [Unchanged-prefix chainload](logs/ssdroot-v3-chainload-20260906.log).
- [Native kernel handoff](logs/ssdroot-v3-native-boot-20260906.log).
- [SSD preparation and mount on panel](logs/ssdroot-v3-screen1-20260906.jpg).
- [KDE desktop and Konsole](logs/ssdroot-v3-screen3-20260906.jpg).

SSD-root attribution is supported by the no-RAM-root candidate, its explicit
root PARTUUID, visible mount/configuration success and the installed KDE
launcher refusing to run unless `findmnt -n -o UUID /` matches the installed
SSD filesystem UUID. A separate post-desktop `findmnt` photo is not yet saved.

## Exact tested boot procedure — host-assisted only

Do not run these against a running Linux session or a used CPU diagnostic
session. There must be a fresh **Running proxy** target, the correct USB
connection and no competing proxy client. Resolve unexpected state rather
than bypassing checks. These are sequential steps, not a blind batch script.

1. On the target, shut down Linux cleanly with `systemctl poweroff` if running.
   Once off, hold power for startup options, choose **Linux**, not **Options**,
   and wait for **Running proxy**. Ask the user for any physical cycle needed.
2. On the host, start from the project directory and create new log names:

   ```sh
   cd /PRIVATE-USER/azahi-port
   boot_log_dir=$(mktemp -d logs/ssdroot-v3-boot.XXXXXX)
   python3 -u probe/cpu-proxy-check.py --verify-v5 --read-core-power --verify-ctrr-wfi > "$boot_log_dir/preflight.log" 2>&1
   tail -n 45 "$boot_log_dir/preflight.log"
   ```

   Require exit status zero, verified unused resident V5 identity, original
   48 KiB CTRR WFI filler, expected topology and `CPU_CHECK_PROXY_ALIVE`.
   Addresses change across boots. Do not reuse the successful run's addresses.

3. Chainload the **unchanged native prefix**:

   ```sh
   M1N1DEVICE=/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED sh /PRIVATE-USER/azahi/run.sh /PRIVATE-USER/azahi/proxyclient/tools/chainload.py -r /PRIVATE-USER/azahi-port/native-loader-prefix-20260906.bin > "$boot_log_dir/chainload.log" 2>&1
   tail -n 10 "$boot_log_dir/chainload.log"
   ```

   Require exit status zero and `Proxy is alive again`. Never load the kernel
   directly through installed V5: its diagnostic trace overlaps kernel RAM.

4. Boot the pinned SSD-root candidate:

   ```sh
   python3 -u probe/boot-native.py native-ssdroot-v3-20260906.bin --ssd-root > "$boot_log_dir/native-boot.log" 2>&1
   tail -n 20 "$boot_log_dir/native-boot.log"
   ```

   The runner validates the candidate, prepares the verified ANS link and MTP
   DAPF, and loads the kernel/DT/initrd inside the established RAM fence.
   USB proxy disappearance at native handoff is expected. A successful upload
   alone is not a successful boot: inspect the target for the KDE desktop.

5. If necessary, inspect the panel with the authorized host webcam. Use a new
   photograph path; do not overwrite earlier evidence. Audio cues are enabled
   when user action is needed (September11 preference).

There is no native remote command route available to the host. Commands for
Konsole must currently be typed by the user. Useful read-only checks are:

```sh
findmnt -n -o SOURCE,UUID,FSTYPE,OPTIONS /
cat /sys/devices/system/cpu/online
```

Normal shutdown is `systemctl poweroff` in Konsole. Do not force power off,
unmount `/`, or disarm the root guard while the root filesystem is active.
If shutdown stalls, inspect the final state before choosing a physical cycle.

## The switch-root failure and fix

v1 mounted/configured the SSD root, but failed at `initrd-switch-root.service`.
The original console was too small to read the actual cause. v2 retained the
same disk checks and added readable initrd logs plus an emergency shell.

v2 revealed that `/sysroot` was absent at handoff. The user's journal showed
successful preparation and mounting followed by unmounting and preparation
stopping. The custom dependency chain was:

```text
sysroot.mount Requires prepare.service Requires systemd-udevd.service
normal initrd cleanup stops udev → stops prepare → unmounts /sysroot
```

v3 changes only the preparation unit's `Requires=systemd-udevd.service` to
`Wants=systemd-udevd.service`, retaining startup ordering. The mount still
requires successful preparation, and configuration still requires the mount.
The unchanged strict preparation script must successfully control udev before
loading NVMe. No disk checks, write bounds, modules or root files were relaxed.
v3's actual KDE boot validates this correction. See
[the detailed boot checkpoint](probe/SSDROOT-BOOT-CHECKPOINT.md) for v1/v2
hashes, photos and diagnostic design.

## SSD layout and protection boundary

Target: Apple M5 Pro, Mac17,9 / J714s / T6050, 18 cores, 64 GB RAM.
Main namespace: NSID 1, 4,096-byte LBAs, 1,000,555,581,440 bytes.
Disk UUID: `PRIVATE-UUID-REMOVED`.

| GPT slot | Purpose | Start LBA | LBA count |
| --- | --- | ---: | ---: |
| 1 | Original iBoot container — preserve | 6 | 140800 |
| 2 | **Daily macOS — no filesystem mutations** | 140806 | 180324745 |
| 3 | Existing Linux APFS installation, retained at 96 GB | 180465551 | 23437500 |
| 4 | New 512 MiB EFI, still unformatted | 203903051 | 131072 |
| 5 | New Linux Btrfs root | 204034123 | 38764544 |
| 6 | New 128 MiB Apple_Boot helper | 242798667 | 32768 |
| 7 | Original Recovery, renumbered — preserve | 242965551 | 1310709 |

The root is `/dev/nvme0n1p5` in tested native Linux. Never reuse a Recovery BSD
disk name without resolving its UUID; Recovery names did not match GPT order.

- Root PARTUUID: `PRIVATE-UUID-REMOVED`.
- Btrfs UUID: `PRIVATE-UUID-REMOVED`.
- Root partition bytes: 158,779,572,224; filesystem initially 14,248,030,208.
- Root mount uses Btrfs subvolume `root`; `/home` is temporarily masked.
- The filesystem has **not** been grown to fill the partition.

The private driver permits ordinary writes only in the fixed root LBA interval
`[204034123, 242798667)` on NSID 1, plus constrained flushes when armed.
It rejects other media-mutating/passthrough operations before submission.
The guard starts disarmed; initrd checks board, namespace count/capacity,
partition parent/extent, both GPT hashes and filesystem identity before arming.
Non-root partitions remain block-read-only. The guard stays armed while `/`
is read-write. It is not a security boundary against root replacing the kernel
and does not promise protection against arbitrary hardware/firmware failures.

No daily macOS filesystem writes were targeted. Recorded protection checks
cover partition metadata/selected headers, not a full-volume daily-macOS hash.
The earlier approved layout work shrank only the Linux APFS allocation to make
space. Do not repeat partition creation, installation or filesystem resizing.

## Installation, configuration and recovery receipts

The 14.25 GB image was written using Apple's Recovery storage driver and fully
read back in 425 verified chunks. Source `ramroot/work-kde/root.img` SHA256:
`bc33421d52f06288c53cba128ccc79b13c077fb90f957fea048a5048cd955f7b`.
The installed root now contains later Linux configuration/runtime writes, so
its entire contents are no longer expected to match the pristine image.

- Installation receipt directory: `logs/recovery-root-install-20260906.cILw73`.
- Whole-readback/validation log: `logs/recovery-root-install-server-20260906.log`.
- Post-install archive SHA256:
  `e98e09c7d47757379a0456020b6bcdf106e1d9b47ae95459a58d5417906dd9a1`.
- Original bootloader backup directory: `logs/recovery-backup-20260906.eTn0av`.
- These are metadata/bootloader backups, **not a complete personal-data backup**.
- Recovery transfer/partition servers were stopped after completion. Do not
  restart old installers. Saved served scripts may contain scoped capabilities;
  do not publish their contents or tokens.

First-boot configuration backs up replaced files within the new Linux root at
`/var/lib/azahi-ssdboot/original/`. The initialized marker is
`/var/lib/azahi-ssdboot/initialized-v1` and contains the Btrfs UUID. Valid later
boots preserve user configuration instead of applying the overlay again.
Boot/EFI mounts, repartitioning, automounting, discard timers and first-run
setup are masked. Root console autologin and security exclusions are temporary
bring-up choices, not a finished security configuration.

Do not restore an old GPT alone after the APFS shrink. Do not disarm the active
root guard or manually force mounts to bypass a failed preflight. If boot
stops, preserve the diagnostic state and inspect it before repair.

## Tests and diagnostic locations

Last local tests: 23 SSD-root tests, 11 mocked rootguard tests, 525,366 shared C
write-policy checks, image/module hashes and offline layout all passed.

```sh
SSDROOT_TEST_IMAGE=native-ssdroot-v3-20260906.bin python3 probe/test-ssdroot.py
python3 probe/test-native-rootguard.py
bash nvme-driver/test-root-write-policy.sh
python3 probe/boot-native.py native-ssdroot-v3-20260906.bin --ssd-root --offline
```

Hardware evidence is separate: a bounded native 16 KiB write/flush/read/restore
at root-relative 32 GiB passed before the SSD-root boot, including before/after
metadata checks. That is not an endurance or crash-recovery test.

Initrd v2/v3 diagnostics, if boot fails:

- `/run/ssdroot-prepare.log`, `/run/ssdroot-configure.log`.
- `/run/ssdroot-handoff.log`: root mount, key paths and stage states.
- `journalctl -b -u initrd-switch-root.service --no-pager -o cat`.
- Initrd-only local prompt `ssd-initrd#`; no automatic repair/guard bypass.
- KDE launcher log after normal boot: `/run/native-ssd-kde.log`.

These `/run` logs are volatile. Never rerun the preparation script in an
already-probed emergency session: it correctly refuses early-loaded NVMe.

## Remaining work

1. **Standalone startup:** design and test a local boot path that supplies the
   verified kernel/initramfs/DT and performs the same ANS/MTP initialization
   currently performed by the host. Select and validate packaging/recovery
   strategy before installing anything. Simply selecting Linux, copying files
   to `/boot`, or enabling a systemd service cannot replace pre-kernel work.
   Do not use legacy m1n1 NVMe reset/init on this unverified M5 register map.
2. **All cores:** secondary clusters reached active power states, but no
   secondary instruction entry was proven. The boot CPU is already running
   thanks to firmware; bringing up the others needs a still-unresolved reset/
   release path. Do not treat power-on status as a running CPU. CPU diagnostic
   checkpoints contain used-state warnings; restart fresh before experiments.
3. **Native input verification / GPU:** verify physical trackpad behavior in
   native KDE; investigate native GPU after the user's CPU/boot priorities.
4. **Usability and hardening:** validate repeat boots and shutdown, expand the
   filesystem deliberately, establish ordinary-user login, networking and
   remaining hardware support, and review security/debug exclusions.

These are remaining tasks, not changes made by this documentation update.

## Detailed source map and standing constraints

- [SSD boot checkpoint](probe/SSDROOT-BOOT-CHECKPOINT.md): current result and v1–v3 history.
- [Storage installation](probe/NATIVE-SSD-CHECKPOINT.md): layout, resize, transfer and readback receipts.
- [Root write guard](probe/ROOTGUARD-CHECKPOINT.md): policy, bounded hardware test and safety limits.
- [CPU experiments](probe/CPU-CHECKPOINT.md): unresolved secondary startup and retained-state hazards.
- [Earlier native boot](probe/NATIVE-CHECKPOINT.md): kernel/prefix provenance and RAM milestones.
- [Input driver](input-driver/README.md): protocol patch, sources and physical HV input proof.
- [NVMe driver](nvme-driver/README.md): source provenance and original read-only diagnostic.

No commits or upstream submissions. Preserve unrelated dirty work. Do not
address the user by name. Use audio cues for needed user actions. Ask for physical actions the host cannot do.
Do not scan arbitrary MMIO/debug/ROM ranges, reuse contaminated SMP state,
unbind dockchannel HID (its remove path has `BUG_ON`), use unsafe old reset
helpers, or remove the required macsmc power/input/hwmon/RTC client blacklist.
Retain macsmc core/GPIO needed by the inputs. Do not upload full ADT/NVRAM,
recovery capabilities or private device data. Daily macOS remains out of scope.
