#!/usr/bin/env python3
"""One board/loader/state-pinned CPU1 ACTIVE request after the failed V4 test.

Uses the existing pmgr_set_mode transform on ADT device MCPU0_1 only. No
power-off/reset, CPU-start writes, loader replacement, or disk operations.
The failed V4 attempt retained CPU1's prepared stack/target for delayed entry.
"""
import argparse
import hashlib
import os
from pathlib import Path
import signal
import struct
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--offline", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
image = (root / "probe/m1n1-smp-diag-v4-20260906.bin").read_bytes()
assert hashlib.sha256(image).hexdigest() == "3fe03928a82d5a32f515eeb6f0668f0a2a80810691a6fe43e85ff81d27d3a185"
sys.path[:0] = ["/PRIVATE-USER/azahi/lib", "/PRIVATE-USER/azahi/proxyclient"]
from m1n1.adt import load_adt

def check_device(adt):
    assert adt["/chosen"].chip_id == 0x6050
    pmgr = adt["/arm-io/pmgr"]
    assert pmgr.get_reg(0) == (0x280600000, 0x1fc000)
    group = pmgr.getprop("ps-groups")[0]
    assert group.reg == 0 and group.offset == 0
    devices = [d for d in pmgr.devices if d.id2 == 2]
    assert len(devices) == 1
    dev = devices[0]
    assert dev.name == "MCPU0_1" and dev.group == 0 and dev.offset == 8
    assert not dev.flags.no_ps and list(dev.parents_un.u16id.parents) == [0, 0]
    assert adt["/cpus/cpu1"].cpu_impl_reg[0] == 0x210150000
    return 0x280600008

def active_request(value):
    if value != 0x1f0:
        raise ValueError("Unexpected CPU1 state; refusing power write")
    # Exactly pmgr_set_mode's clear mask and ACTIVE target from pmgr.c/h.
    return (value & ~((1 << 28) | (1 << 9) | (1 << 8) | 15)) | 15

assert active_request(0x1f0) == 0xff
if args.offline:
    assert check_device(load_adt((root / "adt-real-t6050.bin").read_bytes())) == 0x280600008
    for bad in (0, 0x100, 0xff, 0xabad1dea, 0x100001f0):
        try:
            active_request(bad)
        except ValueError:
            continue
        raise AssertionError("Accepted unexpected state")
    print("CPU1_ACTIVE_OFFLINE_PASS")
    raise SystemExit(0)

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
    address = check_device(u.adt)
    assert u.mrs("MPIDR_EL1") == 0x80040000
    for offset, size in ((0, 8), (0x800, 64), (0x93c, 128)):
        assert iface.readmem(u.base + offset, size) == image[offset:offset + size]
    assert p.read64(0x210150000) & 0x0000fffffffff000 == u.base
    # Symbol offsets from the matching V4 raw ELF; verify retained attempt.
    assert p.read8(u.base + 0xe1890) == 1  # t6050_start_failed
    assert p.read32(u.base + 0xe1888) == 1  # target_cpu
    stack = p.read64(u.base + 0xd6998 + 8)
    assert u.base < stack < 0x1010a960000 - 0x10000
    assert stack % 0x4000 == 0
    assert p.read64(u.base + 0xe1908) == stack + 0x10000
    assert not any(p.smp_is_alive(i) for i in range(18))
    flag = u.base + 0xe1288 + 64 + 8

    def observe(label):
        p.dc_ivac(0x10800010000, 256)
        p.dc_ivac(flag & ~63, 64)
        u.exec("dsb sy")
        trace = struct.unpack("<4Q", iface.readmem(0x10800010000, 32))
        result = (trace, p.read64(flag), p.read32(address))
        print(label, result, flush=True)
        return result

    trace, startup_flag, power = observe("BEFORE_ACTIVE")
    assert trace == (0, 0, 0, 0) and startup_flag == 0
    value = active_request(power)
    assert p.read32(address) == power
    print(f"CPU1_ONLY_ACTIVE_WRITE {address:#x}: {power:#x} -> {value:#x}", flush=True)
    p.write32(address, value)
    u.exec("dsb sy; sev; dsb sy")
    for i in range(8):
        time.sleep(0.125)
        observe(f"AFTER_ACTIVE_{i}")
    p.nop()
    print("CPU1_ACTIVE_CHECK_PROXY_ALIVE", flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
