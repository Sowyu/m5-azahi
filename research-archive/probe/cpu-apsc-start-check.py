#!/usr/bin/env python3
"""One-shot cluster1 APSC-disable hypothesis test, then CPU6 SEV entry.

Only new control write: OR bit23 of exact read64 control 0x211e20020,
as AppleT6050PMGR::enableAPSC(false, 1, 0) does. Never change cluster0,
frequency/voltage fields, debug controls, storage, existing code or traces.
Preserve disabled APSC and all live stubs until a physical cycle afterwards.
This is a hypothesis, not a demonstrated prerequisite of CPU startup.
"""
import argparse
import os
import signal
import struct
import sys
import time

sys.path[:0] = ['/PRIVATE-USER/azahi/lib', '/PRIVATE-USER/azahi/proxyclient']
os.environ['M1N1DEVICE'] = '/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED'
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port
from m1n1.asm import ARMAsm

MEASURE = '''
    .arch armv8.7-a
    isb
    mrs x8, CNTVCT_EL0
    add x9, x8, x1
    mov x0, #0
    sevl
    wfe
1:  wfet x9
    add x0, x0, #1
    isb
    mrs x10, CNTVCT_EL0
    cmp x10, x9
    b.lo 1b
'''
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', action='store_true')
args = parser.parse_args()
assert struct.pack('<I', 0xd5031009) in ARMAsm(MEASURE + '; ret', 0x10000).data
BASE = 0x10005d94000
STUB = BASE + 0x3000
CONTROL = 0x211e20020
ORIGINAL = 0x400102
DISABLED = ORIGINAL | (1 << 23)
if not args.run:
    print(f'APSC_START_OFFLINE_PASS read64/write64 {CONTROL:#x}: {ORIGINAL:#x}->{DISABLED:#x}, changed only bit23')
    raise SystemExit(0)
signal.alarm(25)
iface = UartInterface()
iface.dev.timeout = 3
iface.dev.write_timeout = 3
try:
    p = M1N1Proxy(iface)
    bootstrap_port(iface, p)
    u = ProxyUtils(p, heap_size=16 * 1024 * 1024)
    assert u.base == BASE and u.adt['/chosen'].chip_id == 0x6050
    assert u.mrs('MPIDR_EL1') == 0x80040000 and u.mrs('CurrentEL') == 8
    assert u.mrs((3, 0, 0, 6, 2)) & 15 == 2
    assert u.mrs('CNTFRQ_EL0') == 1_000_000_000
    assert iface.readmem(STUB, 8).hex() == '9f2003d5ffffff17'
    for offset in [slot + 4 for slot in range(0, 0x800, 128)] + [0x800]:
        pc = BASE + offset
        assert p.read32(pc) == 0x14000000 | (((STUB - pc) >> 2) & 0x3ffffff)
    assert u.adt['/arm-io/pmgr'].get_reg(0x1a) == (0x211e20000, 0x12e8)
    cpus = list(u.adt['/cpus'])
    assert len(cpus) == 18 and cpus[6].cpu_id == 6 and cpus[6].reg == 0x100
    assert cpus[6].cpu_impl_reg[0] == 0x211050000
    assert cpus[6].getprop('function-enable_core').args[0] == 64
    assert p.read64(0x211050000) & 0xfffffffff000 == BASE
    devices = [d for d in u.adt['/arm-io/pmgr'].devices if d.id2 == 7]
    assert len(devices) == 1 and devices[0].name == 'MCPU1_0'
    assert devices[0].group == 0 and devices[0].offset == 0x30 and not devices[0].flags.no_ps
    assert p.read32(0x280600098) == 0x1f0
    assert p.read32(0x280600030) == 0x100
    assert p.read32(0x280688004) == 0x3ffe0
    assert all(p.read32(a) == 0 for a in (0x280688008, 0x28068800c, 0x280688010))
    assert p.read64(CONTROL) == ORIGINAL
    for i in range(3):
        count = u.exec(MEASURE, r1=20_000_000)
        assert u.mrs('ISR_EL1') == 0 and count == 1
        print(f'APSC_BASELINE {i} returns={count}', flush=True)
    print(f'APSC_DISABLE_WRITE64 {CONTROL:#x}={DISABLED:#x}; primary cluster untouched', flush=True)
    p.write64(CONTROL, DISABLED)
    u.exec('dsb sy')
    for i in range(20):
        value = p.read64(CONTROL)
        print(f'APSC_DISABLE_POLL {i} value={value:#x}', flush=True)
        assert value not in (0xabad1dea, 0xabad1deaabad1dea)
        if value & (1 << 23) and not value & ((1 << 7) | (1 << 31)):
            break
        time.sleep(.005)
    else:
        raise RuntimeError('APSC did not settle; no CPU start. Cycle required, do not restore blindly')
    for address, value in ((0x280688004, 64), (0x280688008, 0),
                           (0x28068800c, 1), (0x280688010, 0)):
        print(f'APSC_CPU6_START_WRITE {address:#x}={value:#x}', flush=True)
        p.write32(address, value)
    u.exec('dsb sy; sev')
    for i in range(10):
        count = u.exec(MEASURE, r1=20_000_000)
        print(f'APSC_CPU6_OBSERVATION {i} returns={count} isr={u.mrs("ISR_EL1"):#x} power={p.read32(0x280600030):#x} apsc={p.read64(CONTROL):#x}', flush=True)
    p.nop()
    print('APSC_START_PROXY_ALIVE; cluster1 APSC retained disabled, physical cycle before reuse/Linux', flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
