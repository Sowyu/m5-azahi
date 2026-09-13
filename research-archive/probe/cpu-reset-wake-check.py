#!/usr/bin/env python3
"""Bounded post-start observation of the private V2 diagnostic, plus one SEV.

No CPU power/start writes, reset, boot, disk access, or secondary function
calls. Only run with V2 already tested and no other proxy client active.
"""
import hashlib
import os
from pathlib import Path
import signal
import struct
import sys
import time

root = Path(__file__).resolve().parent.parent
image = (root / "probe/m1n1-smp-diag-v2-20260906.bin").read_bytes()
assert hashlib.sha256(image).hexdigest() == "9f37a3f65f64fce68db37a144148bb4a9679fd0cb28241b3eb02279ce5800163"
sys.path[:0] = ["/PRIVATE-USER/azahi/lib", "/PRIVATE-USER/azahi/proxyclient"]
os.environ["M1N1DEVICE"] = "/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED"
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port

signal.alarm(25)
iface = UartInterface()
iface.dev.timeout = 3
iface.dev.write_timeout = 3
try:
    p = M1N1Proxy(iface)
    bootstrap_port(iface, p)
    u = ProxyUtils(p, heap_size=16 * 1024 * 1024)
    assert u.adt["/chosen"].chip_id == 0x6050
    assert u.mrs("MPIDR_EL1") == 0x80040000
    for offset, size in ((0, 8), (0x8fc, 128)):
        if iface.readmem(u.base + offset, size) != image[offset:offset + size]:
            raise RuntimeError("Reset-vector code differs from verified V2 image")
    rvbar = p.read64(0x210150000)
    assert rvbar & 0x0000fffffffff000 == u.base
    assert not any(p.smp_is_alive(i) for i in range(18))
    print(f"V2_VECTOR_AND_RVBAR_MATCH base={u.base:#x}", flush=True)

    def observe(label):
        p.dc_ivac(0x10800010000, 256)
        u.exec("dsb sy")
        trace = struct.unpack("<4Q", iface.readmem(0x10800010000, 32))
        power = p.read32(0x280600008)
        if power == 0xabad1dea:
            raise RuntimeError("CPU1 power read fault")
        print(label, "trace=" + repr(trace), f"cpu1_power={power:#x}", flush=True)
        return trace

    observe("BEFORE_SEV")
    u.exec("dsb sy; sev; dsb sy")
    print("PRIMARY_SEV_SENT; no power/start writes", flush=True)
    for i in range(4):
        time.sleep(0.25)
        observe(f"AFTER_SEV_{i}")
    print("CPU_ALIVE_AFTER_SEV", [i for i in range(18) if p.smp_is_alive(i)], flush=True)
    p.nop()
    print("WAKE_CHECK_PROXY_ALIVE", flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
