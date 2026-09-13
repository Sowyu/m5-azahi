#!/bin/bash
set -eu
[[ $(findmnt -n -o UUID /) == PRIVATE-UUID-REMOVED ]] || exit 1
echo 'KDE root is on the internal SSD. One CPU; software rendering; USB-loaded kernel.'
mkdir -p /run/user/0 /root/bringup-disabled-plugins
chmod 700 /run/user/0
for plugin in bluedevil device_automounter baloosearchmodule kded_plasma_welcome; do
    path=/usr/lib64/qt6/plugins/kf6/kded/$plugin.so
    if [[ -f $path ]]; then mv "$path" /root/bringup-disabled-plugins/; fi
done
exec /bin/sh /usr/local/bin/basic-kde-session > /run/native-ssd-kde.log 2>&1
