#!/bin/sh
# Bring up the full desktop (panel + wallpaper) and capture the screen from
# INSIDE the guest, so we can read it properly instead of photographing a
# bright panel in a dark room with a webcam.
L=/mnt/kde/log
exec >"$L/desktop.log" 2>&1
set -x

RUN='chroot /mnt/kdeovl /bin/sh -c'
ENVS='export XDG_RUNTIME_DIR=/run/user/0 HOME=/root WAYLAND_DISPLAY=wayland-0
      export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
      export QT_QUICK_BACKEND=software XDG_SESSION_TYPE=wayland
      export XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true'

# plasmashell draws the panel, wallpaper and launcher - the desktop proper.
$RUN "$ENVS; pgrep -x plasmashell >/dev/null || (plasmashell >$L/shell.log 2>&1 &)"
sleep 60

echo "=== what is running ==="
ps ax 2>/dev/null | grep -E "plasmashell|kwin|konsole|Welcome" | grep -v grep

echo "=== screenshot tools available ==="
$RUN "ls /usr/bin/spectacle /usr/bin/grim /usr/bin/import 2>&1"

# Try each capture method; whichever works lands a PNG on the 9p share.
$RUN "$ENVS; spectacle -b -n -f -o $L/screen.png" 2>&1
sleep 20
$RUN "$ENVS; grim $L/screen-grim.png" 2>&1
sleep 10
ls -la $L/*.png 2>&1
