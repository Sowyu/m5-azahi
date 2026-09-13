#!/bin/bash
# Started in the existing systemd-supervised autologin VT session.
set -eu
mkdir -p /run/user/0 /root/bringup-disabled-plugins
chmod 700 /run/user/0
for plugin in bluedevil device_automounter baloosearchmodule kded_plasma_welcome; do
    path="/usr/lib64/qt6/plugins/kf6/kded/$plugin.so"
    if test -f "$path"; then mv "$path" /root/bringup-disabled-plugins/; fi
done
echo 'Starting native software-rendered KDE from RAM; no SSD install.'
exec /bin/sh /usr/local/bin/basic-kde-session > /run/native-kde-session.log 2>&1
