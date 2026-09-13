#!/bin/sh
# Target-side test for the right-hand USB-C socket, USB2 host + phone tethering.
# Runs on the J714s native Linux (kernel 7.0.13-400.asahi.fc44.aarch64+16k).
# Nothing here is persistent: no files are written outside /root/usb-candidate
# and the log directory; a reboot returns to the unchanged installed system.
#
# Usage:  sh usb-tether-test.sh            # minimal overlay (loader-prepared power)
#         sh usb-tether-test.sh dry        # only report PMGR/PHY/DWC3 state, no overlay
#         sh usb-tether-test.sh pmgr       # overlay with PMGR power-controller nodes
#
# Plug the phone into the RIGHT-hand socket BEFORE running, with USB tethering
# enabled on the phone (Settings > Connections > USB tethering / Hotspot).
set -u
VARIANT="${1:-minimal}"
DIR="$(cd "$(dirname "$0")" && pwd)"
TS="$(date +%Y%m%d-%H%M%S)"
LOG="/root/usb-test-$TS.log"
KVER="$(uname -r)"

say() { echo "[$(date +%T)] $*" | tee -a "$LOG"; }
run() { say "+ $*"; "$@" 2>&1 | tee -a "$LOG"; }

say "usb-tether-test variant=$VARIANT kernel=$KVER log=$LOG"
case "$KVER" in 7.0.13-400.asahi.fc44.aarch64+16k) ;; *) say "ABORT: unexpected kernel $KVER"; exit 1 ;; esac
for f in phy-apple-t6050-usb2.ko azahi-usb-overlay.ko dwc3-apple-t6050.ko; do
	[ -f "$DIR/$f" ] || { say "ABORT: missing $DIR/$f"; exit 1; }
done
run sha256sum "$DIR"/phy-apple-t6050-usb2.ko "$DIR"/azahi-usb-overlay.ko "$DIR"/dwc3-apple-t6050.ko
run ip -brief link
dmesg -w >> "$LOG" 2>&1 &
DMESG_PID=$!
trap 'kill $DMESG_PID 2>/dev/null' EXIT

say "--- stage 1: in-tree modules"
run modprobe apple-dart
run modprobe dwc3
run modprobe xhci-plat-hcd
run modprobe usbnet
run modprobe cdc_ncm
run modprobe cdc_ether
run modprobe rndis_host

say "--- stage 2: PHY provider (no hardware writes at probe)"
run insmod "$DIR/phy-apple-t6050-usb2.ko"

say "--- stage 3: overlay loader ($VARIANT)"
case "$VARIANT" in
	dry)  run insmod "$DIR/azahi-usb-overlay.ko" dry_run=1; sleep 1; run dmesg | tail -n 40; say "dry run complete"; exit 0 ;;
	pmgr) run insmod "$DIR/azahi-usb-overlay.ko" variant=pmgr ;;
	*)    run insmod "$DIR/azahi-usb-overlay.ko" ;;
esac
sleep 2
run dmesg | grep -E "azahi|apple-dart|phy-apple-t6050|OF: " | tail -n 40

say "--- stage 4: DWC3 glue (forced host mode)"
run insmod "$DIR/dwc3-apple-t6050.ko"
sleep 3
run dmesg | grep -E "dwc3|xhci|azahi|phy-apple-t6050|usb [0-9]" | tail -n 40

say "--- stage 5: wait for xHCI root hub"
i=0
while [ $i -lt 30 ] && [ ! -d /sys/bus/usb/devices/usb1 ]; do sleep 1; i=$((i+1)); done
if [ -d /sys/bus/usb/devices/usb1 ]; then
	say "root hub present after ${i}s"
	run ls /sys/bus/usb/devices/
else
	say "FAIL: no xHCI root hub after 30s"; run dmesg | tail -n 60; exit 2
fi

say "--- stage 6: wait for a child device (phone) and a network interface"
i=0
while [ $i -lt 60 ]; do
	NEWIF="$(ls /sys/class/net | grep -v -E '^lo$' | head -n 1)"
	[ -n "$NEWIF" ] && break
	sleep 1; i=$((i+1))
done
for d in /sys/bus/usb/devices/[0-9]*-[0-9]*; do
	[ -f "$d/idVendor" ] && say "usb device $(basename "$d"): $(cat "$d/idVendor"):$(cat "$d/idProduct") $(cat "$d/product" 2>/dev/null)"
done
if [ -z "${NEWIF:-}" ]; then
	say "FAIL: root hub up but no network interface after 60s (no child device, VBUS, or tethering not enabled on the phone)"
	run dmesg | tail -n 60; exit 3
fi
say "network interface: $NEWIF"

say "--- stage 7: address, route, DNS, HTTPS"
if command -v nmcli >/dev/null 2>&1; then
	run nmcli device status
	nmcli device connect "$NEWIF" 2>&1 | tee -a "$LOG"
else
	run ip link set "$NEWIF" up
fi
i=0
while [ $i -lt 45 ]; do
	ip -4 addr show "$NEWIF" | grep -q "inet " && break
	sleep 1; i=$((i+1))
done
run ip -4 addr show "$NEWIF"
run ip route
run getent hosts asahilinux.org
run curl -sS -m 25 -o /dev/null -w 'HTTPS asahilinux.org -> HTTP %{http_code}\n' https://asahilinux.org/
RC=$?
if [ $RC -eq 0 ]; then say "SUCCESS: outbound HTTPS over $NEWIF"; else say "FAIL: HTTPS rc=$RC"; fi
say "done; full log: $LOG"
