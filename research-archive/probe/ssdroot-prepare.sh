#!/bin/bash
# Runs only in the initramfs. No filesystem writes before the fixed guard arms.
set -Eeuo pipefail
export PATH=/usr/bin:/usr/sbin:/bin:/sbin
BB=/usr/local/libexec/busybox.static
PARTUUID=PRIVATE-UUID-REMOVED
FSUUID=PRIVATE-UUID-REMOVED
PARAM=/sys/module/nvme_apple/parameters/root_write_armed
ROOTDEV=/dev/disk/by-partuuid/$PARTUUID
die() { echo "SSDROOT_STOP: $*" >&2; fail_cleanup; exit 1; }
bb() { "$BB" "$@"; }
fail_cleanup() {
    udevadm control --start-exec-queue || true
    test ! -e "$PARAM" || echo N > "$PARAM"
    echo 'SSDROOT_PREPARE_FAILED; writes disarmed; do not bypass checks' >&2
}
trap fail_cleanup ERR

hash_region() {
    local device=$1 skip=$2 blocks=$3 expected=$4 actual
    actual=$(bb dd "if=$device" bs=4096 "skip=$skip" "count=$blocks" 2>/dev/null | bb sha256sum)
    [[ ${actual%% *} == "$expected" ]] || die "Region hash mismatch ($skip/$blocks)"
}

main() {
    [[ $(uname -m) == aarch64 && -e /etc/initrd-release ]] || die 'Not target initrd'
    bb tr '\0' '\n' < /proc/device-tree/compatible | bb grep -Fxq apple,j714s || die 'Wrong model'
    [[ " $(cat /proc/cmdline) " == *' azahi.ssd_root=1 '* ]] || die 'No explicit SSD boot argument'
    [[ ! -e /sys/block/nvme0n1 ]] || die 'NVMe loaded before guarded preparation'
    for applet in blockdev dd sha256sum stat; do
        bb --list | bb grep -Fxq "$applet" || die "Missing Busybox $applet"
    done
    depmod -a
    udevadm control --stop-exec-queue
    modprobe nvme_apple
    local attempt d disk='' count=0 node nsid rootname actual
    for ((attempt=0; attempt<45; attempt++)); do
        count=0
        for d in /sys/block/nvme*n*; do
            [[ -d $d ]] || continue
            bb blockdev --setro "/dev/${d##*/}"
            [[ $(cat "$d/ro") == 1 ]] || die 'Cannot set namespace RO'
            ((count+=1))
        done
        if ((count >= 3)); then break; fi
        sleep 1
    done
    ((count == 3)) || die 'Expected exactly three namespaces'
    [[ $(cat "$PARAM") == N ]] || die 'Driver unexpectedly armed'
    for d in /sys/block/nvme*n*; do
        if (( $(cat "$d/size") * 512 == 1000555581440 )); then
            [[ -z $disk ]] || die 'Ambiguous main namespace'
            disk=${d##*/}
        fi
    done
    [[ -n $disk ]] || die 'Wrong SSD capacity'
    nsid=/sys/block/$disk/nsid
    [[ -e $nsid ]] || nsid=/sys/block/$disk/device/nsid
    [[ $(cat "$nsid") == 1 ]] || die 'Main namespace is not NSID1'
    [[ $(cat "/sys/block/$disk/queue/logical_block_size") == 4096 ]] || die 'Wrong LBA size'
    udevadm control --start-exec-queue
    udevadm settle --timeout=20
    [[ -b $ROOTDEV ]] || die 'Root PARTUUID missing'
    rootname=$(basename "$(readlink -f "$ROOTDEV")")
    [[ $(dirname "$(readlink -f "/sys/class/block/$rootname")") == "$(readlink -f "/sys/block/$disk")" ]] || die 'Root belongs to wrong disk'
    [[ $(cat "/sys/class/block/$rootname/start") == 1632272984 ]] || die 'Wrong root start'
    [[ $(cat "/sys/class/block/$rootname/size") == 310116352 ]] || die 'Wrong root size'
    # Match both complete GPT copies, not just a partition label or UUID.
    hash_region "/dev/$disk" 0 6 1d5f950b18f43d5b535c50e2f553464749da88d8e34713e8db56d0786fdf53ce
    hash_region "/dev/$disk" 244276260 5 acd9401f19961d84ca3a3a48741325c4420d0325d72736ff5c61c34f2b22cb76
    [[ $(blkid -p -s TYPE -o value "$ROOTDEV") == btrfs ]] || die 'Root is not Btrfs'
    [[ $(blkid -p -s UUID -o value "$ROOTDEV") == "$FSUUID" ]] || die 'Wrong filesystem UUID'
    # No SSD filesystem may already be mounted, including by an automounter.
    if bb grep -q nvme /proc/swaps; then die 'NVMe swap is active'; fi
    for node in /sys/class/block/nvme*n*; do
        [[ -e $node/dev ]] || continue
        actual=$(cat "$node/dev")
        while read -r id parent devno rest; do
            [[ $devno != "$actual" ]] || die 'NVMe volume already mounted'
        done < /proc/self/mountinfo
    done
    mkdir -p /run/ssdroot-inspect
    mount -t btrfs -o ro,rescue=nologreplay,subvol=root "$ROOTDEV" /run/ssdroot-inspect
    [[ -e /run/ssdroot-inspect/usr/lib/systemd/systemd && -e /run/ssdroot-inspect/usr/bin/kwin_wayland ]] || die 'Installed KDE root incomplete'
    if [[ -e /run/ssdroot-inspect/var/lib/azahi-ssdboot/initialized-v1 ]]; then
        [[ $(cat /run/ssdroot-inspect/var/lib/azahi-ssdboot/initialized-v1) == "$FSUUID" ]] || die 'Unexpected initialization marker'
    else
        hash_region "$ROOTDEV" 0 4096 21f2d2b6d658fc729b2c6fbe802ae0e5c150f754736032657160bb122417ea3b
    fi
    umount /run/ssdroot-inspect
    for d in /sys/block/nvme*n*; do
        read -ra stats < "$d/stat"
        [[ ${stats[6]} == 0 && $(cat "$d/ro") == 1 ]] || die 'Unexpected writes before arming'
    done
    bb blockdev --setrw "/dev/$disk"
    for node in /sys/block/$disk/${disk}p*; do
        [[ ${node##*/} == "$rootname" ]] || bb blockdev --setro "/dev/${node##*/}"
    done
    bb blockdev --setrw "$ROOTDEV"
    echo Y > "$PARAM"
    [[ $(cat "$PARAM") == Y ]] || die 'Guard did not arm'
    echo 'SSDROOT_PREPARE_PASS; only fixed Linux-root LBA range writable'
}
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then main; fi
