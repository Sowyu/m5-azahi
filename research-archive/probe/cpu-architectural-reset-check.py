#!/usr/bin/env python3
"""Read the boot CPU's architectural reset vector, no MMIO or SMP writes.

Only read RVBAR_EL2 if PFR0 reports EL2 as highest implemented level.
ProxyUtils guards the MRS against synchronous undefined-register traps.
This does not read the failed CPU's registers or change its retained state.
"""
import os
import signal
import sys

sys.path[:0] = ["/PRIVATE-USER/azahi/lib", "/PRIVATE-USER/azahi/proxyclient"]
os.environ["M1N1DEVICE"] = "/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED"
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port

signal.alarm(20)
iface = UartInterface()
iface.dev.timeout = 3
iface.dev.write_timeout = 3
try:
    p = M1N1Proxy(iface)
    bootstrap_port(iface, p)
    u = ProxyUtils(p, heap_size=16 * 1024 * 1024)
    assert u.adt["/chosen"].chip_id == 0x6050
    assert u.base == 0x10005a0c000
    assert u.mrs("MPIDR_EL1") == 0x80040000
    assert u.mrs("CurrentEL") == 8
    feature = u.mrs("ID_AA64PFR0_EL1")
    print(f"PFR0 {feature:#x}", flush=True)
    if (feature >> 8) & 15 not in (1, 2) or (feature >> 12) & 15 != 0:
        raise RuntimeError("EL2 is not reported as highest EL; refusing RVBAR read")
    vector = u.mrs((3, 4, 12, 0, 1))
    print(f"BOOT_CPU_ARCH_RVBAR_EL2 {vector:#x}", flush=True)
    p.nop()
    print("ARCH_RESET_CHECK_PROXY_ALIVE", flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
