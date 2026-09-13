#!/bin/bash
# ramroot-setup.sh - runs inside the dracut initrd (as ramroot.service).
# Assembles the RAM-backed root image, loop-attaches it, mounts /sysroot,
# and grafts /ramroot/sysroot-overlay into it.  Everything it needs
# (bash, modprobe, losetup, mount, btrfs, cp, cat) is in the stock
# Fedora dracut initramfs; loop.ko/overlay.ko are too (verified live).
set -x

modprobe loop

img=/ramroot/root.img
if [ ! -e "$img" ]; then
    # big images ship as .part000.. chunks (newc 4GiB/file limit)
    # /run is a small tmpfs (nowhere near image size even with 56 GB of RAM):
    # reassembling a 14.2 GB image there dies with
    #   cat: write error: No space left on device
    # after ~8 GB. Give the join its own tmpfs, sized from MemTotal so it
    # scales; chunks are freed as they are consumed, so peak use is roughly
    # image size + one chunk.
    kb=$(awk '/^MemTotal:/{print $2}' /proc/meminfo)
    sz=$(( kb / 1024 / 2 ))      # half of RAM, in MiB
    mkdir -p /ramroot/join
    mount -t tmpfs -o size=${sz}M tmpfs /ramroot/join || exit 1
    img=/ramroot/join/root.img
    : > "$img"
    for p in /ramroot/root.img.part*; do
        [ -e "$p" ] || { echo "ramroot: no image found"; exit 1; }
        cat "$p" >> "$img" && rm -f "$p"     # free each chunk as we go
    done
fi

losetup /dev/loop0 "$img" || exit 1

# Fedora images put the OS in a btrfs subvolume named 'root'; probe for it
mkdir -p /run/rrprobe
mount -t btrfs -o ro /dev/loop0 /run/rrprobe || exit 1
opts="rw"
if btrfs subvolume list /run/rrprobe | grep -q ' path root$'; then
    opts="rw,subvol=root"
fi
umount /run/rrprobe

mount -t btrfs -o "$opts" /dev/loop0 /sysroot || exit 1

# graft host-built config (autologin, injectors, session env) into the root
if [ -d /ramroot/sysroot-overlay ]; then
    cp -a /ramroot/sysroot-overlay/. /sysroot/
fi

echo "ramroot: /sysroot mounted ($opts) from $img"
exit 0
