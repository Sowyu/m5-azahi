#!/bin/bash
exec > /dev/tty1 2>&1
setfont -C /dev/tty1 -d 2>/dev/null || true
echo '=== NATIVE SSD BOOT INPUT CHECK ==='
uname -r
findmnt -n -o SOURCE,FSTYPE,OPTIONS /
printf 'CPU online: '; cat /sys/devices/system/cpu/online
for ((attempt=0; attempt<35; attempt++)); do
    count=0
    for node in /sys/class/input/event*/device/name; do
        test ! -f "$node" || count=$((count+1))
    done
    test "$count" -ge 2 && break
    sleep 1
done
for node in /sys/class/input/event*/device/name; do
    test ! -f "$node" || cat "$node"
done
echo '=== SSD_INPUT_CHECK_DONE; KDE root is on SSD, kernel was loaded over USB ==='
