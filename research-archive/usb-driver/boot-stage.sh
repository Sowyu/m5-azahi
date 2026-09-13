#!/bin/bash
# Initrd-only file courier. No modules, storage writes, networking or mounts.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
[[ -e /etc/initrd-release ]] || exit 1
[[ $(findmnt -n -o FSTYPE /run) == tmpfs ]] || exit 1
source_dir=/azahi-usb-20260913
destination=/run/azahi-usb-20260913
[[ ! -e $destination && ! -L $destination ]] || exit 1
umask 077
temporary=$(mktemp -d /run/azahi-usb-staging.XXXXXX)
for name in phy-apple-t6050-usb2.ko dwc3-apple-t6050.ko azahi-usb-overlay.ko usb-tether-test.sh SHA256SUMS; do
    [[ -f $source_dir/$name && ! -L $source_dir/$name ]] || exit 1
    cp "$source_dir/$name" "$temporary/$name"
done
(cd "$temporary" && /usr/local/libexec/busybox.static sha256sum -c SHA256SUMS)
mv -T -n "$temporary" "$destination"
[[ ! -d $temporary ]] || exit 1
echo 'AZAHI_USB_FILES_READY /run/azahi-usb-20260913 (drivers NOT loaded)'
