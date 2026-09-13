#!/bin/bash
# Runs ONLY as PID 1 inside the no-disk/no-network test VM.
set -euo pipefail
BB=/usr/local/libexec/busybox.static
fail() { echo "COURIER_VM_FAIL: $*"; "$BB" poweroff -f; }
trap 'fail "line $LINENO"' ERR
[[ $$ == 1 ]] || exit 1
"$BB" mount -t proc proc /proc
"$BB" mount -t sysfs sysfs /sys
"$BB" mount -t devtmpfs devtmpfs /dev
"$BB" mkdir -p /run
"$BB" mount -t tmpfs tmpfs /run
echo COURIER_VM_START
"$BB" sha256sum /usr/local/libexec/busybox.static /bin/bash /usr/bin/findmnt
[[ ! -e /usr/bin/mktemp && ! -e /bin/mktemp ]]
old_status=0
/bin/bash /azahi-usb-stage.sh >/run/old-courier.log 2>&1 || old_status=$?
"$BB" cat /run/old-courier.log
[[ $old_status == 127 && ! -e /run/azahi-usb-20260913 ]]
echo COURIER_VM_OLD_FAILURE_REPRODUCED
/bin/bash /courier-v2.sh
[[ -d /run/azahi-usb-20260913 ]]
(cd /run/azahi-usb-20260913 && "$BB" sha256sum -c SHA256SUMS)
echo COURIER_VM_SUCCESS_EMPTY_PATH
if /bin/bash /courier-v2.sh; then fail 'existing destination accepted'; fi
(cd /run/azahi-usb-20260913 && "$BB" sha256sum -c SHA256SUMS)
echo COURIER_VM_EXISTING_PRESERVED
"$BB" mv /run/azahi-usb-20260913 /run/saved-good
"$BB" cp /azahi-usb-20260913/azahi-usb-overlay.ko /run/overlay-original
printf corrupt >/azahi-usb-20260913/azahi-usb-overlay.ko
if /bin/bash /courier-v2.sh; then fail 'corrupt payload accepted'; fi
[[ ! -e /run/azahi-usb-20260913 ]]
echo COURIER_VM_CORRUPTION_REJECTED
"$BB" cp /run/overlay-original /azahi-usb-20260913/azahi-usb-overlay.ko
"$BB" mv /azahi-usb-20260913/azahi-usb-overlay.ko /run/overlay-real
"$BB" ln -s /run/overlay-real /azahi-usb-20260913/azahi-usb-overlay.ko
if /bin/bash /courier-v2.sh; then fail 'source symlink accepted'; fi
[[ ! -e /run/azahi-usb-20260913 ]]
echo COURIER_VM_SYMLINK_REJECTED
"$BB" mount -t ramfs ramfs /run
if /bin/bash /courier-v2.sh; then fail 'non-tmpfs accepted'; fi
echo COURIER_VM_NON_TMPFS_REJECTED
echo COURIER_VM_ALL_PASS
"$BB" poweroff -f
