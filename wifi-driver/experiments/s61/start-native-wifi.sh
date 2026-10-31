#!/usr/bin/env bash
# Guarded fresh-boot startup for the validated J714s/kernel combination.
# No recovery reset, forced unload, BAR4 access, or DMA teardown.
set -euo pipefail
umask 077
bundle=/opt/azahi-wifi/current
config=/etc/azahi-wifi
die() { printf 'N1_START_STOP: %s\n' "$*" >&2; exit 1; }
check() {
    local value
    value=$(cat "/sys/module/$1/parameters/${2:-result}")
    [[ $value == 0 ]] || die "$1 ${2:-result}=$value; resources retained until reboot"
}
private_file() {
    [[ -f $1 && ! -L $1 && $(stat -c '%u:%a' "$1") == 0:600 ]] || die "Private configuration permissions: $1"
}
# udev completion does not imply that NetworkManager's supplicant is ready.
# Wait for NM to leave unknown/unmanaged/unavailable before asking to connect.
wait_wifi_ready() {
    local iface=$1 state attempt
    for ((attempt=0;attempt<100;attempt++)); do
        state=$(LC_ALL=C nmcli -g GENERAL.STATE device show "$iface" 2>/dev/null) || state=0
        state=${state%% *}
        case $state in 30|40|50|60|70|80|90|100) return 0 ;; esac
        sleep 0.1
    done
    printf '%s\n' 'N1_START: NetworkManager Wi-Fi readiness timed out' >&2
    return 1
}
[[ $EUID == 0 ]] || die 'Requires root.'
[[ $(uname -r) == 7.0.13-400.asahi.fc44.aarch64+16k ]] || die 'Unsupported kernel; rebuild and validate before enabling.'
grep -qazx 'apple,j714s' /proc/device-tree/compatible || die 'Unsupported model.'
for file in root-uuid station-mac fallback-connect.bin fallback-profile firmware.sha256 frontend; do private_file "$config/$file"; done
[[ $(findmnt -n -o UUID /) == "$(cat "$config/root-uuid")" ]] || die 'Unexpected root filesystem.'
[[ $(stat -c %s "$config/fallback-connect.bin") == 73 ]] || die 'Invalid connection configuration size.'
cd "$bundle"
sha256sum --status -c SHA256SUMS || die 'Bundle checksum mismatch.'
sha256sum --status -c "$config/firmware.sha256" || die 'Firmware checksum mismatch.'
modules=(s1/azahi-apcie s1/azahi-apcie-link s2/pcie-apple-t6050 s2/azahi-n1-overlay
    s3r/n1-rom-retry s4e/n1-preboot-clean s5/n1-port-cycle s19/n1-control-handoff
    s49/n1-alpha-transport-v9 s50/n1-alpha-data-rx-v2 s51/n1-alpha-data-tx-v2
    s52/n1-alpha-client-v9 s53/n1-connect-v9 s55/n1-packet-netdev)
for module in "${modules[@]}"; do
    [[ -f $module.ko && $(modinfo -F vermagic "$module.ko") == "$(uname -r) "* ]] || die "Invalid module: $module"
done
IFS= read -r station_mac < "$config/station-mac"
[[ $station_mac =~ ^([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}$ ]] || die 'Invalid station address.'
IFS= read -r profile < "$config/fallback-profile"
[[ -n $profile ]] || die 'Missing NetworkManager profile.'
IFS= read -r frontend < "$config/frontend"
[[ $frontend == packet || $frontend == wifi ]] || die 'Invalid frontend selection.'
if [[ $frontend == wifi ]]; then
    private_file "$config/wifi-profile"
    IFS= read -r wifi_profile < "$config/wifi-profile"
    [[ -n $wifi_profile && -f s61/n1-wifi.ko ]] || die 'Missing Wi-Fi frontend configuration.'
    [[ $(modinfo -F vermagic s61/n1-wifi.ko) == "$(uname -r) "* ]] || die 'Invalid Wi-Fi frontend kernel version.'
fi
if [[ ${1:-} == --check ]]; then
    printf '%s\n' 'N1_START_PREFLIGHT_OK: files, kernel, model and root checked; hardware untouched'
    exit 0
fi
[[ $# == 0 ]] || die 'Unknown argument.'
exec 9>/run/azahi-wifi.lock
flock -n 9 || die 'Startup already running.'
[[ ! -e /run/azahi-wifi-attempt ]] || die 'Startup already attempted this boot; no hardware retry.'
[[ ! -e /sys/bus/pci/devices/0000:00:00.0 ]] || die 'N1 PCI already initialized; refusing adoption.'
for module in "${modules[@]}"; do
    name=${module##*/}; name=${name//-/_}
    [[ ! -d /sys/module/$name ]] || die "Existing owner: $name"
done
cat /proc/sys/kernel/random/boot_id > /run/azahi-wifi-attempt
printf '%s\n' 'N1_START: port, signed firmware and control transport'
insmod s1/azahi-apcie.ko stage=2
check azahi_apcie
rmmod azahi_apcie
gpioset -c gpiochip0 -t 0 19=1
insmod s1/azahi-apcie-link.ko
check azahi_apcie_link
rmmod azahi_apcie_link
insmod s2/pcie-apple-t6050.ko
insmod s2/azahi-n1-overlay.ko
[[ $(cat /sys/bus/pci/devices/0000:01:00.0/device) == 0x1900 ]] || die 'ROM enumeration failed.'
printf '%s\n' on > /sys/bus/pci/devices/0000:00:00.0/power/control
insmod s3r/n1-rom-retry.ko launch=1
insmod s4e/n1-preboot-clean.ko arm=1 pme_turnoff=1 hold_for_port_cycle=1
check n1_preboot_clean
[[ $(cat /sys/module/n1_preboot_clean/parameters/phase) == 4 ]] || die 'Preboot handoff incomplete.'
insmod s5/n1-port-cycle.ko arm=1
check n1_port_cycle
[[ $(cat /sys/bus/pci/devices/0000:01:00.0/device) == 0x1901 ]] || die 'Runtime enumeration failed.'
nonce=$(cat /sys/module/n1_preboot_clean/parameters/rom_nonce)
[[ $nonce =~ ^[0-9]+$ ]] || die 'Missing ROM nonce.'
insmod s19/n1-control-handoff.ko launch=0 nonce_provided=1 rom_nonce="$nonce"
rmmod n1_control_handoff
insmod s19/n1-control-handoff.ko launch=1 nonce_provided=1 rom_nonce="$nonce"
unset nonce
for parameter in alpha_result board_result ipc_result management_result ping_result transfer_result; do
    check n1_control_handoff "$parameter"
done
insmod s49/n1-alpha-transport-v9.ko launch=1 fresh=1
check n1_alpha_transport_v9
# Preserve the verified initialization sequence required by RX/TX preflight.
insmod s52/n1-alpha-client-v9.ko launch=1 query=0 repeat=20
check n1_alpha_client_v9
rmmod n1_alpha_client_v9
insmod s52/n1-alpha-client-v9.ko launch=1 query=1 mac="$station_mac"
check n1_alpha_client_v9
rmmod n1_alpha_client_v9
insmod s52/n1-alpha-client-v9.ko launch=1 query=2
check n1_alpha_client_v9
rmmod n1_alpha_client_v9
insmod s52/n1-alpha-client-v9.ko launch=1 query=65551 scan_channel=0
check n1_alpha_client_v9
rmmod n1_alpha_client_v9
for ((i=0;i<100;i++)); do
    [[ $(cat /sys/module/n1_alpha_transport_v9/parameters/scan_pending) == N ]] && break
    sleep 0.1
done
[[ $(cat /sys/module/n1_alpha_transport_v9/parameters/scan_pending) == N ]] || die 'Initial scan timed out.'
check n1_alpha_transport_v9 scan_status
for item in s50/n1-alpha-data-rx-v2 s51/n1-alpha-data-tx-v2; do
    insmod "$item.ko" launch=1
    name=${item##*/}; check "${name//-/_}"
done
# The cfg80211 frontend can be selected once its live checks pass. A failed
# activation returns to the known packet frontend only after normal unload.
if [[ $frontend == wifi ]]; then
    if modprobe cfg80211 && insmod s61/n1-wifi.ko mac="$station_mac"; then
        udevadm settle --timeout=5
        wifi_iface=
        for net in /sys/class/net/*; do
            [[ -d $net/phy80211 && $(cat "$net/address") == "$station_mac" ]] || continue
            [[ -z $wifi_iface ]] || die 'Ambiguous station interface.'
            wifi_iface=${net##*/}
        done
        if [[ -n $wifi_iface ]] && wait_wifi_ready "$wifi_iface" &&
            nmcli --wait 45 connection up "$wifi_profile" ifname "$wifi_iface" >/dev/null; then
            printf '%s\n' 'N1_START_READY: native cfg80211 Wi-Fi active'
            exit 0
        fi
        rmmod n1_wifi || die 'Wi-Fi frontend remains in use; no overlapping fallback.'
    fi
    check n1_alpha_transport_v9
    printf '%s\n' 'N1_START: returning to the validated packet frontend'
fi
# The known packet frontend is the boot recovery path while cfg80211 is
# validated. Keys are read privately and sent through a write-only endpoint.
insmod s53/n1-connect-v9.ko
python3 - "$config/fallback-connect.bin" <<'PY'
import os, sys
with open(sys.argv[1], 'rb') as f:
    request = bytearray(f.read(74))
assert len(request) == 73
try:
    fd = os.open('/proc/n1_connect_v9', os.O_WRONLY)
    try:
        assert os.write(fd, request) == len(request)
    finally:
        os.close(fd)
finally:
    request[:] = bytes(len(request))
PY
check n1_connect_v9
rmmod n1_connect_v9
for ((i=0;i<100;i++)); do
    if insmod s55/n1-packet-netdev.ko mac="$station_mac" llc_tx=1 2>/dev/null; then break; fi
    sleep 0.2
done
[[ -e /sys/class/net/n1data0 ]] || die 'Association did not produce a usable packet interface.'
nmcli --wait 40 connection up "$profile" ifname n1data0 >/dev/null || die 'Native DHCP activation failed.'
printf '%s\n' 'N1_START_READY: native packet interface has NetworkManager connectivity'
