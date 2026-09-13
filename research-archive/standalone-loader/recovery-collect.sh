#!/bin/bash
# Read-only Linux boot backup. No mounts, policy changes, or persistent writes.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
fail() { echo "STOP: $*" >&2; exit 1; }
for required in sysctl cksum mktemp diskutil plutil bputil find stat cp tar curl; do
    command -v "$required" >/dev/null || fail "Required tool unavailable: $required"
done
[[ $(sysctl -n hw.model) == Mac17,9 ]] || fail 'Not the M5 target'
vg=PRIVATE-UUID-REMOVED
work=$(mktemp -d /tmp/azahi-standalone-backup.XXXXXX)
echo "Temporary backup: $work"
get() { plutil -extract "$2" raw -o - "$1"; }
diskutil info -plist PRIVATE-UUID-REMOVED > "$work/linux.plist"
[[ $(get "$work/linux.plist" VolumeUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong Linux UUID'
[[ $(get "$work/linux.plist" VolumeName) == Linux ]] || fail 'Wrong Linux name'
[[ $(get "$work/linux.plist" MountPoint) == /Volumes/Linux ]] || fail 'Linux is not mounted at /Volumes/Linux'
[[ $(get "$work/linux.plist" APFSVolumeGroupID) == "$vg" ]] || fail 'Wrong volume group'
container=$(get "$work/linux.plist" APFSContainerReference)
[[ $container =~ ^disk[0-9]+$ ]] || fail 'Invalid container device'
diskutil apfs list "$container" -plist > "$work/linux-container.plist"
[[ $(get "$work/linux-container.plist" Containers.0.APFSContainerUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong container UUID'
[[ $(get "$work/linux-container.plist" Containers.0.CapacityCeiling) == 96000000000 ]] || fail 'Wrong Linux container size'
prebootdev=$(get "$work/linux.plist" BooterDeviceIdentifier)
[[ $prebootdev =~ ^disk[0-9]+s[0-9]+$ ]] || fail 'Invalid Preboot device'
diskutil info -plist "$prebootdev" > "$work/preboot.plist"
[[ $(get "$work/preboot.plist" VolumeUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong Preboot UUID'
[[ $(get "$work/preboot.plist" APFSContainerReference) == "$container" ]] || fail 'Preboot in different container'
[[ $(get "$work/preboot.plist" VolumeName) == Preboot ]] || fail 'Wrong Preboot name'
mountpoint=$(get "$work/preboot.plist" MountPoint 2>/dev/null || true)
if [[ -z $mountpoint ]]; then
    fail "Verified Linux Preboot is unmounted. Report this message; device is $prebootdev."
fi
[[ $mountpoint == /Volumes/* && $mountpoint != *$'\n'* && $mountpoint != *$'\t'* ]] || fail 'Unexpected Preboot mount point'
[[ $(get "$work/preboot.plist" WritableVolume) == false ]] || fail "Verified Linux Preboot is not read-only ($prebootdev); report this message"
[[ -d $mountpoint/$vg && ! -L $mountpoint/$vg ]] || fail 'Volume-group directory missing or symlinked'
bputil -d -v "$vg" > "$work/boot-policy.txt"
policy=$(< "$work/boot-policy.txt")
[[ $policy == *'OS Type'*': one true recoveryOS'* && $policy == *'OS Pairing Status'*': Paired'* ]] || fail 'Not paired one true Recovery'
[[ $policy == *'Permissive (smb0 && smb1): 1'* ]] || fail 'Existing permissive policy not found'
diskutil apfs listVolumeGroups "$container" > "$work/volume-groups.txt"
diskutil list internal > "$work/disks.txt"
find "$mountpoint/$vg" -type f -name '*custom*' -print0 > "$work/paths.nul"
count=0
total=0
files=()
while IFS= read -r -d '' source; do
    [[ $source != *$'\n'* && $source != *$'\t'* && ! -L $source ]] || fail 'Unsafe backup source name'
    count=$((count + 1))
    [[ $count -le 16 ]] || fail 'Unexpected number of custom files'
    size=$(stat -f %z "$source")
    [[ $size =~ ^[0-9]+$ ]] || fail 'Invalid custom file size'
    total=$((total + size))
    [[ $total -le 33554432 ]] || fail 'Pre-install backup exceeds 32 MiB; do not use this collector after standalone installation'
    dest=$(printf 'custom-%02d.bin' "$count")
    files+=("$dest")
    source_sum=$(cksum < "$source")
    cp -p "$source" "$work/$dest"
    copy_sum=$(cksum < "$work/$dest")
    [[ $source_sum == "$copy_sum" && $source_sum == "$(cksum < "$source")" ]] || fail 'Source/copy mismatch or source changed'
    printf '%s\t%s\n' "$dest" "$source" >> "$work/manifest.tsv"
    printf '%s\t%s\n' "$source_sum" "$source" >> "$work/source-checksums.txt"
    printf '%s\t%s\n' "$copy_sum" "$dest" >> "$work/copy-checksums.txt"
done < "$work/paths.nul"
[[ $count -gt 0 ]] || fail 'No custom boot files found'
archive="$work/backup.tar.gz"
tar -czf "$archive" -C "$work" linux.plist preboot.plist linux-container.plist volume-groups.txt disks.txt boot-policy.txt paths.nul manifest.tsv source-checksums.txt copy-checksums.txt "${files[@]}"
set -- $(cksum < "$archive")
expected="$1 $2"
echo "Copied and checksum-verified $count files ($total bytes). Uploading backup only."
receipt=$(curl --fail --show-error --connect-timeout 10 --max-time 120 --upload-file "$archive" '@UPLOAD_URL@')
printf '%s\n' "$receipt"
[[ ${receipt%%$'\n'*} == "CKSUM $expected" ]] || fail 'Transferred archive checksum/size mismatch'
echo 'BACKUP SENT. Host must validate loader and policy next. No boot settings or partitions changed.'
echo 'Leave Recovery Terminal open. Do not reboot.'
