#!/usr/bin/env python3
"""Read source-resolved T6050 SOC cluster controls; never write MMIO.

KC T6050 initRegGroups: group2/map0/offset0x20000. configCPUComplexPowerState
uses logical cluster+1, enableCluster/getPhysicalClusterID resolve soc-clusters
record byte0, getClusterPowerState reads base+0x20000+4*physicalID.
Only MACC0/MACC1/PACC entries, not display clusters or a register scan.
"""
import os
from pathlib import Path
import signal
import struct
import sys

sys.path[:0] = ['/PRIVATE-USER/azahi/lib', '/PRIVATE-USER/azahi/proxyclient']
os.environ['M1N1DEVICE'] = '/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED'
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port

BASE = 0x10005d94000
STUB = BASE + 0x2000
CODE = bytes.fromhex('0a0073102b0480d24b0100f99f3f03d5ab0038d54b0500f94b4238d54b0900f90b1038d54b0d00f9491100f99f3f03d55f2003d5ffffff17')
blob = Path(__file__).with_name('m1n1-smp-diag-v5-20260906.bin').read_bytes()
expected = bytearray(blob[:0x840])
for slot in range(0, 0x800, 128):
    delta = STUB - (BASE + slot + 4)
    struct.pack_into('<I', expected, slot + 4, 0x14000000 | ((delta >> 2) & 0x3ffffff))
signal.alarm(20)
iface = UartInterface()
iface.dev.timeout = 3
iface.dev.write_timeout = 3
try:
    p = M1N1Proxy(iface)
    bootstrap_port(iface, p)
    u = ProxyUtils(p, heap_size=16 * 1024 * 1024)
    assert u.base == BASE and u.adt['/chosen'].chip_id == 0x6050
    assert u.mrs('MPIDR_EL1') == 0x80040000 and u.mrs('CurrentEL') == 8
    assert iface.readmem(BASE, 0x840) == expected
    assert iface.readmem(STUB, len(CODE)) == CODE
    pmgr = u.adt['/arm-io/pmgr']
    assert pmgr.get_reg(0) == (0x280600000, 0x1fc000)
    records = pmgr.getprop('soc-clusters')
    assert isinstance(records, bytes) and len(records) == 140
    controls = []
    for physical, logical, name in [(0, 1, b'MACC0'), (1, 2, b'MACC1'), (2, 3, b'PACC')]:
        matches = [records[i:i+28] for i in range(0, len(records), 28)
                   if records[i+12:i+28].split(b'\0')[0] == name]
        assert len(matches) == 1
        assert matches[0][0] == physical and matches[0][3] == logical
        controls.append((name.decode(), 0x280620000 + 4 * physical))
    for name, address in controls:
        print(f'CLUSTER_CONTROL_READ_BEGIN {name} {address:#x}', flush=True)
        value = p.read32(address)
        if value == 0xabad1dea:
            raise RuntimeError('Register read fault; stopping, no further accesses')
        print(f'CLUSTER_CONTROL {name} {address:#x}={value:#x} request={value & 15}', flush=True)
    p.nop()
    print('CLUSTER_CONTROL_READ_PROXY_ALIVE; no MMIO writes', flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
