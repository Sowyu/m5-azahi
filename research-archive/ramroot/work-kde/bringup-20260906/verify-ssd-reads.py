#!/usr/bin/env python3
"""Bounded direct-read consistency test; refuses writable/non-NVMe devices.

No mount, filesystem repair, write-capable descriptor, or disk-data output.
Run only after the read-only discovery probe has identified the device.
"""
import hashlib
import mmap
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time

if len(sys.argv) != 2 or not re.fullmatch(r"/dev/nvme0n[1-3](?:p[1-9][0-9]*)?", sys.argv[1]):
    raise SystemExit("Usage: verify-ssd-reads.py /dev/nvme0nN[pN]")
device = Path(sys.argv[1])
node = Path("/sys/class/block", device.name)
parent = re.sub(r"p[0-9]+$", "", device.name)
if (Path("/sys/class/block", parent) / "ro").read_text().strip() != "1":
    raise SystemExit("Parent namespace is not read-only")
if not stat.S_ISBLK(device.stat().st_mode):
    raise SystemExit("Not a block device")
total = int((node / "size").read_text()) * 512
length = 16 * 1024 * 1024
block = 16 * 1024
if total < length:
    raise SystemExit("Device smaller than bounded test extent")
signal.alarm(90)
fd = os.open(device, os.O_RDONLY | os.O_DIRECT | os.O_CLOEXEC)
buffer = mmap.mmap(-1, block)
expected = None
started = time.monotonic()
try:
    for repeat in range(4):
        digest = hashlib.sha256()
        for offset in range(0, length, block):
            amount = os.preadv(fd, [buffer], offset)
            if amount != block:
                raise RuntimeError(f"Short direct read at {offset}: {amount}")
            digest.update(buffer)
        actual = digest.hexdigest()
        if expected is not None and expected != actual:
            raise RuntimeError("Direct-read checksum changed between passes")
        expected = actual
        print("SSD_DIRECT_READ_PASS", device, repeat + 1, length,
              actual, f"{time.monotonic()-started:.2f}s", flush=True)
    print("SSD_DIRECT_READ_VERIFY_DONE", flush=True)
finally:
    buffer.close()
    os.close(fd)
    signal.alarm(0)
