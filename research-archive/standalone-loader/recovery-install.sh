#!/bin/bash
# Private J714s only. Linux Preboot enrollment; no partition/root/macOS writes.
# TEMPLATE ONLY: install-server.py renders current V5 and aligned-v3 pins.
# Never run this unrendered file or an older downloaded helper.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
fail() { echo "STOP: $*. Do not reboot." >&2; exit 1; }
for required in sysctl cksum mktemp diskutil plutil bputil curl kmutil stat cp tar awk; do
    command -v "$required" >/dev/null || fail "Required tool unavailable: $required"
done
[[ $(sysctl -n hw.model) == Mac17,9 ]] || fail 'Wrong target model'
mode=${1:-}
case "$mode" in
    install) selected=standalone.bin; expected='819284573 92651350'; confirmation_word=INSTALL;;
    rollback) selected=v5.bin; expected='901225419 1114112'; confirmation_word=RESTORE;;
    *) fail 'Usage: bash /tmp/ssdboot.sh install OR bash /tmp/ssdboot.sh rollback';;
esac
vg=PRIVATE-UUID-REMOVED
system_uuid=PRIVATE-UUID-REMOVED
preboot_uuid=PRIVATE-UUID-REMOVED
nsih=EA497C1B131D21D16D406E4F2EF5C0E52F11381A52AE8A606D1D111E928F4B6D50876EE195FD5C5AEB78F2FE8A79A1C6
v5_coih=F2BB0BDC7EB3154646420C1F976F9A7AD74B9F1F80C9A2E3243A785068C8BA457F495C2F2EB1F9EF488A45449A24894E
original_coih=84EBA1015DBA2FE2D992D8161B2540F2ECBE1F895CE82EAC3A05B100EBDB39C8E2A815BADB88CD38ABC3388EC91E8269
work=$(mktemp -d /tmp/azahi-enroll.XXXXXX)
echo "Temporary work directory: $work"
get() { plutil -extract "$2" raw -o - "$1"; }
identity() {
    diskutil info -plist "$system_uuid" > "$work/linux.plist"
    [[ $(get "$work/linux.plist" VolumeUUID) == "$system_uuid" ]] || fail 'Wrong Linux UUID'
    [[ $(get "$work/linux.plist" APFSVolumeGroupID) == "$vg" ]] || fail 'Wrong Linux group'
    [[ $(get "$work/linux.plist" VolumeName) == Linux && $(get "$work/linux.plist" MountPoint) == /Volumes/Linux ]] || fail 'Linux mount mismatch'
    container=$(get "$work/linux.plist" APFSContainerReference)
    [[ $container =~ ^disk[0-9]+$ ]] || fail 'Invalid container identifier'
    diskutil apfs list "$container" -plist > "$work/linux-container.plist"
    [[ $(get "$work/linux-container.plist" Containers.0.APFSContainerUUID) == PRIVATE-UUID-REMOVED ]] || fail 'Wrong Linux container'
    [[ $(get "$work/linux-container.plist" Containers.0.CapacityCeiling) == 96000000000 ]] || fail 'Wrong Linux container size'
    free=$(get "$work/linux-container.plist" Containers.0.CapacityFree)
    [[ $free =~ ^[0-9]+$ && $free -ge 536870912 ]] || fail 'Insufficient Linux container free space'
    prebootdev=$(get "$work/linux.plist" BooterDeviceIdentifier)
    [[ $prebootdev =~ ^disk[0-9]+s[0-9]+$ ]] || fail 'Invalid Preboot identifier'
    diskutil info -plist "$prebootdev" > "$work/preboot.plist"
    [[ $(get "$work/preboot.plist" VolumeUUID) == "$preboot_uuid" ]] || fail 'Wrong Preboot UUID'
    [[ $(get "$work/preboot.plist" APFSContainerReference) == "$container" ]] || fail 'Wrong Preboot container'
    mountpoint=$(get "$work/preboot.plist" MountPoint)
    [[ $mountpoint == /Volumes/* && $mountpoint != *$'\n'* && $mountpoint != *$'\t'* ]] || fail 'Unexpected Preboot mount'
    bootdir="$mountpoint/$vg/boot/$nsih/System/Library/Caches/com.apple.kernelcaches"
    [[ -d $bootdir && ! -L $bootdir ]] || fail 'Pinned boot directory missing'
}
policy_check() {
    bputil -d -v "$vg" > "$1"
    policy=$(< "$1")
    [[ $policy == "Operating on Volume Group UUID $vg"* ]] || fail 'Policy target mismatch'
    [[ $policy == *'OS Type'*': one true recoveryOS'* && $policy == *'OS Pairing Status'*': Paired'* ]] || fail 'Not paired one true Recovery'
    [[ $policy == *'Pairing Integrity'*': Valid'* ]] || fail 'Invalid pairing integrity'
    [[ $policy == *'Permissive (smb0 && smb1): 1'* ]] || fail 'Existing permissive policy missing'
    [[ $policy == *'SIP Status:                  Enabled    (sip0): absent'* && $policy == *'Signed System Volume Status: Enabled    (sip1): absent'* && $policy == *'Kernel CTRR Status:          Disabled   (sip2): 1'* ]] || fail 'Security policy changed'
    [[ $policy == *"(nsih): $nsih"* && $policy == *'(CHIP): 0x6050'* && $policy == *'(BORD): 0x8'* && $policy == *'(ECID): PRIVATE-ECID-REMOVED'* ]] || fail 'Firmware or target policy identity changed'
    coih=$(awk '/^CustomKC or fuOS Image4 Hash.*\(coih\): / {print $NF}' "$1")
    [[ $coih =~ ^[0-9A-F]{96}$ ]] || fail 'Invalid/ambiguous coih'
}
old_files_check() {
    local source phase=${1:-before}
    source="$bootdir/kernelcache.custom.$original_coih"
    [[ -f $source && ! -L $source ]] || fail 'Original backup source missing'
    [[ $(cksum < "$source") == '1531755257 1117034' ]] || fail 'Original wrapped object changed'
    source="$bootdir/kernelcache.custom.$v5_coih"
    [[ -f $source && ! -L $source ]] || fail 'V5 backup source missing'
    # Re-enrollment may regenerate V5's signed wrapper at its existing name.
    # Before any write require the backed-up bytes; after rollback the host
    # verifies the selected raw V5 SHA instead. Original stays pinned always.
    if [[ $mode != rollback || $phase != after ]]; then
        [[ $(cksum < "$source") == '2652175684 1117034' ]] || fail 'V5 wrapped object changed'
    fi
}
identity
[[ $(get "$work/preboot.plist" WritableVolume) == false ]] || fail 'Preboot must start read-only'
policy_check "$work/policy-before.txt"
old_files_check
before_coih=$coih
if [[ $mode == install ]]; then
    [[ $coih == "$v5_coih" ]] || fail 'Boot policy no longer selects the backed-up V5'
fi
echo 'Downloading pinned boot artifacts to temporary storage.'
artifacts=(v5.bin)
if [[ $mode == install ]]; then artifacts+=(standalone.bin); fi
for artifact in "${artifacts[@]}"; do
    curl --fail --show-error --connect-timeout 10 --max-time 240 '@BASE_URL@/'"$artifact" -o "$work/$artifact"
done
if [[ $mode == install ]]; then
    [[ $(cksum < "$work/standalone.bin") == '819284573 92651350' ]] || fail 'Candidate download checksum/size mismatch'
fi
[[ $(cksum < "$work/v5.bin") == '901225419 1114112' ]] || fail 'Rollback download checksum/size mismatch'
[[ $(cksum < "$work/$selected") == "$expected" ]] || fail 'Selected artifact mismatch'
echo "Operation: $mode; ONLY Linux group $vg, raw entry 2048."
echo 'The original and V5 wrapped objects are backed up on the host.'
echo 'No partition changes, security downgrade, daily macOS writes, or automatic reboot.'
echo 'If standalone fails to cold-boot, return to paired Linux Recovery and use rollback mode.'
printf 'Type %s to proceed: ' "$confirmation_word"
IFS= read -r answer
[[ $answer == "$confirmation_word" ]] || fail 'Cancelled before changes'
# Repeat identity, policy and file checks immediately before writable remount.
identity
[[ $(get "$work/preboot.plist" WritableVolume) == false ]] || fail 'Preboot state changed'
policy_check "$work/policy-rechecked.txt"
[[ $coih == "$before_coih" ]] || fail 'Policy changed during download/confirmation'
old_files_check
verified_preboot=$prebootdev
diskutil unmount "$verified_preboot"
diskutil mount "$verified_preboot"
identity
[[ $prebootdev == "$verified_preboot" && $(get "$work/preboot.plist" WritableVolume) == true ]] || fail 'Writable Preboot identity mismatch'
old_files_check
echo 'Configuring Linux boot object. Enter owner credentials locally if requested.'
if ! kmutil configure-boot -c "$work/$selected" --raw --entry-point 2048 --lowest-virtual-address 0 -v /Volumes/Linux; then
    fail "kmutil failed; work preserved at $work. Report exact error; do not retry blindly"
fi
policy_check "$work/policy-after.txt"
if [[ $mode == install ]]; then
    [[ $coih != "$v5_coih" && $coih != "$original_coih" ]] || fail 'Policy did not select a new boot object'
fi
old_files_check after
source="$bootdir/kernelcache.custom.$coih"
[[ -f $source && ! -L $source ]] || fail 'Selected installed object missing'
size=$(stat -f %z "$source")
[[ $size =~ ^[0-9]+$ && $size -le 100663296 ]] || fail 'Installed object too large'
sum=$(cksum < "$source")
cp -p "$source" "$work/installed.bin"
[[ $sum == "$(cksum < "$work/installed.bin")" && $sum == "$(cksum < "$source")" ]] || fail 'Installed readback copy mismatch'
printf '%s\n' "$sum" > "$work/installed-cksum.txt"
printf '%s\n' "$source" > "$work/installed-path.txt"
printf '%s\n' "$mode" > "$work/mode.txt"
# Flush via clean unmount, then verify the persisted selected object read-only.
diskutil unmount "$verified_preboot"
diskutil mount readOnly "$verified_preboot"
identity
[[ $(get "$work/preboot.plist" WritableVolume) == false ]] || fail 'Final Preboot not read-only'
source="$bootdir/kernelcache.custom.$coih"
[[ $(cksum < "$source") == "$sum" ]] || fail 'Read-only remount readback mismatch'
old_files_check after
tar -czf "$work/after.tar.gz" -C "$work" linux.plist preboot.plist linux-container.plist policy-before.txt policy-rechecked.txt policy-after.txt installed.bin installed-cksum.txt installed-path.txt mode.txt
archive_sum=$(cksum < "$work/after.tar.gz")
echo 'Uploading installed-object readback for host SHA256 and structure verification.'
receipt=$(curl --fail --show-error --connect-timeout 10 --max-time 240 --upload-file "$work/after.tar.gz" '@UPLOAD_URL@/'"$mode")
printf '%s\n' "$receipt"
[[ ${receipt%%$'\n'*} == "CKSUM $archive_sum" ]] || fail 'Readback transfer mismatch'
[[ $receipt == *"VALIDATED $mode"* ]] || fail 'Host did not validate installed payload'
echo 'INSTALLED AND HOST-VERIFIED. Leave Recovery open; wait for cold-boot instructions.'
