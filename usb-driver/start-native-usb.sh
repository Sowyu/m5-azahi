#!/bin/bash
# Exact-kernel J714s startup. Never tears down the applied USB overlay.
set -Eeuo pipefail
stage=identity
params=/sys/module/azahi_hpm_once/parameters
# Print the HPM tuple on every failing exit. A failed hpm-once init
# deregisters the module, so the tuple would otherwise vanish with it.
hpm_tuple() {
    local name line=
    [[ -d $params ]] || { echo 'HPM_TUPLE: azahi_hpm_once not loaded'; return 0; }
    for name in result ready poisoned; do
        if [[ -r $params/$name ]]; then line+=" $name=$(< "$params/$name")"
        else line+=" $name=?"; fi
    done
    echo "HPM_TUPLE:$line"
}
trap 'status=$?; printf "USB_START_FAILED: stage=%s status=%s; no teardown attempted\n" "$stage" "$status" >&2' ERR
trap 'status=$?; [[ $status = 0 ]] || hpm_tuple' EXIT
[[ $(id -u) = 0 && $(uname -r) = '7.0.13-400.asahi.fc44.aarch64+16k' ]] || {
    echo 'USB_START_REFUSED: root and the pinned kernel are required' >&2
    exit 1
}
IFS= read -r expected_uuid < /etc/azahi-usb-root
[[ $(findmnt -n -o UUID /) = "$expected_uuid" ]] || { echo 'Wrong Linux root'; exit 1; }
grep -zFxq 'apple,j714s' /proc/device-tree/compatible || {
    echo 'USB_START_REFUSED: device tree is not apple,j714s' >&2
    exit 1
}
cd /opt/azahi-usb
stage=checksums
sha256sum -c SHA256SUMS
count=0
for module in phy_apple_t6050_usb2 azahi_usb_overlay dwc3_apple_t6050; do
    [[ ! -d /sys/module/$module ]] || count=$((count+1))
done
if [[ $count = 3 ]]; then
    for hub in /sys/bus/usb/devices/usb*; do
        [[ $(readlink -f "$hub") != */382280000.usb/* ]] || {
            echo 'USB_ALREADY_READY: preserving existing right-port devices'
            exit 0
        }
    done
    echo 'Existing modules without right-port root hub; no reload'
    exit 1
fi
[[ $count = 0 ]] || { echo 'Partial USB load; no retry or teardown'; exit 1; }

stage=hpm
if [[ -d $params && $(< "$params/result") = -11 && $(< "$params/poisoned") = N ]]; then
    # A previous clean refusal occurred before any SSPS task. An explicit
    # service restart may recheck after unplugging. Never recover a bus fault.
    rmmod azahi_hpm_once
fi
if [[ ! -d $params ]]; then
    insmod ./azahi_hpm_once.ko mode=awake
fi
if [[ $(< "$params/result") != 0 || $(< "$params/ready") != Y || $(< "$params/poisoned") != N ]]; then
    echo 'HPM_NOT_READY: no USB load. If clean state-7 refusal, unplug phone and restart azahi-usb.'
    exit 1
fi
for module in apple-dart dwc3 xhci-plat-hcd; do
    stage=modprobe-$module
    modprobe "$module"
done
# A missing phone network driver must not prevent Ethernet adapters or other
# USB devices from enumerating. USB_HOST_READY only promises a host root hub.
for module in usbnet cdc_ncm cdc_ether rndis_host; do
    if ! modprobe "$module"; then
        printf 'USB_OPTIONAL_DRIVER_MISSING: %s; devices needing it cannot network\n' "$module" >&2
    fi
done
stage=phy
insmod ./phy-apple-t6050-usb2.ko
stage=overlay
insmod ./azahi-usb-overlay.ko variant=minimal
stage=dwc3-glue
insmod ./dwc3-apple-t6050.ko
stage=root-hub
for ((i=0; i<10; i++)); do
    for hub in /sys/bus/usb/devices/usb*; do
        [[ $(readlink -f "$hub") != */382280000.usb/* ]] || {
            echo 'USB_HOST_READY: connect phone and enable tethering; NetworkManager will autoconnect'
            exit 0
        }
    done
    sleep 1
done
echo 'No right-port root hub; no teardown or retry'
exit 1
