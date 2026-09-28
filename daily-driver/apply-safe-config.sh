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
backup() {
    local dest
    [[ -e $1 ]] || return 0
    dest=$(mktemp "$1.azahi-bak-$stamp.XXXXXX")
    cp -aL -- "$1" "$dest"
}
systemctl_args=()
[[ -z $root ]] || systemctl_args=(--root "$root")

# Parse before changing anything. Repository-only excludes are not global
# protection, and an empty or indented option must not hide the new values.
dnfconf=$root/etc/dnf/dnf.conf
dnf_desired=$(python3 - "$dnfconf" <<'PY'
import configparser
from pathlib import Path
import re
import shlex
import sys

path = Path(sys.argv[1])
def parse(text):
    config = configparser.ConfigParser(interpolation=None, delimiters=('=',))
    config.optionxform = str
    config.read_string(text)
    if config.defaults():
        raise ValueError('DEFAULT sections require manual review')
    return config

def unquote(value):
    # libdnf5's IniParser removes one matching pair around the whole value.
    if len(value) > 1 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value

try:
    text = path.read_text() if path.exists() else ''
    config = parse(text)
    def items(value):
        lexer = shlex.shlex(unquote(value), posix=True)
        lexer.whitespace = ', \t\r\n'
        lexer.whitespace_split = True
        lexer.commenters = lexer.quotes = ''
        return set(lexer)

    # DNF5 loads sorted drop-ins first. /etc masks a matching vendor filename,
    # then dnf.conf wins. An inherited disable_excludes can defeat every pin.
    config_root = path.parents[2]
    dropins = {}
    for directory in ('etc/dnf/libdnf5.conf.d', 'usr/share/dnf5/libdnf.conf.d'):
        for drop in (config_root / directory).glob('*.conf'):
            if drop.is_file():
                dropins.setdefault(drop.name, drop)
    disabled = ''
    for current in [*(parse(dropins[name].read_text()) for name in sorted(dropins)), config]:
        if current.has_option('main', 'disable_excludes'):
            disabled = current.get('main', 'disable_excludes')
    if '$' in disabled:
        raise ValueError('variable-based disable_excludes requires manual review')
    if items(disabled) & {'main', '*'}:
        raise ValueError('global excludes are disabled')
    if config.has_option('main', 'exclude'):
        raise ValueError('legacy exclude option requires manual review')
    existing = config.get('main', 'excludepkgs', fallback='')
    have = items(existing)
    missing = [p for p in ('kernel*', 'm1n1*', 'uboot-images*', 'update-m1n1') if p not in have]
    if missing:
        lines = text.splitlines(keepends=True)
        main = None
        for i, line in enumerate(lines):
            if line.lstrip().startswith('['):
                if re.fullmatch(r'\s*\[main\]\s*(?:[#;].*)?', line):
                    main = i
                elif main is not None:
                    break
            elif main is not None:
                match = re.match(r'([ \t]*excludepkgs[ \t]*=[ \t]*)(.*)', line)
                if match:
                    if unquote(existing) != existing:
                        # Insert inside the quote, preserving multiline values.
                        if not match[2].startswith(existing[0]):
                            raise ValueError('cannot locate quoted excludes safely')
                        lines[i] = match[1] + existing[0] + ','.join(missing) + ',' + match[2][1:] + '\n'
                    else:
                        suffix = ',' + match[2] if match[2].strip() else ''
                        lines[i] = match[1] + ','.join(missing) + suffix + '\n'
                    break
        # No existing option: put a global one directly after [main].
        if not config.has_option('main', 'excludepkgs'):
            if main is None:
                if lines and not lines[-1].endswith('\n'):
                    lines[-1] += '\n'
                lines.extend(['[main]\n', 'excludepkgs=' + ','.join(missing) + '\n'])
            else:
                if not lines[main].endswith('\n'):
                    lines[main] += '\n'
                lines.insert(main + 1, 'excludepkgs=' + ','.join(missing) + '\n')
        text = ''.join(lines)
        config.read_string(text)
        if not set(missing) <= items(config.get('main', 'excludepkgs', fallback='')):
            raise ValueError('cannot locate the global excludes option safely')
    print(text, end='')
except (OSError, ValueError, configparser.Error) as error:
    detail = str(error) if isinstance(error, ValueError) else type(error).__name__
    print('REFUSED: cannot safely update dnf.conf: ' + detail, file=sys.stderr)
    sys.exit(1)
PY
)

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

# Masked targets block systemd suspend requests, including KDE's.
for target in sleep suspend hibernate hybrid-sleep suspend-then-hibernate; do
    if [[ $(systemctl "${systemctl_args[@]}" is-enabled "$target.target" 2>/dev/null || true) = masked ]]; then
        report OK "$target.target masked"
    elif ((apply)); then
        systemctl "${systemctl_args[@]}" mask "$target.target" > /dev/null
        report CHANGED "$target.target masked"
    else
        report WOULD-CHANGE "mask $target.target"
    fi
done

# 2. The boot image pins this kernel; an update could remove its modules.
if [[ -f $dnfconf && $(< "$dnfconf") = "$dnf_desired" ]]; then
    report OK "dnf excludes kernel and boot-chain packages"
elif ((apply)); then
    mkdir -p "${dnfconf%/*}"; backup "$dnfconf"
    printf '%s\n' "$dnf_desired" > "$dnfconf"
    report CHANGED "dnf excludes kernel and boot-chain packages"
else
    report WOULD-CHANGE "dnf exclude kernel and boot-chain packages"
fi

# 3. Optional: USB at boot. Boot with every USB-C socket empty either way.
if ((usb)); then
    if [[ ! -f $root/etc/systemd/system/azahi-usb.service ]]; then
        report MISSING "azahi-usb.service not installed"
    elif [[ $(systemctl "${systemctl_args[@]}" is-enabled azahi-usb.service 2>/dev/null || true) = enabled ]]; then
        report OK "azahi-usb.service enabled"
    elif ((apply)); then
        systemctl "${systemctl_args[@]}" enable azahi-usb.service > /dev/null 2>&1
        report CHANGED "azahi-usb.service enabled (next boot, sockets empty)"
    else
        report WOULD-CHANGE "enable azahi-usb.service"
    fi
fi
