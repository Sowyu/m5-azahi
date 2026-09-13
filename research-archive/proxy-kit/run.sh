#!/bin/sh
# Drive the M5 Pro running m1n1, from this machine, over USB-C.
# Nothing is installed on this Mac: pure-Python deps are vendored in ./lib.
# Run:  sh run.sh          (interactive shell)
#       sh run.sh <tool>   (e.g. sh run.sh proxyclient/tools/chainload.py ...)

KIT="$(cd "$(dirname "$0")" && pwd)"

# --- python3 check (don't trigger the Xcode CLT installer silently) ---
if ! command -v python3 >/dev/null 2>&1; then
    echo "No python3 on this Mac."
    echo "If a 'command line developer tools' dialog appeared, CANCEL it and tell Claude."
    exit 1
fi
if ! python3 -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
    echo "python3 exists but won't run (likely Command Line Tools not installed)."
    echo "CANCEL any install dialog and tell Claude — we'll ship a standalone Python instead."
    exit 1
fi

# --- find the M5 ---
if [ -z "$M1N1DEVICE" ]; then
    DEV="$(ls /dev/cu.usbmodem* 2>/dev/null | head -1)"
    if [ -z "$DEV" ]; then
        echo "No /dev/cu.usbmodem* found — the M5 isn't visible over USB."
        echo "Check: 1) the M5 shows 'Running proxy...'  2) USB-C cable carries DATA"
        echo "       3) try the other USB-C ports on BOTH machines"
        exit 1
    fi
    M1N1DEVICE="$DEV"
fi
export M1N1DEVICE
echo "Using device: $M1N1DEVICE"

export PYTHONPATH="$KIT/lib:$KIT/proxyclient:$PYTHONPATH"

if [ $# -gt 0 ]; then
    exec python3 "$@"
else
    exec python3 "$KIT/proxyclient/tools/shell.py"
fi
