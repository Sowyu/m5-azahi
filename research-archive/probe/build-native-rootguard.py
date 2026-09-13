#!/usr/bin/env python3
"""Build a RAM diagnostic with root-only write filter and bounded padding test.

Does not change/install any target boot object. Existing RO payload untouched.
"""
import hashlib
import importlib.util
import io
import json
import lzma
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'native-input-v2-20260906.bin'
OUTPUT = ROOT / 'native-rootguard-v1-20260906.bin'
MANIFEST = OUTPUT.with_suffix('.json')
RELEASE = '7.0.13-400.asahi.fc44.aarch64+16k'
MODULES = {
    'nvme-apple': ('build-rootguard', 'nvme/host', '696d0fded6a47bb9929e1f49b1a38d166d6c539e573696c3c206b84c13c6708c'),
    'apple-sart': ('build', 'soc/apple', '58ba58e4a6dd0b4574751d224772d9bfe447fa3f4e8bdba8cfa9e7c52b80305d'),
}


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    assert not OUTPUT.exists() and not MANIFEST.exists(), 'Refuse to overwrite candidate'
    assert digest(SOURCE) == '538512bd3cb93e53b595dd224719e7a396b7990c51b2b10e916dff738ca4be12'
    archive = ROOT / 'logs/recovery-root-install-20260906.cILw73/after/backup.tar.gz'
    assert digest(archive) == 'e98e09c7d47757379a0456020b6bcdf106e1d9b47ae95459a58d5417906dd9a1'
    regions = []
    with tarfile.open(archive) as report:
        for name, offset, size in (('gpt-primary.bin', 0, 24576),
                                   ('gpt-backup.bin', 1000555581440 - 20480, 20480)):
            data = report.extractfile(name).read()
            if name == 'gpt-backup.bin':
                assert len(data) == 24576
                # Collector also included Recovery's final data LBA. Do not
                # pin filesystem bytes that Apple's boot may legitimately change.
                data = data[-20480:]
            assert len(data) == size, (name, len(data))
            regions.append(dict(name=name, offset=offset, bytes=size, sha256=hashlib.sha256(data).hexdigest()))
    with (ROOT / 'ramroot/work-kde/root.img').open('rb') as source:
        prefix = source.read(16 << 20)
    spec = importlib.util.spec_from_file_location('rootguard_test', ROOT / 'probe/native-rootguard-test.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.check_superblock(prefix)
    regions.append(dict(name='root-prefix', offset=835723767808, bytes=len(prefix),
                        sha256=hashlib.sha256(prefix).hexdigest()))
    subprocess.run(['clang', '-E', '-P', '-x', 'assembler-with-cpp', '-I', str(ROOT),
                    str(ROOT / 't6050-j714s-native-rootguard.dts'), '-o',
                    str(ROOT / 'nvme-driver/build-rootguard/native-rootguard.pre.dts')], check=True)
    subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(ROOT / 't6050-j714s-native-rootguard.dtb'),
                    str(ROOT / 'nvme-driver/build-rootguard/native-rootguard.pre.dts')], check=True)
    dtb = (ROOT / 't6050-j714s-native-rootguard.dtb').read_bytes()
    assert b'azahi,j714s-nvme-rootguard\0' in dtb and b'azahi,j714s-nvme-readonly\0' not in dtb
    sys.path.insert(0, str(ROOT / 'ramroot'))
    from mkcpio import Writer, ensure_parents
    buffer = io.BytesIO()
    writer = Writer(buffer)
    seen = set()
    asset_hashes = {}

    def add(name, path):
        ensure_parents(writer, name, seen)
        writer.file(name, path)
        asset_hashes[name] = digest(path)

    with tempfile.TemporaryDirectory(prefix='azahi-rootguard-build-') as temporary:
        temp = Path(temporary)
        for name, (directory, subpath, expected) in MODULES.items():
            path = ROOT / 'nvme-driver' / directory / (name + '.ko')
            assert digest(path) == expected
            data = path.read_bytes()
            assert data[:4] == b'\x7fELF' and struct.unpack_from('<H', data, 18)[0] == 183
            assert ('vermagic=' + RELEASE + ' SMP preempt mod_unload aarch64').encode() in data
            if name == 'nvme-apple':
                assert b'azahi,j714s-nvme-rootguard' in data and b'azahi,j714s-nvme-readonly' not in data
                assert b'root_write_armed' in data
            packed = temp / (name + '.ko.xz')
            packed.write_bytes(lzma.compress(data, check=lzma.CHECK_CRC32))
            target = f'usr/lib/modules/{RELEASE}/kernel/drivers/{subpath}/{name}.ko.xz'
            for prefix_path in ('', 'ramroot/sysroot-overlay/'):
                add(prefix_path + target, packed)
        for target, local in (
            ('root/.bash_profile', 'native-rootguard-profile.sh'),
            ('usr/local/bin/native-rootguard-check', 'native-rootguard-check.sh'),
            ('usr/local/libexec/native-rootguard-test.py', 'native-rootguard-test.py'),
            ('usr/local/libexec/probe-ssd-readonly.py', 'probe-ssd-readonly.py'),
            ('etc/systemd/system/native-rootguard-check.service', 'native-rootguard-check.service'),
        ):
            add('ramroot/sysroot-overlay/' + target, ROOT / 'probe' / local)
        region_file = temp / 'regions.json'
        region_file.write_text(json.dumps(dict(regions=regions), indent=2) + '\n')
        add('ramroot/sysroot-overlay/usr/local/libexec/native-rootguard-regions.json', region_file)
        link = 'ramroot/sysroot-overlay/etc/systemd/system/multi-user.target.wants/native-rootguard-check.service'
        ensure_parents(writer, link, seen)
        writer.symlink(link, '../native-rootguard-check.service')
        writer.trailer()
    extra = subprocess.run(['zstd', '-q', '-c'], input=buffer.getvalue(), capture_output=True, check=True).stdout
    with SOURCE.open('rb') as source:
        head = source.read(64 << 20)
        args_start = head.index(b'chosen.bootargs=')
        dt_start = head.index(b'\n', args_start) + 1
        kernel_start = dt_start + struct.unpack_from('>I', head, dt_start + 4)[0]
        marker = head.index(b'm1n1_initramfs', kernel_start)
        initrd_start = marker + len(b'm1n1_initramfs') + 4
        size = struct.unpack_from('<I', head, initrd_start - 4)[0]
        assert initrd_start + size == SOURCE.stat().st_size
        bootargs = head[args_start:dt_start - 1] + (
            b' systemd.mask=home.mount systemd.mask=systemd-repart.service'
            b' systemd.mask=systemd-repart.socket azahi.native_rootguard_test=1')
        header = head[:args_start] + bootargs + b'\n' + dtb + head[kernel_start:marker]
        header += b'm1n1_initramfs' + struct.pack('<I', size + len(extra))
        with OUTPUT.open('xb') as dest:
            dest.write(header)
            source.seek(initrd_start)
            shutil.copyfileobj(source, dest)
            dest.write(extra)
    with SOURCE.open('rb') as source, OUTPUT.open('rb') as dest:
        source.seek(initrd_start)
        dest.seek(len(header))
        while data := source.read(1 << 20):
            assert dest.read(len(data)) == data
        assert dest.read() == extra
    receipt = dict(image_sha256=digest(OUTPUT), dtb_sha256=hashlib.sha256(dtb).hexdigest(),
                   modules={name: spec[2] for name, spec in MODULES.items()}, assets=asset_hashes,
                   rootguard=True, write_test_only=True, base_initrd_unchanged=True,
                   test=dict(partuuid=module.ROOT_UUID, offset=module.TEST_OFFSET, bytes=module.TEST_BYTES),
                   regions=regions)
    with MANIFEST.open('x') as dest:
        json.dump(receipt, dest, indent=2)
    print('NATIVE_ROOTGUARD_BUILT', OUTPUT.stat().st_size, json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
