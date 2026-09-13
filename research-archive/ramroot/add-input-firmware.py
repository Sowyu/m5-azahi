#!/usr/bin/env python3
"""Append the verified J714s trackpad firmware to an existing guest initramfs."""
import argparse
import hashlib
import io
from pathlib import Path
import shutil
import struct
import subprocess
from mkcpio import Writer, ensure_parents

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
if args.output.exists() or args.source.resolve() == args.output.resolve():
    parser.error("Specify a new output file")
firmware = Path(__file__).resolve().parent / "tpmtfw-j714s.bin"
expected = "03a6d272deae424cd4a8e8ca75161079e4da11ffebc012d8b8088b35f1ad719d"
assert hashlib.sha256(firmware.read_bytes()).hexdigest() == expected
archive = io.BytesIO()
writer = Writer(archive)
seen = set()
for name in ("usr/lib/firmware/apple/tpmtfw-j714s.bin",
             "ramroot/sysroot-overlay/usr/lib/firmware/apple/tpmtfw-j714s.bin"):
    ensure_parents(writer, name, seen)
    writer.file(name, firmware)
writer.trailer()
extra = subprocess.run(["zstd", "-q", "-c"], input=archive.getvalue(), capture_output=True, check=True).stdout
with args.source.open("rb") as source:
    header = source.read(64 << 20)
    bootargs = header.index(b"chosen.bootargs=")
    dtb_start = header.index(b"\n", bootargs) + 1
    assert header[dtb_start:dtb_start + 4] == b"\xd0\x0d\xfe\xed"
    kernel_start = dtb_start + struct.unpack_from(">I", header, dtb_start + 4)[0]
    assert header[kernel_start:kernel_start + 3] == b"\x1f\x8b\x08"
    size_offset = header.index(b"m1n1_initramfs", kernel_start) + len(b"m1n1_initramfs")
    old_size = struct.unpack_from("<I", header, size_offset)[0]
    assert size_offset + 4 + old_size == args.source.stat().st_size
    assert old_size + len(extra) < 1 << 32
    with args.output.open("xb") as output:
        output.write(header[:size_offset])
        output.write(struct.pack("<I", old_size + len(extra)))
        source.seek(size_offset + 4)
        shutil.copyfileobj(source, output)
        output.write(extra)
with args.source.open("rb") as source, args.output.open("rb") as output:
    assert source.read(size_offset) == output.read(size_offset)
    source.seek(size_offset + 4)
    output.seek(size_offset + 4)
    while chunk := source.read(1 << 20):
        assert output.read(len(chunk)) == chunk
    assert output.read() == extra
print(f"Verified existing payload unchanged; appended {len(extra)} bytes of firmware archive")
print(f"Output: {args.output} ({args.output.stat().st_size} bytes)")
