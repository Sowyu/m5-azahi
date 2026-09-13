#!/bin/bash
# Explicit, volume-pinned custom-loader install/restore. No repartitioning.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
fail() { echo "STOP: $*" >&2; exit 1; }
[[ $(sysctl -n hw.model) == Mac17,9 ]] || fail 'Not the M5 target'
for required in cksum mktemp diskutil plutil bputil curl kmutil; do
    command -v "$required" >/dev/null || fail "Required tool unavailable: $required"
done
mode=${1:-}
case "$mode" in
    diag) selected=diag.bin; expected='901225419 1114112';;
    restore) selected=original.bin; expected='330887840 1114112';;
    *) fail 'Usage: bash /tmp/loader.sh diag   OR   bash /tmp/loader.sh restore';;
esac
work=$(mktemp -d /tmp/azahi-loader.XXXXXX)
echo "Working directory: $work"
get() { plutil -extract "$2" raw -o - "$1"; }
diskutil info -plist /Volumes/Linux > "$work/linux.plist"
[[ $(get "$work/linux.plist" VolumeName) == Linux ]] || fail 'Wrong volume name'
[[ $(get "$work/linux.plist" VolumeUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong system UUID'
vg=PRIVATE-UUID-REMOVED
[[ $(get "$work/linux.plist" APFSVolumeGroupID) == "$vg" ]] || fail 'Wrong volume group'
prebootdev=$(get "$work/linux.plist" BooterDeviceIdentifier)
[[ $prebootdev =~ ^disk[0-9]+s[0-9]+$ ]] || fail 'Invalid Preboot identifier'
diskutil info -plist "$prebootdev" > "$work/preboot.plist"
[[ $(get "$work/preboot.plist" VolumeUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong Preboot UUID'
[[ $(get "$work/preboot.plist" APFSContainerReference) == "$(get "$work/linux.plist" APFSContainerReference)" ]] || fail 'Different containers'
policy=$(bputil -d -v "$vg")
printf '%s\n' "$policy" > "$work/policy-before.txt"
[[ $policy == *': Paired'* ]] || fail 'Not paired Recovery'
[[ $policy == *'Permissive (smb0 && smb1): 1'* ]] || fail 'Expected existing permissive policy'
if [[ $mode == diag ]]; then
    [[ $policy == *'84EBA1015DBA2FE2D992D8161B2540F2ECBE1F895CE82EAC3A05B100EBDB39C8E2A815BADB88CD38ABC3388EC91E8269'* ]] || fail 'Original boot policy has changed'
fi
for artifact in diag.bin original.bin; do
    curl --fail --show-error --connect-timeout 10 --max-time 60 \
        "PRIVATE-LAN-ENDPOINT-REMOVED" -o "$work/$artifact"
done
[[ $(cksum < "$work/diag.bin") == '901225419 1114112' ]] || fail 'Diagnostic download checksum/size mismatch'
[[ $(cksum < "$work/original.bin") == '330887840 1114112' ]] || fail 'Original download checksum/size mismatch'
[[ $(cksum < "$work/$selected") == "$expected" ]] || fail 'Selected file mismatch'
echo "Target: Linux only, volume group $vg"
echo "Operation: $mode; raw loader entry 2048, lowest virtual address 0."
echo 'This changes the Linux custom boot object. It does not install KDE.'
echo 'No partition changes, macOS changes, security downgrade, or automatic reboot.'
echo 'Original loader is backed up on the M1 host; restore mode reinstalls it.'
printf 'Type INSTALL to proceed, or anything else to stop: '
IFS= read -r confirmation
[[ $confirmation == INSTALL ]] || fail 'Cancelled before boot changes'
# Only the UUID-verified Linux Preboot volume is made writable for kmutil.
if [[ -n $(get "$work/preboot.plist" MountPoint 2>/dev/null || true) ]]; then
    diskutil unmount "$prebootdev"
fi
diskutil mount "$prebootdev"
diskutil info -plist "$prebootdev" > "$work/preboot-writable.plist"
[[ $(get "$work/preboot-writable.plist" VolumeUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Preboot identity changed'
[[ $(get "$work/preboot-writable.plist" WritableVolume) == true ]] || fail 'Preboot not writable'
echo 'Configuring the selected Linux loader; enter administrator credentials locally if asked.'
kmutil configure-boot -c "$work/$selected" --raw --entry-point 2048 \
    --lowest-virtual-address 0 -v /Volumes/Linux
bputil -d -v "$vg" > "$work/policy-after.txt"
echo "KMUTIL_COMPLETED mode=$mode. Leave this screen open for verification."
echo "Policy output: $work/policy-after.txt"
echo 'Do not reboot yet.'
