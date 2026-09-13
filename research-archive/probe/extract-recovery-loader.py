#!/usr/bin/env python3
"""Extract the verified original raw loader; never overwrite an artifact."""
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parent.parent / 'logs/recovery-backup-20260906.eTn0av'
blob = (root / 'custom-01.bin').read_bytes()
assert hashlib.sha256(blob).hexdigest() == 'fed0eb4d7ea1eaf6ba10d0487840bb59f4940edcc986b029b3b5753630bf7e31'


def items(data):
    cursor = 0
    result = []
    while cursor < len(data):
        tag = data[cursor]
        cursor += 1
        if tag & 31 == 31:
            while data[cursor] & 128:
                cursor += 1
            cursor += 1
        length = data[cursor]
        cursor += 1
        if length & 128:
            count = length & 127
            assert 0 < count <= 4
            length = int.from_bytes(data[cursor:cursor + count], 'big')
            cursor += count
        assert cursor + length <= len(data)
        result.append((tag, data[cursor:cursor + length]))
        cursor += length
    return result


outer = items(blob)
assert len(outer) == 1 and outer[0][0] == 0x30
image4 = items(outer[0][1])
assert image4[0] == (0x16, b'IMG4') and image4[1][0] == 0x30
im4p = items(image4[1][1])
assert im4p[:2] == [(0x16, b'IM4P'), (0x16, b'fuos')]
assert im4p[3][0] == 4 and im4p[4][0] == 0xa0
payload = im4p[3][1]
assert len(payload) == 1114112
assert hashlib.sha256(payload).hexdigest() == 'f2f234d99be7bdd0181366ec16c055ac14bdfa48cb2774c238836462521d2505'
payp = items(items(im4p[4][1])[0][1])
assert payp[0] == (0x16, b'PAYP')
properties = {}
for _, entry in items(payp[1][1]):
    fields = items(items(entry)[0][1])
    assert fields[0][0] == 0x16 and fields[1][0] == 2
    properties[fields[0][1].decode()] = int.from_bytes(fields[1][1], 'big')
assert properties == dict(kcep=2048, kclf=1114112, kclo=0, kclz=0,
                         kcrf=0, kcrz=0, kcwf=0, kcwz=1114112)
output = root / 'original-loader.bin'
with output.open('xb') as handle:
    handle.write(payload)
print('ORIGINAL_LOADER_EXTRACTED', output)
print('RAW_PROPERTIES', properties)
print('SHA256', hashlib.sha256(payload).hexdigest())
