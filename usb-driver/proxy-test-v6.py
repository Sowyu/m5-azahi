#!/usr/bin/env python3
"""One-shot v6 RAM test of the freshly observed v4 fallback session.

No flash/SSD writes, no injected code, no heap setup, no RVBAR/SMP experiment.
Writes only the identified existing bundle's initrd, then its 44-byte header.
Calls the byte-verified original standalone function and exits proxy ONLY if
it returns success with the expected kernel/FDT next-stage addresses.
--run consumes proxy access on successful Linux handoff. Not persistent.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import signal
import struct
import sys
if not __debug__: raise SystemExit('Refusing python -O: assert statements here are safety checks')

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
F = runpy.run_path(str(HERE / 'build-transfer-fixed.py'))
V = runpy.run_path(str(HERE / 'build-transfer-v6.py'))
B = F['B']
BASE = 0x10004d58000
TOP = 0x1000ad04000
FUNCTION = 0x7454
FUNCTION_SIZE = 0x80c
NEXT_STAGE = 0xdf5d0
FIXED_SHA = '324822de14a43ab164d0ec6257d50d9dd6be1b17fd063faf24b0d571e41096ee'
PORT = '/dev/cu.usbmodemPRIVATE'
CHUNK = 64 << 10  # 4 MiB reads lost data on this proxy link; 64 KiB verified.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    destination = args.destination.resolve(strict=True)
    assert destination.is_dir() and not any(destination.iterdir())
    image = V['OUTPUT'].read_bytes()
    receipt = json.loads(V['OUTPUT'].with_suffix('.json').read_text())
    assert hashlib.sha256(image).hexdigest() == FIXED_SHA
    new = V['inspect'](image, receipt)
    original = F['SOURCE'].read_bytes()
    assert hashlib.sha256(original).hexdigest() == F['SOURCE_SHA']
    old = B['parts'](original)
    header_offset = B['LOADER_SIZE']
    initrd_offset = header_offset + B['HEADER'].size + sum(len(old[n]) for n in ('args', 'dt', 'gzip'))
    assert BASE + initrd_offset + len(old['initrd']) < TOP < 0x1010a960000
    assert image[:header_offset] == original[:header_offset]
    assert image[header_offset + 44:initrd_offset] == original[header_offset + 44:initrd_offset]
    assert len(new['initrd']) == F['INITRD_BYTES'] < len(old['initrd'])
    print('RAM_TEST_OFFLINE_CHECKS_PASS; no persistent installation', flush=True)
    if not args.run:
        return
    sys.path[:0] = [str(ROOT / 'pylib'), str(ROOT / 'proxy-kit/proxyclient')]
    from m1n1.proxy import UartInterface, M1N1Proxy
    from m1n1.tgtypes import BootArgs_r3
    from m1n1.adt import load_adt

    signal.alarm(240)
    interface = UartInterface(PORT)
    interface.dev.timeout = interface.dev.write_timeout = 5
    log = (destination / 'events.log').open('x')
    def note(message):
        print(message, flush=True)
        log.write(message + '\n'); log.flush()
    try:
        proxy = M1N1Proxy(interface)
        interface.tty_enable = False  # Resync without printing stale binary data.
        interface.nop()
        interface.tty_enable = True
        assert proxy.get_base() == BASE and proxy.get_chipid() == 0x6050
        ba_address, revision = proxy.get_bootargs_rev()
        assert revision == 3 and ba_address == 0x1000acf4000
        ba = interface.readstruct(ba_address, BootArgs_r3)
        assert ba.top_of_kernel_data == TOP and ba.phys_base == 0x10003af8000
        assert ba.phys_base + ba.mem_size >= 0x10f4ab00000
        adt_address = ba.devtree - ba.virt_base + ba.phys_base
        assert ba.phys_base <= adt_address < adt_address + ba.devtree_size <= TOP
        assert 0 < ba.devtree_size <= 1 << 20
        tree = load_adt(interface.readmem(adt_address, ba.devtree_size))
        assert tree.model == 'Mac17,9' and tree.target_type == 'J714s'
        assert interface.readmem(BASE, 0x840) == original[:0x840]
        assert interface.readmem(BASE + FUNCTION, FUNCTION_SIZE) == original[FUNCTION:FUNCTION + FUNCTION_SIZE]
        assert interface.readmem(BASE + header_offset, 44) == original[header_offset:header_offset + 44]
        assert proxy.read64(BASE + NEXT_STAGE) == 0
        assert not any(proxy.smp_is_alive(n) for n in range(1, 18))
        note('IDENTITY_FUNCTION_HEADER_LAYOUT_VERIFIED; begin bounded read-only payload hash')
        # Verify all original payload bytes in RAM before modifying the bundle.
        digest = hashlib.sha256()
        for offset in range(header_offset, initrd_offset + len(old['initrd']), CHUNK):
            size = min(CHUNK, initrd_offset + len(old['initrd']) - offset)
            digest.update(interface.readmem(BASE + offset, size))
            if (offset + size - header_offset) % (4 << 20) == 0 or offset + size == initrd_offset + len(old['initrd']):
                note(f'PRECHECK_READ {offset + size - header_offset}')
        assert digest.hexdigest() == hashlib.sha256(original[header_offset:initrd_offset + len(old['initrd'])]).hexdigest()
        note('CURRENT_V4_PAYLOAD_RAM_HASH_VERIFIED; begin initrd-only RAM replacement')
        for offset in range(0, len(new['initrd']), CHUNK):
            chunk = new['initrd'][offset:offset + CHUNK]
            address = BASE + initrd_offset + offset
            assert BASE + initrd_offset <= address < address + len(chunk) <= BASE + initrd_offset + F['INITRD_BYTES']
            interface.writemem(address, chunk)
            assert interface.readmem(address, len(chunk)) == chunk
            if (offset + len(chunk)) % (4 << 20) == 0 or offset + len(chunk) == len(new['initrd']):
                note(f'INITRD_RAM_WRITE_READBACK {offset + len(chunk)}/{len(new["initrd"])}')
        # Publish the valid size/CRC header only after all new data is verified.
        header = image[header_offset:header_offset + 44]
        interface.writemem(BASE + header_offset, header)
        assert interface.readmem(BASE + header_offset, 44) == header
        proxy.dc_cvau(BASE + header_offset, initrd_offset + len(new['initrd']) - header_offset)
        note('RAM_FIXED_HEADER_PUBLISHED; installed SSD boot object is still bad v4')
        result = proxy.call(BASE + FUNCTION)
        note(f'ORIGINAL_STANDALONE_FUNCTION_RETURN {result}')
        assert result == 0, 'Original loader rejected corrected RAM payload; stay in proxy'
        next_stage = interface.readmem(BASE + NEXT_STAGE, 56)
        entry, dt, arg1, arg2, arg3, arg4, restore = struct.unpack('<7Q', next_stage)
        assert (entry, dt, arg1, arg2, arg3, arg4) == (0x10800000000, 0x10900000000, 0, 0, 0, 0)
        assert restore & 0xff == 0
        with (destination / 'prepared.json').open('x') as output:
            json.dump(dict(base=BASE, fixed_sha256=FIXED_SHA, persistent=False,
                           entry=entry, dt=dt, kernel_boot_observed=False), output, indent=2)
        note('NEXT_STAGE_VERIFIED; one-way proxy exit to native Linux')
        proxy.exit()
        note('HANDOFF_SENT; confirm screen and courier files; NOT a persistent fix')
    finally:
        interface.dev.close()
        log.close()
        signal.alarm(0)


if __name__ == '__main__':
    main()
