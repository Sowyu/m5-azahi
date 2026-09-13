#!/usr/bin/env python3
"""Read-only, bounded APFS volume-label inspection of the 250 GB partition.

Selects the latest checksum-valid container checkpoint and resolves its
volume OIDs through the physical object map. No filesystem mount or repair.
Field layout: sgan81/apfs-fuse ApfsLib/DiskStruct.h.
"""
import os
from pathlib import Path
import signal
import struct
import subprocess
import uuid

device = "/dev/nvme0n1p3"
if Path("/sys/block/nvme0n1/ro").read_text().strip() != "1":
    raise SystemExit("Refusing writable namespace")
identity = subprocess.check_output(
    ["blkid", "-p", "-o", "export", device], text=True, timeout=5)
fields = dict(line.split("=", 1) for line in identity.splitlines() if "=" in line)
if (fields.get("UUID") != "PRIVATE-UUID-REMOVED"
        or fields.get("TYPE") != "apfs"):
    raise SystemExit("APFS container identity mismatch")

def valid_checksum(block):
    lo = hi = 0
    modulus = 0xffffffff
    for word, in struct.iter_unpack("<I", block[8:]):
        lo = (lo + word) % modulus
        hi = (hi + lo) % modulus
    check_lo = modulus - ((lo + hi) % modulus)
    check_hi = modulus - ((lo + check_lo) % modulus)
    return struct.unpack_from("<Q", block)[0] == (check_hi << 32 | check_lo)

signal.alarm(30)
fd = os.open(device, os.O_RDONLY | os.O_CLOEXEC)
found = {}
try:
    first = os.pread(fd, 4096, 0)
    if first[32:36] != b"NXSB" or struct.unpack_from("<I", first, 36)[0] != 4096:
        raise RuntimeError("Unexpected container block layout")
    if not valid_checksum(first):
        raise RuntimeError("Container checksum failed")
    def u64(block, offset):
        return struct.unpack_from("<Q", block, offset)[0]
    block_count = u64(first, 40)
    actual_size = int(Path("/sys/class/block/nvme0n1p3/size").read_text()) * 512
    if block_count * 4096 != actual_size:
        raise RuntimeError("Container size mismatch")
    budget = 2048
    def read_block(number, verify=True):
        global budget
        budget -= 1
        if budget < 0 or not 0 <= number < block_count:
            raise RuntimeError("Metadata read outside bounds or budget")
        block = os.pread(fd, 4096, number * 4096)
        if len(block) != 4096 or (verify and not valid_checksum(block)):
            raise RuntimeError(f"Metadata checksum/read failed at block {number}")
        return block
    count = struct.unpack_from("<I", first, 104)[0]
    base = u64(first, 112)
    if not 0 < count <= 1024:
        raise RuntimeError("Unsupported checkpoint descriptor layout")
    latest = first
    for number in range(base, base + count):
        block = read_block(number, verify=False)
        if (block[32:36] == b"NXSB" and valid_checksum(block)
                and block[72:88] == first[72:88] and u64(block, 16) > u64(latest, 16)):
            latest = block
    xid = u64(latest, 16)
    omap = read_block(u64(latest, 160))
    if struct.unpack_from("<I", omap, 24)[0] & 0xffff != 11:
        raise RuntimeError("Expected physical object map")
    root = u64(omap, 48)
    def lookup(oid):
        number = root
        for depth in range(8):
            block = read_block(number)
            flags, level, nkeys, off, length = struct.unpack_from("<HHIHH", block, 32)
            if (not flags & 4 or flags & ~7 or off or not 0 < nkeys <= 1000
                    or 4 * nkeys > length or 56 + length > 4056):
                raise RuntimeError("Unsupported object-map node")
            value_end = 4096 - (40 if flags & 1 else 0)
            entries = []
            for index in range(nkeys):
                ko, vo = struct.unpack_from("<HH", block, 56 + index * 4)
                kp, vp = 56 + length + ko, value_end - vo
                size = 16 if level == 0 else 8
                if not (56 + length <= kp <= value_end - 16 and
                        56 + length <= vp <= value_end - size):
                    raise RuntimeError("Object-map entry outside node")
                key = struct.unpack_from("<QQ", block, kp)
                if key <= (oid, xid):
                    entries.append((key, vp))
            if not entries:
                raise RuntimeError("No object-map key")
            key, vp = max(entries)
            if level:
                number = u64(block, vp)
                continue
            if key[0] != oid:
                raise RuntimeError("Volume OID missing")
            vflags, size, paddr = struct.unpack_from("<IIQ", block, vp)
            if vflags & ~2 or size != 4096:
                raise RuntimeError("Unsupported/deleted/encrypted volume mapping")
            return paddr
        raise RuntimeError("Object map exceeds depth bound")
    for oid in struct.unpack_from("<100Q", latest, 184):
        if not oid:
            continue
        paddr = lookup(oid)
        block = read_block(paddr)
        if (block[32:36] != b"APSB" or u64(block, 8) != oid
                or u64(block, 16) > xid):
            raise RuntimeError("Volume superblock identity mismatch")
        volume = str(uuid.UUID(bytes=block[240:256]))
        name = block[704:960].split(b"\0", 1)[0].decode("utf-8", "strict")
        role = struct.unpack_from("<H", block, 964)[0]
        found[(volume, name, role)] = (u64(block, 16), paddr * 4096)
    for (volume, name, role), (xid, offset) in sorted(found.items()):
        print("APFS_VOLUME_LABEL", repr(name), volume, f"role={role:#x}",
              f"xid={xid}", f"byte_offset={offset}", flush=True)
    print("APFS_VOLUME_INSPECTION_DONE", len(found), flush=True)
finally:
    os.close(fd)
    signal.alarm(0)
