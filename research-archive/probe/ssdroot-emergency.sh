#!/bin/bash
# Explicit offline bring-up console IN INITRD ONLY; never modifies passwords.
[[ -e /etc/initrd-release ]] || exit 1
setfont -C /dev/tty1 -d 2>/dev/null || true
dmesg -n 3 || true
echo '=== SSDROOT BOOT STOPPED: LOCAL DIAGNOSTIC CONSOLE ==='
echo 'No automatic repair or guard bypass will be performed.'
for stage in prepare configure; do
    if [[ -f /run/ssdroot-$stage.log ]]; then
        echo "--- $stage final lines ---"
        tail -12 "/run/ssdroot-$stage.log"
    else
        echo "$stage: no stage log exists"
    fi
done
echo '--- switch-root error ---'
journalctl -b -u initrd-switch-root.service --no-pager -n 12 -o cat || true
echo '--- current mount and guard state ---'
findmnt -n -o SOURCE,FSTYPE,OPTIONS /sysroot || true
printf 'guard armed: '
cat /sys/module/nvme_apple/parameters/root_write_armed 2>/dev/null || echo absent
echo 'Logs: /run/ssdroot-prepare.log, /run/ssdroot-configure.log, /run/ssdroot-handoff.log'
echo 'Leave this console open. Do not force writable mounts or repeat setup.'
export PS1='ssd-initrd# '
exec /bin/bash --noprofile --norc -i
