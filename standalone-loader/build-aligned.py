#!/usr/bin/env python3
"""Host-only v3 packaging: exact RAM-tested v2 plus 16 KiB zero padding.

No recompilation, target access or installation. Refuses overwrite.
Alignment is supported by T6040 cold-boot evidence, not yet proven on T6050.
"""
import hashlib
import json
from pathlib import Path
import runpy
if not __debug__: raise SystemExit('Refusing python -O: assert statements here are safety checks')

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
B = runpy.run_path(str(HERE / 'build-bundle.py'))
SOURCE = ROOT / 'standalone-ssdroot-v2-20260911.bin'
SOURCE_SHA = '866aea9d523152f0a0767cb7529be297f52ad4e64d94a70d0fe5bddf222a5a2a'
OUTPUT = ROOT / 'standalone-ssdroot-v3-aligned-20260912.bin'
PAGE = 16384


def inspect(data, receipt):
    size = 92651350
    assert len(data) == 92651520 and len(data) % PAGE == 0
    assert hashlib.sha256(data[:size]).hexdigest() == SOURCE_SHA
    assert data[size:] == bytes(170)
    assert receipt['image_bytes'] == len(data)
    assert receipt['image_sha256'] == hashlib.sha256(data).hexdigest()
    assert receipt['padding_bytes'] == 170 and receipt['page_bytes'] == PAGE
    assert receipt['source_sha256'] == SOURCE_SHA
    B['inspect'](data[:size], receipt['source_receipt'])


def main():
    assert not OUTPUT.exists() and not OUTPUT.with_suffix('.json').exists()
    source = SOURCE.read_bytes()
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA
    old = json.loads(SOURCE.with_suffix('.json').read_text())
    B['inspect'](source, old)
    data = source + bytes((-len(source)) % PAGE)
    receipt = dict(image_bytes=len(data), image_sha256=hashlib.sha256(data).hexdigest(),
                   source_sha256=SOURCE_SHA, source_receipt=old,
                   padding_bytes=len(data) - len(source), page_bytes=PAGE,
                   raw_entry=2048, one_cpu=True, installed=False,
                   cold_boot_verified=False, change='Append zero padding only')
    inspect(data, receipt)
    with OUTPUT.open('xb') as stream:
        stream.write(data)
    with OUTPUT.with_suffix('.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'source_receipt'}, indent=2))


if __name__ == '__main__':
    main()
