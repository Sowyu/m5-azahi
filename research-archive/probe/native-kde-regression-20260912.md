# Native KDE responsiveness regression — 2026-09-12

## Sep13 current input success confirmed, no further restart requested

Latest user photo confirms OFF accepted1.769702, new AFE image1.876061,
Touch MT ready2.013180, ON accepted2.013191. User reports trackpad functioning.
See input-driver/README.md for failed/successful-boot comparison. Intermittent
AFE startup remains unresolved; do not confuse this successful boot or the
installed fresh KDE config with a general stability fix. Preserve session.

## Sep13 follow-up: expected on-disk firmware hash confirmed

User photo now confirms correct `tpmtfw-j714s.bin` path and SHA256
`03a6d272deae424cd4a8e8ca75161079e4da11ffebc012d8b8088b35f1ad719d`.
This supersedes the path/hash-unverified statements below. Trackpad currently
working per user after reboot; next compare this boot's AFE/Touch MT/power
logs with the failed boot. Do not infer all initramfs copies verified or
intermittent startup fixed. Preserve working session, no driver reload.

## Sep13 CURRENT: per-launch fresh config installation confirmed by user photo

User-provided photo of successful `tail -n 5
/usr/local/bin/basic-kde-session` shows exactly:

```sh
export QT_QPA_PLATFORM=wayland
export XDG_CONFIG_HOME=$(mktemp -d /run/kde-clean.XXXXXX)
unset DBUS_SESSION_BUS_ADDRESS DISPLAY WAYLAND_DISPLAY
exec dbus-run-session kwin_wayland --drm --no-lockscreen \
-- "plasmashell --no-respawn" konsole
```

This supersedes earlier uncertainty about installation, not earlier freeze
evidence. Current screenshot shows graphical Konsole. User reports trackpad
worked after another reboot, following an earlier boot with AFE failure. No
sustained/repeated-boot stability established. Do not reboot just to verify.
KDE config is recreated each launch; terminal startup is explicit, not itself
evidence of restored applications. User clarified that "save windows into RAM"
meant apps reopening at login, not suspend or a RAM-root request. Fresh config
does not repair the independent intermittent AFE startup failure.

Photo also resolves the latest firmware hash-command failure: user typed
`/lib/firmware/apple/tmptfw-j714s.bin`, not expected `tpmtfw-j714s.bin`.
Correct firmware path presence/hash remains unverified; no missing-firmware
conclusion justified. Earlier log showed firmware sending followed by
`Failed to attach to AFE (-6)`, `AFE Chip Boot Failure`, and interface timeout,
despite AZAHI_V2_POWER state0/state2 accepted. Never unload dockchannel transport.

## CURRENT: freeze after chvt1; persistent repair NOT verified

Final webcam `logs/kde-final-check-20260912.jpg` contradicted the assumed
successful retest: still text console, earlier command errors visible
(cp/missing path and failed temporary-script invocation). User's "works like
a charm" and "done" are insufficient to establish the intended test/install
actually succeeded. Latest install command was typed but no byte readback or
launch success observed. User ran chvt1 at agent request, now reports freeze.
`logs/kde-freeze-after-vt-switch-20260912.jpg` is obscured, no useful screen
evidence. Agent explicitly retracted premature confirmation of repair.

Next: recover text VT with Control+Option+F3 (Fn if required), then stop
getty@tty1 runtime-only if console responds. Do NOT relaunch KDE or powercycle
blindly. Need inspect actual installed launcher and active process environment
before another test; previous shell variables t/b are not reliable evidence.
No new target driver/boot/macOS changes or host transport established.

## Latest: fresh-config retest works; per-launch fresh config offered

User reports the bounded fresh-config test "works like a charm" and has one
minute before leaving. Offered backup-backed persistent launcher change:
replace literal /root/kde-good in installed launcher with shell expression
$(mktemp -d /run/kde-clean.XXXXXX), creating new config on every launch;
syntax-check/install/sync then start getty@tty1 after timed test returns.
This preserves renderer exports, saved old settings and normal files; desktop
customisations do not persist through the new XDG_CONFIG_HOME. No reboot,
kernel/module/boot image or macOS change. **Commands offered, not yet confirmed
executed.** Exact backup suffix unknown; user shell variable b identifies it.
Do not claim persistent repair or coldboot tested yet. Existing shutdown hang
and one-CPU/software graphics limitations remain.

## Latest resumed session: black screen returned, fresh-config test pending

User reports another boot to black screen after shutdown with terminal and
Minesweeper previously open. Cause not established; do not blame open apps.
Text-console recovery succeeded. Webcam
`logs/kde-launcher-check-20260912-resume.jpg` shows repeated
`kwin_scene_opengl: generating OpenGL texture handle failed` in current
`/run/native-ssd-kde.log`, and installed `basic-kde-session` still has known
software exports, `/root/kde-good`, fresh D-Bus and Plasma/Konsole command.
Observed separate text console (not tty1); do not infer current live KWin
environment solely from the file. Prior post-repair boot success does not
establish ongoing reliability.

Next instructed, NOT YET EXECUTED/VERIFIED: make unique /run/kde-test.XXXXXX,
preserve current log there; stop getty@tty1 runtime-only; terminate remaining
kwin_wayland gracefully; copy launcher with only /root/kde-good substituted
by temporary config path; run under timeout60s/kill-after5s. No installed-file,
kernel, module, boot-policy or macOS change. Keep saved settings intact.
This is a diagnostic clean-config comparison, not an established fix.

## Post-install boot passed; shutdown remains broken (latest)

User reports: "it booted straight into kde yayy" after the instructed
shutdown/power-cycle/Linux boot sequence. First post-repair automatic KDE
boot PASS per user; no new postboot screenshot or sustained-use test yet.
Host-disconnected boot was instructed; physical cable absence not separately
verified. No host proxy/payload was supplied for this boot.

IMPORTANT user now clarifies systemctl poweroff hangs at "reached target
poweroff.target" and they hold power to force off. Thus this was NOT a clean
software poweroff success. Exact shutdown stage/cause and filesystem final
state are unknown. Don't assume that target message proves unmount/flush
completion or label forced poweroff safe. Preserve existing SMC blacklists;
don't re-enable macsmc_power based only on this report. Shutdown needs its own
diagnosis; no extra cycle requested now. Saved config and new launcher have
survived the reported physical cycle. Still one CPU/software rendering.

Next-step recommendation for trip: preserve responsive baseline, establish
native connectivity/transfer path, then ordinary-user Codex CLI + project and
handoff docs on target. Current last network inventory has only lo; minimal
DT lacks USB/PCIe/Wi-Fi nodes. Codex is not yet installed; host-backed models
need connectivity. This is controller/driver bringup, not just enabling sshd.
Keep shutdown/recovery hardening high priority; SMP/native GPU separate work.

## Milestone: clean full Plasma test responsive (latest)

INSTALL CONFIRMED: logs/native-kde-clean-installed-20260912.jpg shows full
guarded backup/install/cmp/sync chain and INSTALLED backup=/root/kde-backup.*.
Exact random suffix is not confidently readable from photo; don't invent it.
Current shell variable b identifies that directory, containing original
basic-kde-session. k still identifies candidate. New installed launcher uses
/root/kde-good and fresh D-Bus, same software exports + Plasma/Konsole, no
90s timeout or 2x scale command. Wrapper root UUID guard unchanged.
Next ask copy /run/kde-*.log into "$b/" before orderly systemctl poweroff,
disconnect host data cable, then power-button startup picker -> Linux.
Cold boot and postboot responsiveness NOT yet tested. No host payload needed.
If recovery required, tty1 five-second countdown Ctrl+C gets root shell;
backup directories can be listed with ls -dt /root/kde-backup.* after boot.
Do not blindly restore original broken graphical startup unless needed.

Candidate preparation now user-confirmed and photographed:
logs/native-kde-clean-launcher-readback-20260912.jpg. Visible first10-line
copy command, tee appended config/unset/exec stanza, and successful sh -n
followed by matching tail4. Shell variable k holds unique candidate pathname
(actual suffix not printed). Saved config copy and SAVED also visible.
Next issued install sequence will set p=/usr/local/bin/basic-kde-session,
create unique backup directory b=/root/kde-backup.XXXXXX, cp -p original,
install -m755 candidate, cmp readback, sync, and print INSTALLED backup path.
Backup/install NOT yet executed or confirmed. No reboot requested yet.

User now reports SAVED from guarded copy to /root/kde-good. No boot launcher
change yet. Next prepare unique candidate /root/kde-start.XXXXXX via mktemp
(shell variable k), first10 lines of trusted installed basic-kde-session,
then persistent XDG_CONFIG_HOME, unset stale bus/display fields, same tested
dbus-run-session KWin + Plasma/Konsole without timeout. Syntax-check and show
last4 lines before installation. Host reference candidate:
probe/native-kde-clean-session-20260912.sh. Preserve wrapper root UUID guard.
Target script preparation, backup, installation, and reboot are pending.

User: "holy crap soo much more responsive" after the 90-second test adding
plasmashell --no-respawn and Konsole to clean-config KWin. Webcam
logs/native-kde-clean-desktop-responsive-20260912.jpg confirms wallpaper,
panel and graphical terminal. Same parent shell renderer exports and fresh
XDG_CONFIG_HOME; no explicit 2x scaling in this test. One CPU/software GPU,
same native SSD kernel and drivers. This is a responsiveness improvement,
not proof of sustained stability, exact offending old setting, or reboot fix.

Next preserve current temp config in NEW /root/kde-good, guarded against an
empty source variable or existing destination, after timeout returns to the
original shell. Copy NOT yet run. Original /root/.config and installed boot
launcher unchanged. Need backup-backed persistent launcher using verified
exports + preserved config + fresh D-Bus + Plasma/Konsole, then reboot test.
Do not reboot before persistent repair; old startup still uses old config.

Latest clean-test log photo logs/native-kde-clean-log-20260912.jpg confirms
source/export/timeout launch sequence in same shell (initial incomplete
continuation canceled with Ctrl+C, then full launch retried). Terminal window
was visible in previous photo; test returned to text shell and chvt/head ran.
First20 lines of NEW /run/kde-clean.log show normal known DRM/EDID/PipeWire
warnings and portal activation, but NOT repeated GL texture allocation errors
that appear in the OLD log above it on screen. This is only a head excerpt,
not a full-log absence claim. Input responsiveness still unreported.
Next proposed: same-shell/same temp configuration and rendering exports,
90-second bounded KWin with plasmashell --no-respawn plus Konsole, separate
/run/kde-desktop.log. Do not change scaling/config/backend in this comparison.
Not persistent; original startup remains unchanged until usability confirmed.

Follow-up: user reports running the grouped clean-config test, stopping input
before the final chvt/head commands. Webcam photo
logs/native-kde-clean-timeout-followup-20260912.jpg shows a small graphical
terminal window on black background. Window visibility confirmed; typing
responsiveness, actual launched process environment, timeout completion,
and /run/kde-clean.log are not yet verified. Do not infer lag resolved.
Final chvt/head must run in original text shell, not graphical Konsole.

Latest verified-parent-environment launch was reported BLACK. Photo
logs/native-kde-verified-baseline-failure-20260912.jpg now confirms the
/run/kde-test.log head: repeated generating OpenGL texture handle failed,
alongside DRM devnode/EDID and PipeWire warnings and portal activation.
User has recovered a responsive shell. Missing exports are NOT a complete
explanation/fix. Exact installed KWin version remains unknown; upstream
Plasma/6.6 was only a reference. Old PID2238 stopped; new PID unknown.

Next proposed test (not executed yet): in ONE shell stop test KWin, source
trusted installed launcher lines4..10, set fresh mktemp XDG_CONFIG_HOME,
run fresh D-Bus KWin+Konsole under timeout45s/kill-after5s with new log, then
chvt back to current XDG_VTNR and display log head. This combines the verified
renderer exports and clean configuration for the first time, preserves
original configuration, and bounds another possible black-screen wait.
No reboot, persistent launcher change, kernel change, or daily macOS write.

## Latest runtime evidence supersedes earlier clean-config interpretation

Follow-up native-kde-baseline-env-verified-20260912 photo now verifies all
baseline renderer exports in current tty2 shell after sourcing trusted lines:
QPainter/software Qt/llvmpipe/LP_NUM_THREADS1/force software cursor/LIBGL1,
Wayland Qt and desktop session variables. No XDG_CONFIG_HOME (original config).
Stop of old KWin was user-confirmed. Next guarded same-shell launch with
fresh D-Bus and Konsole, stderr/stdout saved to /run/kde-test.log. Do not change
TTY/login between verified environment and launch. Result pending. GUI may
occupy VT2 now rather than previous VT4, since this shell has VTNR2.

Photo native-kde-live-environment-20260912 shows allowlisted process startup
environment twice: XDG_SESSION_TYPE=tty, XDG_VTNR=4, session ID4 and runtime
directory, but no KWIN/Qt/GALLIUM/LP settings and no XDG_CONFIG_HOME. This is
not the intended test environment. Shell exports probably did not survive
console/login transitions; exact sequence not known. Do not claim temporary
config fixed startup, or missing LP alone caused lag. Need reproduce actual
working script settings in ONE shell and verify process environment afterward.
Next stop current test, then source only trusted export/setup lines4..10 of
the photographed installed basic-kde-session, excluding set-e/daemon/exec.
That restores all baseline rendering/session exports without manual retyping
every setting. Keep tty2 until launching, no intervening login/console change.
No persistence or kernel/driver change needed for this control.

## User baseline is important

User explicitly reports BOTH previous RAM-root and SSD-root desktop sessions
were smooth, not just visible. Existing KDE-CHECKPOINT.md also records actual
keyboard interaction in first RAM-root session. Treat today's severe lag as
a regression. One CPU/software rendering alone does not explain the change.
Do not dismiss the earlier smooth performance as an untested impression.

## Separate the failures

1. Original autonomous SSD KDE reached desktop, then a subsequent boot/launch
   went black. Installed basic-kde-session was photographed and had its
   software rendering exports. Original black-screen cause remains unknown.
2. Minimal direct KWin + Konsole with existing config also reported black.
3. Minimal direct KWin + Konsole using mktemp XDG_CONFIG_HOME became visible,
   with pointer movement, but severe lag and intermittent duplicated keys.
   Config is implicated but no ABA test excludes timing/restart effects.
4. Text tty2 typing is normal. GUI top had ~34% user/~65% idle in two samples,
   later ~62% KWin in a retained frame. No memory/swap pressure observed.
5. Changing KWin PID2238 main thread from RR priority1 to OTHER priority0 did
   not improve lag, per user. Restore baseline after identity verification.

## Known-working startup vs current minimal test

The original `basic-kde-session.sh` and `basic-kde-clients.sh` explicitly set:

```
LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe LP_NUM_THREADS=1
QT_QUICK_BACKEND=software KWIN_COMPOSE=Q KWIN_FORCE_SW_CURSOR=1
XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true
```

They also used fixed /run/user/0/bus, fixed wayland-0, a client script that
requested 2x scale, and D-Bus activation environment propagation.

The manually shortened test explicitly exported only:

```
KWIN_COMPOSE=Q QT_QUICK_BACKEND=software
XDG_RUNTIME_DIR=/run/user/0 LIBGL_ALWAYS_SOFTWARE=1
QT_QPA_PLATFORM=wayland KWIN_FORCE_SW_CURSOR=1
XDG_CONFIG_HOME="$(mktemp -d)"
```

Then `dbus-run-session kwin_wayland --drm --no-lockscreen -- konsole`.
Thus renderer choice/thread limit and desktop session variables were not
explicitly carried into this test. The actual process environment is still
unread; don't claim those variables are definitely absent or causal yet.
Missing llvmpipe variables may not affect QPainter paths. Need evidence.

## Safe next checks

- Recover to known tty2 via `chvt 2` if still in GUI (probably tty4).
- Verify PID2238 still KWin, read only allowlisted relevant environment,
  recording actual XDG_CONFIG_HOME path too. Don't dump credentials/environment
  wholesale. Suggested input split into short continuation lines:
  `tr '\0' '\n' < /proc/2238/environ |`
  `grep -E '^(KWIN|QT_|GALLIUM|LP_|XDG_)'`
- Restore observed main-thread scheduler baseline for same process:
  `chrt -r -R -p 1 2238` (original RR + RESET_ON_FORK priority1).
- Reproduce original renderer/session settings in a controlled test while
  preserving configs/logs and the responsive text console. Account for old
  fixed session bus still potentially alive; don't blindly rerun the original
  launcher into a socket collision. No restart scheduled yet.
- If still laggy, targeted tracing is needed rather than further guesses.

No commits. No daily macOS writes. No kernel/loader/module changes during
this userspace sequence. No further reboot needed to perform these checks.
