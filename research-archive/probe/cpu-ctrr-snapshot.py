#!/usr/bin/env python3
"""Copy only the firmware RAM range identified by upstream PR657.

No MMIO reads, CPU starts, register writes, firmware execution, or storage
operations on the target. Primary MRS reads require EL2. Bounded to this
fresh direct V5 boot and exactly 48KiB; output is a new host artifact.
Register provenance: https://github.com/AsahiLinux/m1n1/pull/657
"""
import hashlib
import os
from pathlib import Path
import signal
import sys

sys.path[:0] = ['/PRIVATE-USER/azahi/lib', '/PRIVATE-USER/azahi/proxyclient']
os.environ['M1N1DEVICE'] = '/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED'
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port

out = Path('logs/cpu-direct-v5-cycle3-ctrr-20260906.bin')
assert not out.exists()
signal.alarm(20)
iface = UartInterface()
iface.dev.timeout = 3
iface.dev.write_timeout = 3
try:
    p = M1N1Proxy(iface)
    bootstrap_port(iface, p)
    u = ProxyUtils(p, heap_size=16 * 1024 * 1024)
    assert u.adt['/chosen'].chip_id == 0x6050 and u.base == 0x100055e0000
    assert u.mrs('CurrentEL') == 8 and u.mrs('MPIDR_EL1') == 0x80040000
    start = u.mrs((3, 0, 11, 1, 0))
    last_page = u.mrs((3, 0, 11, 1, 1))
    control = u.mrs((3, 0, 11, 1, 4))
    assert (start, last_page, control) == (0x10005dec000, 0x10005df7000, 0)
    end = last_page + 4096  # UPR is the beginning of the final protected page.
    assert end - start == 48 * 1024 and end <= u.heap_base
    image = Path('probe/m1n1-smp-diag-v5-20260906.bin').read_bytes()
    assert hashlib.sha256(image).hexdigest() == '7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef'
    assert iface.readmem(u.base, 0x840) == image[:0x840]
    assert p.read32(u.base + 0xe1888) == 0 and p.read8(u.base + 0xe1890) == 0
    data = iface.readmem(start, end - start)
    assert len(data) == 48 * 1024
    with out.open('xb') as f:
        f.write(data)
    print(f'CTRR_RAM_SNAPSHOT {start:#x}..{end:#x} bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()}', flush=True)
    p.nop()
    print('CTRR_SNAPSHOT_PROXY_ALIVE; no secondary start or target data writes', flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
