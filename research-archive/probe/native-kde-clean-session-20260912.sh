#!/bin/sh
# Candidate SSD launcher; not installed on target by host-side creation.
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
