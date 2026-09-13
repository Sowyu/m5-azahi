#!/usr/bin/env python3
"""Append the local input module at the existing module-index path in RAM only."""
import argparse
import hashlib
import io
import lzma
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from mkcpio import Writer, ensure_parents

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("source", type=Path)
p.add_argument("module", type=Path)
p.add_argument("output", type=Path)
a = p.parse_args()
if a.output.exists() or a.source.resolve() == a.output.resolve():
    p.error("Specify a new output file")
module = a.module.read_bytes()
release = "7.0.13-400.asahi.fc44.aarch64+16k"
assert module[:4] == b"\x7fELF"
assert struct.unpack_from("<H", module, 18)[0] == 183
assert ("vermagic=" + release + " SMP preempt mod_unload aarch64").encode() in module
assert b"AZAHI_V2_POWER" in module
compressed = lzma.compress(module, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC32)
archive = io.BytesIO()
w = Writer(archive)
seen = set()
path = f"usr/lib/modules/{release}/kernel/drivers/hid/dockchannel-hid/dockchannel-hid.ko.xz"
with tempfile.TemporaryDirectory(prefix="azahi-input-module-") as temporary:
    packed = Path(temporary) / "dockchannel-hid.ko.xz"
    packed.write_bytes(compressed)
    for name in (path, "ramroot/sysroot-overlay/" + path):
        ensure_parents(w, name, seen)
        w.file(name, packed)
w.trailer()
extra = subprocess.run(["zstd", "-q", "-c"], input=archive.getvalue(), capture_output=True, check=True).stdout
with a.source.open("rb") as source:
    head = source.read(64 << 20)
    dtb = head.index(b"\n", head.index(b"chosen.bootargs=")) + 1
    assert head[dtb:dtb+4] == b"\xd0\x0d\xfe\xed"
    kernel = dtb + struct.unpack_from(">I", head, dtb+4)[0]
    offset = head.index(b"m1n1_initramfs", kernel) + len(b"m1n1_initramfs")
    size = struct.unpack_from("<I", head, offset)[0]
    assert offset + 4 + size == a.source.stat().st_size
    assert size + len(extra) < 1 << 32
    with a.output.open("xb") as output:
        output.write(head[:offset])
        output.write(struct.pack("<I", size + len(extra)))
        source.seek(offset + 4)
        shutil.copyfileobj(source, output)
        output.write(extra)
with a.source.open("rb") as source, a.output.open("rb") as output:
    assert source.read(offset) == output.read(offset)
    source.seek(offset + 4)
    output.seek(offset + 4)
    while chunk := source.read(1 << 20):
        assert output.read(len(chunk)) == chunk
    assert output.read() == extra
print("Module SHA256:", hashlib.sha256(module).hexdigest())
print(f"Verified prior kernel/FDT/initramfs bytes unchanged; appended {len(extra)} bytes")
print(f"Output: {a.output} ({a.output.stat().st_size} bytes)")
