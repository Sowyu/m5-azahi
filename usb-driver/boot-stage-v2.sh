#!/bin/bash
# Initrd-only RAM courier. Every external utility is explicitly addressed.
# No module loading, persistent writes, networking or mounts.
set -euo pipefail
export PATH=/nonexistent
BB=/usr/local/libexec/busybox.static
[[ -e /etc/initrd-release && -x $BB ]] || exit 1
[[ $(/usr/bin/findmnt -n -o FSTYPE /run) == tmpfs ]] || exit 1
source_dir=/azahi-usb-20260913
destination=/run/azahi-usb-20260913
[[ ! -e $destination && ! -L $destination ]] || exit 1
umask 077
temporary=$("$BB" mktemp -d /run/azahi-usb-staging.XXXXXX)
for name in phy-apple-t6050-usb2.ko dwc3-apple-t6050.ko azahi-usb-overlay.ko usb-tether-test.sh SHA256SUMS; do
    [[ -f $source_dir/$name && ! -L $source_dir/$name ]] || exit 1
    "$BB" cp "$source_dir/$name" "$temporary/$name"
done
(cd "$temporary" && "$BB" sha256sum -c SHA256SUMS)
"$BB" mv -T -n "$temporary" "$destination"
[[ ! -d $temporary && -d $destination && ! -L $destination ]] || exit 1
echo 'AZAHI_USB_FILES_READY /run/azahi-usb-20260913 (drivers NOT loaded; courier v2)'
