#!/usr/bin/env python3
"""Host-only transfer boot bundle: preserve all baseline bytes, append initrd files.

No target access, enrollment or source-tree rebuild. Exclusive new outputs.
"""
import hashlib
import io
import json
from pathlib import Path
import runpy
import stat
import struct
import subprocess
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / 'standalone-ssdroot-v3-aligned-20260912.bin'
BASE_SHA = '397a0e4125087c63b83c09b35cd44fe6bc35508d7d54613bd9a2bf4d9aff46fc'
OUTPUT = ROOT / 'standalone-ssdroot-usb-files-v4-20260913.bin'
HEADER = struct.Struct('<8s9I')
LOADER_SIZE = 1114112
FILES = ('phy-apple-t6050-usb2.ko', 'dwc3-apple-t6050.ko',
         'azahi-usb-overlay.ko', 'usb-tether-test.sh', 'SHA256SUMS')
PINS = dict(zip(FILES, (
    'c54ffb8d82f966c5a907898e09e0d53fec42904493e42a45999791586f3e0b12',
    '24b80b4e23f9a0065547df170ca7e6016e93ac7f17a3b47a2b8757636be045ce',
    'bf9a5c1804f7c37db022d5db46a6f2dd75d4d6490b294e7388271fcd693903b1',
    '2d0296c61058fdc252f7192c5eefa0eb3c4121643652078f16b623ad9fd2dd58',
)))
A = runpy.run_path(str(ROOT / 'standalone-loader/build-aligned.py'))
C = runpy.run_path(str(ROOT / 'probe/build-native-ssdroot.py'))
W = runpy.run_path(str(ROOT / 'ramroot/mkcpio.py'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parts(data):
    magic, version, *fields = HEADER.unpack_from(data, LOADER_SIZE)
    assert magic == b'AZAHI1\0\0' and version == 1
    position = LOADER_SIZE + HEADER.size
    result = {}
    for name, length, crc in zip(('args', 'dt', 'gzip', 'initrd'), fields[:4], fields[4:]):
        value = data[position:position + length]
        assert len(value) == length and zlib.crc32(value) == crc
        result[name] = value
        position += length
    assert len(data) % 16384 == 0
    assert data[position:] == bytes((-position) % 16384)
    return result


def baseline():
    data = BASE.read_bytes()
    assert sha(data) == BASE_SHA
    A['inspect'](data, json.loads(BASE.with_suffix('.json').read_text()))
    return data, parts(data)


def assets():
    result = {}
    for name in FILES:
        path = HERE / 'deliver' / name
        if name in PINS:
            assert sha(path.read_bytes()) == PINS[name], name
        result['azahi-usb-20260913/' + name] = (path, 0o644)
    expected_manifest = ''.join(f'{PINS[name]}  {name}\n' for name in FILES[:-1]).encode()
    assert (HERE / 'deliver/SHA256SUMS').read_bytes() == expected_manifest
    result['azahi-usb-stage.sh'] = (HERE / 'boot-stage.sh', 0o755)
    result['etc/systemd/system/initrd-switch-root.service.d/usb-files.conf'] = (HERE / 'boot-stage.conf', 0o644)
    return result


def inspect(data, receipt):
    old, original = baseline()
    new = parts(data)
    assert data[:LOADER_SIZE] == old[:LOADER_SIZE]
    for name in ('args', 'dt', 'gzip'):
        assert new[name] == original[name], name
    assert new['initrd'].startswith(original['initrd'])
    extra = new['initrd'][len(original['initrd']):]
    assert 0 < len(extra) < 8 << 20
    contents = list(C['entries'](C['unpack'](extra)))
    assert len(contents) == len({name for name, _, _ in contents})
    files = {name: (mode, payload) for name, mode, payload in contents if not stat.S_ISDIR(mode)}
    expected = assets()
    assert files.keys() == expected.keys()
    for name, (path, mode) in expected.items():
        assert files[name] == (stat.S_IFREG | mode, path.read_bytes()), name
    # The only overlaps with the old cpio are benign existing parent directories.
    old_assets = {name: (mode, payload) for name, mode, payload in C['entries'](C['unpack'](original['initrd']))}
    for name, mode, _ in contents:
        if name in old_assets:
            assert stat.S_ISDIR(mode) and old_assets[name][0] == mode, name
    assert len(data) < 96 << 20
    assert receipt['image_sha256'] == sha(data) and receipt['image_bytes'] == len(data)
    assert receipt['base_sha256'] == BASE_SHA
    assert receipt['initrd_original_bytes'] == len(original['initrd'])
    assert receipt['extra_sha256'] == sha(extra)
    assert receipt['assets'] == {name: sha(path.read_bytes()) for name, (path, _) in expected.items()}
    assert receipt['installed'] is False and receipt['driver_auto_load'] is False
    return new


def build():
    old, original = baseline()
    archive = io.BytesIO()
    writer = W['Writer'](archive)
    seen = set()
    selected = assets()
    for name, (path, mode) in selected.items():
        W['ensure_parents'](writer, name, seen)
        writer.file(name, path, mode)
    writer.trailer()
    extra = subprocess.run(['zstd', '-q', '-c'], input=archive.getvalue(), capture_output=True, check=True).stdout
    new = dict(original)
    new['initrd'] += extra
    header = HEADER.pack(b'AZAHI1\0\0', 1, *(len(p) for p in new.values()),
                         *(zlib.crc32(p) for p in new.values()))
    data = old[:LOADER_SIZE] + header + b''.join(new.values())
    data += bytes((-len(data)) % 16384)
    receipt = dict(image_sha256=sha(data), image_bytes=len(data), base_sha256=BASE_SHA,
                   initrd_original_bytes=len(original['initrd']), extra_sha256=sha(extra),
                   assets={name: sha(path.read_bytes()) for name, (path, _) in selected.items()},
                   installed=False, driver_auto_load=False, raw_entry=2048,
                   unchanged=['loader', 'args', 'dt', 'kernel', 'original initrd'],
                   runtime_files='/run/azahi-usb-20260913')
    inspect(data, receipt)
    return data, receipt


if __name__ == '__main__':
    assert not OUTPUT.exists() and not OUTPUT.with_suffix('.json').exists()
    image, report = build()
    with OUTPUT.open('xb') as stream:
        stream.write(image)
    with OUTPUT.with_suffix('.json').open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report, indent=2))
