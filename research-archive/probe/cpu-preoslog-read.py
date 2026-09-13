#!/usr/bin/env python3
"""Copy live ADT-declared pre-OS log from RAM; no MMIO or startup writes.

Pinned to the second direct V5 boot with retained in-image parking stub.
Output is created exclusively; no target disk reads/writes or firmware calls.
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
output = Path(__file__).resolve().parent.parent / 'logs/cpu-direct-v5-preoslog-20260906.bin'
assert not output.exists()
signal.alarm(25)
iface = UartInterface()
iface.dev.timeout = 3
iface.dev.write_timeout = 3
try:
    p = M1N1Proxy(iface)
    bootstrap_port(iface, p)
    u = ProxyUtils(p, heap_size=16 * 1024 * 1024)
    assert u.base == BASE and u.adt['/chosen'].chip_id == 0x6050
    assert u.mrs('MPIDR_EL1') == 0x80040000
    for slot in range(0, 0x800, 128):
        pc = BASE + slot + 4
        expected = 0x14000000 | (((STUB - pc) >> 2) & 0x3ffffff)
        assert struct.unpack('<I', iface.readmem(pc, 4))[0] == expected
    address, size = u.adt['/chosen/memory-map'].getprop('preoslog')
    assert 0x10000000000 <= address < 0x10100000000
    assert 0 < size <= 0x40000 and address + size <= 0x10100000000
    print(f'PREOSLOG_RAM {address:#x}+{size:#x}', flush=True)
    data = iface.readmem(address, size)
    assert len(data) == size
    with output.open('xb') as stream:
        stream.write(data)
    p.nop()
    print(f'PREOSLOG_READ_PROXY_ALIVE saved={output}', flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
