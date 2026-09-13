#!/usr/bin/env python3
"""Catch the M5 m1n1 proxy window and park the machine in the proxy.

When the M5 reboots it shows "Running proxy..." for a few seconds waiting for a
client, then auto-boots KDE. Connecting during that window makes m1n1 enter
uartproxy_run() and stay there instead of booting. This polls for the USB port
and connects the instant it appears, then does only SAFE reads: a nop handshake,
the chip id, and the ATC2 (right-socket) PMGR power-state registers. It writes
nothing to the target.

  PYTHONPATH=~/azahi/lib:~/azahi/proxyclient python3 grab-proxy.py [timeout_s]
"""
import glob
import os
import sys
import time

TIMEOUT = int(sys.argv[1]) if len(sys.argv) > 1 else 240

# ATC2 = right USB-C socket (ADT instance 2). PMGR power-state registers are
# always-on and safe to read cold. group0 = 0x280600000, group2 = 0x288300000.
PS = [
    ("FAB5_SOC",       0x2806001f0),
    ("ATC2_COMMON",    0x280600238),
    ("ATC2_USB_AON",   0x288300178),
    ("ATC2_USB",       0x288300180),
    ("ATC2_PHYMXWRAP", 0x288300188),
]


def find_dev():
    devs = sorted(glob.glob("/dev/cu.usbmodem*"))
    return devs[0] if devs else None


def any_usbmodem():
    return sorted(glob.glob("/dev/*.usbmodem*"))


def main():
    import m1n1.proxy as proxy
    print(f"[grab] waiting up to {TIMEOUT}s for the M5 proxy window...", flush=True)
    os.environ["M1N1TIMEOUT"] = "2"
    deadline = time.time() + TIMEOUT
    p = None
    seen = set()
    while time.time() < deadline and p is None:
        allmodems = any_usbmodem()
        for d in allmodems:
            if d not in seen:
                seen.add(d)
                print(f"[grab] {time.strftime('%H:%M:%S')} USB device appeared: {d}", flush=True)
        dev = find_dev()
        if not dev:
            time.sleep(0.1)
            continue
        print(f"[grab] port appeared: {dev} — connecting", flush=True)
        time.sleep(0.1)
        try:
            iface = proxy.UartInterface(dev, debug=False)
            pp = proxy.M1N1Proxy(iface, debug=False)
            iface.nop()          # handshake; raises if the M5 is not answering
            p = pp
        except Exception as e:
            print(f"[grab] connect attempt failed ({e!r}); retrying", flush=True)
            time.sleep(0.3)
    if p is None:
        print("[grab] TIMED OUT — no proxy caught; the M5 likely booted KDE.", flush=True)
        return 2

    print("[grab] CONNECTED — the M5 is parked in the proxy (will not auto-boot).", flush=True)
    try:
        cid = p.get_chipid()
        print(f"[grab] chip id = {cid:#x} ({'T6050 as expected' if cid == 0x6050 else 'UNEXPECTED'})",
              flush=True)
    except Exception as e:
        print(f"[grab] chip id read note: {e!r}", flush=True)

    print("[grab] ATC2 (right socket) PMGR power state, read over the proxy:", flush=True)
    for name, addr in PS:
        try:
            v = p.read32(addr)
            print(f"[grab]   {name:14s} @{addr:#011x} = {v:#010x}  "
                  f"target={v & 0xf:#x} actual={(v >> 4) & 0xf:#x}"
                  f"{'  ACTIVE' if ((v >> 4) & 0xf) == 0xf else ''}", flush=True)
        except Exception as e:
            print(f"[grab]   {name:14s} @{addr:#011x} read FAILED: {e!r}", flush=True)

    print("[grab] link healthy. The M5 stays in the proxy; run more tools with "
          "sh ~/azahi/run.sh <tool>.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
