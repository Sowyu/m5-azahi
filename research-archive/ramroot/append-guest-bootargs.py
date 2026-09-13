#!/usr/bin/env python3
"""Append guest boot arguments, byte-verifying all other payloads unchanged."""
import argparse
from pathlib import Path
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("arguments")
args = parser.parse_args()
if args.output.exists() or args.source.resolve() == args.output.resolve():
    parser.error("Specify a new output file")
if "\n" in args.arguments or "\0" in args.arguments:
    parser.error("Arguments must be a single line without NULs")
extra = b" " + args.arguments.encode()
with args.source.open("rb") as source:
    header = source.read(2 << 20)
    start = header.index(b"chosen.bootargs=")
    end = header.index(b"\n", start)
    assert header[end + 1:end + 5] == b"\xd0\x0d\xfe\xed"
    with args.output.open("xb") as output:
        output.write(header[:end])
        output.write(extra)
        source.seek(end)
        shutil.copyfileobj(source, output)
with args.source.open("rb") as source, args.output.open("rb") as output:
    assert source.read(end) == output.read(end)
    assert output.read(len(extra)) == extra
    while chunk := source.read(1 << 20):
        assert output.read(len(chunk)) == chunk
    assert not output.read(1)
print("Verified: only boot arguments changed; all other bytes preserved")
print((header[start:end] + extra).decode())
print(f"Output: {args.output} ({args.output.stat().st_size} bytes)")
