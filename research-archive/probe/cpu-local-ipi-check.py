#!/usr/bin/env python3
"""Bounded secondary event diagnostics; default is offline validation.

Tests only the hypothesis that an interrupt releases firmware WFI. The
current reset/main-entry SEV loops and all retained allocations remain intact.
Physical cycle is mandatory before loader/Linux reuse, regardless of result.
Local target encoding follows src/hv_exc.c: target Aff0, current Aff1/Aff2.
Never use smp_send_ipi: this boot's uninitialized spin table has no MPIDRs.
--cpu5-fast-bank instead tests the complete start bank in one on-target call,
without USB gaps between register writes. It does not send an IPI.
"""
import argparse
import os
import signal
import struct
import sys

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
SEND = 'mov x0, #1; dsb sy; msr S3_5_C15_C0_0, x0; isb'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', action='store_true')
parser.add_argument('--cpu5-fast-bank', action='store_true')
args = parser.parse_args()
assert struct.pack('<I', 0xd5031009) in ARMAsm(MEASURE + '; ret', 0x10000).data
assert struct.pack('<I', 0xd51df000) in ARMAsm(SEND + '; ret', 0x10000).data
BASE = 0x10005d94000
STUB = BASE + 0x3000
if not args.run:
    print('LOCAL_IPI_OFFLINE_PASS: local Aff0=1; optional CPU5 fast-bank needs --run')
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
    cpus = list(u.adt['/cpus'])
    assert len(cpus) == 18 and cpus[1].cpu_id == 1 and cpus[1].reg == 1
    assert cpus[1].cpu_impl_reg[0] == 0x210150000
    assert p.read64(0x210150000) & 0xfffffffff000 == BASE
    assert p.read32(0x280600008) == 0x1f0
    assert p.read64(0x211e20020) == 0xc00102
    if args.cpu5_fast_bank:
        assert cpus[5].cpu_id == 5 and cpus[5].reg == 5
        assert cpus[5].cpu_impl_reg[0] == 0x210550000
        assert cpus[5].getprop('function-enable_core').args[0] == 32
        assert p.read64(0x210550000) & 0xfffffffff000 == BASE
        devices = [d for d in u.adt['/arm-io/pmgr'].devices if d.id2 == 6]
        assert len(devices) == 1 and devices[0].name == 'MCPU0_5'
        assert devices[0].group == 0 and devices[0].offset == 0x28
        assert p.read32(0x280600028) == 0x100
        assert p.read32(0x280688004) == 0x3ffa0
        assert all(p.read32(a) == 0 for a in (0x280688008, 0x28068800c, 0x280688010))
    for i in range(3):
        count = u.exec(MEASURE, r1=20_000_000)
        assert count == 1 and u.mrs('ISR_EL1') == 0
        print(f'LOCAL_IPI_BASELINE {i} returns={count}', flush=True)
    if args.cpu5_fast_bank:
        print('CPU5_FAST_BANK_ONCE 32,32,0,0; DSB between stores; no USB gaps', flush=True)
        u.exec('''
            mov w8, #32
            dsb sy
            str w8, [x0, #4]
            dsb sy
            str w8, [x0, #8]
            dsb sy
            str wzr, [x0, #12]
            dsb sy
            str wzr, [x0, #16]
            dsb sy
            sev
        ''', r0=0x280688000)
    else:
        print('LOCAL_IPI_SEND_ONCE S3_5_C15_C0_0=1; already-requested same-cluster CPU1', flush=True)
        u.exec(SEND)
    for i in range(10):
        count = u.exec(MEASURE, r1=20_000_000)
        power_addr = 0x280600028 if args.cpu5_fast_bank else 0x280600008
        print(f'EVENT_OBSERVATION {i} returns={count} isr={u.mrs("ISR_EL1"):#x} power={p.read32(power_addr):#x}', flush=True)
    p.nop()
    print('LOCAL_IPI_PROXY_ALIVE; preserve patches/allocations/APSC until physical cycle', flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
