#!/usr/bin/env python3
"""Build a v8 shutdown candidate: the pinned v7 image plus one SMC DT child.

Host files only. Never installs; preserves existing images. Loader, boot
arguments, kernel and initrd bytes are copied unchanged. The DT gains exactly
/soc/smc@28c600000/reboot with compatible "apple,smc-reboot" and no nvmem
cells, which is what macsmc-reboot needs to probe (it refuses a device without
an OF node). Evidence, risks and the attended test plan are in
docs/audit-2026-09-25/tooling-loader.md.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'standalone-ssdroot-notch-v7-20260913.bin'
PIN = '2eaea0bc1503c2ac74a1b11dbb88423675f324a61db3da6db1aa88392672f5ba'
OUT = ROOT / 'standalone-ssdroot-shutdown-v8-20260925.bin'
HEADER = struct.Struct('<8s9I')
NAMES = ('args', 'dt', 'gzip', 'initrd')
SMC = '/soc/smc@28c600000'
NODE = SMC + '/reboot'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parts(data, offset):
    try:
        magic, version, *fields = HEADER.unpack_from(data, offset)
    except struct.error as error:
        raise ValueError('short header') from error
    if magic != b'AZAHI1\0\0' or version != 1:
        raise ValueError('not a bundle header')
    pos = offset + HEADER.size
    result = {}
    for name, length, crc in zip(NAMES, fields[:4], fields[4:]):
        piece = data[pos:pos + length]
        if len(piece) != length or zlib.crc32(piece) != crc:
            raise ValueError('section length/CRC')
        result[name] = piece
        pos += length
    if len(data) % 16384 or data[pos:] != bytes(len(data) - pos):
        raise ValueError('padding')
    return result


def split(data):
    """Return (header offset, parts). The loader's own magic literal is skipped
    because only the real header validates every section CRC."""
    found = []
    offset = data.find(b'AZAHI1\0\0')
    while offset >= 0:
        try:
            found.append((offset, parts(data, offset)))
        except ValueError:
            pass
        offset = data.find(b'AZAHI1\0\0', offset + 1)
    if len(found) != 1:
        raise RuntimeError(f'expected exactly one valid bundle header, found {len(found)}')
    return found[0]


def canonical(blob):
    return subprocess.run(['dtc', '-q', '-s', '-I', 'dtb', '-O', 'dts'],
                          input=blob, capture_output=True, check=True).stdout


def add_reboot_node(dtb):
    with tempfile.TemporaryDirectory(prefix='azahi-shutdown-dt-') as temporary:
        dt = Path(temporary) / 'candidate.dtb'
        dt.write_bytes(dtb)

        def get(*args):
            return subprocess.run(['fdtget', str(dt), *args], capture_output=True, text=True)
        compatible = get('-t', 's', SMC, 'compatible')
        if compatible.returncode or 'apple,t8103-smc' not in compatible.stdout.split():
            raise RuntimeError('SMC node missing or unexpected compatible; refusing')
        children = get('-l', SMC).stdout.split()
        if children != ['gpio']:
            raise RuntimeError(f'unexpected SMC children {children}; refusing')
        subprocess.run(['fdtput', '-c', str(dt), NODE], check=True)
        subprocess.run(['fdtput', '-t', 's', str(dt), NODE, 'compatible', 'apple,smc-reboot'],
                       check=True)
        new = dt.read_bytes()
        # Removing the node again must give the original tree exactly.
        subprocess.run(['fdtput', '-r', str(dt), NODE], check=True)
        if canonical(dt.read_bytes()) != canonical(dtb):
            raise RuntimeError('DT changed beyond the reboot node')
    # The loader stops unless 40 <= dt_len <= 65536 and fdt_totalsize == dt_len.
    if not 40 <= len(new) <= 65536 or new[:4] != b'\xd0\x0d\xfe\xed' or \
            struct.unpack_from('>I', new, 4)[0] != len(new):
        raise RuntimeError('DT outside loader bounds')
    return new


def build(data):
    offset, previous = split(data)
    new = dict(previous, dt=add_reboot_node(previous['dt']))
    header = HEADER.pack(b'AZAHI1\0\0', 1, *(len(v) for v in new.values()),
                         *(zlib.crc32(v) for v in new.values()))
    image = data[:offset] + header + b''.join(new.values())
    image += bytes((-len(image)) % 16384)
    if split(image) != (offset, new) or image[:offset] != data[:offset]:
        raise RuntimeError('rebuilt bundle does not decode to the intended parts')
    for name in ('args', 'gzip', 'initrd'):
        if new[name] != previous[name]:
            raise RuntimeError(name + ' changed')
    return image, offset, previous, new


def main():
    if OUT.exists() or OUT.with_suffix('.json').exists():
        raise SystemExit('Refusing to overwrite an existing candidate')
    original = SOURCE.read_bytes()
    if sha(original) != PIN:
        raise SystemExit('Source is not the pinned installed v7 image')
    image, offset, previous, new = build(original)
    receipt = dict(image_sha256=sha(image), image_bytes=len(image), source_sha256=PIN,
                   loader_bytes=offset, loader_sha256=sha(original[:offset]),
                   parts={n: dict(bytes=len(v), sha256=sha(v)) for n, v in new.items()},
                   previous_dt_sha256=sha(previous['dt']),
                   changes=[f'DT: add {NODE} compatible apple,smc-reboot (no nvmem cells)'],
                   installed=False, hardware_tested=False,
                   rollback='reinstall pinned v7 ' + PIN)
    with OUT.open('xb') as target:
        target.write(image)
    with OUT.with_suffix('.json').open('x') as target:
        json.dump(receipt, target, indent=2)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
