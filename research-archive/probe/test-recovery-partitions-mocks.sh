# Test-only functions. All data reads/writes are inside RESIZE_TEST_DIR.
sysctl() { echo Mac17,9; }
test_phase() {
    if [[ -e $RESIZE_TEST_DIR/root-created ]]; then echo root
    elif [[ -e $RESIZE_TEST_DIR/esp-created ]]; then echo esp
    else echo before; fi
}
diskutil() {
    local phase info candidate
    phase=$(test_phase)
    case "$*" in
        'info -plist disk0') /bin/cat "$RESIZE_TEST_DIR/$phase/disk.plist" ;;
        'info -plist PRIVATE-UUID-REMOVED') /bin/cat "$RESIZE_TEST_DIR/$phase/linux.plist" ;;
        'info -plist disk0s'*)
            for info in "$RESIZE_TEST_DIR/$phase"/part-*.plist; do
                candidate=$(/usr/bin/plutil -extract DeviceIdentifier raw -o - "$info")
                if [[ $candidate == "$3" ]]; then /bin/cat "$info"; return; fi
            done
            return 90 ;;
        'list -plist disk0') /bin/cat "$RESIZE_TEST_DIR/$phase/disk-list.plist" ;;
        'apfs list disk3 -plist') /bin/cat "$RESIZE_TEST_DIR/$phase/linux-container.plist" ;;
        'addPartition disk0s3 %PRIVATE-UUID-REMOVED% %noformat% 536870912')
            echo "$*" >> "$RESIZE_TEST_DIR/mutations"
            /usr/bin/touch "$RESIZE_TEST_DIR/esp-created" ;;
        'addPartition disk0s6 %PRIVATE-UUID-REMOVED% %noformat% 158913789952')
            echo "$*" >> "$RESIZE_TEST_DIR/mutations"
            /usr/bin/touch "$RESIZE_TEST_DIR/root-created" ;;
        *) echo "Unexpected diskutil call: $*" >&2; return 91 ;;
    esac
}
dd() {
    local phase input='' output='' argument backup=false
    phase=$(test_phase)
    for argument in "$@"; do
        case "$argument" in
            if=*) input=${argument#if=} ;;
            of=*) output=${argument#of=} ;;
            skip=244276259) backup=true ;;
            bs=4096|count=6|count=1) ;;
            *) return 92 ;;
        esac
    done
    case "$output" in "$RESIZE_TEST_DIR"/*) ;; *) return 93 ;; esac
    if [[ ${PART_TEST_MODE:-} == changed_gpt && $output == */final-primary.bin ]]; then
        /bin/cp "$RESIZE_TEST_DIR/esp/gpt-primary.bin" "$output"; return
    fi
    case "$input" in
        /dev/rdisk0s3) /bin/cp "$RESIZE_TEST_DIR/$phase/linux-superblock.bin" "$output" ;;
        /dev/rdisk0)
            if $backup; then /bin/cp "$RESIZE_TEST_DIR/$phase/gpt-backup.bin" "$output"
            else /bin/cp "$RESIZE_TEST_DIR/$phase/gpt-primary.bin" "$output"; fi ;;
        *) return 94 ;;
    esac
}
gpt() { [[ $* == '-r show -l /dev/disk0' ]] || return 95; /bin/cat "$RESIZE_TEST_DIR/before/gpt.txt"; }
mktemp() { /usr/bin/mktemp -d "$RESIZE_TEST_DIR/work.XXXXXX"; }
curl() {
    local archive='' argument previous='' phase
    phase=$(test_phase)
    for argument in "$@"; do
        [[ $previous != --upload-file ]] || archive=$argument
        previous=$argument
    done
    case "$archive" in "$RESIZE_TEST_DIR"/*/backup.tar.gz) ;; *) return 96 ;; esac
    if [[ ${PART_TEST_MODE:-} == bad_before || ( ${PART_TEST_MODE:-} == bad_esp && $phase == esp ) ]]; then
        echo 'NO VALIDATION'; return
    fi
    set -- $(/usr/bin/cksum "$archive")
    echo "CKSUM $1 $2"
    echo "VALIDATED_PARTITIONS $phase"
}
export -f sysctl test_phase diskutil dd gpt mktemp curl
