#!/bin/sh
export HOME=/root USER=root LOGNAME=root SHELL=/bin/bash
cd /root
export XDG_RUNTIME_DIR=/run/user/0 XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe LP_NUM_THREADS=1
export QT_QUICK_BACKEND=software
export WAYLAND_DISPLAY=wayland-0
export QT_QPA_PLATFORM=wayland
kscreen-doctor output.1.scale.2 > /run/kde-scale.log 2>&1
dbus-update-activation-environment HOME USER LOGNAME SHELL WAYLAND_DISPLAY XDG_RUNTIME_DIR XDG_SESSION_TYPE XDG_CURRENT_DESKTOP QT_QUICK_BACKEND LIBGL_ALWAYS_SOFTWARE
plasmashell --no-respawn > /run/plasmashell.log 2>&1 &
konsole --separate > /run/konsole.log 2>&1 &
wait
