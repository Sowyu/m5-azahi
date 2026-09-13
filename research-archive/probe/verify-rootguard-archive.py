#!/usr/bin/env python3
"""Inspect the actual appended cpio, rather than only builder input files."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

root = Path(__file__).resolve().parent.parent
source = root / 'native-input-v2-20260906.bin'
candidate = root / 'native-rootguard-v1-20260906.bin'


def layout(path):
    with path.open('rb') as stream:
        head = stream.read(64 << 20)
    args = head.index(b'chosen.bootargs=')
    dt = head.index(b'\n', args) + 1
    kernel = dt + struct.unpack_from('>I', head, dt + 4)[0]
    marker = head.index(b'm1n1_initramfs', kernel)
    size_at = marker + len(b'm1n1_initramfs')
    return size_at + 4, struct.unpack_from('<I', head, size_at)[0]


_, original_size = layout(source)
start, size = layout(candidate)
assert size > original_size
with candidate.open('rb') as stream:
    stream.seek(start + original_size)
    compressed = stream.read()
assert len(compressed) == size - original_size
extra = subprocess.run(['zstd', '-dq', '-c'], input=compressed,
                       capture_output=True, check=True).stdout
pos = 0
assets = {}
links = {}
while pos < len(extra):
    header = extra[pos:pos + 110]
    assert header[:6] == b'070701'
    fields = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
    mode, uid, gid, size, name_size = fields[1], fields[2], fields[3], fields[6], fields[11]
    assert uid == gid == 0
    name = extra[pos + 110:pos + 110 + name_size - 1].decode()
    pos = (pos + 110 + name_size + 3) & ~3
    data = extra[pos:pos + size]
    pos = (pos + size + 3) & ~3
    assert not name.startswith('/') and '..' not in name.split('/')
    if name == 'TRAILER!!!':
        assert not extra[pos:].strip(b'\0')
        break
    if mode & 0o170000 == 0o100000:
        assert name not in assets
        assets[name] = hashlib.sha256(data).hexdigest()
    elif mode & 0o170000 == 0o120000:
        assert name not in links
        links[name] = data.decode()
    else:
        assert mode & 0o170000 == 0o040000
else:
    raise AssertionError('No cpio trailer')
receipt = json.loads(candidate.with_suffix('.json').read_text())
assert assets == receipt['assets']
assert links == {
    'ramroot/sysroot-overlay/etc/systemd/system/multi-user.target.wants/native-rootguard-check.service':
    '../native-rootguard-check.service',
}
print('ROOTGUARD_CPIO_ASSETS_VERIFIED', len(assets), len(links))
