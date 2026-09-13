# Basic KDE live checkpoint — 2026-09-06

**Later state:** this session was stopped cleanly for PRIVATE-USER's CPU/native-boot
request. PID 34774 is no longer the current runner. These are reproduction
notes for the verified desktop, not a claim that it is still running.
See the newest `PROGRESS.md` section before operating the target.

KDE wallpaper, bottom panel, launcher and Konsole are visible. PRIVATE-USER physically
typed `echo kde_ok` and its output is visible in
`logs/basic-kde-screen4-20260906.jpg`. KWin owns both built-in evdev nodes.
This is a basic Wayland desktop, not a full login/session-manager setup.

## Current live guest

- Host runner PID at checkpoint: 34774. Verify before signaling it.
- Host logs: `logs/input-ssd-limit-boot-20260906/console.log` and
  `logs/input-ssd-limit-launch-20260906.log`.
- `basic-kde.service`: KWin (PID 1413 at checkpoint) and private session bus.
- `basic-kde-clients.service`: Plasma + Konsole in this first live run.
- Guest root: `/mnt/basic-kde`, overlay on read-only `/mnt/basic-kde-lower`.
- Lower image `/mnt/inputfiles/root.img` via read-only `/dev/loop1`.
- All SSD namespaces still read-only and unmounted. Do not alter partitions.
- 2x display scale, 1512x945 logical desktop; software rendering, one core.
- No new physical reboot was required.

Leave this running for the user. Settings and files inside this desktop are
in RAM and do not survive reboot. The host image is unchanged. No networking,
audio, suspend, acceleration, or full desktop-service support is claimed.
The first Konsole shows an empty-shell fallback warning; SHELL=/bin/bash is
now explicit in the startup scripts for subsequent launches. Its shell was
functional and the user demonstrated keyboard input in it.

## Reproduce on a fresh working RAM-root guest with inputfiles 9p mounted

Run via `probe/guest-command.py`, not a second proxy connection:

```sh
sh /mnt/inputfiles/bringup-20260906/prepare-basic-kde.sh > /run/basic-kde-prepare.log 2>&1 &
```

Wait for `BASIC_KDE_ROOT_READY` and preparation completion, then:

```sh
sh /mnt/inputfiles/bringup-20260906/start-basic-kde.sh > /run/basic-kde-start.log 2>&1 &
```

The prepared root is one-shot per boot. Do not run preparation twice. It
mounts the Btrfs lower with `ro,rescue=nologreplay,subvol=root`, uses a tmpfs
overlay, shares /dev and /sys, and exposes guest udev/system bus sockets.
It never opens an NVMe disk. An initial unsupported standalone `nologreplay`
option was corrected to `rescue=nologreplay`; its unmounted loop was detached
before retry. Do not use old broad-pkill KDE scripts in the host live kit.

The startup script moves these plugins outside Qt discovery in the overlay:
bluedevil, device_automounter, baloosearchmodule, kded_plasma_welcome. This
avoids absent Bluetooth retries, disk automounting, indexing and first-run
welcome activity. Original image files remain untouched.

KWin treats each positional argument as a complete application command;
the client script must be one quoted command string. Startup now does that.
No `KWIN_DRM_NO_AMS`: simpledrm requires atomic modesetting. Do not unbind
fbcon manually. Fixed session bus: `/run/user/0/bus` inside the chroot.

## Logs and supervision

```sh
systemctl status basic-kde basic-kde-clients --no-pager
tail -n 30 /run/basic-kde-session.log
tail -n 30 /mnt/basic-kde/run/plasmashell.log
tail -n 20 /mnt/basic-kde/run/konsole.log
```

To stop ONLY this desktop if needed, use `systemctl stop basic-kde-clients
basic-kde`. Do not stop the hypervisor or power-cycle the target for desktop
configuration issues. Do not clear or unmount the RAM overlay while clients
are running. Use the existing serial command sender for diagnostics.
