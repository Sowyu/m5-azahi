# Appended to reviewed read-only collector functions by recovery-root-server.py.
upload_report() {
    local stage=$1 archive="$work/$1/backup.tar.gz" receipt expected
    tar -czf "$archive" -C "$work/$stage" disk.plist disk-list.plist linux.plist linux-container.plist \
        gpt-primary.bin gpt-backup.bin linux-superblock.bin gpt.txt "${part_files[@]}"
    expected=$(fingerprint "$archive")
    receipt=$(curl -q --noproxy '*' --proto '=http' --fail --show-error --connect-timeout 10 --max-time 120 \
        --upload-file "$archive" "@TRANSFER_URL@/$stage")
    printf '%s\n' "$receipt"
    [[ ${receipt%%$'\n'*} == "CKSUM $expected" && ${receipt##*$'\n'} == "VALIDATED_ROOT_INSTALL $stage" ]] || fail 'Host metadata validation failed'
}
check_root() {
    local found=0 index info identity
    root_device=''
    for index in 0 1 2 3 4 5 6; do
        info="$1/part-$index.plist"
        [[ -f $info ]] || continue
        identity=$(get "$info" DiskUUID)
        if [[ $identity == PRIVATE-UUID-REMOVED ]]; then
            found=$((found + 1))
            root_device=$(get "$info" DeviceIdentifier)
            [[ $root_device =~ ^disk0s[1-9][0-9]*$ && $root_device != disk0s2 && $root_device != disk0s3 ]] || fail 'Invalid root device'
            [[ $(get "$info" Content) == 'Linux Filesystem' && $(get "$info" ParentWholeDisk) == disk0 ]] || fail 'Wrong root type/parent'
            [[ $(get "$info" PartitionMapPartitionOffset) == 835723767808 && $(get "$info" TotalSize) == 158779572224 ]] || fail 'Wrong root extent'
            [[ $(get "$info" DeviceBlockSize) == 4096 ]] || fail 'Wrong root sector size'
            local mountpoint
            mountpoint=$(get "$info" MountPoint 2>/dev/null || true)
            [[ -z $mountpoint ]] || fail 'Root partition mounted'
        fi
    done
    [[ $found == 1 ]] || fail 'Pinned root partition missing/duplicated'
    raw="/dev/r$root_device"
}
check_live_root() {
    diskutil info -plist "$root_device" > "$work/current-root.plist"
    [[ $(get "$work/current-root.plist" DiskUUID) == PRIVATE-UUID-REMOVED && $(get "$work/current-root.plist" PartitionMapPartitionOffset) == 835723767808 && $(get "$work/current-root.plist" TotalSize) == 158779572224 && $(get "$work/current-root.plist" DeviceBlockSize) == 4096 && $(get "$work/current-root.plist" ParentWholeDisk) == disk0 ]] || fail 'Root identity/extent changed'
    local mountpoint
    mountpoint=$(get "$work/current-root.plist" MountPoint 2>/dev/null || true)
    [[ -z $mountpoint ]] || fail 'Root became mounted'
}
collect "$work/preflight"
check_root "$work/preflight"
upload_report preflight
# Confirm supported dd flags on RAM scratch before any disk write.
dd if=/dev/zero of="$work/dd-feature-test" bs=4096 count=1 iflag=fullblock oflag=fsync 2> "$work/dd-feature-test.log"
dd if="$raw" of="$work/root-header-before.bin" bs=4096 count=17 iflag=fullblock 2> "$work/header-read.log"
[[ $(stat -f %z "$work/root-header-before.bin") == 69632 ]] || fail 'Short root prefix backup'
receipt=$(curl -q --noproxy '*' --proto '=http' --fail --show-error --connect-timeout 10 --max-time 120 \
    --upload-file "$work/root-header-before.bin" '@TRANSFER_URL@/prefix')
[[ $receipt == 'BLANK_ROOT_PREFIX_BACKED_UP' ]] || fail 'Root prefix validation failed; do not overwrite'
curl -q --noproxy '*' --proto '=http' --fail --show-error --connect-timeout 10 --max-time 120 \
    '@TRANSFER_URL@/manifest' -o "$work/chunks.txt"
[[ $(fingerprint "$work/chunks.txt") == '@MANIFEST_CKSUM@' ]] || fail 'Manifest checksum/size mismatch'
expected_index=0
expected_offset=0
echo 'Writing KDE to the new Linux root only. Keep charger connected; do not reboot.'
while read -r index offset bytes crc sha extra; do
    [[ -z ${extra:-} && $index =~ ^[0-9]+$ && $offset =~ ^[0-9]+$ && $bytes =~ ^[0-9]+$ && $crc =~ ^[0-9]+$ && $sha =~ ^[0-9a-f]{64}$ ]] || fail 'Invalid manifest row'
    [[ $index -eq $expected_index && $offset -eq $expected_offset && $bytes -gt 0 && $bytes -le 33554432 && $((bytes % 4096)) -eq 0 && $((offset % 1048576)) -eq 0 && $((offset + bytes)) -le 14248030208 ]] || fail 'Chunk outside image bounds'
    check_live_root
    curl -q --noproxy '*' --proto '=http' --fail --show-error --connect-timeout 10 --max-time 300 \
        --max-filesize "$bytes" "@TRANSFER_URL@/chunk/$index" -o "$work/chunk.bin"
    [[ $(fingerprint "$work/chunk.bin") == "$crc $bytes" ]] || fail 'Downloaded chunk corrupt/short'
    # Output is the bounded new partition device, never the whole disk.
    dd if="$work/chunk.bin" of="$raw" bs=1048576 seek=$((offset / 1048576)) conv=notrunc oflag=fsync 2> "$work/chunk-write.log"
    if [[ $((bytes % 1048576)) -eq 0 ]]; then
        dd if="$raw" of="$work/readback.bin" bs=1048576 skip=$((offset / 1048576)) count=$((bytes / 1048576)) iflag=fullblock 2> "$work/chunk-readback.log"
    else
        dd if="$raw" of="$work/readback.bin" bs=4096 skip=$((offset / 4096)) count=$((bytes / 4096)) iflag=fullblock 2> "$work/chunk-readback.log"
    fi
    [[ $(fingerprint "$work/readback.bin") == "$crc $bytes" ]] || fail 'SSD read-back checksum/length failed'
    receipt=$(curl -q --noproxy '*' --proto '=http' --fail --show-error --connect-timeout 10 --max-time 300 \
        --upload-file "$work/readback.bin" "@TRANSFER_URL@/verify/$index")
    [[ $receipt == "VERIFIED_CHUNK $index $sha" ]] || fail 'Host read-back SHA256 failed'
    expected_index=$((expected_index + 1))
    expected_offset=$((expected_offset + bytes))
    echo "KDE_COPY_VERIFIED $expected_index/425 bytes=$expected_offset/14248030208"
done < "$work/chunks.txt"
[[ $expected_index == 425 && $expected_offset == 14248030208 ]] || fail 'Incomplete chunk manifest'
receipt=$(curl -q --noproxy '*' --proto '=http' --fail --show-error '@TRANSFER_URL@/complete')
[[ $receipt == 'VERIFIED_IMAGE bc33421d52f06288c53cba128ccc79b13c077fb90f957fea048a5048cd955f7b' ]] || fail 'Whole-image read-back SHA256 failed'
collect "$work/after"
check_root "$work/after"
upload_report after
echo 'KDE_ROOT_IMAGE_INSTALLED_AND_VERIFIED. Bootloader and native writable-driver setup still pending.'
echo 'Leave Recovery open. Do not repeat the install command or boot yet.'
