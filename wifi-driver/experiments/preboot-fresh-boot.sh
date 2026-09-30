#!/usr/bin/env bash
# Private J714s experiment. Starts signed firmware and control IPC only.
# Explicit invocation after a fresh Linux boot; never install as a service.
# Does not create a Wi-Fi interface. Never invokes the quarantined BAR4 reader.
set -euo pipefail

scratch=/root/azahi-20260929
die() { printf '%s\n' "$*" >&2; exit 1; }
check_result() {
    local value
    value=$(cat "/sys/module/$1/parameters/$2")
    [[ "$value" == 0 ]] || die "$1 $2=$value; stopped with resources retained"
}

[[ $EUID == 0 ]] || die 'Run on the target as root.'
[[ $(uname -r) == 7.0.13-400.asahi.fc44.aarch64+16k ]] || die 'Wrong kernel.'
grep -qazx 'apple,j714s' /proc/device-tree/compatible || die 'Wrong target model.'
[[ ! -e /sys/bus/pci/devices/0000:00:00.0 ]] || die 'PCI already initialized; requires fresh boot.'
for mod in pcie_apple_t6050 azahi_n1_overlay n1_rom_retry n1_control_boot; do
    [[ ! -d /sys/module/$mod ]] || die "$mod is already loaded."
done
for item in s1/azahi-apcie s1/azahi-apcie-link s2/pcie-apple-t6050 \
    s2/azahi-n1-overlay s3r/n1-rom-retry s4e/n1-preboot-clean \
    s5/n1-port-cycle s8/n1-control-boot s7survey/n1-os-survey; do
    [[ -f "$scratch/$item.ko" ]] || die "Missing $item.ko"
    [[ $(modinfo -F vermagic "$scratch/$item.ko") == "$(uname -r) "* ]] || die "Wrong build: $item"
done
[[ -r /lib/firmware/azahi-n1/n1-boot-candidate.bin ]] || die 'Missing primary image.'
[[ -r /lib/firmware/azahi-n1/n1-secondary-candidate.bin ]] || die 'Missing secondary image.'

printf '%s\n' 'Initializing N1 GP port and ROM link.'
insmod "$scratch/s1/azahi-apcie.ko" stage=2
check_result azahi_apcie result
rmmod azahi_apcie
gpioset -c gpiochip0 -t 0 19=1
insmod "$scratch/s1/azahi-apcie-link.ko"
check_result azahi_apcie_link result
rmmod azahi_apcie_link
insmod "$scratch/s2/pcie-apple-t6050.ko"
insmod "$scratch/s2/azahi-n1-overlay.ko"
[[ $(cat /sys/bus/pci/devices/0000:01:00.0/device) == 0x1900 ]] || die 'ROM did not enumerate.'
printf '%s\n' on > /sys/bus/pci/devices/0000:00:00.0/power/control

printf '%s\n' 'Sending signed ROM image and completing preboot handoff.'
insmod "$scratch/s3r/n1-rom-retry.ko" launch=1
insmod "$scratch/s4e/n1-preboot-clean.ko" arm=1 pme_turnoff=1 hold_for_port_cycle=1
check_result n1_preboot_clean result
[[ $(cat /sys/module/n1_preboot_clean/parameters/phase) == 4 ]] || die 'Unexpected preboot cleanup phase.'
insmod "$scratch/s5/n1-port-cycle.ko" arm=1
check_result n1_port_cycle result
[[ $(cat /sys/bus/pci/devices/0000:01:00.0/device) == 0x1901 ]] || die 'Runtime functions did not enumerate.'

printf '%s\n' 'Runtime functions ready in boot stage. Main firmware has not been launched.'
sync
