#!/usr/bin/env python3
"""Architectural preflight and optional RAM-independent SEV entry test.

Pinned to second direct V5 boot and completed in-image CPU2 test. No core
start, timer, reset-vector or MMIO writes without --start-cpu3. That option
retains all old code and redirects reset slots to SEV/B in unused init
padding, then starts only CPU3 with the source-verified full-bank sequence.
Physical cycle mandatory afterwards; no C SMP, Linux, freeing or reuse.
"""
import argparse
import hashlib
import os
from pathlib import Path
import signal
import struct
import sys

sys.path[:0] = ['/PRIVATE-USER/azahi/lib', '/PRIVATE-USER/azahi/proxyclient']
os.environ['M1N1DEVICE'] = '/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED'
from m1n1.proxy import UartInterface, M1N1Proxy, REGION_RW_EL0
from m1n1.proxyutils import ProxyUtils, bootstrap_port
from m1n1.asm import ARMAsm

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--measure', action='store_true', help='Measure bounded WFET on primary only; no timer/core writes')
parser.add_argument('--start-cpu3', action='store_true', help='One-shot CPU3 SEV test, requires --measure')
parser.add_argument('--start-entry-cpu4', action='store_true', help='After CPU3 test, redirect main entry too and test CPU4')
parser.add_argument('--offline', action='store_true')
args = parser.parse_args()
assert not args.start_cpu3 or args.measure
assert not args.start_entry_cpu4 or args.measure
assert not (args.start_cpu3 and args.start_entry_cpu4)

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

BASE = 0x10005d94000
STUB = BASE + 0x2000
CODE = bytes.fromhex('0a0073102b0480d24b0100f99f3f03d5ab0038d54b0500f94b4238d54b0900f90b1038d54b0d00f9491100f99f3f03d55f2003d5ffffff17')
EVENT_STUB = BASE + 0x3000
EVENT_CODE = ARMAsm('1: sev; b 1b', EVENT_STUB).data
assert EVENT_CODE.hex() == '9f2003d5ffffff17'
blob = Path(__file__).with_name('m1n1-smp-diag-v5-20260906.bin').read_bytes()
assert hashlib.sha256(blob).hexdigest() == '7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef'
assert blob[0x3000:0x3008] == bytes(8)
if args.offline:
    measurement = ARMAsm(MEASURE + '; ret', BASE).data
    assert struct.pack('<I', 0xd5031009) in measurement  # WFET x9
    print('EVENT_OFFLINE_PASS', EVENT_CODE.hex(), 'measurement=' + measurement.hex())
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
    assert iface.readmem(STUB, len(CODE)) == CODE
    assert u.mrs('VBAR_EL1') == BASE + 0x2a800
    assert iface.readmem(BASE + 0x2a800, 0x800) == blob[0x2a800:0x2b000]
    for slot in range(0, 0x800, 128):
        pc = BASE + slot + 4
        target = EVENT_STUB if args.start_entry_cpu4 else STUB
        expected = 0x14000000 | (((target - pc) >> 2) & 0x3ffffff)
        assert struct.unpack('<I', iface.readmem(pc, 4))[0] == expected
    registers = {}
    for name, encoding in [
        ('ID_AA64ISAR2_EL1', (3, 0, 0, 6, 2)),
        ('HCR_EL2', (3, 4, 1, 1, 0)),
        ('CNTHCTL_EL2', (3, 4, 14, 1, 0)),
        ('CNTKCTL_EL1', (3, 0, 14, 1, 0)),
        ('CNTFRQ_EL0', (3, 3, 14, 0, 0)),
        ('CNTPCT_EL0', (3, 3, 14, 0, 1)),
        ('ISR_EL1', (3, 0, 12, 1, 0)),
    ]:
        registers[name] = u.mrs(encoding)
        print(f'EVENT_PREFLIGHT {name}={registers[name]:#x}', flush=True)
    if args.measure:
        assert registers['ID_AA64ISAR2_EL1'] & 15 == 2  # FEAT_WFxT
        assert registers['HCR_EL2'] & (1 << 34)  # VHE; counter offset effectively zero
        assert registers['CNTFRQ_EL0'] == 1_000_000_000
        assert registers['ISR_EL1'] == 0
        for i in range(5):
            count = u.exec(MEASURE, r1=20_000_000)
            status = u.mrs('ISR_EL1')
            print(f'EVENT_PRIMARY_BASELINE {i} returns={count} window_ms=20 isr={status:#x}', flush=True)
            assert status == 0 and 1 <= count < 1000, 'Baseline not quiet; no core test allowed'
    if args.start_cpu3:
        cpus = list(u.adt['/cpus'])
        assert len(cpus) == 18 and cpus[3].cpu_id == 3 and cpus[3].reg == 3
        assert cpus[3].cpu_impl_reg[0] == 0x210350000
        assert cpus[3].getprop('function-enable_core').args[0] == 8
        devices = [d for d in u.adt['/arm-io/pmgr'].devices if d.id2 == 4]
        assert len(devices) == 1 and devices[0].name == 'MCPU0_3'
        assert devices[0].offset == 0x18 and devices[0].group == 0
        assert not devices[0].flags.no_ps
        assert p.read64(0x210350000) & 0xfffffffff000 == BASE
        assert p.read32(0x280600018) == 0x100
        assert p.read32(0x280688004) == 0x3fff8
        assert all(p.read32(a) == 0 for a in (0x280688008, 0x28068800c, 0x280688010))
        assert iface.readmem(EVENT_STUB, 8) == bytes(8)
        assert iface.readmem(BASE + 0xe8000, 40) == bytes(40)
        print(f'EVENT_STUB_INSTALL {EVENT_STUB:#x}; all prior stubs retained', flush=True)
        iface.writemem(EVENT_STUB | REGION_RW_EL0, EVENT_CODE)
        assert iface.readmem(EVENT_STUB, 8) == EVENT_CODE
        p.dc_cvac(EVENT_STUB | REGION_RW_EL0, 8)
        for slot in range(0, 0x800, 128):
            pc = BASE + slot + 4
            branch = 0x14000000 | (((EVENT_STUB - pc) >> 2) & 0x3ffffff)
            p.write32(pc | REGION_RW_EL0, branch)
            assert p.read32(pc) == branch
        p.dc_cvac(BASE | REGION_RW_EL0, 0x800)
        u.exec('dsb sy; ic ialluis; dsb sy; isb')
        for address, value in ((0x280688004, 8), (0x280688008, 8),
                               (0x28068800c, 0), (0x280688010, 0)):
            print(f'EVENT_CPU3_START_WRITE {address:#x}={value:#x}', flush=True)
            p.write32(address, value)
        u.exec('dsb sy; sev')
        for i in range(10):
            count = u.exec(MEASURE, r1=20_000_000)
            status = u.mrs('ISR_EL1')
            print(f'EVENT_CPU3_OBSERVATION {i} returns={count} window_ms=20 isr={status:#x} power={p.read32(0x280600018):#x}', flush=True)
        print('EVENT_CPU3_COMPLETE; physical cycle before SMP/chainload/Linux/reuse', flush=True)
    if args.start_entry_cpu4:
        assert iface.readmem(EVENT_STUB, 8) == EVENT_CODE
        assert iface.readmem(BASE + 0x800, 0x40) == blob[0x800:0x840]
        cpus = list(u.adt['/cpus'])
        assert len(cpus) == 18 and cpus[4].cpu_id == 4 and cpus[4].reg == 4
        assert cpus[4].cpu_impl_reg[0] == 0x210450000
        assert cpus[4].getprop('function-enable_core').args[0] == 16
        devices = [d for d in u.adt['/arm-io/pmgr'].devices if d.id2 == 5]
        assert len(devices) == 1 and devices[0].name == 'MCPU0_4'
        assert devices[0].offset == 0x20 and devices[0].group == 0
        assert not devices[0].flags.no_ps
        assert p.read64(0x210450000) & 0xfffffffff000 == BASE
        assert p.read32(0x280600018) == 0x1f0
        assert p.read32(0x280600020) == 0x100
        assert p.read32(0x280688004) == 0x3fff0
        assert all(p.read32(a) == 0 for a in (0x280688008, 0x28068800c, 0x280688010))
        pc = BASE + 0x800
        branch = 0x14000000 | (((EVENT_STUB - pc) >> 2) & 0x3ffffff)
        print(f'EVENT_MAIN_ENTRY_PATCH {pc:#x} -> {EVENT_STUB:#x}', flush=True)
        p.write32(pc | REGION_RW_EL0, branch)
        assert p.read32(pc) == branch
        p.dc_cvac(pc | REGION_RW_EL0, 4)
        u.exec('dsb sy; ic ialluis; dsb sy; isb')
        for address, value in ((0x280688004, 16), (0x280688008, 16),
                               (0x28068800c, 0), (0x280688010, 0)):
            print(f'EVENT_CPU4_START_WRITE {address:#x}={value:#x}', flush=True)
            p.write32(address, value)
        u.exec('dsb sy; sev')
        for i in range(10):
            count = u.exec(MEASURE, r1=20_000_000)
            status = u.mrs('ISR_EL1')
            print(f'EVENT_CPU4_OBSERVATION {i} returns={count} window_ms=20 isr={status:#x} power={p.read32(0x280600020):#x}', flush=True)
        print('EVENT_CPU4_COMPLETE; physical cycle before SMP/chainload/Linux/reuse', flush=True)
    p.nop()
    print('EVENT_CHECK_PROXY_ALIVE; timer controls unchanged', flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
