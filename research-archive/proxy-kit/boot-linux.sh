#!/bin/sh
# First Linux boot attempt on T6050 (M5 Pro), over the USB-C proxy link.
# Nothing is installed or written on either Mac — the kernel is loaded into the
# M5's RAM and jumped to. Hold the power button to recover, always.
#
# Run on the HOST Mac (M1 Pro):   sh boot-linux.sh
# Add "full" to also load the initramfs:   sh boot-linux.sh full

KIT="$(cd "$(dirname "$0")" && pwd)"
cd "$KIT" || exit 1

KERNEL="$KIT/Image-asahi"
DTB="$KIT/t6050-j714s.dtb"
INITRD="$KIT/initramfs-asahi.img"

for f in "$KERNEL" "$DTB"; do
    [ -f "$f" ] || { echo "MISSING: $f"; exit 1; }
done

# console=tty0 -> framebuffer console (CONFIG_FRAMEBUFFER_CONSOLE=y, SIMPLEDRM=y)
# keep_bootcon + ignore_loglevel so we see everything before/if it dies
BOOTARGS="console=tty0 earlycon keep_bootcon ignore_loglevel debug"

echo "=== T6050 Linux boot attempt ==="
echo "kernel : $KERNEL"
echo "dtb    : $DTB"
echo "args   : $BOOTARGS"

if [ "$1" = "full" ] && [ -f "$INITRD" ]; then
    echo "initrd : $INITRD"
    echo "(~150 MB over USB — this takes a few minutes)"
    exec sh "$KIT/run.sh" "$KIT/proxyclient/tools/linux.py" \
        "$KERNEL" "$DTB" "$INITRD" --compression none -b "$BOOTARGS"
else
    echo "initrd : (none — kernel will panic at 'unable to mount root fs',"
    echo "          which is EXPECTED and still counts as success)"
    exec sh "$KIT/run.sh" "$KIT/proxyclient/tools/linux.py" \
        "$KERNEL" "$DTB" --compression none -b "$BOOTARGS"
fi
