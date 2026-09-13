#!/bin/bash
# /sysroot is the verified new Linux root, mounted by our explicit mount unit.
set -Eeuo pipefail
export PATH=/usr/bin:/usr/sbin:/bin:/sbin
BB=/usr/local/libexec/busybox.static
ROOTDEV=/dev/disk/by-partuuid/PRIVATE-UUID-REMOVED
FSUUID=PRIVATE-UUID-REMOVED
fail() { echo "SSDROOT_CONFIG_STOP: $*" >&2; exit 1; }
[[ -e /etc/initrd-release ]] || fail 'Not in initrd'
[[ $(findmnt -n -o UUID /sysroot) == "$FSUUID" ]] || fail 'Wrong mounted root'
[[ $(findmnt -n -o FSROOT /sysroot) == /root ]] || fail 'Wrong subvolume'
[[ ,$(findmnt -n -o OPTIONS /sysroot), == *,rw,* ]] || fail 'Root not writable'
[[ $(cat /sys/module/nvme_apple/parameters/root_write_armed) == Y ]] || fail 'Guard disarmed'
[[ $(blkid -p -s UUID -o value "$ROOTDEV") == "$FSUUID" ]] || fail 'Device UUID changed'
backup=/sysroot/var/lib/azahi-ssdboot/original
marker=/sysroot/var/lib/azahi-ssdboot/initialized-v1
if [[ -e $marker ]]; then
    [[ $(cat "$marker") == "$FSUUID" ]] || fail 'Wrong initialization marker'
    echo 'SSDROOT_ALREADY_CONFIGURED; preserving user changes'
    exit 0
fi
mkdir -p "$backup"
# The full list is generated from the archive. Back up each existing file or
# link before first replacement; don't traverse symlinked parent directories.
while IFS= read -r relative; do
    [[ -n $relative && $relative != /* && /$relative/ != */../* ]] || fail 'Unsafe overlay path'
    parent=${relative%/*}
    check=/sysroot
    IFS=/ read -ra components <<< "$parent"
    for component in "${components[@]}"; do
        check=$check/$component
        [[ ! -L $check ]] || fail "Symlinked destination parent: $relative"
    done
    target=/sysroot/$relative
    if [[ -L $target && ! -L /ramroot/sysroot-overlay/$relative ]]; then
        fail "Refuse to copy regular file through destination symlink: $relative"
    fi
    if [[ (-e $target || -L $target) && ! -e $backup/$relative && ! -L $backup/$relative ]]; then
        mkdir -p "$backup/${relative%/*}"
        cp -a "$target" "$backup/$relative"
    fi
done < /ssdroot-overlay-files
cp -a /ramroot/sysroot-overlay/. /sysroot/
# Preserve user configuration on subsequent boots. Initial overlay is applied
# once; builder/configure unit uses a first-boot marker for later boots.
echo "$FSUUID" > "$marker"
"$BB" sync
echo 'SSDROOT_CONFIGURED; next / is the internal SSD, not a loop/RAM filesystem'
