#!/usr/bin/env python3
"""One-shot test of the all-WFI firmware RAM region as a secondary park area.

Hypothesis only: PR657 identifies a secondary-read-only range, not its PC.
Require all 48KiB equal WFI and the exact saved snapshot hash, then replace
each 8-byte pair with SEV/B(-4), safe at either instruction-aligned entry.
Use V5's bounded startup (stops at CPU1 on failure, progresses only on success)
so a core reaching normal reset code has a valid stack and target context.
Keep the entire
region patched until physical cycle; no SMP/chainload/Linux/restore/reuse.
No reset-vector edits, control MSRs, new MMIO offsets, or SSD operations.
Register provenance: https://github.com/AsahiLinux/m1n1/pull/657
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
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port, REGION_RW_EL0
from m1n1.asm import ARMAsm

BASE = 0x100055e0000
START, END = 0x10005dec000, 0x10005df8000
ORIGINAL = bytes.fromhex('7f2003d5') * ((END - START) // 4)
PATCH = bytes.fromhex('9f2003d5ffffff17') * ((END - START) // 8)
HASH = 'bc4a4e3073dfa66ac5ea39867e4c18866e96b396f32b9479b1499b9744b81871'
assert hashlib.sha256(ORIGINAL).hexdigest() == HASH
assert Path('logs/cpu-direct-v5-cycle3-ctrr-20260906.bin').read_bytes() == ORIGINAL
assert ARMAsm('1: sev; b 1b', START).data == PATCH[:8]
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
assert struct.pack('<I', 0xd5031009) in ARMAsm(MEASURE + '; ret', 0x10000).data
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', action='store_true')
parser.add_argument('--wake-existing', action='store_true',
                    help='One local CPU1 IPI after the already-completed parking test')
args = parser.parse_args()
if not args.run:
    print(f'CTRR_PARK_OFFLINE_PASS: {START:#x}..{END:#x}, {len(PATCH)} bytes; each word is SEV or branch to SEV')
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
    assert u.mrs('CurrentEL') == 8 and u.mrs('MPIDR_EL1') == 0x80040000
    assert u.mrs('CNTFRQ_EL0') == 1_000_000_000
    assert u.mrs((3, 0, 0, 6, 2)) & 15 == 2
    assert tuple(u.mrs((3, 0, 11, 1, n)) for n in (0, 1, 4)) == (START, END - 4096, 0)
    assert END <= u.heap_base
    image = Path('probe/m1n1-smp-diag-v5-20260906.bin').read_bytes()
    assert hashlib.sha256(image).hexdigest() == '7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef'
    assert iface.readmem(BASE, 0x840) == image[:0x840]
    if args.wake_existing:
        assert p.read32(BASE + 0xe1888) == 1 and p.read8(BASE + 0xe1890) == 1
        assert iface.readmem(START, END - START) == PATCH
    else:
        assert not p.read32(BASE + 0xe1888) and not p.read8(BASE + 0xe1890)
        assert iface.readmem(START, END - START) == ORIGINAL
    cpus = list(u.adt['/cpus'])
    assert len(cpus) == 18 and cpus[1].cpu_id == 1 and cpus[1].reg == 1
    assert cpus[1].cpu_impl_reg[0] == 0x210150000
    assert cpus[1].getprop('function-enable_core').args[0] == 2
    assert u.adt['/arm-io/pmgr'].get_reg(0) == (0x280600000, 0x1fc000)
    assert p.read64(0x210150000) & 0xfffffffff000 == BASE
    assert p.read32(0x280600008) == (0x1f0 if args.wake_existing else 0x100)
    assert p.read32(0x280688004) == (0x3fffc if args.wake_existing else 0x3fffe)
    assert all(p.read32(a) == 0 for a in (0x280688008, 0x28068800c, 0x280688010))
    for i in range(3):
        count = u.exec(MEASURE, r1=20_000_000)
        assert count == 1 and u.mrs('ISR_EL1') == 0
        print(f'CTRR_PARK_BASELINE {i} returns={count}', flush=True)
    if args.wake_existing:
        print('CTRR_PARK_LOCAL_IPI_ONCE; S3_5_C15_C0_0=1', flush=True)
        u.exec('mov x0, #1; dsb sy; msr S3_5_C15_C0_0, x0; isb')
    else:
        print('CTRR_PARK_PATCH_BEGIN; cycle required from this point', flush=True)
        iface.writemem(START | REGION_RW_EL0, PATCH)
        p.dc_cvac(START | REGION_RW_EL0, len(PATCH))
        u.exec('dsb sy; ic ialluis; dsb sy; isb')
        assert iface.readmem(START, len(PATCH)) == PATCH
        print('CTRR_PARK_PATCH_VERIFIED; reset/main-entry untouched', flush=True)
        p.smp_set_wfe_mode(True)
        print('CTRR_PARK_BOUNDED_V5_START; first CPU1, stops on first failure', flush=True)
        p.smp_start_secondaries()
    for i in range(10):
        count = u.exec(MEASURE, r1=20_000_000)
        print(f'CTRR_PARK_OBSERVATION {i} returns={count} isr={u.mrs("ISR_EL1"):#x} power={p.read32(0x280600008):#x}', flush=True)
    p.nop()
    p.dc_ivac(0x10800010000, 256)
    u.exec('dsb sy')
    print('CTRR_PARK_V5_TRACE', struct.unpack('<5Q', iface.readmem(0x10800010000, 40)), flush=True)
    print('CTRR_PARK_ALIVE', [i for i in range(18) if p.smp_is_alive(i)], flush=True)
    print('CTRR_PARK_PROXY_ALIVE; retain entire patched region until physical cycle', flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
