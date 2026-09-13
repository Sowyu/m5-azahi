#!/bin/sh
# Full KDE session, done properly.
#
# Fixes three mistakes from the earlier attempts:
#  1. The 9p share was NOT visible inside the chroot, so every redirect to
#     /mnt/kde/log/... failed and the command died before running - which is
#     why plasmashell never started and there was no shell.log. Bind-mount it.
#  2. Everything was launched OUTSIDE the session's private dbus, so it could
#     not talk to kwin ("Spectacle requires KWin, which does not seem to be
#     available"). Start dbus at a FIXED socket we can rejoin later.
#  3. kded6 span forever re-activating org.bluez.obex, eating the single core.
#     No bluetooth here - mask it.
L=/mnt/kde/log
exec >"$L/session.log" 2>&1
set -x

pkill -f startplasma; pkill -f kwin_wayland; pkill -f plasmashell; sleep 3

mkdir -p /mnt/kdeovl/mnt/kde
mountpoint -q /mnt/kdeovl/mnt/kde || mount --bind /mnt/kde /mnt/kdeovl/mnt/kde

# No bluetooth stack in this guest; stop kded from spinning on it.
mkdir -p /mnt/kdeovl/etc/xdg
printf '[Module-bluedevil]\nautoload=false\n[Module-obexftp]\nautoload=false\n' \
  > /mnt/kdeovl/etc/xdg/kded6rc

chroot /mnt/kdeovl /bin/sh -c '
  export XDG_RUNTIME_DIR=/run/user/0 HOME=/root
  export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
  export QT_QUICK_BACKEND=software XDG_SESSION_TYPE=wayland
  export XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true
  export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus
  mkdir -p /run/user/0
  dbus-daemon --session --address="$DBUS_SESSION_BUS_ADDRESS" --nofork --print-address &
  sleep 3
  exec startplasma-wayland
' >"$L/session-inner.log" 2>&1 &
echo "session pid $!"

for i in 1 2 3 4 5 6 7 8; do
  sleep 20
  echo "--- t=$((i*20))s ---"
  ps ax 2>/dev/null | grep -E "plasmashell|kwin_wayland|startplasma" | grep -v grep
done
