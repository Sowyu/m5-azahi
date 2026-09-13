#!/bin/bash
# Read-only post-cold-boot evidence. No mount, policy, nvram or disk writes.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
fail() { echo "STOP: $*" >&2; exit 1; }
for required in sysctl diskutil plutil bputil mktemp cksum tar curl stat head tail awk; do
    command -v "$required" >/dev/null || fail "Missing tool: $required"
done
[[ $(sysctl -n hw.model) == Mac17,9 ]] || fail 'Wrong target model'
work=$(mktemp -d /tmp/azahi-boot-diagnose.XXXXXX)
echo "Read-only boot evidence: $work"
get() { plutil -extract "$2" raw -o - "$1"; }
vg=PRIVATE-UUID-REMOVED
diskutil info -plist PRIVATE-UUID-REMOVED > "$work/linux.plist"
[[ $(get "$work/linux.plist" VolumeUUID) == PRIVATE-UUID-REMOVED && $(get "$work/linux.plist" APFSVolumeGroupID) == "$vg" ]] || fail 'Linux identity mismatch'
container=$(get "$work/linux.plist" APFSContainerReference)
[[ $container =~ ^disk[0-9]+$ ]] || fail 'Invalid container identifier'
diskutil apfs list "$container" -plist > "$work/linux-container.plist"
[[ $(get "$work/linux-container.plist" Containers.0.APFSContainerUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong Linux container'
prebootdev=$(get "$work/linux.plist" BooterDeviceIdentifier)
[[ $prebootdev =~ ^disk[0-9]+s[0-9]+$ ]] || fail 'Invalid Preboot identifier'
diskutil info -plist "$prebootdev" > "$work/preboot.plist"
[[ $(get "$work/preboot.plist" VolumeUUID) == PRIVATE-UUID-REMOVED && $(get "$work/preboot.plist" APFSContainerReference) == "$container" ]] || fail 'Preboot identity mismatch'
files=(linux.plist linux-container.plist preboot.plist)
# Optional evidence collection records absent tools/fields without losing the
# rest of the report. Each command output is capped, and no NVRAM values set.
capture() {
    local name=$1 result
    shift
    files+=("$name" "$name.status")
    if "$@" 2>&1 | head -c 1048576 > "$work/$name"; then result=0; else result=$?; fi
    printf '%s\n' "$result" > "$work/$name.status"
}
capture boot-policy.txt bputil -d -v "$vg"
capture chosen.txt ioreg -p IODeviceTree -n chosen -r -l -w 0
for key in boot-volume alt-boot-volume boot-args boot-breadcrumbs failboot-breadcrumbs iboot-failure-reason iboot-failure-reason-str iboot-failure-volume; do
    capture "nvram-$key.txt" nvram "$key"
done
# Apple can store these under GUID-qualified names. Return only the exact
# boot-diagnostic keys, never a complete NVRAM dump or unrelated values.
boot_nvram() {
    nvram -p | awk '$1 ~ /(^|:)(boot-volume|alt-boot-volume|boot-args|boot-breadcrumbs|failboot-breadcrumbs|iboot-failure-reason|iboot-failure-reason-str|iboot-failure-volume)$/ {print}'
}
capture nvram-boot-fields-qualified.txt boot_nvram
capture system-version.txt sw_vers
capture recovery-log-tail.txt tail -c 1048576 /var/log/recovery.log
files+=(selected-object.txt)
mountpoint=$(get "$work/preboot.plist" MountPoint 2>/dev/null || true)
coih=$(awk '/^CustomKC or fuOS Image4 Hash.*\(coih\): / {print $NF}' "$work/boot-policy.txt")
nsih=$(awk '/^Next Stage Image4 Hash.*\(nsih\): / {print $NF}' "$work/boot-policy.txt")
if [[ -z $mountpoint ]]; then
    echo "PREBOOT_UNMOUNTED $prebootdev (left unchanged)" > "$work/selected-object.txt"
elif [[ $mountpoint == /Volumes/* && $mountpoint != *$'\n'* && $mountpoint != *$'\t'* && $coih =~ ^[0-9A-F]{96}$ && $nsih =~ ^[0-9A-F]{96}$ ]]; then
    source="$mountpoint/$vg/boot/$nsih/System/Library/Caches/com.apple.kernelcaches/kernelcache.custom.$coih"
    if [[ -f $source && ! -L $source ]]; then
        size=$(stat -f %z "$source")
        [[ $size =~ ^[0-9]+$ && $size -le 100663296 ]] || fail 'Selected object exceeds read bound'
        printf 'SOURCE %s\nCKSUM %s\n' "$source" "$(cksum < "$source")" > "$work/selected-object.txt"
    else
        printf 'SELECTED_OBJECT_MISSING %s\n' "$source" > "$work/selected-object.txt"
    fi
else
    echo 'MOUNT_OR_POLICY_UNRESOLVED (no boot object read attempted)' > "$work/selected-object.txt"
fi
tar -czf "$work/backup.tar.gz" -C "$work" "${files[@]}"
expected=$(cksum < "$work/backup.tar.gz")
receipt=$(curl --fail --show-error --connect-timeout 10 --max-time 120 --upload-file "$work/backup.tar.gz" '@UPLOAD_URL@')
printf '%s\n' "$receipt"
[[ ${receipt%%$'\n'*} == "CKSUM $expected" ]] || fail 'Diagnostic transfer mismatch'
echo 'BOOT_DIAGNOSTICS_SENT. No mounts, boot settings, partitions or NVRAM changed.'
echo 'Leave Recovery Terminal open; do not reinstall or reboot.'
