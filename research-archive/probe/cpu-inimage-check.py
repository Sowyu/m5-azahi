#!/usr/bin/env python3
"""CPU2 follow-up: PC-relative entry marker entirely inside direct V5 image.

Pinned to completed full-bank CPU1 test, retaining its stateless stub forever.
New code occupies linker-confirmed .init padding at +0x2000. Trace occupies
unused EL3 stack at +0xe8000; PFR0 must report no EL3. No C/stack startup,
CPU reset/off or RVBAR writes, storage operations, or existing stub reuse.
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
parser.add_argument('--offline', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
blob = (root / 'probe/m1n1-smp-diag-v5-20260906.bin').read_bytes()
assert hashlib.sha256(blob).hexdigest() == '7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef'
sys.path[:0] = ['/PRIVATE-USER/azahi/lib', '/PRIVATE-USER/azahi/proxyclient']
from m1n1.asm import ARMAsm

BASE = 0x10005d94000
OLD_STUB = 0x10008bb4000
STUB = BASE + 0x2000
TRACE = BASE + 0xe8000
OLD_CODE = bytes.fromhex('0a0084d22a00a0f20a21c0f2ab0038d54b0500f94b4238d54b0900f90b1038d54b0d00f9491100f92b0280d24b0100f99f3f03d55f2003d5ffffff17')
SOURCE = '''
    adr x10, . + 0xe6000
    mov x11, #0x21
    str x11, [x10]
    dsb sy
    mrs x11, MPIDR_EL1
    str x11, [x10, #8]
    mrs x11, CurrentEL
    str x11, [x10, #16]
    mrs x11, SCTLR_EL1
    str x11, [x10, #24]
    str x9, [x10, #32]
    dsb sy
1:  wfe
    b 1b
'''


def branch(pc, target):
    delta = target - pc
    assert delta % 4 == 0 and -(1 << 27) <= delta < 1 << 27
    return 0x14000000 | ((delta >> 2) & 0x3ffffff)


code = ARMAsm(SOURCE, STUB).data
assert len(code) == 56
word = struct.unpack_from('<I', code)[0]
assert word & 0x9f00001f == 0x1000000a  # ADR x10
imm = ((word >> 29) & 3) | (((word >> 5) & 0x7ffff) << 2)
if imm & (1 << 20):
    imm -= 1 << 21
assert STUB + imm == TRACE
assert blob[0x2000:0x2000 + len(code)] == bytes(len(code))
assert blob[0xe8000:0xe8100] == bytes(256)
expected = bytearray(blob[:0x840])
for slot in range(0, 0x800, 128):
    struct.pack_into('<I', expected, slot + 4, branch(BASE + slot + 4, OLD_STUB))
if args.offline:
    print('INIMAGE_OFFLINE_PASS', f'code={STUB:#x}', f'PC-relative trace={TRACE:#x}', code.hex())
    raise SystemExit(0)

os.environ['M1N1DEVICE'] = '/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED'
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
    assert u.base == BASE and u.adt['/chosen'].chip_id == 0x6050
    assert u.mrs('MPIDR_EL1') == 0x80040000 and u.mrs('CurrentEL') == 8
    assert ((u.mrs('ID_AA64PFR0_EL1') >> 12) & 15) == 0
    assert u.mrs('VBAR_EL1') == BASE + 0x2a800
    assert iface.readmem(BASE, 0x840) == expected
    assert iface.readmem(OLD_STUB, len(OLD_CODE)) == OLD_CODE
    assert iface.readmem(STUB, len(code)) == bytes(len(code))
    assert iface.readmem(TRACE, 256) == bytes(256)
    assert p.read32(BASE + 0xe1888) == 0 and p.read8(BASE + 0xe1890) == 0
    assert not any(p.smp_is_alive(i) for i in range(18))
    cpus = list(u.adt['/cpus'])
    assert len(cpus) == 18 and cpus[2].cpu_id == 2 and cpus[2].reg == 2
    assert cpus[2].cpu_impl_reg[0] == 0x210250000
    assert cpus[2].getprop('function-enable_core').args[0] == 4
    devices = [d for d in u.adt['/arm-io/pmgr'].devices if d.id2 == 3]
    assert len(devices) == 1 and devices[0].name == 'MCPU0_2'
    assert devices[0].offset == 0x10 and devices[0].group == 0
    assert not devices[0].flags.no_ps
    assert p.read32(0x280600008) == 0x1f0
    assert p.read32(0x280600010) == 0x100
    assert p.read32(0x280688004) == 0x3fffc
    assert all(p.read32(a) == 0 for a in (0x280688008, 0x28068800c, 0x280688010))
    print(f'INIMAGE_STUB {STUB:#x} TRACE {TRACE:#x}; old stub {OLD_STUB:#x} retained', flush=True)
    p.dc_civac(TRACE, 256)
    iface.writemem(STUB | REGION_RW_EL0, code)
    assert iface.readmem(STUB, len(code)) == code
    p.dc_cvac(STUB | REGION_RW_EL0, len(code))
    for slot in range(0, 0x800, 128):
        pc = BASE + slot + 4
        p.write32(pc | REGION_RW_EL0, branch(pc, STUB))
        assert p.read32(pc) == branch(pc, STUB)
    p.dc_cvac(BASE | REGION_RW_EL0, 0x800)
    u.exec('dsb sy; ic ialluis; dsb sy; isb')
    for address, value in ((0x280688004, 4), (0x280688008, 4),
                           (0x28068800c, 0), (0x280688010, 0)):
        print(f'CPU2_START_WRITE {address:#x}={value:#x}', flush=True)
        p.write32(address, value)
    u.exec('dsb sy; sev')
    for i in range(8):
        time.sleep(.125)
        p.dc_ivac(TRACE, 256)
        u.exec('dsb sy')
        values = struct.unpack('<5Q', iface.readmem(TRACE, 40))
        print(f'INIMAGE_OBSERVATION {i} trace={values} power={p.read32(0x280600010):#x}', flush=True)
    assert iface.readmem(OLD_STUB, len(OLD_CODE)) == OLD_CODE
    p.nop()
    print('INIMAGE_PROXY_ALIVE; physical cycle required before reuse/Linux', flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
