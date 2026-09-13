#!/usr/bin/env python3
"""Offline exact-delta validation, not a claim that native boot succeeds."""
from pathlib import Path
import hashlib
import struct

root = Path(__file__).resolve().parent.parent
stock = (root / "Image-asahi").read_bytes()
candidate = (root / "Image-baremetal.bin").read_bytes()
assert hashlib.sha256(stock).hexdigest() == "f1672f680082c40b8f606b5acd70f9a5ec7cef0d04abc2f63a2d26862a045999"
assert len(candidate) == len(stock)
expected = bytearray(stock)
for offset in (0xbbb63c, 0xbbb654, 0xbbbc70, 0xbbc114):
    old, = struct.unpack_from("<I", stock, offset)
    # MSR s3_5_c15_c1_3, Xn; allow only the documented X0/X1 variants.
    assert old in (0xd51df160, 0xd51df161), (hex(offset), hex(old))
    struct.pack_into("<I", expected, offset, 0xd503201f)
    print(f"NATIVE_DELTA {offset:#x}: {old:#x} -> NOP")
assert candidate == expected, "Unexpected kernel modifications"
dtb = (root / "t6050-j714s-bare.dtb").read_bytes()
assert dtb[:4] == bytes.fromhex("d00dfeed")
assert struct.unpack_from(">I", dtb, 4)[0] == len(dtb)
assert b"console=tty0" in dtb
assert b"earlycon=" not in dtb
print("NATIVE_CANDIDATE_DELTA_VERIFIED; hardware boot NOT tested")
