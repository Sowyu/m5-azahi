#!/bin/sh
# Attempt 3 on T6050.
#
# What changed vs attempt 2:
#   Attempt 2 chainloaded a bare m1n1. After relocating, m1n1's payload_run()
#   scans the memory right after its own image, found garbage, and died in an
#   SError loop. (It got that far, which means cpufreq init with the new T6050
#   cluster tables already ran fine.)
#
#   So this time we chainload m1n1 WITH a real payload appended:
#       m1n1.bin + t6050-j714s.dtb + Image-asahi
#   m1n1 finds a valid device tree + kernel, and boots Linux itself.
#   No separate linux.py step, and nothing for payload_run to trip over.
#
# Run on the HOST Mac (M1 Pro):  sh boot-linux3.sh

KIT="$(cd "$(dirname "$0")" && pwd)"
cd "$KIT" || exit 1

IMG="$KIT/boot-t6050.bin"
[ -f "$IMG" ] || { echo "MISSING: $IMG"; exit 1; }

echo "=== T6050 attempt 3: chainload m1n1 + dtb + kernel (75 MB, ~1-3 min) ==="
echo "Watch the M5's screen, not this one."
echo
# NOTE: no -E flag. chainload.py parses it with type=int, which rejects "0x800",
# and 0x800 is already the default entry point for raw images anyway.
exec sh "$KIT/run.sh" "$KIT/proxyclient/tools/chainload.py" -r "$IMG"
