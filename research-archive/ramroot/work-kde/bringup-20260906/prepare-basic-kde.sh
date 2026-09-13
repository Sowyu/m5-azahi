#!/bin/sh
# Guest-only: read-only host image + RAM overlay. Never touches NVMe.
set -eu
image=/mnt/inputfiles/root.img
lower=/mnt/basic-kde-lower
root=/mnt/basic-kde
test -r "$image"
test ! -e /run/basic-kde-prepared
test ! -e "$root/usr/bin/kwin_wayland"
modprobe loop
modprobe overlay
mkdir -p "$lower" "$root" /run/basic-kde-overlay
loopdev=$(losetup --find --show --read-only "$image")
mount -t btrfs -o ro,rescue=nologreplay,subvol=root "$loopdev" "$lower"
mount -t tmpfs -o size=8G,mode=755 tmpfs /run/basic-kde-overlay
mkdir -p /run/basic-kde-overlay/upper /run/basic-kde-overlay/work
mount -t overlay overlay -o lowerdir="$lower",upperdir=/run/basic-kde-overlay/upper,workdir=/run/basic-kde-overlay/work "$root"
for dir in dev proc sys run tmp mnt/inputfiles; do mkdir -p "$root/$dir"; done
mount --rbind /dev "$root/dev"
mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"
mount --rbind /sys "$root/sys"
mount --make-rslave "$root/sys"
mount -t tmpfs -o mode=755 tmpfs "$root/run"
mount -t tmpfs -o mode=1777,size=2G tmpfs "$root/tmp"
mkdir -p "$root/run/udev" "$root/run/dbus" "$root/run/user/0"
chmod 700 "$root/run/user/0"
mount --bind /run/udev "$root/run/udev"
mount --bind /run/dbus "$root/run/dbus"
mount --bind /mnt/inputfiles "$root/mnt/inputfiles"
test -x "$root/usr/bin/kwin_wayland"
test -x "$root/usr/bin/plasmashell"
touch /run/basic-kde-prepared
echo BASIC_KDE_ROOT_READY
chroot "$root" /usr/bin/kwin_wayland --help
find "$root/usr/lib64/qt6/plugins" -iname '*blue*' -o -iname '*obex*'
