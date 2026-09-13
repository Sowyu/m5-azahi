#!/bin/bash
# RAM-only evidence collection. Never mount or repair any SSD filesystem.
set -euo pipefail
exec > /dev/tty1 2>&1
: > /run/native-ssd-ro-requested
: > /run/native-ssd-ro.log
setfont -C /dev/tty1 -d 2>/dev/null || true
trap 'echo "NATIVE_SSD_TEST_STOPPED: see /run/native-ssd-ro.log"' ERR
echo '=== NATIVE SSD READ-ONLY TEST ==='
uname -r
printf 'CPU online: '; cat /sys/devices/system/cpu/online
printf 'PID 1: '; cat /proc/1/comm
for node in /sys/class/input/event*/device/name; do
    test ! -f "$node" || cat "$node"
done
# New DT compatibles do not match stock module aliases. Load only after
# dependency indexes have incorporated the two diagnostic modules.
depmod -a
python3 -u /usr/local/libexec/probe-ssd-readonly.py > /run/native-ssd-ro.log 2>&1 || {
    tail -30 /run/native-ssd-ro.log
    dmesg | tail -25
    exit 1
}
lsblk -o NAME,SIZE,RO,TYPE
for device in /dev/nvme0n1 /dev/nvme0n1p3; do
    python3 -u /usr/local/libexec/verify-ssd-reads.py "$device" | tee -a /run/native-ssd-ro.log
done
python3 - <<'PY'
from pathlib import Path
log = Path('/run/native-ssd-ro.log').read_text()
for digest in ('0831f0559b5954235f96f43f6c75c41b70ee45ab153063ccba95a02baa820339',
               'a5c325dc0f058ba496143d3553f9cb9832c7a0e875cb83846d5698d96f7b014c'):
    assert log.count(digest) == 4, 'Read digest differs from verified HV baseline'
for disk in Path('/sys/block').glob('nvme*n*'):
    assert (disk / 'ro').read_text().strip() == '1'
    stats = (disk / 'stat').read_text().split()
    assert int(stats[4]) == 0 and int(stats[6]) == 0, 'Nonzero write statistics'
    print('ZERO_WRITES', disk.name)
assert Path('/sys/class/nvme/nvme0/state').read_text().strip() == 'live'
print('NATIVE_SSD_READS_PASS: 128 MiB, hashes match, zero completed writes')
PY
echo 'Root remains in RAM. macOS and partition layout unchanged.'
echo '=== NATIVE_SSD_RO_CHECK_DONE ==='
