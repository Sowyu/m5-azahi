#!/bin/sh
# Attempt 2 on T6050: chainload a PATCHED m1n1 over USB (no Recovery needed),
# then boot the kernel with it.
#
# Fixes since attempt 1:
#   - skip pcie_init()/dapf_init_all() on T6050 (they caused the SError)
#   - cpufreq support for chip 0x6050
#
# Run on the HOST Mac (M1 Pro):  sh boot-linux2.sh
#              with initramfs:   sh boot-linux2.sh full

KIT="$(cd "$(dirname "$0")" && pwd)"
cd "$KIT" || exit 1

M1N1="$KIT/m1n1-patched.macho"
KERNEL="$KIT/Image-asahi"
DTB="$KIT/t6050-j714s.dtb"
INITRD="$KIT/initramfs-asahi.img"
BOOTARGS="console=tty0 earlycon keep_bootcon ignore_loglevel debug"

for f in "$M1N1" "$KERNEL" "$DTB"; do
    [ -f "$f" ] || { echo "MISSING: $f"; exit 1; }
done

echo "=== STEP 1: chainload patched m1n1 (M5 screen will clear and re-log) ==="
sh "$KIT/run.sh" "$KIT/proxyclient/tools/chainload.py" "$M1N1" || {
    echo
    echo "Chainload failed. If the M5 rebooted, redo: hold power -> Linux ->"
    echo "wait for 'Running proxy...', then run this script again."
    exit 1
}

echo
echo "=== STEP 2: wait for the M5 to come back up in proxy mode ==="
echo "Watch the M5: it should print its boot log again and stop at"
echo "'Running proxy...'. Look for the line:"
echo "    kboot: T6050 bring-up: skipping pcie_init()/dapf_init_all()"
echo "(that line appears later, during the kernel boot, not now)"
echo
printf "Press return once the M5 shows 'Running proxy...' again: "
read _

echo "=== STEP 3: boot Linux ==="
if [ "$1" = "full" ] && [ -f "$INITRD" ]; then
    exec sh "$KIT/run.sh" "$KIT/proxyclient/tools/linux.py" \
        "$KERNEL" "$DTB" "$INITRD" --compression none -b "$BOOTARGS"
else
    exec sh "$KIT/run.sh" "$KIT/proxyclient/tools/linux.py" \
        "$KERNEL" "$DTB" --compression none -b "$BOOTARGS"
fi
