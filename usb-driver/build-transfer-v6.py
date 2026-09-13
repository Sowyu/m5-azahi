#!/usr/bin/env python3
"""Host-only fixed-size courier-v2 image; preserve v3/v4/v5 artifacts unchanged."""
import hashlib
import io
import json
from pathlib import Path
import runpy
import stat
import subprocess
import zlib

HERE = Path(__file__).resolve().parent
F = runpy.run_path(str(HERE / 'build-transfer-fixed.py'))
B = F['B']
ROOT = HERE.parent
OUTPUT = ROOT / 'standalone-ssdroot-usb-files-v6-courier-20260913.bin'
V5_SHA = '2af8a24f94756f38ef7dfe6056c4e6c43d9df4ede993ddcc718932160dc26b75'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def assets():
    result = B['assets']()
    result['azahi-usb-stage.sh'] = (HERE / 'boot-stage-v2.sh', 0o755)
    return result


def inspect(data, receipt):
    old, baseline = B['baseline']()
    parts = B['parts'](data)
    assert len(data) == len(old) == 92651520
    assert data[:B['LOADER_SIZE']] == old[:B['LOADER_SIZE']]
    assert len(parts['initrd']) == F['loader_length']() == 70698084
    for name in ('args', 'dt', 'gzip'):
        assert parts[name] == baseline[name]
    v5 = F['OUTPUT'].read_bytes()
    assert sha(v5) == V5_SHA
    r5 = json.loads(F['OUTPUT'].with_suffix('.json').read_text())
    packed_size = r5['recompressed_original_bytes']
    assert receipt['recompressed_original_bytes'] == packed_size
    assert parts['initrd'][:packed_size] == B['parts'](v5)['initrd'][:packed_size]
    original = B['C']['unpack'](baseline['initrd'])
    assert B['C']['unpack'](parts['initrd'][:packed_size]) == original
    assert sha(original) == receipt['original_cpio_sha256']
    extra_size = receipt['extra_bytes']
    assert 0 < extra_size < 1 << 20
    assert packed_size + extra_size < F['INITRD_BYTES']
    extra = parts['initrd'][packed_size:packed_size + extra_size]
    assert sha(extra) == receipt['extra_sha256']
    assert not any(parts['initrd'][packed_size + extra_size:])
    entries = list(B['C']['entries'](B['C']['unpack'](extra)))
    assert len({n for n, _, _ in entries}) == len(entries)
    files = {n: (m, d) for n, m, d in entries if not stat.S_ISDIR(m)}
    expected = assets()
    assert files.keys() == expected.keys()
    for name, (path, mode) in expected.items():
        assert files[name] == (stat.S_IFREG | mode, path.read_bytes())
    old_files = {n: (m, d) for n, m, d in B['C']['entries'](original)}
    for name, mode, _ in entries:
        if name in old_files:
            assert stat.S_ISDIR(mode) and old_files[name][0] == mode
    assert receipt['assets'] == {n: sha(p.read_bytes()) for n, (p, _) in expected.items()}
    assert receipt['image_sha256'] == sha(data)
    assert receipt['image_bytes'] == len(data)
    assert receipt['installed'] is False and receipt['driver_auto_load'] is False
    return parts


def build():
    old, baseline = B['baseline']()
    v5 = F['OUTPUT'].read_bytes()
    assert sha(v5) == V5_SHA
    r5 = json.loads(F['OUTPUT'].with_suffix('.json').read_text())
    p5 = F['inspect'](v5, r5)
    packed = p5['initrd'][:r5['recompressed_original_bytes']]
    archive = io.BytesIO()
    writer = B['W']['Writer'](archive)
    seen = set()
    for name, (path, mode) in assets().items():
        B['W']['ensure_parents'](writer, name, seen)
        writer.file(name, path, mode)
    writer.trailer()
    extra = subprocess.run(['zstd', '-q', '-c'], input=archive.getvalue(), capture_output=True, check=True).stdout
    assert len(packed) + len(extra) < F['INITRD_BYTES']
    parts = dict(baseline)
    parts['initrd'] = packed + extra + bytes(F['INITRD_BYTES'] - len(packed) - len(extra))
    header = B['HEADER'].pack(b'AZAHI1\0\0', 1, *(len(p) for p in parts.values()),
                              *(zlib.crc32(p) for p in parts.values()))
    data = old[:B['LOADER_SIZE']] + header + b''.join(parts.values())
    data += bytes((-len(data)) % 16384)
    receipt = dict(image_sha256=sha(data), image_bytes=len(data),
                   base_sha256=B['BASE_SHA'], previous_v5_sha256=V5_SHA,
                   recompressed_original_bytes=len(packed), extra_bytes=len(extra),
                   original_cpio_sha256=r5['original_cpio_sha256'], extra_sha256=sha(extra),
                   assets={n: sha(p.read_bytes()) for n, (p, _) in assets().items()},
                   installed=False, driver_auto_load=False,
                   correction='Courier v2: explicit BusyBox utilities with empty PATH; exact initrd size preserved')
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
