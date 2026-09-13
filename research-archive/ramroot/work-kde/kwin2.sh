#!/bin/sh
# Retry the compositor with ATOMIC modesetting.
#
# Attempt 1 set KWIN_DRM_NO_AMS=1, which forces kwin onto the legacy DRM API.
# simpledrm is atomic-only, so kwin could not configure a plane and reported
# "Failed to find a working output layer configuration!" - black screen with
# kwin_wayland and konsole both alive. Drop that variable.
L=/mnt/kde/log
exec >"$L/kwin2-start.log" 2>&1
set -x
pkill -f kwin_wayland; pkill konsole; sleep 3

chroot /mnt/kdeovl /bin/sh -c '
  export XDG_RUNTIME_DIR=/run/user/0
  export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
  export QT_QUICK_BACKEND=software XDG_SESSION_TYPE=wayland
  export KWIN_COMPOSE=Q
  export KWIN_FORCE_SW_CURSOR=1
  kwin_wayland --drm --no-lockscreen -- konsole
' >"$L/kwin2.log" 2>&1 &
echo "kwin pid $!"
for i in 1 2 3 4 5; do
  sleep 10
  echo "--- t=$((i*10))s ---"
  ps ax 2>/dev/null | grep -E "kwin|konsole" | grep -v grep
  grep -aE "output layer|Atomic|present|Failed" "$L/kwin2.log" 2>/dev/null | tail -4
done
