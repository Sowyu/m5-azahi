#!/bin/bash
set -euo pipefail
exec > /dev/tty1 2>&1
: > /run/native-rootguard-requested
setfont -C /dev/tty1 -d 2>/dev/null || true
trap 'echo "ROOTGUARD_TEST_STOPPED: see /run/native-rootguard.log; do not mount SSD writable"' ERR
echo '=== NATIVE ROOT-ONLY WRITE TEST; OS STILL IN RAM ==='
printf 'CPU online: '; cat /sys/devices/system/cpu/online
depmod -a
python3 -u /usr/local/libexec/probe-ssd-readonly.py > /run/native-rootguard.log 2>&1 || {
    tail -30 /run/native-rootguard.log
    dmesg | tail -20
    exit 1
}
python3 -u /usr/local/libexec/native-rootguard-test.py 2>&1 | tee -a /run/native-rootguard.log
echo '=== ROOTGUARD_CHECK_DONE; leave running for inspection ==='
