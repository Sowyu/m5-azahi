#!/usr/bin/env python3
"""Correct v4's initrd-size incompatibility without changing loader code.

Recompress the exact original cpio bytes, append the same courier archive,
then pad the initrd back to the loader's exact 70698084-byte requirement.
Host-only. Original v3/v4 files are preserved; new output is exclusive.
"""
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
import zlib
if not __debug__: raise SystemExit('Refusing python -O: assert statements here are safety checks')

HERE = Path(__file__).resolve().parent
B = runpy.run_path(str(HERE / 'build-transfer.py'))
ROOT = HERE.parent
OUTPUT = ROOT / 'standalone-ssdroot-usb-files-v5-fixed-20260913.bin'
SOURCE = ROOT / 'standalone-ssdroot-usb-files-v4-20260913.bin'
SOURCE_SHA = '0ca32c0df14ce714d32029ede06a428722616da0711fc5d0b85a98f1a77d77d0'
INITRD_BYTES = 70698084


def sha(data):
    return hashlib.sha256(data).hexdigest()


def loader_length():
    source = (ROOT / 'standalone-loader/m1n1-20260911/src/azahi_standalone.c').read_text()
    return int(re.search(r'^#define INITRD_BYTES (\d+)U$', source, re.M)[1])


def inspect(data, receipt):
    old, baseline = B['baseline']()
    new = B['parts'](data)
    assert loader_length() == INITRD_BYTES == len(new['initrd'])
    assert data[:B['LOADER_SIZE']] == old[:B['LOADER_SIZE']]
    for name in ('args', 'dt', 'gzip'):
        assert new[name] == baseline[name], name
    packed_size = receipt['recompressed_original_bytes']
    extra_size = receipt['extra_bytes']
    assert 0 < packed_size < INITRD_BYTES and 0 < extra_size < 8 << 20
    assert packed_size + extra_size < INITRD_BYTES
    compressed = new['initrd'][:packed_size]
    extra = new['initrd'][packed_size:packed_size + extra_size]
    assert new['initrd'][packed_size + extra_size:] == bytes(INITRD_BYTES - packed_size - extra_size)
    original_cpio = B['C']['unpack'](baseline['initrd'])
    assert B['C']['unpack'](compressed) == original_cpio
    # Every original newc header, file, ownership and order is byte-identical.
    assert receipt['original_cpio_sha256'] == sha(original_cpio)
    v4 = SOURCE.read_bytes()
    assert sha(v4) == SOURCE_SHA
    v4parts = B['parts'](v4)
    assert extra == v4parts['initrd'][INITRD_BYTES:]
    assert receipt['extra_sha256'] == sha(extra)
    assert receipt['image_sha256'] == sha(data) and receipt['image_bytes'] == len(data)
    assert len(data) == len(old) == 92651520
    assert receipt['driver_auto_load'] is False and receipt['installed'] is False
    assert receipt['base_sha256'] == B['BASE_SHA']
    return new


def build():
    assert loader_length() == INITRD_BYTES
    old, baseline = B['baseline']()
    v4 = SOURCE.read_bytes()
    assert sha(v4) == SOURCE_SHA
    # Validate every courier asset against the preserved v4 receipt before reuse.
    v4parts = B['inspect'](v4, json.loads(SOURCE.with_suffix('.json').read_text()))
    extra = v4parts['initrd'][INITRD_BYTES:]
    original_cpio = B['C']['unpack'](baseline['initrd'])
    packed = subprocess.run(['zstd', '-19', '-q', '-c'], input=original_cpio,
                            capture_output=True, check=True).stdout
    print('INITRD_COMPRESSION', len(original_cpio), len(packed), len(extra), flush=True)
    assert len(packed) + len(extra) < INITRD_BYTES, 'Compression insufficient; no output written'
    new = dict(baseline)
    new['initrd'] = packed + extra + bytes(INITRD_BYTES - len(packed) - len(extra))
    header = B['HEADER'].pack(b'AZAHI1\0\0', 1, *(len(p) for p in new.values()),
                              *(zlib.crc32(p) for p in new.values()))
    data = old[:B['LOADER_SIZE']] + header + b''.join(new.values())
    data += bytes((-len(data)) % 16384)
    receipt = dict(image_sha256=sha(data), image_bytes=len(data), base_sha256=B['BASE_SHA'],
                   original_cpio_sha256=sha(original_cpio), recompressed_original_bytes=len(packed),
                   extra_bytes=len(extra), extra_sha256=sha(extra), initrd_bytes=INITRD_BYTES,
                   installed=False, driver_auto_load=False,
                   correction='Preserve loader exact initrd size; recompress only, preserve all cpio bytes')
    inspect(data, receipt)
    return data, receipt


if __name__ == '__main__':
    assert not OUTPUT.exists() and not OUTPUT.with_suffix('.json').exists()
    data, receipt = build()
    with OUTPUT.open('xb') as stream:
        stream.write(data)
    with OUTPUT.with_suffix('.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps(receipt, indent=2))
