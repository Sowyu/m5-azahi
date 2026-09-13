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

# GUEST=<path> selects the boot image; default is the no-initramfs one.
GUEST="${GUEST:-$KIT/guest-hv.bin}"
[ -f "$GUEST" ] || { echo "Missing $GUEST"; exit 1; }
echo "Guest image:  $GUEST"

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

# --- capture the GUEST console (THE run-2 lesson) ---
# m1n1 exposes TWO CDC-ACM ports over the one USB cable. The first is the
# proxy (M1N1DEVICE). The emulated uart0 the guest's earlycon/console=ttySAC0
# writes to (src/hv_vuart.c -> IODEV_USB_VUART) comes out on the SECOND port.
# In run 2 nobody had that port open: the entire guest kernel log - earlycon
# banner included - went to a device node nobody was reading, which is why the
# guest looked "silent" while it was in fact deep into driver probing.
VUART_DEV=""
for d in /dev/cu.usbmodem*; do
    [ -e "$d" ] || continue
    [ "$d" = "$M1N1DEVICE" ] && continue
    VUART_DEV="$d"
    break
done
if [ -n "$VUART_DEV" ]; then
    echo "Guest console: $VUART_DEV  (tee -> $KIT/guest-console.log)"
    ( stty -f "$VUART_DEV" raw 2>/dev/null
      exec cat "$VUART_DEV" ) | tee "$KIT/guest-console.log" &
    VUART_PID=$!
    trap 'kill $VUART_PID 2>/dev/null' EXIT INT TERM
else
    echo "WARNING: only one usbmodem port found - guest console will be invisible!"
fi

# -C 0: show the guest ONLY cpu0. T6050 secondaries never actually start
# (CPU PS writes are ignored), so when the guest writes CPUSTART the hv calls
# hv_start_secondary, which blocks on a core that will never answer - the run
# dies with "Python exception while handling guest exception: HV/HOOK_VM".
# Deleting the other cpu nodes from the guest's ADT means it never asks.
# This runs after hv.init(), so the host's own bring-up is unaffected.
# (no exec: the trap above must fire afterwards to reap the vuart reader)
python3 "$KIT/proxyclient/tools/run_guest.py" \
    -r -C 0 $SYMS -l "$KIT/hv.log" "$GUEST"
