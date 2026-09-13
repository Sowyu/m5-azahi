#!/usr/bin/env python3
"""V5-state-pinned second-cluster entry test, with a stateless RAM parking stub.

Replaces only 16 reset-vector branch instructions; runtime vectors stay intact.
CPU1's retained stack/target are never changed. Any late CPU1 entry also parks
without using C globals. One CPU6 start uses its ADT-proven global bit 6 and
cluster 1 bit 0. No reset/off requests, RVBAR writes, scans or disk operations.
After this test a physical cycle is required; do not restore/reuse the stub.
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
parser.add_argument("--direct-boot", action="store_true",
                    help="Pin the first direct-installed V5 session instead of the old RAM-chainload session")
parser.add_argument("--performance-core", action="store_true",
                    help="CPU12-only follow-up; verify/reuse the exact already-installed CPU6 stub")
args = parser.parse_args()
BASE = 0x10005200000 if args.direct_boot else 0x1000495c000
root = Path(__file__).resolve().parent.parent
image = (root / "probe/m1n1-smp-diag-v5-20260906.bin").read_bytes()
assert hashlib.sha256(image).hexdigest() == "7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef"
sys.path[:0] = ["/PRIVATE-USER/azahi/lib", "/PRIVATE-USER/azahi/proxyclient"]
from m1n1.adt import load_adt
from m1n1.asm import ARMAsm

TRACE = 0x10800012000
CPU = 12 if args.performance_core else 6
POWER = 0x280600000 + 8 * CPU
IMPL = 0x210050000 + (CPU // 6) * 0x1000000
DOORBELL = 0x280688008 + 4 * (CPU // 6)
assert 0x1010a960000 <= TRACE < TRACE + 256 <= 0x10f4ab00000
SOURCE = """
    movz x10, #0x2000
    movk x10, #0x0001, lsl #16
    movk x10, #0x0108, lsl #32
    mrs x11, MPIDR_EL1
    str x11, [x10, #8]
    mrs x11, CurrentEL
    str x11, [x10, #16]
    mrs x11, SCTLR_EL1
    str x11, [x10, #24]
    str x9, [x10, #32]
    mov x11, #6
    str x11, [x10]
    dsb sy
1:  wfe
    b 1b
"""

def branch(address, target):
    delta = target - address
    if delta % 4 or not -(1 << 27) <= delta < 1 << 27:
        raise ValueError("Branch out of range")
    return 0x14000000 | ((delta >> 2) & 0x03ffffff)

def topology(adt):
    assert adt["/chosen"].chip_id == 0x6050
    assert adt["/arm-io/pmgr"].get_reg(0) == (0x280600000, 0x1fc000)
    nodes = list(adt["/cpus"])
    assert len(nodes) == 18
    for i, n in enumerate(nodes):
        assert n.cpu_id == i and n.reg == (i // 6) * 256 + i % 6
        assert n.getprop("function-enable_core").args[0] == 1 << i
    assert nodes[6].cpu_impl_reg[0] == 0x211050000
    devices = [d for d in adt["/arm-io/pmgr"].devices if d.id2 == 7]
    assert len(devices) == 1
    assert devices[0].name == "MCPU1_0" and devices[0].offset == 0x30 and devices[0].group == 0

if args.offline:
    topology(load_adt((root / "adt-real-t6050.bin").read_bytes()))
    code = ARMAsm(SOURCE, 0x10007000000).data
    assert len(code) == 60
    for slot in range(0, 0x800, 128):
        word = branch(BASE + slot + 4, 0x10007000000)
        assert word & 0xfc000000 == 0x14000000
    print("CPU6_PARK_OFFLINE_PASS", code.hex())
    raise SystemExit(0)

os.environ["M1N1DEVICE"] = "/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED"
from m1n1.proxy import UartInterface, M1N1Proxy, REGION_RW_EL0
from m1n1.proxyutils import ProxyUtils, bootstrap_port
signal.alarm(30)
iface = UartInterface()
iface.dev.timeout = 3
iface.dev.write_timeout = 3
try:
    p = M1N1Proxy(iface)
    bootstrap_port(iface, p)
    u = ProxyUtils(p, heap_size=16 * 1024 * 1024)
    topology(u.adt)
    assert u.base == BASE
    assert u.mrs("MPIDR_EL1") == 0x80040000
    assert u.mrs("CurrentEL") == 8
    assert u.mrs("VBAR_EL1") == u.base + 0x2a800
    expected = bytearray(image[:0x840])
    if args.performance_core:
        # Exact native retained allocations from each session's CPU6 log.
        stub = 0x10008034000 if args.direct_boot else 0x1000768c000
        code = ARMAsm(SOURCE, stub).data
        assert iface.readmem(stub, len(code)) == code
        for slot in range(0, 0x800, 128):
            struct.pack_into("<I", expected, slot + 4, branch(u.base + slot + 4, stub))
    assert iface.readmem(u.base, 0x840) == expected
    assert p.read8(u.base + 0xe1890) == 1
    assert p.read32(u.base + 0xe1888) == 1
    retained_stack = p.read64(u.base + 0xe1908)
    assert u.base < retained_stack < 0x1010a960000
    assert not any(p.smp_is_alive(i) for i in range(18))
    assert p.read32(POWER) == 0x100
    assert p.read64(IMPL) & 0x0000fffffffff000 == u.base
    assert p.read32(0x280688004) == (0x3ffbc if args.performance_core else 0x3fffc)
    assert p.read32(DOORBELL) == 0

    # Native allocation is intentionally retained across later proxy clients.
    if not args.performance_core:
        stub = p.memalign(0x4000, 0x4000)
        assert u.base < stub < stub + 0x4000 < 0x1010a960000
        code = ARMAsm(SOURCE, stub).data
        patches = [(u.base + slot + 4, branch(u.base + slot + 4, stub))
                   for slot in range(0, 0x800, 128)]
        print(f"PARK_ALLOCATION {stub:#x}; patching through existing writable RAM alias", flush=True)
        assert iface.readmem(u.base | REGION_RW_EL0, 0x840) == image[:0x840]
        iface.writemem(TRACE, bytes(256))
        p.dc_civac(TRACE, 256)
        iface.writemem(stub, code)
        assert iface.readmem(stub, len(code)) == code
        p.dc_cvac(stub, len(code))
        for address, instruction in patches:
            p.write32(address | REGION_RW_EL0, instruction)
            assert p.read32(address) == instruction
        p.dc_cvac(u.base | REGION_RW_EL0, 0x800)
        u.exec("dsb sy; ic ialluis; dsb sy; isb")
    else:
        # Do not change executable bytes, trace contents, or either core's state.
        p.dc_ivac(TRACE, 256)
        u.exec("dsb sy")
        assert iface.readmem(TRACE, 40) == bytes(40)
        assert p.read32(0x280600030) == 0x1f0
    print(f"STATELESS_PARK_STUB {stub:#x} TRACE {TRACE:#x}; no shared C startup state", flush=True)
    print(f"CPU{CPU}_START global={1 << CPU:#x} @0x280688004, cluster=0x1 @{DOORBELL:#x}", flush=True)
    p.write32(0x280688004, 1 << CPU)
    p.write32(DOORBELL, 1)
    u.exec("dsb sy; sev")
    for i in range(8):
        time.sleep(0.125)
        p.dc_ivac(TRACE, 256)
        u.exec("dsb sy")
        trace = struct.unpack("<5Q", iface.readmem(TRACE, 40))
        print(f"CPU{CPU}_PARK_OBSERVATION {i} trace={trace} power={p.read32(POWER):#x}", flush=True)
    assert p.read32(u.base + 0xe1888) == 1
    assert p.read64(u.base + 0xe1908) == retained_stack
    p.nop()
    print(f"CPU{CPU}_PARK_PROXY_ALIVE; reset branches now patched; physical cycle before Linux/reuse", flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
