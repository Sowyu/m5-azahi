#!/usr/bin/env python3
"""Fresh direct V5: stateless CPU1 entry test using Apple's full cluster bank.

Source: ApplePMGR::configMiscCores in local mac17j KC, 0xfffffe0009495b74
through 0xfffffe0009495c5c: global mask, then EVERY cluster request (including
zero masks). No CPU stop/off/RVBAR writes. RAM reset slots remain patched
after this test; physical cycle required, never free/reuse the stub.
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
from m1n1.adt import load_adt
from m1n1.asm import ARMAsm

BASE = 0x10005d94000
TRACE = 0x10800012000
SEQUENCE = ((0x280688004, 2), (0x280688008, 2),
            (0x28068800c, 0), (0x280688010, 0))
SOURCE = '''
    movz x10, #0x2000
    movk x10, #1, lsl #16
    movk x10, #0x108, lsl #32
    mrs x11, MPIDR_EL1
    str x11, [x10, #8]
    mrs x11, CurrentEL
    str x11, [x10, #16]
    mrs x11, SCTLR_EL1
    str x11, [x10, #24]
    str x9, [x10, #32]
    mov x11, #0x11
    str x11, [x10]
    dsb sy
1:  wfe
    b 1b
'''


def topology(adt):
    assert adt['/chosen'].chip_id == 0x6050
    assert adt['/arm-io/pmgr'].get_reg(0) == (0x280600000, 0x1fc000)
    nodes = list(adt['/cpus'])
    assert len(nodes) == 18
    for i, node in enumerate(nodes):
        assert node.cpu_id == i and node.reg == (i // 6) * 256 + i % 6
        assert node.getprop('function-enable_core').args[0] == 1 << i
    assert nodes[1].cpu_impl_reg[0] == 0x210150000


def branch(pc, target):
    delta = target - pc
    assert delta % 4 == 0 and -(1 << 27) <= delta < (1 << 27)
    return 0x14000000 | ((delta >> 2) & 0x3ffffff)


if args.offline:
    topology(load_adt((root / 'adt-real-t6050.bin').read_bytes()))
    code = ARMAsm(SOURCE, BASE + 0x400000).data
    assert len(code) == 60
    for slot in range(0, 0x800, 128):
        assert branch(BASE + slot + 4, BASE + 0x400000) & 0xfc000000 == 0x14000000
    assert SEQUENCE[0][1] == SEQUENCE[1][1] == 2
    assert all(value == 0 for _, value in SEQUENCE[2:])
    print('FULL_BANK_OFFLINE_PASS', code.hex(), SEQUENCE)
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
    topology(u.adt)
    assert u.base == BASE
    assert u.mrs('MPIDR_EL1') == 0x80040000 and u.mrs('CurrentEL') == 8
    assert u.mrs('VBAR_EL1') == BASE + 0x2a800
    assert iface.readmem(BASE, 0x840) == blob[:0x840]
    assert not p.read8(BASE + 0xe1890) and not p.read32(BASE + 0xe1888)
    assert not any(p.smp_is_alive(i) for i in range(18))
    assert p.read32(0x280600008) == 0x100
    assert p.read32(0x280600030) == p.read32(0x280600060) == 0x100
    assert p.read32(0x280688004) == 0x3fffe
    assert all(p.read32(address) == 0 for address, _ in SEQUENCE[1:])
    assert p.read64(0x210150000) & 0x0000fffffffff000 == BASE
    stub = p.memalign(0x4000, 0x4000)
    assert BASE < stub < 0x1010a960000
    code = ARMAsm(SOURCE, stub).data
    assert len(code) == 60
    patches = [(BASE + slot + 4, branch(BASE + slot + 4, stub)) for slot in range(0, 0x800, 128)]
    print(f'RETAINED_FULL_BANK_STUB {stub:#x} TRACE {TRACE:#x}', flush=True)
    iface.writemem(TRACE, bytes(256))
    p.dc_civac(TRACE, 256)
    iface.writemem(stub, code)
    assert iface.readmem(stub, len(code)) == code
    p.dc_cvac(stub, len(code))
    for address, instruction in patches:
        p.write32(address | REGION_RW_EL0, instruction)
        assert p.read32(address) == instruction
    p.dc_cvac(BASE | REGION_RW_EL0, 0x800)
    u.exec('dsb sy; ic ialluis; dsb sy; isb')
    for address, value in SEQUENCE:
        print(f'APPLE_FULL_BANK_WRITE {address:#x}={value:#x}', flush=True)
        p.write32(address, value)
    u.exec('dsb sy; sev')
    for i in range(8):
        time.sleep(.125)
        p.dc_ivac(TRACE, 256)
        u.exec('dsb sy')
        values = struct.unpack('<5Q', iface.readmem(TRACE, 40))
        print(f'FULL_BANK_OBSERVATION {i} trace={values} power={p.read32(0x280600008):#x}', flush=True)
    assert p.read32(0x280600030) == p.read32(0x280600060) == 0x100
    p.nop()
    print('FULL_BANK_PROXY_ALIVE; CPU1 may be pending; physical cycle before reuse', flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
