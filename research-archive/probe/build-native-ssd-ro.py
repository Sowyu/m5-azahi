#!/usr/bin/env python3
"""Append diagnostic modules/services to the proven native input RAM payload."""
from pathlib import Path
import hashlib
import io
import json
import lzma
import shutil
import struct
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
source = root / 'native-input-v2-20260906.bin'
output = root / 'native-ssd-ro-v3-20260906.bin'
manifest = output.with_suffix('.json')
assert not output.exists() and not manifest.exists()
with source.open('rb') as f:
    assert hashlib.file_digest(f, 'sha256').hexdigest() == '538512bd3cb93e53b595dd224719e7a396b7990c51b2b10e916dff738ca4be12'
subprocess.run(['clang', '-E', '-P', '-x', 'assembler-with-cpp', '-I', str(root),
                str(root / 't6050-j714s-native-ssd-ro.dts'),
                '-o', str(root / 'nvme-driver/build/native-ssd-ro.pre.dts')], check=True)
subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(root / 't6050-j714s-native-ssd-ro.dtb'),
                str(root / 'nvme-driver/build/native-ssd-ro.pre.dts')], check=True)
dtb = (root / 't6050-j714s-native-ssd-ro.dtb').read_bytes()
assert b'azahi,j714s-nvme-readonly\0' in dtb and b'azahi,j714s-sart-v4\0' in dtb
sys.path.insert(0, str(root / 'ramroot'))
from mkcpio import Writer, ensure_parents
wbuffer = io.BytesIO()
w = Writer(wbuffer)
seen = set()
release = '7.0.13-400.asahi.fc44.aarch64+16k'
module_hashes = {}
with tempfile.TemporaryDirectory(prefix='azahi-native-ssd-') as temp:
    for module, subpath in (('nvme-apple', 'nvme/host'), ('apple-sart', 'soc/apple')):
        blob = (root / f'nvme-driver/build/{module}.ko').read_bytes()
        assert blob[:4] == b'\x7fELF' and struct.unpack_from('<H', blob, 18)[0] == 183
        assert ('vermagic=' + release + ' SMP preempt mod_unload aarch64').encode() in blob
        module_hashes[module] = hashlib.sha256(blob).hexdigest()
        packed = Path(temp) / (module + '.ko.xz')
        packed.write_bytes(lzma.compress(blob, check=lzma.CHECK_CRC32))
        path = f'usr/lib/modules/{release}/kernel/drivers/{subpath}/{module}.ko.xz'
        for prefix in ('', 'ramroot/sysroot-overlay/'):
            name = prefix + path
            ensure_parents(w, name, seen)
            w.file(name, packed)
    for name, local in (
        ('root/.bash_profile', 'native-ssd-ro-profile.sh'),
        ('usr/local/bin/native-ssd-ro-check', 'native-ssd-ro-check.sh'),
        ('usr/local/libexec/probe-ssd-readonly.py', 'probe-ssd-readonly.py'),
        ('usr/local/libexec/verify-ssd-reads.py', 'verify-ssd-reads.py'),
        ('etc/systemd/system/native-ssd-ro-check.service', 'native-ssd-ro-check.service'),
    ):
        name = 'ramroot/sysroot-overlay/' + name
        ensure_parents(w, name, seen)
        w.file(name, root / 'probe' / local)
    name = 'ramroot/sysroot-overlay/etc/systemd/system/multi-user.target.wants/native-ssd-ro-check.service'
    ensure_parents(w, name, seen)
    w.symlink(name, '../native-ssd-ro-check.service')
    w.trailer()
extra = subprocess.run(['zstd', '-q', '-c'], input=wbuffer.getvalue(), capture_output=True, check=True).stdout
with source.open('rb') as f:
    head = f.read(64 << 20)
    arg_start = head.index(b'chosen.bootargs=')
    dt_start = head.index(b'\n', arg_start) + 1
    kernel_start = dt_start + struct.unpack_from('>I', head, dt_start + 4)[0]
    marker = head.index(b'm1n1_initramfs', kernel_start)
    initrd_start = marker + len(b'm1n1_initramfs') + 4
    size = struct.unpack_from('<I', head, initrd_start - 4)[0]
    assert initrd_start + size == source.stat().st_size
    bootargs = head[arg_start:dt_start-1] + (
        b' systemd.mask=home.mount systemd.mask=systemd-repart.service'
        b' systemd.mask=systemd-repart.socket azahi.native_ssd_ro=1')
    header = (head[:arg_start] + bootargs + b'\n' + dtb + head[kernel_start:marker]
              + b'm1n1_initramfs' + struct.pack('<I', size + len(extra)))
    with output.open('xb') as dest:
        dest.write(header)
        f.seek(initrd_start)
        shutil.copyfileobj(f, dest)
        dest.write(extra)
with source.open('rb') as f, output.open('rb') as dest:
    f.seek(initrd_start)
    dest.seek(len(header))
    while data := f.read(1 << 20):
        assert dest.read(len(data)) == data
    assert dest.read() == extra
with output.open('rb') as f:
    digest = hashlib.file_digest(f, 'sha256').hexdigest()
receipt = dict(image_sha256=digest, dtb_sha256=hashlib.sha256(dtb).hexdigest(),
               modules=module_hashes, readonly=True, base_initrd_unchanged=True)
with manifest.open('x') as f:
    json.dump(receipt, f, indent=2)
print('NATIVE_SSD_RO_BUILT', output.stat().st_size, json.dumps(receipt))
