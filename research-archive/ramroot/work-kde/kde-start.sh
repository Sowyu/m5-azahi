#!/bin/sh
# Bring up a Wayland compositor from the 9p-backed KDE rootfs.
#
# Changes from attempt 1 (which left a black screen and no diagnostics):
#  - Do NOT unbind fbcon up front. fbcon is a DRM *client*, not master, so
#    kwin can usually take master anyway. Unbinding first meant that when the
#    compositor failed there was nothing drawing at all - just a dark panel.
#  - Write every log to the 9p share, which the HOST can read directly. The
#    vuart console has repeatedly gone silent mid-session; this bypasses it.
L=/mnt/kde/log
mkdir -p "$L" 2>/dev/null
exec >"$L/start.log" 2>&1
set -x

modprobe overlay
mkdir -p /run/ovl /mnt/kdeovl
mountpoint -q /mnt/kdeovl || {
  mount -t tmpfs -o size=8G tmpfs /run/ovl
  mkdir -p /run/ovl/upper /run/ovl/work
  mount -t overlay overlay \
    -o lowerdir=/mnt/kderoot,upperdir=/run/ovl/upper,workdir=/run/ovl/work \
    /mnt/kdeovl || exit 1
}

for d in dev proc sys tmp run; do mkdir -p "/mnt/kdeovl/$d"; done
mountpoint -q /mnt/kdeovl/dev  || mount --bind /dev /mnt/kdeovl/dev
mountpoint -q /mnt/kdeovl/proc || mount -t proc proc /mnt/kdeovl/proc
mountpoint -q /mnt/kdeovl/sys  || mount -t sysfs sys /mnt/kdeovl/sys
mountpoint -q /mnt/kdeovl/run  || mount -t tmpfs tmpfs /mnt/kdeovl/run
mkdir -p /mnt/kdeovl/run/user/0 && chmod 700 /mnt/kdeovl/run/user/0

echo "=== drm ==="; ls -l /dev/dri/ 2>&1
echo "=== who holds card0 ==="; fuser -v /dev/dri/card0 2>&1
echo "=== fbcon binding ==="; for v in /sys/class/vtconsole/vtcon*; do echo "$v: $(cat $v/name 2>/dev/null) bind=$(cat $v/bind 2>/dev/null)"; done

chroot /mnt/kdeovl /bin/sh -c '
  export XDG_RUNTIME_DIR=/run/user/0
  export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
  export QT_QUICK_BACKEND=software XDG_SESSION_TYPE=wayland
  export KWIN_COMPOSE=Q       # force QPainter (no GL) - safest on simpledrm
  export KWIN_DRM_NO_AMS=1
  kwin_wayland --drm --no-lockscreen -- konsole
' >"$L/kwin.log" 2>&1 &
KPID=$!
echo "kwin pid $KPID"

for i in 1 2 3 4 5 6; do
  sleep 10
  echo "--- t=$((i*10))s ---"
  ps ax 2>/dev/null | grep -E "kwin|konsole" | grep -v grep
  tail -5 "$L/kwin.log" 2>/dev/null
done
echo "=== done ==="
