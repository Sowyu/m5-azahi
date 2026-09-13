#!/bin/bash
# Exact-kernel J714s startup. Never tears down the applied USB overlay.
set -Eeuo pipefail
params=/sys/module/azahi_hpm_once/parameters
# Every exit must name its step. Without this the cold-boot journal cannot
# tell an identity refusal from a failed HPM insmod from a driver failure.
hpm_tuple() {
    local name line=
    [[ -d $params ]] || { echo 'HPM_TUPLE: azahi_hpm_once not loaded'; return 0; }
    for name in result ready poisoned; do
        if [[ -r $params/$name ]]; then line+=" $name=$(< "$params/$name")"
        else line+=" $name=?"; fi
    done
    echo "HPM_TUPLE:$line"
}
die() { echo "STEP_FAILED: $1"; hpm_tuple; exit 1; }
trap 'echo "STEP_FAILED: line $LINENO: $BASH_COMMAND"; hpm_tuple' ERR
[[ $(id -u) = 0 && $(uname -r) = '7.0.13-400.asahi.fc44.aarch64+16k' ]]
IFS= read -r expected_uuid < /etc/azahi-usb-root
[[ $(findmnt -n -o UUID /) = "$expected_uuid" ]] || die 'Linux root UUID does not match /etc/azahi-usb-root'
grep -zFxq 'apple,j714s' /proc/device-tree/compatible || die 'device tree is not apple,j714s'
cd /opt/azahi-usb
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
    die 'existing USB modules without a right-port root hub; no reload'
fi
[[ $count = 0 ]] || die "partial USB load ($count of 3 modules); no retry or teardown"

if [[ -d $params && $(< "$params/result") = -11 && $(< "$params/poisoned") = N ]]; then
    # A previous clean refusal occurred before any SSPS task. An explicit
    # service restart may recheck after unplugging. Never recover a bus fault.
    rmmod azahi_hpm_once
fi
if [[ ! -d $params ]]; then
    insmod ./azahi_hpm_once.ko mode=awake
fi
hpm_tuple
if [[ $(< "$params/result") != 0 || $(< "$params/ready") != Y || $(< "$params/poisoned") != N ]]; then
    echo 'HPM_NOT_READY: no USB load. If clean state-7 refusal (result=-11 poisoned=N),'
    echo 'unplug the phone and restart azahi-usb. A poisoned tuple needs a reboot.'
    exit 1
fi
for module in apple-dart dwc3 xhci-plat-hcd usbnet cdc_ncm; do
    modprobe "$module" || die "modprobe $module (required for the host stack or NCM tethering)"
done
# ponytail: cdc_ether/rndis_host only matter for an RNDIS-mode phone, so a
# missing one must not abort host bring-up. Make them required again if a
# phone that offers only RNDIS becomes the tether this machine depends on.
for module in cdc_ether rndis_host; do
    modprobe "$module" || echo "OPTIONAL_MODULE_MISSING: $module (RNDIS tethering unavailable)"
done
insmod ./phy-apple-t6050-usb2.ko
insmod ./azahi-usb-overlay.ko variant=minimal
insmod ./dwc3-apple-t6050.ko
for ((i=0; i<10; i++)); do
    for hub in /sys/bus/usb/devices/usb*; do
        [[ $(readlink -f "$hub") != */382280000.usb/* ]] || {
            echo 'USB_HOST_READY: connect phone and enable tethering; NetworkManager will autoconnect'
            exit 0
        }
    done
    sleep 1
done
die 'no right-port root hub 10 s after the three insmods; no teardown or retry'
