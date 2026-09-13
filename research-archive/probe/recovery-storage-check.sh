#!/bin/bash
# Read-only Recovery inventory and GPT backup. No mount/resize/boot changes.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
fail() { echo "STOP: $*" >&2; exit 1; }
[[ $(sysctl -n hw.model) == Mac17,9 ]] || fail 'Not the M5 target'
for required in diskutil plutil gpt dd cksum mktemp tar curl stat; do
    command -v "$required" >/dev/null || fail "Missing tool: $required"
done
work=$(mktemp -d /tmp/azahi-storage-check.XXXXXX)
echo "Read-only storage report: $work"
get() { plutil -extract "$2" raw -o - "$1"; }

# Resolve by Linux system volume UUID; never select a volume by name alone.
diskutil info -plist PRIVATE-UUID-REMOVED > "$work/linux.plist"
[[ $(get "$work/linux.plist" VolumeUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong Linux system UUID'
[[ $(get "$work/linux.plist" APFSVolumeGroupID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong Linux volume group'
store=$(get "$work/linux.plist" APFSPhysicalStores.0.APFSPhysicalStore)
[[ $store == disk0s3 ]] || fail 'Physical store numbering/layout changed; review before proceeding'
if get "$work/linux.plist" APFSPhysicalStores.1.APFSPhysicalStore >/dev/null 2>&1; then
    fail 'Multiple physical stores are not supported'
fi
container=$(get "$work/linux.plist" APFSContainerReference)
[[ $container =~ ^disk[0-9]+$ ]] || fail 'Invalid container identifier'

# Check all existing GPT entries against the established layout before raw reads.
# Partition 2 is the protected daily macOS; only its disk metadata is queried.
uuids=(PRIVATE-UUID-REMOVED PRIVATE-UUID-REMOVED
       PRIVATE-UUID-REMOVED PRIVATE-UUID-REMOVED)
starts=(6 140806 180465551 242965551)
counts=(140800 180324745 62500000 1310709)
for index in 0 1 2 3; do
    part=$((index + 1))
    info="$work/partition-$part.plist"
    diskutil info -plist "disk0s$part" > "$info"
    [[ $(get "$info" DiskUUID) == "${uuids[$index]}" ]] || fail "Partition $part UUID mismatch"
    [[ $(get "$info" PartitionMapPartitionOffset) == $((starts[index] * 4096)) ]] || fail "Partition $part offset mismatch"
    [[ $(get "$info" TotalSize) == $((counts[index] * 4096)) ]] || fail "Partition $part size mismatch"
    [[ $(get "$info" DeviceBlockSize) == 4096 ]] || fail 'Unexpected sector size'
    [[ $(get "$info" ParentWholeDisk) == disk0 ]] || fail 'Unexpected parent disk'
done
diskutil info -plist disk0 > "$work/disk.plist"
[[ $(get "$work/disk.plist" Internal) == true ]] || fail 'Not internal storage'
[[ $(get "$work/disk.plist" WholeDisk) == true ]] || fail 'Not a whole disk'
[[ $(get "$work/disk.plist" DeviceBlockSize) == 4096 ]] || fail 'Wrong disk block size'
bytes=$(get "$work/disk.plist" TotalSize)
[[ $bytes =~ ^[0-9]+$ ]] || fail 'Invalid disk length'
[[ $bytes -ge 1000000000000 && $bytes -le 1010000000000 ]] || fail 'Unexpected disk capacity'
[[ $((bytes % 4096)) == 0 ]] || fail 'Unaligned disk length'
sectors=$((bytes / 4096))

diskutil list internal > "$work/disks.txt"
diskutil list -plist disk0 > "$work/disk-list.plist"
diskutil apfs list "$container" -plist > "$work/linux-container.plist"
[[ $(get "$work/linux-container.plist" Containers.0.APFSContainerUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong APFS container UUID'
gpt -r show -l /dev/disk0 > "$work/gpt.txt"

# 'limits' is query-only, per Apple's diskutil manual. Never substitute a size.
if diskutil apfs resizeContainer "$store" limits -plist > "$work/limits.plist" 2> "$work/limits-error.txt"; then
    echo LIMITS_QUERY_OK > "$work/limits-status.txt"
else
    echo LIMITS_QUERY_FAILED > "$work/limits-status.txt"
fi
diskutil apfs list "$container" > "$work/linux-container.txt"

# GPT headers/tables and Linux's first APFS superblock only; no daily OS content.
dd if=/dev/rdisk0 of="$work/gpt-primary.bin" bs=4096 count=6 2> "$work/dd-primary.txt"
dd if=/dev/rdisk0 of="$work/gpt-backup.bin" bs=4096 skip=$((sectors - 6)) count=6 2> "$work/dd-backup.txt"
dd if=/dev/rdisk0s3 of="$work/linux-superblock.bin" bs=4096 count=1 2> "$work/dd-superblock.txt"
[[ $(stat -f %z "$work/gpt-primary.bin") == 24576 ]] || fail 'Short primary GPT copy'
[[ $(stat -f %z "$work/gpt-backup.bin") == 24576 ]] || fail 'Short backup GPT copy'
[[ $(stat -f %z "$work/linux-superblock.bin") == 4096 ]] || fail 'Short Linux superblock copy'

archive="$work/backup.tar.gz"
tar -czf "$archive" -C "$work" linux.plist partition-1.plist partition-2.plist \
    partition-3.plist partition-4.plist disk.plist disks.txt disk-list.plist \
    linux-container.plist linux-container.txt gpt.txt limits.plist limits-error.txt \
    limits-status.txt gpt-primary.bin gpt-backup.bin linux-superblock.bin
set -- $(cksum "$archive")
expected="$1 $2"
receipt=$(curl --fail --show-error --connect-timeout 10 --max-time 120 \
    --upload-file "$archive" '@UPLOAD_URL@')
printf '%s\n' "$receipt"
[[ ${receipt%%$'\n'*} == "CKSUM $expected" ]] || fail 'Transfer checksum/size mismatch'
echo 'STORAGE_REPORT_SENT. No partitions, mounts, filesystems or boot settings changed.'
echo 'Leave Recovery open. Do not resize anything manually.'
