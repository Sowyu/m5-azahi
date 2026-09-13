#!/usr/bin/env python3
"""Fetch only selected input firmware members from Apple's IPSW using HTTP ranges."""
import argparse
import io
from pathlib import Path
import urllib.request
import zipfile


class RangeReader(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.position = url, size, 0

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (0 if whence == 0 else self.position if whence == 1 else self.size)
        if self.position < 0:
            raise ValueError("negative seek")
        return self.position

    def read(self, count=-1):
        count = self.size - self.position if count < 0 else min(count, self.size - self.position)
        if count <= 0:
            return b""
        if count > 32 << 20:
            raise ValueError("Refusing a range larger than 32 MiB")
        end = self.position + count - 1
        request = urllib.request.Request(self.url, headers={"Range": f"bytes={self.position}-{end}"})
        with urllib.request.urlopen(request, timeout=30) as response:
            expected = f"bytes {self.position}-{end}/{self.size}"
            if response.status != 206 or response.headers.get("Content-Range") != expected:
                raise OSError(f"Server did not honor range {expected}: {response.status}, {response.headers}")
            data = response.read(count + 1)
        if len(data) != count:
            raise OSError("incomplete range")
        self.position += count
        return data


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("url")
parser.add_argument("size", type=int)
parser.add_argument("--member", help="Exact archive member to extract; otherwise list input firmware")
parser.add_argument("--output", type=Path)
args = parser.parse_args()
if not args.url.startswith("https://updates.cdn-apple.com/"):
    parser.error("Use Apple's HTTPS restore-image origin")
with zipfile.ZipFile(RangeReader(args.url, args.size)) as archive:
    if args.member:
        if not args.output or args.output.exists():
            parser.error("Specify a new --output file")
        member = archive.getinfo(args.member)
        if member.file_size > 32 << 20:
            parser.error("Member is too large for input firmware")
        data = archive.read(member)  # ZipFile verifies the member CRC.
        with args.output.open("xb") as output:
            output.write(data)
        print(f"Extracted and CRC-verified {args.member}: {len(data)} bytes -> {args.output}")
    else:
        for member in archive.infolist():
            name = member.filename.lower()
            if "j714" in name or "multitouch" in name or "mtfw" in name:
                print(member.file_size, member.filename)
