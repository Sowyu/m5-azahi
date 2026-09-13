# Offline tests only. Every apparent block-device operation is redirected to fixtures.
sysctl() { echo Mac17,9; }
mktemp() { /usr/bin/mktemp -d "$ROOT_TEST_DIR/work.XXXXXX"; }
diskutil() {
    local info identifier
    case "$*" in
        'info -plist disk0') /bin/cat "$ROOT_TEST_DIR/disk.plist" ;;
        'info -plist PRIVATE-UUID-REMOVED') /bin/cat "$ROOT_TEST_DIR/linux.plist" ;;
        'info -plist disk0s'*)
            for info in "$ROOT_TEST_DIR"/part-*.plist; do
                identifier=$(/usr/bin/plutil -extract DeviceIdentifier raw -o - "$info")
                if [[ $identifier == "$3" ]]; then /bin/cat "$info"; return; fi
            done
            return 90 ;;
        'list -plist disk0') /bin/cat "$ROOT_TEST_DIR/disk-list.plist" ;;
        'apfs list disk3 -plist') /bin/cat "$ROOT_TEST_DIR/linux-container.plist" ;;
        *) echo "Unexpected diskutil: $*" >&2; return 91 ;;
    esac
}
gpt() { [[ $* == '-r show -l /dev/disk0' ]] || return 92; /bin/cat "$ROOT_TEST_DIR/gpt.txt"; }
dd() {
    local input='' output='' argument backup=false count='' seek=0
    for argument in "$@"; do
        case "$argument" in
            if=*) input=${argument#if=} ;;
            of=*) output=${argument#of=} ;;
            skip=244276259) backup=true ;;
            count=*) count=${argument#count=} ;;
            seek=*) seek=${argument#seek=} ;;
            bs=4096|bs=1048576|iflag=fullblock|oflag=fsync|conv=notrunc|skip=0) ;;
            *) echo 'Unexpected dd operand' >&2; return 93 ;;
        esac
    done
    if [[ $output == /dev/rdisk0s5 ]]; then
        [[ $input == "$ROOT_TEST_DIR"/*/chunk.bin && $seek == 0 ]] || return 94
        echo ROOT_CHUNK_WRITE >> "$ROOT_TEST_DIR/mutations"
        /bin/cp "$input" "$ROOT_TEST_DIR/device.bin"
        return
    fi
    case "$output" in "$ROOT_TEST_DIR"/*) ;; *) echo 'Forbidden write target' >&2; return 95 ;; esac
    case "$input" in
        /dev/rdisk0)
            if $backup; then /bin/cp "$ROOT_TEST_DIR/gpt-backup.bin" "$output"
            else /bin/cp "$ROOT_TEST_DIR/gpt-primary.bin" "$output"; fi ;;
        /dev/rdisk0s3) /bin/cp "$ROOT_TEST_DIR/linux-superblock.bin" "$output" ;;
        /dev/zero) /bin/cp "$ROOT_TEST_DIR/zeros.bin" "$output" ;;
        /dev/rdisk0s5)
            if [[ $count == 17 ]]; then /bin/cp "$ROOT_TEST_DIR/prefix.bin" "$output"
            elif [[ ${ROOT_TEST_MODE:-} == corrupt_readback ]]; then /bin/cp "$ROOT_TEST_DIR/corrupt.bin" "$output"
            else /bin/cp "$ROOT_TEST_DIR/device.bin" "$output"; fi ;;
        *) return 96 ;;
    esac
}
curl() {
    local file='' out='' url='' previous='' arg stage crc sha
    for arg in "$@"; do
        [[ $previous != --upload-file ]] || file=$arg
        [[ $previous != -o ]] || out=$arg
        case "$arg" in http://127.0.0.1/*) url=$arg ;; esac
        previous=$arg
    done
    case "$url" in
        */preflight|*/after)
            stage=${url##*/}
            if [[ ${ROOT_TEST_MODE:-} == bad_preflight ]]; then echo 'FAILED'; return; fi
            set -- $(/usr/bin/cksum "$file")
            echo "CKSUM $1 $2"
            echo "VALIDATED_ROOT_INSTALL $stage" ;;
        */prefix) echo BLANK_ROOT_PREFIX_BACKED_UP ;;
        */manifest) /bin/cp "$ROOT_TEST_DIR/manifest.txt" "$out" ;;
        */chunk/0)
            if [[ ${ROOT_TEST_MODE:-} == corrupt_download ]]; then /bin/cp "$ROOT_TEST_DIR/corrupt.bin" "$out"
            else /bin/cp "$ROOT_TEST_DIR/source.bin" "$out"; fi ;;
        */verify/0)
            if [[ ${ROOT_TEST_MODE:-} == bad_sha ]]; then echo 'FAILED'; return; fi
            sha=$(/usr/bin/shasum -a 256 "$file"); sha=${sha%% *}
            echo "VERIFIED_CHUNK 0 $sha" ;;
        */complete) sha=$(/usr/bin/shasum -a 256 "$ROOT_TEST_DIR/source.bin"); echo "VERIFIED_IMAGE ${sha%% *}" ;;
        *) echo 'Unexpected test URL' >&2; return 97 ;;
    esac
}
export -f sysctl mktemp diskutil gpt dd curl
