#!/usr/bin/env python3
"""Read-only symbol/disassembly view of selected driver entries in a Mach-O KC.

Use the isolated capstone environment recorded in CPU-CHECKPOINT.md.
No extraction modifications, execution of firmware, or target connection.
"""
import argparse
from pathlib import Path
import re
import struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("image", type=Path)
p.add_argument("--symbol")
p.add_argument("--symbols-only", action="store_true")
p.add_argument("--address", type=lambda x: int(x, 0))
p.add_argument("--size", type=lambda x: int(x, 0), default=0x180)
p.add_argument("--entry", action="append", help="Exact fileset entry; repeat for dependencies (replaces defaults)")
args = p.parse_args()
b = args.image.read_bytes()
assert struct.unpack_from("<I", b)[0] == 0xfeedfacf

def commands(offset):
    ncmds = struct.unpack_from("<I", b, offset + 16)[0]
    q = offset + 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", b, q)
        assert size >= 8 and q + size <= len(b)
        yield cmd, q, size
        q += size

segments = []
symbols = {}
entries = set(args.entry or ("com.apple.kernel", "com.apple.driver.AppleARMPlatform",
                           "com.apple.driver.ApplePMGR", "com.apple.driver.AppleT6050PMGR"))
found_entries = set()
for cmd, q, size in commands(0):
    if cmd != 0x80000035:
        continue
    va, offset, nameoff, _ = struct.unpack_from("<QQII", b, q + 8)
    entry = b[q + nameoff:q + size].split(b"\0")[0].decode()
    if entry not in entries:
        continue
    found_entries.add(entry)
    for cc, r, sz in commands(offset):
        if cc == 0x19:
            segva, vmsize, fileoff, filesize = struct.unpack_from("<4Q", b, r + 24)
            segments.append((segva, fileoff, filesize))
        if cc == 2:
            symoff, count, stroff, strsize = struct.unpack_from("<4I", b, r + 8)
            for i in range(count):
                nameidx, ty, sect, desc, value = struct.unpack_from("<IBBHQ", b, symoff + 16 * i)
                if value == 0 or not (ty & 0xe):
                    continue
                assert nameidx < strsize
                name = b[stroff + nameidx:b.find(b"\0", stroff + nameidx)].decode(errors="replace")
                symbols.setdefault(value, []).append(name)

if entries - found_entries:
    p.error("Missing fileset entries: " + ", ".join(sorted(entries - found_entries)))

def read_va(va, size):
    for base, offset, length in segments:
        if base <= va and va + size <= base + length:
            return b[offset + va - base:offset + va - base + size]
    raise ValueError(f"Unmapped VA {va:#x}+{size:#x}")

dis = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
dis.skipdata = True
selected = [(args.address, args.size)] if args.address is not None else []
if args.symbol:
    for va, names in sorted(symbols.items()):
        if any(re.search(args.symbol, name) for name in names):
            next_va = min((v for v in symbols if v > va), default=va + args.size)
            selected.append((va, min(args.size, next_va - va)))
for va, size in selected:
    print(f"\n{va:#x} {' / '.join(symbols.get(va, []))}")
    if args.symbols_only:
        continue
    for ins in dis.disasm(read_va(va, size), va):
        annotation = ""
        if ins.mnemonic in ("b", "bl") and ins.op_str.startswith("#0x"):
            target = int(ins.op_str[1:], 16)
            annotation = " ; " + " / ".join(symbols.get(target, []))
        print(f"{ins.address:016x}: {ins.mnemonic:9} {ins.op_str}{annotation}")
