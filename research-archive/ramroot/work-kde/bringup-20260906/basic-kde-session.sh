#!/bin/sh
# Runs inside the RAM overlay, supervised by basic-kde.service in the guest.
set -eu
export HOME=/root USER=root LOGNAME=root SHELL=/bin/bash
cd /root
export XDG_RUNTIME_DIR=/run/user/0 XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe LP_NUM_THREADS=1
export QT_QUICK_BACKEND=software KWIN_COMPOSE=Q KWIN_FORCE_SW_CURSOR=1
export QT_QPA_PLATFORM=wayland
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus
unset KWIN_DRM_NO_AMS DISPLAY
dbus-daemon --session --address="$DBUS_SESSION_BUS_ADDRESS" --fork
exec kwin_wayland --drm --no-lockscreen --socket wayland-0 -- "/bin/sh /mnt/inputfiles/bringup-20260906/basic-kde-clients.sh"
