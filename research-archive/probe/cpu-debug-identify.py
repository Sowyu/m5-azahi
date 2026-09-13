#!/usr/bin/env python3
"""Identify only the ADT CPU0/CPU1 CoreSight components using standard RO IDs.

No debug unlock, halt, instruction injection, CPU start, or disk access.
Stop on an access fault or non-CoreSight identity; never scan adjacent banks.
Register definitions: ARM-software/CSAL include/csregisters.h (Arm upstream).
"""
import os
import signal
import sys

sys.path[:0] = ["/PRIVATE-USER/azahi/lib", "/PRIVATE-USER/azahi/proxyclient"]
os.environ["M1N1DEVICE"] = "/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED"
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port

raise SystemExit("DISABLED: CPU0 CIDR0 at 0x210010ff0 caused SError on T6050; do not retry")

signal.alarm(25)
iface = UartInterface()
iface.dev.timeout = 3
iface.dev.write_timeout = 3
try:
    p = M1N1Proxy(iface)
    bootstrap_port(iface, p)
    u = ProxyUtils(p, heap_size=16 * 1024 * 1024)
    assert u.adt["/chosen"].chip_id == 0x6050

    def read_id(address, label):
        print(f"DEBUG_ID_READ_BEGIN {label} {address:#x}", flush=True)
        value = p.read32(address)
        print(f"DEBUG_ID_READ {label} {value:#x}", flush=True)
        if value == 0xabad1dea:
            raise RuntimeError("Debug ID access fault; no further reads or writes")
        return value

    for index in (0, 1):
        node = u.adt[f"/cpus/cpu{index}"]
        base, size = node.coresight_reg
        assert base == 0x210010000 + index * 0x100000 and size == 0x300c8
        power = p.read32(0x280600000 + 8 * index)
        if power == 0xabad1dea or ((power >> 4) & 15) != 15:
            raise RuntimeError("CPU not reported powered; refusing debug access")
        cid = [read_id(base + off, f"CPU{index}_CIDR{n}") & 0xff
               for n, off in enumerate((0xff0, 0xff4, 0xff8, 0xffc))]
        if cid != [0x0d, 0x90, 0x05, 0xb1]:
            raise RuntimeError(f"Not a standard class-9 CoreSight identity: {cid}")
        for name, offset in (("DEVARCH", 0xfbc), ("DEVTYPE", 0xfcc),
                             ("DEVID", 0xfc8), ("DEVID1", 0xfc4)):
            read_id(base + offset, f"CPU{index}_{name}")
    p.nop()
    print("DEBUG_IDENTIFY_PROXY_ALIVE", flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
