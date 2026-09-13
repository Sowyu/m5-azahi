#!/usr/bin/env python3
"""Replace only the FDT of an existing guest image, preserving all payloads."""
import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import struct

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path)
parser.add_argument("dtb", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
if args.source.resolve() == args.output.resolve() or args.output.exists():
    parser.error("output must be a new file")
dtb = args.dtb.read_bytes()
assert dtb[:4] == b"\xd0\x0d\xfe\xed"
assert struct.unpack_from(">I", dtb, 4)[0] == len(dtb)
with args.source.open("rb") as source:
    header = source.read(64 << 20)
    bootargs = header.index(b"chosen.bootargs=")
    start = header.index(b"\n", bootargs) + 1
    assert header[start:start + 4] == b"\xd0\x0d\xfe\xed"
    old_size = struct.unpack_from(">I", header, start + 4)[0]
    tail = start + old_size
    assert header[tail:tail + 3] == b"\x1f\x8b\x08"
    initrd = header.index(b"m1n1_initramfs", tail)
    kernel = gzip.decompress(header[tail:initrd])
    expected_kernel = args.source.parent / "Image-asahi"
    if expected_kernel.exists():
        assert hashlib.sha256(kernel).digest() == hashlib.sha256(expected_kernel.read_bytes()).digest()
    with args.output.open("xb") as output:
        output.write(header[:start])
        output.write(dtb)
        source.seek(tail)
        shutil.copyfileobj(source, output)
with args.source.open("rb") as source, args.output.open("rb") as output:
    assert source.read(start) == output.read(start)
    source.seek(tail)
    output.seek(start + len(dtb))
    while chunk := source.read(1 << 20):
        assert output.read(len(chunk)) == chunk
    assert not output.read(1)
print(f"Verified: FDT {old_size} -> {len(dtb)} bytes; all other bytes unchanged")
print(f"Kernel SHA256: {hashlib.sha256(kernel).hexdigest()}")
print(f"Output: {args.output} ({args.output.stat().st_size} bytes)")
