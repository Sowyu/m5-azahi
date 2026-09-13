# Test-only exported shell functions: never source on the target.
sysctl() { echo Mac17,9; }
diskutil() {
    local phase=before
    [[ ! -e $RESIZE_TEST_DIR/mutated ]] || phase=after
    case "$*" in
        'info -plist PRIVATE-UUID-REMOVED') /bin/cat "$RESIZE_TEST_DIR/$phase/linux.plist" ;;
        'info -plist disk0') /bin/cat "$RESIZE_TEST_DIR/$phase/disk.plist" ;;
        'info -plist disk0s'[1234]) /bin/cat "$RESIZE_TEST_DIR/$phase/partition-${3#disk0s}.plist" ;;
        'list internal') /bin/cat "$RESIZE_TEST_DIR/$phase/disks.txt" ;;
        'list -plist disk0') /bin/cat "$RESIZE_TEST_DIR/$phase/disk-list.plist" ;;
        'apfs list disk3 -plist') /bin/cat "$RESIZE_TEST_DIR/$phase/linux-container.plist" ;;
        'apfs list disk3') /bin/cat "$RESIZE_TEST_DIR/$phase/linux-container.txt" ;;
        'apfs resizeContainer disk0s3 limits -plist') /bin/cat "$RESIZE_TEST_DIR/$phase/limits.plist" ;;
        'apfs resizeContainer disk0s3 96000000000')
            echo "$*" >> "$RESIZE_TEST_DIR/mutations"
            /usr/bin/touch "$RESIZE_TEST_DIR/mutated"
            echo 'Mock resize only; no device accessed.' ;;
        *) echo "Unexpected diskutil call: $*" >&2; return 91 ;;
    esac
}
dd() {
    local phase=before input='' output='' argument backup=false
    [[ ! -e $RESIZE_TEST_DIR/mutated ]] || phase=after
    for argument in "$@"; do
        case "$argument" in
            if=*) input=${argument#if=} ;;
            of=*) output=${argument#of=} ;;
            skip=244276259) backup=true ;;
            bs=4096|count=6|count=1) ;;
            *) echo 'Unexpected dd argument' >&2; return 92 ;;
        esac
    done
    case "$output" in "$RESIZE_TEST_DIR"/*) ;; *) return 93 ;; esac
    case "$input" in
        /dev/rdisk0s3) /bin/cp "$RESIZE_TEST_DIR/$phase/linux-superblock.bin" "$output" ;;
        /dev/rdisk0)
            if $backup; then /bin/cp "$RESIZE_TEST_DIR/$phase/gpt-backup.bin" "$output"
            else /bin/cp "$RESIZE_TEST_DIR/$phase/gpt-primary.bin" "$output"; fi ;;
        *) return 94 ;;
    esac
}
gpt() {
    [[ $* == '-r show -l /dev/disk0' ]] || return 95
    /bin/cat "$RESIZE_TEST_DIR/before/gpt.txt"
}
mktemp() { /usr/bin/mktemp -d "$RESIZE_TEST_DIR/work.XXXXXX"; }
curl() {
    local archive='' argument previous='' stage=before
    for argument in "$@"; do
        [[ $previous != --upload-file ]] || archive=$argument
        previous=$argument
    done
    case "$archive" in "$RESIZE_TEST_DIR"/*/backup.tar.gz) ;; *) return 96 ;; esac
    [[ ! -e $RESIZE_TEST_DIR/mutated ]] || stage=after
    if [[ ${RESIZE_TEST_BAD_RECEIPT:-0} == 1 ]]; then echo 'NO VALIDATION'; return 0; fi
    set -- $(/usr/bin/cksum "$archive")
    echo "CKSUM $1 $2"
    echo "VALIDATED_STORAGE $stage"
}
export -f sysctl diskutil dd gpt mktemp curl
