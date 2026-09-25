#!/usr/bin/env python3
"""Build opt-in full-height v7 candidate from pinned working v6 payload.

Host files only. Never installs; preserves existing images. Kernel, initrd,
boot arguments and every DT property except the one opt-in remain unchanged.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib
if not __debug__: raise SystemExit('Refusing python -O: assert statements here are safety checks')

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'standalone-ssdroot-usb-files-v6-courier-20260913.bin'
PIN = '324822de14a43ab164d0ec6257d50d9dd6be1b17fd063faf24b0d571e41096ee'
OUT = ROOT / 'standalone-ssdroot-notch-v7-20260913.bin'
HEADER = struct.Struct('<8s9I')
OLD_LOADER_SIZE = 1114112


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parts(data, offset):
    magic, version, *fields = HEADER.unpack_from(data, offset)
    assert magic == b'AZAHI1\0\0' and version == 1
    pos = offset + HEADER.size
    result = {}
    for name, length, crc in zip(('args', 'dt', 'gzip', 'initrd'), fields[:4], fields[4:]):
        piece = data[pos:pos+length]
        assert len(piece) == length and zlib.crc32(piece) == crc
        result[name] = piece
        pos += length
    assert len(data) % 16384 == 0 and data[pos:] == bytes((-pos) % 16384)
    return result


def main():
    assert not OUT.exists() and not OUT.with_suffix('.json').exists()
    original = SOURCE.read_bytes()
    assert sha(original) == PIN
    previous = parts(original, OLD_LOADER_SIZE)
    new = dict(previous)
    with tempfile.TemporaryDirectory(prefix='azahi-notch-dt-') as td:
        dt = Path(td) / 'candidate.dtb'
        dt.write_bytes(previous['dt'])
        subprocess.run(['fdtput', '-t', 'i', str(dt), '/chosen',
                        'azahi,full-height-framebuffer', '1'], check=True)
        new['dt'] = dt.read_bytes()
        assert subprocess.check_output(['fdtget', '-t', 'i', str(dt), '/chosen',
                                        'azahi,full-height-framebuffer'], text=True).strip() == '1'
        subprocess.run(['fdtput', '-d', str(dt), '/chosen',
                        'azahi,full-height-framebuffer'], check=True)
        # Canonical textual DT equality proves no unrelated property changes.
        def canonical(blob):
            return subprocess.run(['dtc', '-q', '-s', '-I', 'dtb', '-O', 'dts'],
                                  input=blob, capture_output=True, check=True).stdout
        assert canonical(dt.read_bytes()) == canonical(previous['dt'])
    tree = ROOT / 'standalone-loader/m1n1-20260911'
    loader = (tree / 'build/m1n1.bin').read_bytes()
    symbols = subprocess.check_output(['/opt/homebrew/opt/llvm/bin/llvm-nm', '-n',
                                      str(tree / 'build/m1n1-raw.elf')], text=True)
    syms = {line.split()[-1]: int(line.split()[0], 16) for line in symbols.splitlines()
            if len(line.split()) == 3 and line.split()[0][0] in '0123456789abcdef'}
    assert syms['_base'] == 0 and syms['_start'] == 2048
    assert syms['_payload_start'] == len(loader)
    assert b'AZAHI_FULL_HEIGHT_FB:' in loader
    assert b'azahi-standalone-notch-v7-20260913' in loader
    assert len(new['initrd']) == 70698084 and len(new['dt']) <= 65536
    header = HEADER.pack(b'AZAHI1\0\0', 1, *(len(v) for v in new.values()),
                         *(zlib.crc32(v) for v in new.values()))
    data = loader + header + b''.join(new.values())
    data += bytes((-len(data)) % 16384)
    assert len(data) < 96 << 20
    decoded = parts(data, len(loader))
    assert decoded == new
    for name in ('args', 'gzip', 'initrd'):
        assert decoded[name] == previous[name]
    receipt = dict(image_sha256=sha(data), image_bytes=len(data), source_sha256=PIN,
                   loader_bytes=len(loader), loader_sha256=sha(loader), raw_entry=2048,
                   parts={n: dict(bytes=len(v), sha256=sha(v)) for n, v in new.items()},
                   expected_display='3024x1964; exact guard else cropped fallback',
                   installed=False, hardware_tested=False,
                   changes=['opt-in guarded original framebuffer geometry', 'build tag'])
    with OUT.open('xb') as target:
        target.write(data)
    with OUT.with_suffix('.json').open('x') as target:
        json.dump(receipt, target, indent=2)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
