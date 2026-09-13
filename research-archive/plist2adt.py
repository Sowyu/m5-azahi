#!/usr/bin/env python3
# Reconstruct a raw binary Apple Device Tree from an `ioreg -alp IODeviceTree` plist dump.
# Format per m1n1/proxyclient/m1n1/adt.py: node = u32 prop_count, u32 child_count,
# props = [name:32s pad, size:u32le, value (4-byte aligned)], then children recursively.
import plistlib, struct, sys

SYNTHETIC = ("IORegistryEntry", "IOObject", "IOService", "IOMatch", "IOUserClient",
             "IOPersonality", "IOProbeScore", "IOClass", "IOProviderClass",
             "IONameMatch", "IOResourceMatch", "IOPropertyMatch", "IOFunctionParent",
             "IOPlatform", "IOBusy", "IODeviceMemory", "IOInterrupt", "IOReportLegend",
             "IOPowerManagement", "IOGeneralInterest", "IOKit", "IOCPU", "IOPolled",
             "IODT", "IOMACAddress", "IOSerialized")

def prop_bytes(v):
    if isinstance(v, bytes):
        return v
    if isinstance(v, str):
        return v.encode() + b"\x00"
    if isinstance(v, bool):
        return struct.pack("<I", int(v))
    if isinstance(v, int):
        return struct.pack("<I", v) if 0 <= v < 1 << 32 else struct.pack("<q", v)
    return None  # dicts/arrays: IOKit-synthesized, not ADT data

def emit(node, out):
    props = []
    name = node.get("IORegistryEntryName", "?")
    for k, v in node.items():
        if any(k.startswith(p) for p in SYNTHETIC):
            continue
        b = prop_bytes(v)
        if b is None or len(k) > 31:
            continue
        if k == "name" and not b.rstrip(b"\x00"):
            continue  # empty/garbage name (IOKit nubs, chosen) — synthesize below
        props.append((k, b))
    if not any(k == "name" for k, _ in props):
        props.insert(0, ("name", name.encode(errors="replace") + b"\x00"))
    children = node.get("IORegistryEntryChildren", [])
    out.append(struct.pack("<II", len(props), len(children)))
    for k, b in props:
        out.append(k.encode().ljust(32, b"\x00"))
        out.append(struct.pack("<I", len(b)))
        out.append(b + b"\x00" * (-len(b) % 4))
    for c in children:
        emit(c, out)

root = plistlib.load(open(sys.argv[1], "rb"))
if isinstance(root, list):
    root = root[0]
# descend past the IORegistry root to the device-tree root ("device-tree")
while root.get("IORegistryEntryName") in ("Root", "IORegistryEntry"):
    root = root["IORegistryEntryChildren"][0]
out = []
emit(root, out)
open(sys.argv[2], "wb").write(b"".join(out))
print(f"wrote {sys.argv[2]}: {sum(len(x) for x in out)} bytes, root={root.get('IORegistryEntryName')}")
