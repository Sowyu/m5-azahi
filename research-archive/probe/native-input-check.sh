#!/bin/bash
# One-shot evidence to the physical console; all writes are in the RAM root.
exec > /dev/tty1 2>&1
for font in latarcyrheb-sun32 ter-v32n LatGrkCyr-12x22; do
    if setfont -C /dev/tty1 "$font" 2>/dev/null; then break; fi
done
# Some minimal images do not ship those named fonts. The standard kbd tool
# can double its default font; failure is harmless to the input checkpoint.
setfont -C /dev/tty1 -d 2>/dev/null || true
echo
echo '=== NATIVE RAM BOOT CHECK ==='
uname -r
printf 'CPU online: '; cat /sys/devices/system/cpu/online
printf 'PID 1: '; cat /proc/1/comm
echo 'Waiting up to 35 seconds for built-in input...'
for ((attempt=0; attempt<35; attempt++)); do
    count=0
    for node in /sys/class/input/event*/device/name; do
        test -f "$node" && count=$((count+1))
    done
    test "$count" -ge 2 && break
    sleep 1
done
for node in /sys/class/input/event*/device/name; do
    test -f "$node" && cat "$node"
done
echo '=== NATIVE_INPUT_CHECK_DONE ==='
echo 'No SSD installation. This root is in RAM.'
