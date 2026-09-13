#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Pull the running m1n1 image off the M5 over the proxy.

Why: the M5 boots a STOCK m1n1 (banner "m1n1 88a9821", no -dirty) while the
local tree is patched, and the bytes differ - so no local symbol or offset
can be trusted for any address in the running binary. The hypervisor died
with an UNDEF at rel 0x155d4 (ESR 0x2000000, EC=0); m1n1 prints "rel:" as
elr - _base (src/exception.c:216), and u.base is that same _base.

Ordering matters: the window containing the fault is read and written FIRST,
so even if the link drops during the bulk read we still have the answer and
nobody has to reboot again. The bulk read is chunked with retries because a
single 2 MB transfer knocks the CDC link over ("Device not configured").

Pure reads. Nothing is modified and this cannot fault the machine.
"""

import sys, pathlib, time

sys.path.append(str(pathlib.Path(__file__).resolve().parents[0] / "proxyclient"))

from m1n1.setup import *

HERE = pathlib.Path(__file__).resolve().parents[0]

FAULT = 0x155d4
WIN_START, WIN_SIZE = 0x14000, 0x4000     # critical window, read first
BULK_SIZE = 0x140000                      # 1.25 MB - past the end of the image
CHUNK = 0x10000                           # 64 KB; 2 MB in one go drops the link


def read_chunk(addr, size, tries=3):
    for attempt in range(tries):
        try:
            return iface.readmem(addr, size)
        except Exception as e:
            print(f"    retry {attempt + 1}/{tries} at 0x{addr:x}: {e}")
            time.sleep(0.5)
    return None


print(f"m1n1 base : 0x{u.base:x}")

# ---- 1. the part we actually need ------------------------------------------
print(f"\n[1/3] fault window: _base+0x{WIN_START:x} .. +0x{WIN_START + WIN_SIZE:x}")
win = read_chunk(u.base + WIN_START, WIN_SIZE)
if win is None:
    print("  FAILED - cannot read even the fault window. Stop and tell Claude.")
    sys.exit(1)
(HERE / "m1n1-fault.bin").write_bytes(win)
print(f"  wrote m1n1-fault.bin ({len(win)} bytes, starts at rel 0x{WIN_START:x})")

print(f"\nfault at rel 0x{FAULT:x}:")
for off in range(FAULT - 0x30, FAULT + 0x34, 4):
    w = int.from_bytes(win[off - WIN_START:off - WIN_START + 4], "little")
    print(f"  0x{off:06x}: {w:08x}{'   <<< FAULTING INSTRUCTION' if off == FAULT else ''}")

# ---- 2. the whole image, chunked -------------------------------------------
print(f"\n[2/3] bulk image: {BULK_SIZE} bytes in {CHUNK // 1024} KB chunks")
parts, got = [], 0
for off in range(0, BULK_SIZE, CHUNK):
    d = read_chunk(u.base + off, min(CHUNK, BULK_SIZE - off))
    if d is None:
        print(f"  giving up at rel 0x{off:x} - keeping what we have")
        break
    parts.append(d)
    got += len(d)
    print(f"  0x{off:06x}  {got * 100 // BULK_SIZE:3d}%")

data = b"".join(parts)
(HERE / "m1n1-running.bin").write_bytes(data)
print(f"  wrote m1n1-running.bin ({len(data)} bytes)")

import re
m = re.search(rb"m1n1 ([0-9a-f]{7}[-A-Za-z0-9.]*)", data)
print(f"  build tag: {m.group(1).decode() if m else 'not found in dumped range'}")

# ---- 3. this boot's ADT ----------------------------------------------------
print("\n[3/3] ADT")
try:
    adt = u.adt.build()
    (HERE / "adt-thisboot.bin").write_bytes(adt)
    print(f"  wrote adt-thisboot.bin ({len(adt)} bytes)")
except Exception as e:
    print(f"  skipped: {e}")

print("\nDone. Reboot to macOS and tell Claude.")
