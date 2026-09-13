#!/bin/sh
# Kill the dbus spin loop, then start plasmashell inside the live session.
#
# kded6 has been re-activating org.bluez.obex in a tight loop since the session
# started. There is no bluetooth in this guest, and with ONE cpu core that loop
# starves everything else - which is why plasmashell never appeared. The
# kded6rc autoload=false did not take, so just kill the offenders.
L=/mnt/kde/log
exec >"$L/shell-start.log" 2>&1
set -x

echo "=== cpu hogs before ==="
ps aux 2>/dev/null | sort -rnk3 | head -6

pkill -f obexd; pkill -f kded6; sleep 5

echo "=== cpu hogs after ==="
ps aux 2>/dev/null | sort -rnk3 | head -6

# Join the session bus we started at a known path and launch the shell.
chroot /mnt/kdeovl /bin/sh -c '
  export XDG_RUNTIME_DIR=/run/user/0 HOME=/root
  export WAYLAND_DISPLAY=wayland-0
  export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus
  export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
  export QT_QUICK_BACKEND=software XDG_SESSION_TYPE=wayland
  export XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true
  plasmashell --no-respawn
' >"$L/plasmashell.log" 2>&1 &
echo "plasmashell pid $!"

for i in 1 2 3 4 5 6; do
  sleep 20
  echo "--- t=$((i*20))s ---"
  ps ax 2>/dev/null | grep -E "plasmashell|kwin_wayland" | grep -v grep
  tail -3 "$L/plasmashell.log" 2>/dev/null
done
