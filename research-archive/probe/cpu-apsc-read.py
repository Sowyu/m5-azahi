#!/usr/bin/env python3
"""Read only the exact T6050 APSC controls resolved from local Apple driver.

enableAPSC 0xfffffe0009880b30 reads ACC logical offset 0xe20020 as u64.
_getACCMappingAndLength/readACCReg resolve mapping IDs 0x2c/0x37/0x15,
whose initRegMaps indices are 0x10/0x1a/0x24 and logical base 0xe20000.
No MMIO writes, core starts, debug access, or storage operations.
Pinned to completed CPU4 SEV test, retaining every live RAM patch.
"""
import os
import signal
import struct
import sys

sys.path[:0] = ['/PRIVATE-USER/azahi/lib', '/PRIVATE-USER/azahi/proxyclient']
os.environ['M1N1DEVICE'] = '/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED'
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port

BASE = 0x10005d94000
STUB = BASE + 0x3000
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
    assert iface.readmem(STUB, 8).hex() == '9f2003d5ffffff17'
    for offset in [slot + 4 for slot in range(0, 0x800, 128)] + [0x800]:
        pc = BASE + offset
        branch = 0x14000000 | (((STUB - pc) >> 2) & 0x3ffffff)
        assert struct.unpack('<I', iface.readmem(pc, 4))[0] == branch
    pmgr = u.adt['/arm-io/pmgr']
    controls = [(0, 0x10, 0x210e20000), (1, 0x1a, 0x211e20000), (2, 0x24, 0x212e20000)]
    for cluster, index, base in controls:
        assert pmgr.get_reg(index) == (base, 0x12e8)
        assert p.read32(0x280600090 + cluster * 8) == 0x1f0
    for cluster, index, base in controls:
        address = base + 0x20
        print(f'APSC_READ_BEGIN cluster={cluster} address={address:#x}', flush=True)
        value = p.read64(address)
        assert value not in (0xabad1dea, 0xabad1deaabad1dea), 'Read fault, stopping'
        print(f'APSC_READ cluster={cluster} value={value:#x} disabled_bit23={(value >> 23) & 1} busy_bit7={(value >> 7) & 1} pending_bit31={(value >> 31) & 1}', flush=True)
    p.nop()
    print('APSC_READ_PROXY_ALIVE; no MMIO writes', flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
