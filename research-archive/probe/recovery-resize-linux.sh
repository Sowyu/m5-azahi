#!/bin/bash
# One guarded Linux-side APFS shrink. No formatting, GPT raw writes or other OS changes.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
fail() { echo "STOP: $*" >&2; exit 1; }
[[ $(sysctl -n hw.model) == Mac17,9 ]] || fail 'Not the M5 target'
for required in diskutil plutil gpt dd cksum mktemp tar curl stat mkdir tee; do
    command -v "$required" >/dev/null || fail "Missing tool: $required"
done
[[ $# == 1 && $1 == resize-linux-96gb ]] || fail 'Explicit resize-linux-96gb argument required'
work=$(mktemp -d /tmp/azahi-resize-linux.XXXXXX)
echo "Logs and metadata backups: $work"
echo 'Only Linux APFS disk0s3 will shrink from 256GB to 96GB. Nothing will be formatted.'
echo 'Keep the charger connected. Do not interrupt or reboot during the resize.'
get() { plutil -extract "$2" raw -o - "$1"; }
uuids=(PRIVATE-UUID-REMOVED PRIVATE-UUID-REMOVED
       PRIVATE-UUID-REMOVED PRIVATE-UUID-REMOVED)
starts=(6 140806 180465551 242965551)
counts=(140800 180324745 62500000 1310709)
resolve_linux() {
    diskutil info -plist PRIVATE-UUID-REMOVED > "$1/linux.plist"
    [[ $(get "$1/linux.plist" VolumeUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong Linux system UUID'
    [[ $(get "$1/linux.plist" APFSVolumeGroupID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong Linux volume group'
    [[ $(get "$1/linux.plist" APFSPhysicalStores.0.APFSPhysicalStore) == disk0s3 ]] || fail 'Wrong Linux physical store'
    if get "$1/linux.plist" APFSPhysicalStores.1.APFSPhysicalStore >/dev/null 2>&1; then
        fail 'Multiple physical stores'
    fi
    container=$(get "$1/linux.plist" APFSContainerReference)
    [[ $container =~ ^disk[0-9]+$ ]] || fail 'Invalid container identifier'
}
check_partitions() {
    local directory=$1 linux_size=$2 index part expected
    for index in 0 1 2 3; do
        part=$((index + 1))
        diskutil info -plist "disk0s$part" > "$directory/partition-$part.plist"
        local info="$directory/partition-$part.plist"
        expected=$((counts[index] * 4096))
        [[ $part != 3 ]] || expected=$linux_size
        [[ $(get "$info" DiskUUID) == "${uuids[$index]}" ]] || fail "Partition $part UUID changed"
        [[ $(get "$info" PartitionMapPartitionOffset) == $((starts[index] * 4096)) ]] || fail "Partition $part offset changed"
        [[ $(get "$info" TotalSize) == "$expected" ]] || fail "Partition $part size unexpected"
        [[ $(get "$info" DeviceBlockSize) == 4096 && $(get "$info" ParentWholeDisk) == disk0 ]] || fail 'Wrong disk geometry'
    done
}
check_volumes() {
    local info=$1 index identity
    local seen=' '
    [[ $(get "$info" Containers.0.APFSContainerUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong APFS container'
    [[ $(get "$info" Containers.0.DesignatedPhysicalStore) == disk0s3 ]] || fail 'Wrong APFS store'
    if get "$info" Containers.1.APFSContainerUUID >/dev/null 2>&1; then fail 'Multiple containers'; fi
    for index in 0 1 2 3 4 5; do
        identity=$(get "$info" "Containers.0.Volumes.$index.APFSVolumeUUID")
        case "$identity" in
            PRIVATE-UUID-REMOVED|PRIVATE-UUID-REMOVED|PRIVATE-UUID-REMOVED|PRIVATE-UUID-REMOVED|PRIVATE-UUID-REMOVED|PRIVATE-UUID-REMOVED) ;;
            *) fail 'Unexpected Linux volume UUID' ;;
        esac
        [[ $seen != *" $identity "* ]] || fail 'Duplicate volume UUID'
        seen="$seen$identity "
        [[ $(get "$info" "Containers.0.Volumes.$index.Locked") == false ]] || fail "Linux volume $identity still locked"
        [[ $(get "$info" "Containers.0.Volumes.$index.CryptoMigrationOn") == false ]] || fail 'Encryption migration active'
    done
    if get "$info" Containers.0.Volumes.6.APFSVolumeUUID >/dev/null 2>&1; then fail 'Extra Linux volumes'; fi
}
collect() {
    local directory=$1 linux_size=$2
    mkdir "$directory"
    resolve_linux "$directory"
    check_partitions "$directory" "$linux_size"
    diskutil info -plist disk0 > "$directory/disk.plist"
    [[ $(get "$directory/disk.plist" Internal) == true && $(get "$directory/disk.plist" WholeDisk) == true ]] || fail 'Wrong disk'
    [[ $(get "$directory/disk.plist" DeviceBlockSize) == 4096 && $(get "$directory/disk.plist" TotalSize) == 1000555581440 ]] || fail 'Disk size changed'
    diskutil apfs list "$container" -plist > "$directory/linux-container.plist"
    check_volumes "$directory/linux-container.plist"
    [[ $(get "$directory/linux-container.plist" Containers.0.CapacityCeiling) == "$linux_size" ]] || fail 'APFS size mismatch'
    diskutil list internal > "$directory/disks.txt"
    diskutil list -plist disk0 > "$directory/disk-list.plist"
    diskutil apfs list "$container" > "$directory/linux-container.txt"
    gpt -r show -l /dev/disk0 > "$directory/gpt.txt"
    diskutil apfs resizeContainer disk0s3 limits -plist > "$directory/limits.plist" 2> "$directory/limits-error.txt"
    echo LIMITS_QUERY_OK > "$directory/limits-status.txt"
    [[ $(get "$directory/limits.plist" CurrentSize) == "$linux_size" ]] || fail 'Limits target size mismatch'
    [[ $(get "$directory/limits.plist" Type) == APFSPhysicalStore ]] || fail 'Wrong limits target type'
    local minimum
    minimum=$(get "$directory/limits.plist" MinimumSizePreferred)
    [[ $minimum =~ ^[0-9]+$ ]] || fail 'Invalid minimum'
    [[ $minimum -le 96000000000 ]] || fail '96GB is below the current preferred minimum'
    dd if=/dev/rdisk0 of="$directory/gpt-primary.bin" bs=4096 count=6 2> "$directory/dd-primary.txt"
    dd if=/dev/rdisk0 of="$directory/gpt-backup.bin" bs=4096 skip=244276259 count=6 2> "$directory/dd-backup.txt"
    dd if=/dev/rdisk0s3 of="$directory/linux-superblock.bin" bs=4096 count=1 2> "$directory/dd-superblock.txt"
    [[ $(stat -f %z "$directory/gpt-primary.bin") == 24576 && $(stat -f %z "$directory/gpt-backup.bin") == 24576 ]] || fail 'Short GPT copy'
    [[ $(stat -f %z "$directory/linux-superblock.bin") == 4096 ]] || fail 'Short Linux superblock copy'
}
upload() {
    local stage=$1 archive="$work/$1/backup.tar.gz" receipt expected
    tar -czf "$archive" -C "$work/$stage" linux.plist partition-1.plist partition-2.plist \
        partition-3.plist partition-4.plist disk.plist disks.txt disk-list.plist \
        linux-container.plist linux-container.txt gpt.txt limits.plist limits-error.txt \
        limits-status.txt gpt-primary.bin gpt-backup.bin linux-superblock.bin
    set -- $(cksum "$archive")
    expected="$1 $2"
    receipt=$(curl -q --noproxy '*' --proto '=http' --fail --show-error --connect-timeout 10 --max-time 120 \
        --upload-file "$archive" "@UPLOAD_URL@/$stage")
    printf '%s\n' "$receipt"
    [[ ${receipt%%$'\n'*} == "CKSUM $expected" ]] || fail 'Transfer checksum/size mismatch'
    [[ ${receipt##*$'\n'} == "VALIDATED_STORAGE $stage" ]] || fail 'Host did not validate the metadata backup'
}
collect "$work/before" 256000000000
upload before
# Fresh re-resolution and geometry/unlock/limits check immediately before the only mutation.
resolve_linux "$work/before"
check_partitions "$work/before" 256000000000
diskutil apfs list "$container" -plist > "$work/final-container.plist"
check_volumes "$work/final-container.plist"
diskutil apfs resizeContainer disk0s3 limits -plist > "$work/final-limits.plist"
[[ $(get "$work/final-limits.plist" CurrentSize) == 256000000000 ]] || fail 'Size changed before resize'
minimum=$(get "$work/final-limits.plist" MinimumSizePreferred)
[[ $minimum =~ ^[0-9]+$ && $minimum -le 96000000000 ]] || fail 'Resize minimum changed'
echo 'BACKUP_VALIDATED. Starting Linux-only APFS resize now. Do not interrupt.'
if diskutil apfs resizeContainer disk0s3 96000000000 | tee "$work/resize.log"; then
    echo 'Resize command completed; validating the resulting layout.'
else
    fail "Resize returned an error. Keep Recovery open; do not retry or restore old GPT. Log: $work/resize.log"
fi
collect "$work/after" 96000000000
upload after
echo 'LINUX_RESIZE_VERIFIED. Linux APFS is 96GB; 160GB is free partition space.'
echo 'Protected GPT entries unchanged. No new filesystem created. Leave Recovery open.'
