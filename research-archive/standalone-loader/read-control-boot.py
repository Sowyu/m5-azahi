#!/usr/bin/env python3
"""Bounded V5 control-boot RAM evidence; no disk/MMIO/SMP-start writes.

Default validates local pinned inputs only. --run is tied to the Sep12 fresh
restored V5 base; do not reuse after another boot without a fresh review.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys

ROOT = Path(__file__).resolve().parent.parent
BASE = 0x100046d4000
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', action='store_true')
parser.add_argument('--destination', type=Path, required=True)
args = parser.parse_args()
directory = args.destination.resolve(strict=True)
for name in ('preoslog.bin', 'adt.bin', 'boot.json'):
    if (directory / name).exists():
        raise SystemExit('STOP: output already exists')
raw = (ROOT / 'probe/m1n1-smp-diag-v5-20260906.bin').read_bytes()
if hashlib.sha256(raw).hexdigest() != '7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef':
    raise SystemExit('STOP: V5 pin mismatch')
if not args.run:
    print('OFFLINE PASS: V5 pin and exclusive output paths; no target access')
    raise SystemExit(0)
sys.path[:0] = ['/PRIVATE-USER/azahi/lib', '/PRIVATE-USER/azahi/proxyclient']
os.environ['M1N1DEVICE'] = '/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED'
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port

signal.alarm(25)
iface = UartInterface()
iface.dev.timeout = iface.dev.write_timeout = 3
try:
    p = M1N1Proxy(iface)
    bootstrap_port(iface, p)
    u = ProxyUtils(p, heap_size=16 * 1024 * 1024)
    if (u.base != BASE or u.adt['/chosen'].chip_id != 0x6050
            or u.mrs('MPIDR_EL1') != 0x80040000 or u.mrs('CurrentEL') != 8
            or iface.readmem(BASE, 0x840) != raw[:0x840]
            or p.read8(BASE + 0xe1890) or p.read32(BASE + 0xe1888)
            or any(p.smp_is_alive(i) for i in range(18))):
        raise RuntimeError('STOP: not the reviewed clean V5 control boot')
    address, size = u.adt['/chosen/memory-map'].getprop('preoslog')
    if not (0x10000000000 <= address < address + size <= 0x10100000000
            and 0 < size <= 0x40000):
        raise RuntimeError('STOP: unexpected declared pre-OS log range')
    data = iface.readmem(address, size)
    if len(data) != size:
        raise RuntimeError('STOP: short RAM read')
    p.nop()
    report = dict(base=BASE, bootargs=u.ba_addr, preoslog_address=address,
                  preoslog_bytes=size, preoslog_sha256=hashlib.sha256(data).hexdigest(),
                  adt_sha256=hashlib.sha256(u.adt_data).hexdigest(),
                  phys_base=u.ba.phys_base, mem_size=u.ba.mem_size,
                  top_of_kernel_data=u.ba.top_of_kernel_data,
                  description='Current successful V5 control boot, not necessarily prior failed boot')
    for name, blob in [('preoslog.bin', data), ('adt.bin', u.adt_data),
                       ('boot.json', json.dumps(report, indent=2).encode())]:
        with (directory / name).open('xb') as stream:
            stream.write(blob)
    print(json.dumps(report, indent=2))
    print('CONTROL_BOOT_RAM_CAPTURED; proxy alive; no disk/SMP-start operation')
finally:
    iface.dev.close()
    signal.alarm(0)
