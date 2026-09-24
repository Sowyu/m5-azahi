#!/bin/bash
# Safe daily-driving settings for the installed J714s Linux. Run as root.
#   apply-safe-config.sh            report only (default)
#   apply-safe-config.sh --apply    make the changes, backing up edited files
#   add --usb-at-boot to also re-enable azahi-usb.service
# No reboot, module load or service restart. AZAHI_ROOT exists for host tests.
set -euo pipefail
root=${AZAHI_ROOT:-}
apply=0 usb=0
for arg in "$@"; do
    case $arg in
        --apply) apply=1 ;;
        --usb-at-boot) usb=1 ;;
        *) echo "usage: $0 [--apply] [--usb-at-boot]" >&2; exit 2 ;;
    esac
done
[[ $(uname -r) = '7.0.13-400.asahi.fc44.aarch64+16k' ]] || { echo 'REFUSED: not the pinned kernel'; exit 1; }
grep -zFxq 'apple,j714s' "$root/proc/device-tree/compatible" || { echo 'REFUSED: not a J714s'; exit 1; }
[[ -n $root || $(id -u) = 0 ]] || { echo 'REFUSED: run as root'; exit 1; }

stamp=$(date +%Y%m%d-%H%M%S)
report() { printf '%-14s %s\n' "$1" "$2"; }
backup() { [[ ! -e $1 ]] || cp -a "$1" "$1.azahi-bak-$stamp"; }

# 1. Sleep would stop the SSD controller and resume removes the root disk.
logind=$root/etc/systemd/logind.conf.d/90-azahi-no-sleep.conf
want=$'[Login]\nHandleLidSwitch=ignore\nHandleLidSwitchExternalPower=ignore\nHandleLidSwitchDocked=ignore\nHandleSuspendKey=ignore\nHandleHibernateKey=ignore'
if [[ -f $logind && $(< "$logind") = "$want" ]]; then
    report OK "lid and suspend keys ignored (takes effect next boot)"
elif ((apply)); then
    mkdir -p "${logind%/*}"; backup "$logind"; printf '%s\n' "$want" > "$logind"
    report CHANGED "lid and suspend keys ignored (takes effect next boot)"
else
    report WOULD-CHANGE "write ${logind#"$root"}"
fi

# Masked targets make every suspend request fail at once, including KDE's.
for target in sleep suspend hibernate hybrid-sleep suspend-then-hibernate; do
    if [[ $(systemctl is-enabled "$target.target" 2>/dev/null || true) = masked ]]; then
        report OK "$target.target masked"
    elif ((apply)); then
        systemctl mask "$target.target" > /dev/null
        report CHANGED "$target.target masked"
    else
        report WOULD-CHANGE "mask $target.target"
    fi
done

# 2. The boot image pins this kernel; an update could remove its modules.
dnfconf=$root/etc/dnf/dnf.conf
patterns=(kernel\* m1n1\* uboot-images\* update-m1n1)
current=$(sed -n 's/^excludepkgs[[:space:]]*=[[:space:]]*//p' "$dnfconf" 2>/dev/null | head -n 1 || true)
missing=()
for p in "${patterns[@]}"; do
    [[ ",${current// /}," = *",$p,"* ]] || missing+=("$p")
done
if ((${#missing[@]} == 0)); then
    report OK "dnf excludes kernel and boot-chain packages"
elif ((apply)); then
    mkdir -p "${dnfconf%/*}"; backup "$dnfconf"
    joined=$(IFS=,; echo "${missing[*]}")
    if [[ -n $current ]]; then
        sed -i "0,/^excludepkgs[[:space:]]*=.*/s//&,$joined/" "$dnfconf"
    elif grep -q '^\[main\]' "$dnfconf" 2>/dev/null; then
        sed -i "0,/^\[main\]/s//&\nexcludepkgs=$joined/" "$dnfconf"
    else
        printf '[main]\nexcludepkgs=%s\n' "$joined" >> "$dnfconf"
    fi
    report CHANGED "dnf excludes ${missing[*]}"
else
    report WOULD-CHANGE "dnf exclude ${missing[*]}"
fi

# 3. Optional: USB at boot. Boot with every USB-C socket empty either way.
if ((usb)); then
    if [[ ! -f $root/etc/systemd/system/azahi-usb.service ]]; then
        report MISSING "azahi-usb.service not installed"
    elif [[ $(systemctl is-enabled azahi-usb.service 2>/dev/null || true) = enabled ]]; then
        report OK "azahi-usb.service enabled"
    elif ((apply)); then
        systemctl enable azahi-usb.service > /dev/null 2>&1
        report CHANGED "azahi-usb.service enabled (next boot, sockets empty)"
    else
        report WOULD-CHANGE "enable azahi-usb.service"
    fi
fi
