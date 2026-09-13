#!/bin/sh
# Boot Linux on the M5 Pro as an m1n1 HYPERVISOR GUEST, with a real console.
#
# Unlike chainloading, m1n1 stays resident at EL2 and Linux runs at EL1.
# m1n1 traps the uart0 MMIO page and emulates the UART, so the guest's
# kernel log streams back over this same USB cable. Everything is also
# written to hv.log for pasting back to Claude.
#
# Run:  sh hv.sh
#
# DO NOT chainload first: on locked-sysreg chips RVBAR still points at the
# 1TR-installed m1n1, so secondaries would reset into a stale image.

set -e
KIT="$(cd "$(dirname "$0")" && pwd)"

[ -f "$KIT/guest-hv.bin" ] || { echo "Missing $KIT/guest-hv.bin"; exit 1; }

# --- find the M5 (proxy port is the first CDC interface m1n1 exposes) ---
if [ -z "$M1N1DEVICE" ]; then
    DEV="$(ls /dev/cu.usbmodem* 2>/dev/null | head -1)"
    if [ -z "$DEV" ]; then
        echo "No /dev/cu.usbmodem* found — the M5 isn't visible over USB."
        echo "Check the M5 shows 'Running proxy...' and the cable carries DATA."
        exit 1
    fi
    M1N1DEVICE="$DEV"
fi
export M1N1DEVICE
export PYTHONPATH="$KIT/lib:$KIT/proxyclient:$PYTHONPATH"

# --- teach the hypervisor about T6050 (idempotent) ---
# Mirrors src/smp.c: T6050 uses the same 0x88000 CPU-start offset as T6031.
# Without this the hv prints "CPUSTART unknown for this SoC!" and cannot
# intercept secondary-CPU starts.
python3 - "$KIT/proxyclient/m1n1/hv/__init__.py" <<'EOF'
import sys
path = sys.argv[1]
src = open(path).read()
old = "chip_id in (0x6031, 0x6034, 0x6040, 0x6041):"
new = "chip_id in (0x6031, 0x6034, 0x6040, 0x6041, 0x6050):"
if new in src:
    print("hv: T6050 CPUSTART already patched")
elif old in src:
    open(path, "w").write(src.replace(old, new))
    print("hv: patched T6050 CPUSTART offset")
else:
    print("hv: WARNING - CPUSTART table not found, continuing anyway")
EOF

SYMS=""
[ -f "$KIT/System.map" ] && SYMS="-s $KIT/System.map"

echo "Using device: $M1N1DEVICE"
echo "Logging to:   $KIT/hv.log"
echo
exec python3 "$KIT/proxyclient/tools/run_guest.py" \
    -r $SYMS -l "$KIT/hv.log" "$KIT/guest-hv.bin"
