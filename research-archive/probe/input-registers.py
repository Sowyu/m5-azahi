#!/usr/bin/env python3
"""Read-only MTP register survey, run through the live kit's run.sh in proxy mode.

Do not run while a guest/another proxy client owns the USB connection.
"""
from m1n1.setup import p, u

BAD = 0xabad1dea


def read(address):
    value = p.read32(address)
    if value == BAD:
        raise RuntimeError(f"Fault at {address:#x}; stopping the survey")
    return value


for name, address in (("NUB_DOCK", 0x288300080), ("NUB_GPIO", 0x288300088)):
    value = read(address)
    print(f"POWER {name} {address:#x}={value:#010x}", flush=True)
    if (value >> 4) & 15 != 15:
        raise RuntimeError("NUB power is not active; not reading input hardware")

asc, _ = u.adt["arm-io/mtp"].get_reg(0)
dart, size = u.adt["arm-io/dart-mtp"].get_reg(0)
assert asc == 0x294600000 and dart == 0x294800000 and size == 0xc000
for offset in (0, 0x40, 0x44, 0x48, 0x8110, 0x8114):
    print(f"ASC {asc + offset:#x}={read(asc + offset):#010x}", flush=True)

# reg[0] spans three 16-KiB windows. Identify a second DART by its parameter
# registers before reading its status, rather than assuming another SoC's bank.
for delta in (0, 0x4000):
    base = dart + delta
    params = [read(base + offset) for offset in (0, 4, 8, 12)]
    print(f"DART BANK {base:#x} PARAMS {[hex(v) for v in params]}", flush=True)
    if (params[0] >> 24) & 15 != 14 or (params[2] >> 24) & 63 != 42:
        print("Not a recognized T6050 DART bank; skipping status reads", flush=True)
        continue
    for offset in (0x100, 0x104, 0x170, 0x174, 0xc00, 0x1000, 0x1004, 0x1008, 0x100c):
        print(f"DART {base + offset:#x}={read(base + offset):#010x}", flush=True)
print("INPUT_SURVEY_DONE", flush=True)
