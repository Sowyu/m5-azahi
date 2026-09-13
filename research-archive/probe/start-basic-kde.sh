#!/bin/sh
set -eu
root=/mnt/basic-kde
test -e /run/basic-kde-prepared
test -x "$root/usr/bin/kwin_wayland"
test -x "$root/usr/bin/plasmashell"
# Disable absent-hardware services in the disposable overlay only. The
# original image stays read-only. Move plugins outside Qt's discovery path.
mkdir -p "$root/root/bringup-disabled-plugins"
for plugin in bluedevil device_automounter baloosearchmodule kded_plasma_welcome; do
    path="$root/usr/lib64/qt6/plugins/kf6/kded/$plugin.so"
    if test -f "$path"; then
        mv "$path" "$root/root/bringup-disabled-plugins/"
    fi
done
systemd-run --unit=basic-kde --property=Type=exec --property=Restart=no \
    --property=TimeoutStopSec=10 \
    --property=StandardOutput=append:/run/basic-kde-session.log \
    --property=StandardError=append:/run/basic-kde-session.log \
    /usr/sbin/chroot "$root" /bin/sh /mnt/inputfiles/bringup-20260906/basic-kde-session.sh
echo BASIC_KDE_SERVICE_STARTED
