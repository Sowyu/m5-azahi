#!/bin/bash
# Create blank Linux partitions only inside the verified post-resize gap.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
fail() { echo "STOP: $*" >&2; exit 1; }
[[ $(sysctl -n hw.model) == Mac17,9 ]] || fail 'Not the M5 target'
[[ $# == 1 && $1 == create-linux-partitions ]] || fail 'Explicit create-linux-partitions argument required'
for required in diskutil plutil gpt dd cksum mktemp tar curl stat mkdir tee; do
    command -v "$required" >/dev/null || fail "Missing tool: $required"
done
work=$(mktemp -d /tmp/azahi-create-partitions.XXXXXX)
trap 'echo "STOP: A command failed. Keep Recovery open; do not rerun or restore GPT. Logs: $work" >&2' ERR
echo "Metadata backups and logs: $work"
echo 'Creating blank 512MiB EFI and 148GiB Linux partitions in the freed Linux-side space only.'
echo 'An optional 128MiB Apple boot-helper may also be created there. No existing volume is erased.'
get() { plutil -extract "$2" raw -o - "$1"; }
fingerprint() { local sum; sum=$(cksum "$1"); set -- $sum; echo "$1 $2"; }
collect() {
    local directory=$1 index device info identity start size expected_start expected_size seen=' '
    mkdir "$directory"
    diskutil info -plist disk0 > "$directory/disk.plist"
    [[ $(get "$directory/disk.plist" Internal) == true && $(get "$directory/disk.plist" WholeDisk) == true ]] || fail 'Wrong disk'
    [[ $(get "$directory/disk.plist" DeviceBlockSize) == 4096 && $(get "$directory/disk.plist" TotalSize) == 1000555581440 ]] || fail 'Wrong disk geometry'
    diskutil info -plist PRIVATE-UUID-REMOVED > "$directory/linux.plist"
    [[ $(get "$directory/linux.plist" VolumeUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong Linux system'
    [[ $(get "$directory/linux.plist" APFSVolumeGroupID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong Linux group'
    [[ $(get "$directory/linux.plist" APFSPhysicalStores.0.APFSPhysicalStore) == disk0s3 ]] || fail 'Wrong Linux store'
    if get "$directory/linux.plist" APFSPhysicalStores.1.APFSPhysicalStore >/dev/null 2>&1; then fail 'Multiple stores'; fi
    local container
    container=$(get "$directory/linux.plist" APFSContainerReference)
    [[ $container =~ ^disk[0-9]+$ ]] || fail 'Invalid container'
    diskutil apfs list "$container" -plist > "$directory/linux-container.plist"
    [[ $(get "$directory/linux-container.plist" Containers.0.APFSContainerUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong container'
    [[ $(get "$directory/linux-container.plist" Containers.0.CapacityCeiling) == 96000000000 ]] || fail 'Linux resize not verified/current'
    diskutil list -plist disk0 > "$directory/disk-list.plist"
    [[ $(get "$directory/disk-list.plist" AllDisksAndPartitions.0.DeviceIdentifier) == disk0 ]] || fail 'Wrong disk list'
    part_files=()
    esp_device='' esp_uuid=''
    local originals=0
    for index in 0 1 2 3 4 5 6; do
        if ! device=$(get "$directory/disk-list.plist" "AllDisksAndPartitions.0.Partitions.$index.DeviceIdentifier" 2>/dev/null); then break; fi
        [[ $device =~ ^disk0s[1-9][0-9]*$ ]] || fail 'Invalid partition device'
        info="$directory/part-$index.plist"
        part_files+=("part-$index.plist")
        diskutil info -plist "$device" > "$info"
        identity=$(get "$info" DiskUUID)
        [[ $identity =~ ^[A-Fa-f0-9-]{36}$ && $seen != *" $identity "* ]] || fail 'Invalid/duplicate partition UUID'
        seen="$seen$identity "
        [[ $(get "$info" ParentWholeDisk) == disk0 && $(get "$info" DeviceBlockSize) == 4096 ]] || fail 'Wrong partition parent/sector'
        start=$(get "$info" PartitionMapPartitionOffset)
        size=$(get "$info" TotalSize)
        [[ $start =~ ^[0-9]+$ && $size =~ ^[0-9]+$ ]] || fail 'Invalid extent'
        expected_start='' expected_size=''
        case "$identity" in
            PRIVATE-UUID-REMOVED) expected_start=6; expected_size=140800 ;;
            PRIVATE-UUID-REMOVED) expected_start=140806; expected_size=180324745 ;;
            PRIVATE-UUID-REMOVED)
                expected_start=180465551; expected_size=23437500
                [[ $device == disk0s3 ]] || fail 'Linux store numbering changed' ;;
            PRIVATE-UUID-REMOVED) expected_start=242965551; expected_size=1310709 ;;
        esac
        if [[ -n $expected_start ]]; then
            [[ $start -eq $((expected_start * 4096)) && $size -eq $((expected_size * 4096)) ]] || fail 'Original partition extent changed'
            originals=$((originals + 1))
        else
            [[ $start -ge $((203903051 * 4096)) && $size -gt 0 && $size -le 160000000000 && $((start + size)) -le $((242965551 * 4096)) ]] || fail 'New partition outside approved gap'
            if [[ $(get "$info" Content) == EFI ]]; then
                [[ -z $esp_device && $start -eq $((203903051 * 4096)) && $size -eq 536870912 ]] || fail 'Unexpected EFI partition'
                esp_device=$device; esp_uuid=$identity
            fi
        fi
    done
    [[ $originals == 4 && ${#part_files[@]} -ge 4 ]] || fail 'Original partitions missing'
    if get "$directory/disk-list.plist" AllDisksAndPartitions.0.Partitions.7.DeviceIdentifier >/dev/null 2>&1; then fail 'Too many partitions'; fi
    gpt -r show -l /dev/disk0 > "$directory/gpt.txt"
    dd if=/dev/rdisk0 of="$directory/gpt-primary.bin" bs=4096 count=6 2> "$directory/dd-primary.txt"
    dd if=/dev/rdisk0 of="$directory/gpt-backup.bin" bs=4096 skip=244276259 count=6 2> "$directory/dd-backup.txt"
    dd if=/dev/rdisk0s3 of="$directory/linux-superblock.bin" bs=4096 count=1 2> "$directory/dd-superblock.txt"
    [[ $(stat -f %z "$directory/gpt-primary.bin") == 24576 && $(stat -f %z "$directory/gpt-backup.bin") == 24576 && $(stat -f %z "$directory/linux-superblock.bin") == 4096 ]] || fail 'Short metadata backup'
}
upload() {
    local stage=$1 archive="$work/$1/backup.tar.gz" receipt expected
    tar -czf "$archive" -C "$work/$stage" disk.plist disk-list.plist linux.plist linux-container.plist \
        gpt-primary.bin gpt-backup.bin linux-superblock.bin gpt.txt "${part_files[@]}"
    expected=$(fingerprint "$archive")
    receipt=$(curl -q --noproxy '*' --proto '=http' --fail --show-error --connect-timeout 10 --max-time 120 \
        --upload-file "$archive" "@UPLOAD_URL@/$stage")
    printf '%s\n' "$receipt"
    [[ ${receipt%%$'\n'*} == "CKSUM $expected" && ${receipt##*$'\n'} == "VALIDATED_PARTITIONS $stage" ]] || fail 'Host backup validation missing/mismatched'
}
unchanged() {
    local directory=$1
    dd if=/dev/rdisk0 of="$directory/final-primary.bin" bs=4096 count=6 2> "$directory/dd-final-primary.txt"
    dd if=/dev/rdisk0 of="$directory/final-backup.bin" bs=4096 skip=244276259 count=6 2> "$directory/dd-final-backup.txt"
    [[ $(fingerprint "$directory/final-primary.bin") == "$(fingerprint "$directory/gpt-primary.bin")" && $(fingerprint "$directory/final-backup.bin") == "$(fingerprint "$directory/gpt-backup.bin")" ]] || fail 'GPT changed since host validation'
}
collect "$work/before"
upload before
unchanged "$work/before"
echo 'Validated backup received. Creating only the new EFI partition.'
diskutil addPartition disk0s3 '%PRIVATE-UUID-REMOVED%' '%noformat%' 536870912 | tee "$work/create-esp.log"
collect "$work/esp"
upload esp
[[ $esp_device =~ ^disk0s[1-9][0-9]*$ && -n $esp_uuid ]] || fail 'No validated EFI device'
unchanged "$work/esp"
diskutil info -plist "$esp_device" > "$work/final-esp.plist"
[[ $(get "$work/final-esp.plist" DiskUUID) == "$esp_uuid" ]] || fail 'EFI device identity changed'
echo 'EFI validated. Creating only the new Linux root partition after it.'
diskutil addPartition "$esp_device" '%PRIVATE-UUID-REMOVED%' '%noformat%' 158913789952 | tee "$work/create-root.log"
collect "$work/root"
upload root
echo 'LINUX_PARTITIONS_VERIFIED. Original partition entries preserved. New partitions are blank.'
echo 'Leave Recovery open. Do not rerun this script; the Linux system image is not installed yet.'
