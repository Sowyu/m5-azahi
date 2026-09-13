#!/bin/bash
# Recovery-only inventory and backup. No target boot/policy/disk writes.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
fail() { echo "STOP: $*" >&2; exit 1; }
[[ $(sysctl -n hw.model) == Mac17,9 ]] || fail 'Not the M5 target'
for required in cksum mktemp diskutil plutil bputil find stat cp tar curl; do
    command -v "$required" >/dev/null || fail "Required tool unavailable: $required"
done
work=$(mktemp -d /tmp/azahi-boot-backup.XXXXXX)
echo "Temporary backup: $work"
diskutil info -plist /Volumes/Linux > "$work/linux.plist"
diskutil info -plist /Volumes/Preboot > "$work/preboot.plist"
get() { plutil -extract "$2" raw -o - "$1"; }
[[ $(get "$work/linux.plist" VolumeName) == Linux ]] || fail 'Wrong system volume'
[[ $(get "$work/linux.plist" DeviceIdentifier) == disk4s3 ]] || fail 'System disk changed'
[[ $(get "$work/preboot.plist" DeviceIdentifier) == disk4s4 ]] || fail 'Preboot disk changed'
[[ $(get "$work/preboot.plist" VolumeName) == Preboot ]] || fail 'Wrong Preboot volume'
[[ $(get "$work/preboot.plist" MountPoint) == /Volumes/Preboot ]] || fail 'Wrong mount point'
[[ $(get "$work/preboot.plist" WritableVolume) == false ]] || fail 'Preboot is not read-only'
[[ $(get "$work/linux.plist" APFSContainerReference) == "$(get "$work/preboot.plist" APFSContainerReference)" ]] || fail 'Different containers'
vg=$(get "$work/linux.plist" APFSVolumeGroupID)
[[ $vg =~ ^[0-9A-Fa-f-]{36}$ ]] || fail 'Invalid volume group'
[[ -d /Volumes/Preboot/$vg ]] || fail 'Volume-group directory missing'
diskutil apfs listVolumeGroups disk4 > "$work/volume-groups.txt"
diskutil list internal > "$work/disks.txt"
bputil -d -v "$vg" > "$work/boot-policy.txt"
find "/Volumes/Preboot/$vg" -type f -name '*custom*' -print0 > "$work/paths.nul"
count=0
total=0
files=()
while IFS= read -r -d '' source; do
    count=$((count + 1))
    [[ $count -le 16 ]] || fail 'Unexpected number of custom files'
    size=$(stat -f %z "$source")
    total=$((total + size))
    [[ $total -le 33554432 ]] || fail 'Backup exceeds 32 MiB bound'
    dest=$(printf 'custom-%02d.bin' "$count")
    files+=("$dest")
    source_sum=$(cksum < "$source")
    cp -p "$source" "$work/$dest"
    copy_sum=$(cksum < "$work/$dest")
    [[ $source_sum == "$copy_sum" ]] || fail 'Backup checksum/size differs from source'
    printf '%s\t%s\n' "$dest" "$source" >> "$work/manifest.tsv"
    printf '%s\t%s\n' "$source_sum" "$source" >> "$work/source-checksums.txt"
    printf '%s\t%s\n' "$copy_sum" "$dest" >> "$work/copy-checksums.txt"
done < "$work/paths.nul"
[[ $count -gt 0 ]] || fail 'No custom boot files found'
archive="$work/backup.tar.gz"
tar -czf "$archive" -C "$work" linux.plist preboot.plist volume-groups.txt disks.txt boot-policy.txt paths.nul manifest.tsv source-checksums.txt copy-checksums.txt "${files[@]}"
echo "Copied and checksum/size-verified $count files ($total bytes)."
set -- $(cksum "$archive")
expected="$1 $2"
echo "Archive checksum and size: $expected"
receipt=$(curl --fail --show-error --connect-timeout 10 --max-time 120 --upload-file "$archive" '@UPLOAD_URL@')
printf '%s\n' "$receipt"
received=${receipt%%$'\n'*}
[[ $received == "CKSUM $expected" ]] || fail 'Transferred archive checksum/size mismatch'
echo 'BACKUP SENT. No boot settings or partitions changed. Leave Recovery open.'
