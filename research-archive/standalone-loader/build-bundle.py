#!/usr/bin/env python3
"""Package the tested v3 kernel/DT/initrd, with a private autonomous loader.

Host files only. Does not install or boot anything. Refuses overwrite.
"""
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'native-ssdroot-v3-20260906.bin'
TREE = ROOT / 'standalone-loader/m1n1-20260911'
OUTPUT = ROOT / 'standalone-ssdroot-v2-20260911.bin'
SOURCE_SHA = '43d9bc1fc960acefe0161c244ce942dc0af0ec42a6a5083625fec1bdc4da82a6'
HEADER = struct.Struct('<8s9I')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect(blob, receipt):
    assert sha(blob) == receipt['image_sha256']
    offset = receipt['loader_bytes']
    assert sha(blob[:offset]) == receipt['loader_sha256']
    magic, version, *fields = HEADER.unpack_from(blob, offset)
    assert magic == b'AZAHI1\0\0' and version == 1
    lengths, crcs = fields[:4], fields[4:]
    assert 1 <= lengths[0] <= 4096 and 40 <= lengths[1] <= 65536
    assert 32 <= lengths[2] <= 32 << 20 and lengths[3] == 70698084
    pos = offset + HEADER.size
    parts = {}
    for name, length, crc in zip(('args', 'dt', 'gzip', 'initrd'), lengths, crcs):
        part = blob[pos:pos + length]
        assert len(part) == length and zlib.crc32(part) == crc
        assert sha(part) == receipt['parts'][name]['sha256']
        parts[name] = part
        pos += length
    assert pos == len(blob)
    assert parts['args'][-1:] == b'\0' and b'\0' not in parts['args'][:-1]
    assert b'maxcpus=1' in parts['args'] and b'azahi.ssd_root=1' in parts['args']
    assert b'azahi,j714s-nvme-rootguard\0' in parts['dt']
    kernel = gzip.decompress(parts['gzip'])
    assert len(kernel) == 77398016 and struct.unpack_from('<Q', kernel, 16)[0] == len(kernel)
    assert sha(kernel) == 'd2ec67ab79aea96292869f66e83c50d0fdb354d237d9787a9d6c238f0b7bffe7'
    return parts


def main():
    assert not OUTPUT.exists() and not OUTPUT.with_suffix('.json').exists()
    source = SOURCE.read_bytes()
    assert sha(source) == SOURCE_SHA
    start = source.index(b'chosen.bootargs=')
    dt_start = source.index(b'\n', start) + 1
    args = source[start + len(b'chosen.bootargs='):dt_start - 1]
    args += b' azahi.standalone=1 drm.panic_screen=qr_code\0'
    dt_len = struct.unpack_from('>I', source, dt_start + 4)[0]
    gz_start = dt_start + dt_len
    marker = source.index(b'm1n1_initramfs', gz_start)
    initrd_start = marker + len(b'm1n1_initramfs') + 4
    assert struct.unpack_from('<I', source, initrd_start - 4)[0] == len(source) - initrd_start
    parts = dict(args=args, dt=source[dt_start:gz_start],
                 gzip=source[gz_start:marker], initrd=source[initrd_start:])
    loader = (TREE / 'build/m1n1.bin').read_bytes()
    symbols = subprocess.check_output(['/opt/homebrew/opt/llvm/bin/llvm-nm', '-n',
                                       str(TREE / 'build/m1n1-raw.elf')], text=True)
    parsed = {line.split()[-1]: int(line.split()[0], 16) for line in symbols.splitlines()
              if len(line.split()) == 3 and line.split()[0][0] in '0123456789abcdef'}
    assert parsed['_base'] == 0 and parsed['_start'] == 2048
    assert parsed['_payload_start'] == len(loader)
    assert 't6050_smp_trace' not in symbols and 'smp_reset_mark' not in symbols
    header = HEADER.pack(b'AZAHI1\0\0', 1, *(len(p) for p in parts.values()),
                         *(zlib.crc32(p) for p in parts.values()))
    output = loader + header + b''.join(parts.values())
    receipt = dict(image_sha256=sha(output), image_bytes=len(output),
                   loader_sha256=sha(loader), loader_bytes=len(loader),
                   source_image=SOURCE.name, source_sha256=SOURCE_SHA,
                   parts={n: dict(bytes=len(p), sha256=sha(p)) for n, p in parts.items()},
                   raw_entry=2048, kernel_address=0x10800000000,
                   initrd_address=0x10a00000000, dt_address=0x10900000000,
                   one_cpu=True, target='J714s', installed=False,
                   source_base_commit='88a98213d55f2cbd69844762c3171b39c0cd0bf9')
    inspect(output, receipt)
    with OUTPUT.open('xb') as target:
        target.write(output)
    with OUTPUT.with_suffix('.json').open('x') as target:
        json.dump(receipt, target, indent=2)
    print('STANDALONE_BUNDLE_BUILT', len(output), receipt['image_sha256'])
    print('Loader', len(loader), receipt['loader_sha256'])
    print('Same v3 DT/kernel/initrd; RAM test and Recovery installation still pending.')


if __name__ == '__main__':
    main()
