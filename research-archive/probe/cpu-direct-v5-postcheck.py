#!/usr/bin/env python3
"""Read-only late observation of the first directly booted V5 CPU1 test."""
import hashlib
import os
from pathlib import Path
import signal
import struct
import sys

sys.path[:0] = ['/PRIVATE-USER/azahi/lib', '/PRIVATE-USER/azahi/proxyclient']
os.environ['M1N1DEVICE'] = '/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED'
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port

image = Path(__file__).with_name('m1n1-smp-diag-v5-20260906.bin').read_bytes()
assert hashlib.sha256(image).hexdigest() == '7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef'
signal.alarm(20)
iface = UartInterface()
iface.dev.timeout = 3
iface.dev.write_timeout = 3
try:
    p = M1N1Proxy(iface)
    bootstrap_port(iface, p)
    u = ProxyUtils(p, heap_size=16 * 1024 * 1024)
    assert u.adt['/chosen'].chip_id == 0x6050
    assert u.base == 0x10005200000
    assert u.mrs('MPIDR_EL1') == 0x80040000 and u.mrs('CurrentEL') == 8
    assert iface.readmem(u.base, 0x840) == image[:0x840]
    assert p.read8(u.base + 0xe1890) == 1
    assert p.read32(u.base + 0xe1888) == 1
    stack = p.read64(u.base + 0xe1908)
    assert u.base < stack < 0x1010a960000
    print(f'RETAINED_CPU1_RESET_STACK {stack:#x}', flush=True)
    p.dc_ivac(0x10800010000, 256)
    u.exec('dsb sy')
    print('LATE_TRACE', struct.unpack('<5Q', iface.readmem(0x10800010000, 40)), flush=True)
    print('ALIVE_FLAGS', [i for i in range(18) if p.smp_is_alive(i)], flush=True)
    for address in (0x280600008, 0x280688004, 0x280688008):
        value = p.read32(address)
        assert value != 0xabad1dea
        print(f'POST_STATUS {address:#x}={value:#x}', flush=True)
    assert p.read64(u.base + 0xe1908) == stack
    assert p.read32(u.base + 0xe1888) == 1
    p.nop()
    print('DIRECT_V5_POSTCHECK_PROXY_ALIVE; no restart, code patch or storage operation', flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
