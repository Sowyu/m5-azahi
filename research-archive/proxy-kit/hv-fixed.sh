#!/bin/sh
# Chainload the VM_TMR-fixed m1n1, then run Linux under its hypervisor.
#
# Why chainloading is safe here despite hv.sh's old warning: the stale-RVBAR
# hazard only exists if secondaries actually START. On T6050 the CPU-start
# writes are provably ignored (PS registers stay 0x100, all 17 secondaries
# time out), so no core ever resets into the 1TR-installed image. smp.c:127
# only prints a warning and continues. Revisit ONLY if CPU-start ever works.
#
# The fixed image is m1n1-vmtmrfix.bin (built from the local tree +
# m1n1-vmtmr-ro.patch: hv_update_fiq masks guest timers via CNTx_CTL_EL02
# IMASK instead of writing the read-only VM_TMR_FIQ_ENA). It is zero-padded
# so payload_run() hits the "No more payloads" path and drops into the proxy
# instead of scanning leftover RAM garbage (the attempt-2 SError).
#
# Run on the HOST Mac:  sh hv-fixed.sh

set -e
KIT="$(cd "$(dirname "$0")" && pwd)"
# HOSTM1N1=<path> overrides the host m1n1 that gets chainloaded.
# Use m1n1-nvme.bin for storage work (vmtmr fix + SART v4).
IMG="${HOSTM1N1:-}"
[ -n "$IMG" ] || IMG="$KIT/../m1n1-vmtmrfix.bin"
[ -f "$IMG" ] || IMG="$KIT/m1n1-vmtmrfix.bin"
[ -f "$IMG" ] || { echo "Missing m1n1-vmtmrfix.bin"; exit 1; }

echo "=== step 1/2: chainload fixed m1n1 (watch the M5: expect 'Running proxy...') ==="
sh "$KIT/run.sh" "$KIT/proxyclient/tools/chainload.py" -r "$IMG"

echo "=== waiting for USB re-enumeration ==="
i=0
while [ $i -lt 30 ]; do
    sleep 2
    [ -n "$(ls /dev/cu.usbmodem* 2>/dev/null)" ] && break
    i=$((i+1))
done
[ -n "$(ls /dev/cu.usbmodem* 2>/dev/null)" ] || { echo "M5 did not come back on USB"; exit 1; }
sleep 3

# Step 2 is RETRIED. After the chainload m1n1 re-enumerates its CDC gadget and
# the /dev node reappears before the endpoint is actually ready, so the first
# bootstrap_port() often times out ("Expected 1 bytes, got 0"). A failed
# bootstrap is harmless - it never reaches the guest, and the M5 stays sitting
# at "Running proxy..." - so just try again rather than burning an operator
# power cycle. Observed: attempt 1 fails, a later one succeeds.
echo "=== step 2/2: boot Linux as hv guest (log -> hv.log) ==="
n=1
while [ $n -le 6 ]; do
    echo "--- hv attempt $n/6 ---"
    sh "$KIT/hv.sh" && exit 0
    rc=$?
    # Only retry the handshake failure; anything else is a real error.
    if ! tail -40 "$KIT/hv.log" 2>/dev/null | grep -q . && [ $n -lt 6 ]; then
        :
    fi
    echo "--- attempt $n failed (rc=$rc), settling 15s ---"
    sleep 15
    n=$((n + 1))
done
echo "hv failed after 6 attempts"
exit 1
