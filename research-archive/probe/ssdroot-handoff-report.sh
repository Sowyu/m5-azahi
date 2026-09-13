#!/bin/bash
# Read-only observations immediately before switch-root. No mount or disk I/O
# commands that can mutate data, and no arming/disarming of the driver.
[[ -e /etc/initrd-release ]] || exit 1
setfont -C /dev/tty1 -d 2>/dev/null || true
report() {
    echo '=== SSDROOT HANDOFF STATE ==='
    printf 'guard armed: '
    cat /sys/module/nvme_apple/parameters/root_write_armed 2>/dev/null || echo absent
    echo 'mounted /sysroot:'
    findmnt -n -o SOURCE,FSTYPE,OPTIONS /sysroot || true
    for path in /sysroot/etc/os-release /sysroot/usr/lib/os-release /sysroot/sbin/init /sysroot/usr/lib/systemd/systemd; do
        if [[ -e $path ]]; then echo "PRESENT $path"; else echo "MISSING $path"; fi
    done
    echo 'boot-stage unit state:'
    systemctl show ssdroot-prepare.service sysroot.mount ssdroot-configure.service \
        -p Id -p ActiveState -p SubState -p Result -p ExecMainStatus --no-pager || true
    echo '=== END HANDOFF STATE ==='
}
report > /run/ssdroot-handoff.log 2>&1
cat /run/ssdroot-handoff.log
exit 0
