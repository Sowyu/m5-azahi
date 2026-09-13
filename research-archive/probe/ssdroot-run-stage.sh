#!/bin/bash
# Diagnostic wrapper; logs only to initrd /run, preserves the stage's status.
set -u
[[ -e /etc/initrd-release ]] || exit 1
case "${1:-}" in
    prepare) script=/ssdroot-prepare.sh ;;
    configure) script=/ssdroot-configure.sh ;;
    *) exit 2 ;;
esac
stage=$1
setfont -C /dev/tty1 -d 2>/dev/null || true
echo "=== SSDROOT $stage BEGIN ==="
if /bin/bash -x "$script" > "/run/ssdroot-$stage.log" 2>&1; then
    echo "=== SSDROOT $stage PASS ==="
    tail -3 "/run/ssdroot-$stage.log"
else
    result=$?
    echo "=== SSDROOT $stage FAILED: exit $result ==="
    tail -25 "/run/ssdroot-$stage.log"
    exit "$result"
fi
