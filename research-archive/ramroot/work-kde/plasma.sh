#!/bin/sh
# Full Plasma desktop: panel, wallpaper, launcher - not just a bare compositor
# with one window. startplasma-wayland brings up kwin AND plasmashell plus the
# session services, instead of kwin with a single client.
L=/mnt/kde/log
exec >"$L/plasma-start.log" 2>&1
set -x
pkill -f kwin_wayland; pkill konsole; sleep 3

chroot /mnt/kdeovl /bin/sh -c '
  export XDG_RUNTIME_DIR=/run/user/0
  export HOME=/root
  export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
  export QT_QUICK_BACKEND=software XDG_SESSION_TYPE=wayland
  export KWIN_COMPOSE=Q KWIN_FORCE_SW_CURSOR=1
  export XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true
  # NO KWIN_DRM_NO_AMS: simpledrm is atomic-only, forcing legacy gives a
  # black screen ("Failed to find a working output layer configuration").
  dbus-run-session startplasma-wayland
' >"$L/plasma.log" 2>&1 &
echo "plasma pid $!"

for i in 1 2 3 4 5 6 7 8 9; do
  sleep 15
  echo "--- t=$((i*15))s ---"
  ps ax 2>/dev/null | grep -E "kwin|plasmashell|startplasma" | grep -v grep
done
