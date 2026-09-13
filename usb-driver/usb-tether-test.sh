#!/bin/bash
# Private J714s USB2 candidate. Default is a PMGR-only diagnostic, not a live test.
# `sh usb-tether-test.sh` is supported by re-executing bash.
[ -n "${BASH_VERSION:-}" ] || exec /bin/bash "$0" "$@"

say() { printf '%s\n' "$*" | tee -a "$LOG"; }
run() {
    say "+ $*" || return
    # Return the command failure even when tee succeeds (and vice versa).
    (set -o pipefail; "$@" 2>&1 | tee -a "$LOG")
}
fail() { say "FAIL: $*"; return 1; }

verify_bundle() {
    local name hash line count=0 seen=' '
    [[ -f "$DIR/SHA256SUMS" ]] || return 1
    while IFS= read -r line; do
        [[ "$line" =~ ^([0-9a-f]{64})\ \ ([-a-zA-Z0-9.]+)$ ]] || return 1
        hash=${BASH_REMATCH[1]}; name=${BASH_REMATCH[2]}
        case "$name" in
            phy-apple-t6050-usb2.ko|dwc3-apple-t6050.ko|azahi-usb-overlay.ko|usb-tether-test.sh) ;;
            *) return 1 ;;
        esac
        [[ "$seen" != *" $name "* ]] || return 1
        seen="$seen$name "; count=$((count+1))
    done < "$DIR/SHA256SUMS"
    [[ $count = 4 ]] || return 1
    (cd "$DIR" && run sha256sum -c SHA256SUMS)
}

candidate_hub() {
    local node resolved
    for node in "$SYS_USB"/usb*; do
        [[ -d "$node" ]] || continue
        resolved=$(readlink -f "$node") || continue
        case "$resolved" in
            */382280000.usb/*) printf '%s\n' "$resolved"; return 0 ;;
        esac
    done
    return 1
}

candidate_interface() {
    local node resolved hub count=0 result=''
    hub=$(candidate_hub) || return 1
    for node in "$SYS_NET"/*; do
        [[ -e "$node/device" ]] || continue
        resolved=$(readlink -f "$node/device") || continue
        case "$resolved" in
            "$hub"/*) result=${node##*/}; count=$((count+1)) ;;
        esac
    done
    # Ambiguous devices must not pick an arbitrary interface.
    [[ $count = 1 ]] || return 1
    printf '%s\n' "$result"
}

https_test() {
    # Bypass curl config and proxies, bind the transfer to the USB interface,
    # require certificate validation and a successful HTTP status. DNS may be
    # supplied by the system resolver; this does not prove DNS's packet path.
    run curl -q --noproxy '*' --interface "$NEWIF" --ipv4 --fail \
        --silent --show-error --connect-timeout 10 --max-time 25 \
        --output /dev/null --write-out 'HTTPS HTTP %{http_code}\n' \
        https://asahilinux.org/
}

cleanup() {
    local rc=$?
    trap - EXIT
    if [[ ${DRY_LOADED:-0} = 1 ]]; then
        # Only our successfully loaded dry module; never an applied overlay.
        run rmmod azahi_usb_overlay || rc=1
    fi
    if [[ -n ${DMESG_PID:-} ]]; then
        kill "$DMESG_PID" 2>/dev/null || :
        wait "$DMESG_PID" 2>/dev/null || :
    fi
    exit "$rc"
}

main() {
    set -u
    local variant=${1:-dry} module i
    [[ $# -le 1 ]] || { printf 'Usage: bash usb-tether-test.sh [dry|minimal]\n'; return 1; }
    case "$variant" in dry|minimal) ;; *) printf 'Only dry or minimal is supported; PMGR variant is withheld.\n'; return 1 ;; esac
    [[ $(id -u) = 0 ]] || { printf 'Run as root on the target Linux laptop.\n'; return 1; }
    [[ $(uname -r) = '7.0.13-400.asahi.fc44.aarch64+16k' ]] || { printf 'Wrong kernel; aborting.\n'; return 1; }
    [[ $(findmnt -n -o UUID /) = PRIVATE-LINUX-FSUUID-NOT-CONFIGURED ]] || {
        printf 'Wrong root filesystem; no changes made.\n'; return 1;
    }
    DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) || return 1
    SYS_USB=/sys/bus/usb/devices
    SYS_NET=/sys/class/net
    LOG=$(mktemp /root/usb-test.XXXXXX.log) || return 1
    DRY_LOADED=0
    DMESG_PID=''
    trap cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    say "USB candidate: $variant. Log: $LOG" || return 1
    verify_bundle || { fail 'Bundle checksum/manifest verification failed.'; return 1; }
    for module in azahi_usb_overlay phy_apple_t6050_usb2 dwc3_apple_t6050; do
        [[ ! -d "/sys/module/$module" ]] || {
            fail "$module already loaded; do not retry or unload a live overlay."; return 1;
        }
    done

    if [[ $variant = dry ]]; then
        run insmod "$DIR/azahi-usb-overlay.ko" dry_run=1 || return 1
        DRY_LOADED=1
        run dmesg || return 1
        run rmmod azahi_usb_overlay || return 1
        DRY_LOADED=0
        say 'Diagnostic complete; no overlay applied. Active power does NOT prove USB works.'
        return
    fi

    # Fail BEFORE hardware changes if the necessary user-space tools are absent.
    for module in nmcli curl ip readlink; do
        command -v "$module" >/dev/null || { fail "Missing $module"; return 1; }
    done
    run nmcli general status || return 1
    say 'Live experiment: may hang the port/kernel and require an attended power cycle.'
    say 'Only logs and a temporary NetworkManager profile are intended; boot files stay unchanged.'
    dmesg -w >> "$LOG" 2>&1 &
    DMESG_PID=$!
    for module in apple-dart dwc3 xhci-plat-hcd usbnet cdc_ncm cdc_ether rndis_host; do
        run modprobe "$module" || return 1
    done
    run insmod "$DIR/phy-apple-t6050-usb2.ko" || return 1
    run insmod "$DIR/azahi-usb-overlay.ko" variant=minimal || return 1
    run insmod "$DIR/dwc3-apple-t6050.ko" || return 1

    for ((i=0; i<30; i++)); do
        candidate_hub >/dev/null && break
        sleep 1
    done
    candidate_hub || { fail 'No right-port root hub after 30 seconds.'; return 2; }
    NEWIF=''
    for ((i=0; i<60; i++)); do
        NEWIF=$(candidate_interface) && break
        sleep 1
    done
    [[ -n "$NEWIF" ]] || { fail 'No unique right-port USB network interface; check enumeration/VBUS/phone tethering.'; return 3; }
    say "Right-port USB network interface: $NEWIF"
    # save no stores the profile in memory. Do not overwrite existing profiles.
    local profile="azahi-usb-${LOG##*.}-$BASHPID"
    run nmcli connection add save no type ethernet ifname "$NEWIF" \
        con-name "$profile" connection.autoconnect no ipv4.method auto ipv6.method disabled || return 1
    say "Temporary profile: $profile (retained for this boot, including on connection failure)."
    run nmcli --wait 45 connection up id "$profile" ifname "$NEWIF" || return 1
    run ip -4 addr show dev "$NEWIF" || return 1
    ip -4 -o addr show dev "$NEWIF" scope global | grep -q 'inet ' || {
        fail 'No global IPv4 address on USB interface.'; return 4;
    }
    https_test || { fail "HTTPS over $NEWIF failed; no networking success claimed."; return 5; }
    say "SUCCESS: verified outbound HTTPS transfer bound to $NEWIF. Not yet a reboot-persistent setup."
}

# Sourceable for offline mocks: sourcing must never run hardware operations.
if [[ ${BASH_SOURCE[0]} = "$0" ]]; then
    main "$@"
    exit $?
fi
