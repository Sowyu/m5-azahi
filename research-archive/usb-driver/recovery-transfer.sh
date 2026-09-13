#!/bin/bash
# Rendered only by transfer-server.py; do not run the template.
# snapshot: RO backup; install/rollback: ONLY verified Linux Preboot + Linux policy.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
fail() { echo "STOP: $*. Leave Recovery open; do not reboot." >&2; exit 1; }
for tool in sysctl cksum mktemp diskutil plutil bputil curl kmutil stat cp tar awk; do
    command -v "$tool" >/dev/null || fail "Missing $tool"
done
[[ $(sysctl -n hw.model) == Mac17,9 ]] || fail 'Wrong model'
mode=${1:-snapshot}
case "$mode" in snapshot|install|rollback) ;; *) fail 'Expected snapshot, install or rollback' ;; esac
vg=PRIVATE-UUID-REMOVED
system_uuid=PRIVATE-UUID-REMOVED
preboot_uuid=PRIVATE-UUID-REMOVED
nsih='@NSIH@'
baseline_coih='@BASELINE_COIH@'
baseline_wrapped='@BASELINE_WRAPPED@'
work=$(mktemp -d /tmp/azahi-usb-transfer.XXXXXX)
get() { plutil -extract "$2" raw -o - "$1"; }
identity() {
    diskutil info -plist "$system_uuid" > "$work/linux.plist"
    [[ $(get "$work/linux.plist" VolumeUUID) == "$system_uuid" && $(get "$work/linux.plist" APFSVolumeGroupID) == "$vg" ]] || fail 'Linux UUID/group mismatch'
    [[ $(get "$work/linux.plist" VolumeName) == Linux && $(get "$work/linux.plist" MountPoint) == /Volumes/Linux ]] || fail 'Linux mount mismatch'
    container=$(get "$work/linux.plist" APFSContainerReference)
    [[ $container =~ ^disk[0-9]+$ ]] || fail 'Invalid Linux container identifier'
    diskutil apfs list "$container" -plist > "$work/linux-container.plist"
    [[ $(get "$work/linux-container.plist" Containers.0.APFSContainerUUID) == PRIVATE-UUID-REMOVED && $(get "$work/linux-container.plist" Containers.0.CapacityCeiling) == 96000000000 ]] || fail 'Wrong Linux container'
    free=$(get "$work/linux-container.plist" Containers.0.CapacityFree)
    [[ $free =~ ^[0-9]+$ && $free -ge 536870912 ]] || fail 'Insufficient Linux container space'
    prebootdev=$(get "$work/linux.plist" BooterDeviceIdentifier)
    [[ $prebootdev =~ ^disk[0-9]+s[0-9]+$ ]] || fail 'Invalid Preboot identifier'
    diskutil info -plist "$prebootdev" > "$work/preboot.plist"
    [[ $(get "$work/preboot.plist" VolumeUUID) == "$preboot_uuid" && $(get "$work/preboot.plist" APFSContainerReference) == "$container" ]] || fail 'Wrong Preboot UUID/container'
    mountpoint=$(get "$work/preboot.plist" MountPoint 2>/dev/null || true)
    [[ $mountpoint == /Volumes/* && $mountpoint != *$'\n'* && $mountpoint != *$'\t'* && $mountpoint != *'/../'* ]] || fail "Linux Preboot unmounted or unexpected mount ($prebootdev)"
    bootdir="$mountpoint/$vg/boot/$nsih/System/Library/Caches/com.apple.kernelcaches"
    [[ -d $bootdir && ! -L $bootdir ]] || fail 'Pinned Linux boot directory missing'
}
policy_check() {
    bputil -d -v "$vg" > "$1"
    policy=$(< "$1")
    [[ $policy == "Operating on Volume Group UUID $vg"* ]] || fail 'Policy target mismatch'
    [[ $policy == *'OS Type'*': one true recoveryOS'* && $policy == *'OS Pairing Status'*': Paired'* && $policy == *'Pairing Integrity'*': Valid'* ]] || fail 'Not valid Linux-paired Recovery'
    [[ $policy == *'Permissive (smb0 && smb1): 1'* && $policy == *'SIP Status:                  Enabled    (sip0): absent'* && $policy == *'Signed System Volume Status: Enabled    (sip1): absent'* && $policy == *'Kernel CTRR Status:          Disabled   (sip2): 1'* ]] || fail 'Security policy mismatch'
    [[ $policy == *"(nsih): $nsih"* && $policy == *'(CHIP): 0x6050'* && $policy == *'(BORD): 0x8'* && $policy == *'(ECID): PRIVATE-ECID-REMOVED'* ]] || fail 'Firmware/target changed'
    coih=$(awk '/^CustomKC or fuOS Image4 Hash.*\(coih\): / {print $NF}' "$1")
    [[ $coih =~ ^[0-9A-F]{96}$ ]] || fail 'Invalid/ambiguous coih'
}
check_base() {
    local file="$bootdir/kernelcache.custom.$baseline_coih"
    [[ -f $file && ! -L $file ]] || fail 'Current KDE rollback object missing'
    [[ $(cksum < "$file") == "$baseline_wrapped" ]] || fail 'KDE rollback object changed'
}
snapshot_object() {
    local source="$bootdir/kernelcache.custom.$coih" size sum
    [[ -f $source && ! -L $source ]] || fail 'Selected object missing/symlink'
    size=$(stat -f %z "$source")
    [[ $size =~ ^[0-9]+$ && $size -gt 0 && $size -le 100663296 ]] || fail 'Selected object size out of bounds'
    sum=$(cksum < "$source")
    cp -p "$source" "$work/installed.bin"
    [[ $(cksum < "$work/installed.bin") == "$sum" && $(cksum < "$source") == "$sum" ]] || fail 'Backup/readback differs from source'
    printf '%s\n' "$source" > "$work/installed-path.txt"
    printf '%s\n' "$sum" > "$work/installed-cksum.txt"
}
upload() {
    printf '%s\n' "$mode" > "$work/mode.txt"
    tar -czf "$work/readback.tar.gz" -C "$work" linux.plist preboot.plist linux-container.plist policy-before.txt policy-rechecked.txt policy-after.txt installed.bin installed-cksum.txt installed-path.txt mode.txt
    local sum receipt
    sum=$(cksum < "$work/readback.tar.gz")
    receipt=$(curl --fail --show-error --connect-timeout 10 --max-time 240 --upload-file "$work/readback.tar.gz" '@UPLOAD_URL@/'"$mode")
    printf '%s\n' "$receipt"
    [[ ${receipt%%$'\n'*} == "CKSUM $sum" && $receipt == *"VALIDATED $mode"* ]] || fail 'Host did not validate backup/readback'
}
identity
[[ $(get "$work/preboot.plist" WritableVolume) == false ]] || fail "Linux Preboot must start read-only ($prebootdev)"
policy_check "$work/policy-before.txt"
before_coih=$coih
if [[ $mode != rollback ]]; then
    [[ $coih == "$baseline_coih" ]] || fail 'Current selected boot differs from known KDE image'
fi
check_base
if [[ $mode == snapshot ]]; then
    snapshot_object
    policy_check "$work/policy-rechecked.txt"
    [[ $coih == "$before_coih" ]] || fail 'Policy changed during backup'
    cp "$work/policy-rechecked.txt" "$work/policy-after.txt"
    identity
    [[ $(get "$work/preboot.plist" WritableVolume) == false ]] || fail 'Preboot state changed'
    upload
    echo 'BACKUP HOST-VERIFIED. No mounts, policy changes or persistent writes. Leave Recovery open.'
    exit 0
fi
[[ '@ENABLE_INSTALL@' == yes ]] || fail 'Installer unavailable until fresh backup is host-verified'
selected=candidate.bin
expected='@CANDIDATE_CKSUM@'
word=INSTALL
if [[ $mode == rollback ]]; then selected=rollback.bin; expected='750659463 92651520'; word=RESTORE; fi
for artifact in candidate.bin rollback.bin; do
    curl --fail --show-error --connect-timeout 10 --max-time 240 '@BASE_URL@/'"$artifact" -o "$work/$artifact"
done
[[ $(cksum < "$work/rollback.bin") == '750659463 92651520' ]] || fail 'Rollback download mismatch'
[[ $(cksum < "$work/candidate.bin") == '@CANDIDATE_CKSUM@' && $(cksum < "$work/$selected") == "$expected" ]] || fail 'Candidate download mismatch'
echo 'ONLY Linux-paired boot object will change. No partition/format/macOS operation.'
echo 'Rollback restores the working autonomous SSD KDE image, not proxy.'
printf 'Type %s: ' "$word"
IFS= read -r answer
[[ $answer == "$word" ]] || fail 'Cancelled without boot changes'
identity
[[ $(get "$work/preboot.plist" WritableVolume) == false ]] || fail 'Preboot state changed'
policy_check "$work/policy-rechecked.txt"
[[ $coih == "$before_coih" ]] || fail 'Policy changed before write'
check_base
verified_preboot=$prebootdev
diskutil unmount "$verified_preboot"
diskutil mount "$verified_preboot"
identity
[[ $prebootdev == "$verified_preboot" && $(get "$work/preboot.plist" WritableVolume) == true ]] || fail 'Writable Preboot identity mismatch'
check_base
kmutil configure-boot -c "$work/$selected" --raw --entry-point 2048 --lowest-virtual-address 0 -v /Volumes/Linux || fail 'kmutil failed; do not retry blindly'
policy_check "$work/policy-after.txt"
if [[ $mode == install ]]; then
    [[ $coih != "$before_coih" ]] || fail 'No new boot selection'
    check_base
fi
snapshot_object
diskutil unmount "$verified_preboot"
diskutil mount readOnly "$verified_preboot"
identity
[[ $prebootdev == "$verified_preboot" && $(get "$work/preboot.plist" WritableVolume) == false ]] || fail 'Final Preboot not read-only'
[[ $(cksum < "$bootdir/kernelcache.custom.$coih") == "$(< "$work/installed-cksum.txt")" ]] || fail 'Persisted readback mismatch'
upload
echo 'INSTALLED AND HOST-VERIFIED. Cold boot untested; leave Recovery open for instructions.'
