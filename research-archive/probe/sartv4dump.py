# Read-only dump of the T6050 SARTv4 register file, host-side over the proxy.
#
# Purpose: record the pristine (iBoot-programmed) SARTv4 state on a fresh
# boot, and re-verify the v4 layout discovered 2026-08-29:
#     FLAGS @ 0x00 + 4*i     (same offset as v3 CONFIG)
#     hole  @ 0x40..0x5f     (v3's PADDR window: reads 0, drops writes)
#     PADDR @ 0x60 + 4*i     (<<12, same encoding as v3)
#     SIZE  @ 0xc0 + 4*i     (<<12)
# Evidence: after a failed Linux probe, Linux's v3 writes for entry 6 read
# back as FLAGS(6)=0xff at 0x18 (landed - same offset in both layouts),
# PADDR write to 0x58 lost, SIZE write to 0x98 landed as v4 PADDR(14)=8;
# iBoot's entries pair up only in the 0x60/0xc0 reading, e.g. entry 7 =
# paddr 0x10000028000 (just above DRAM base) size 0x24f000 flags 0xea.
#
# STRICTLY read-only: refuses to touch SART unless PMGR says fab6_soc is
# already ACTIVE (run anspower_inline / ANSPOWER=1 first). A cold read of a
# gated block SErrors and costs a physical power cycle. A faulted proxy read
# returns 0xabad1dea (GUARD_MARK low half) - we stop at the first one.
#
# Run:  sh ~/azahi/run.sh ~/azahi/sartv4dump.py

from m1n1.setup import *

FAB6_SOC = 0x280600138          # PMGR PS reg, always-on, safe cold
SART     = 0x41dc50000          # ADT /arm-io/sart-ans reg[0], TRANSLATED
FAULT    = 0xabad1dea

v = p.read32(FAB6_SOC)
print(f"fab6_soc PS = {v:#010x} target={v & 0xf:#x} actual={(v >> 4) & 0xf:#x}")
if (v >> 4) & 0xf != 0xf:
    print("fab6_soc is NOT active - refusing to read SART cold.")
    print("Power it first (anspower_inline.py / ANSPOWER=1), then re-run.")
    import sys
    sys.exit(1)

def dump(lo, hi, tag):
    print(f"--- SART+{lo:#x}..{hi:#x} ({tag}) ---")
    for off in range(lo, hi, 16):
        vals = []
        for i in (0, 4, 8, 12):
            d = p.read32(SART + off + i)
            if d == FAULT:
                print(f"  FAULT at +{off + i:#x} - stopping, link may desync")
                import sys
                sys.exit(1)
            vals.append(d)
        if any(vals) or off % 64 == 0:
            print("  +%04x: %08x %08x %08x %08x" % (off, *vals))

dump(0x000, 0x040, "v4 FLAGS  (v3 CONFIG - same place)")
dump(0x040, 0x060, "v3 PADDR window - RAZ/WI hole on v4")
dump(0x060, 0x0c0, "v4 PADDR  (<<12)")
dump(0x0c0, 0x120, "v4 SIZE   (<<12)")
dump(0x120, 0x200, "tail")
dump(0x13c0, 0x1400, "ADT sart-power-reg-offset 0x13e8 area")

print("Decoded entries (v4 layout):")
for i in range(16):
    fl = p.read32(SART + 0x00 + 4 * i)
    pa = p.read32(SART + 0x60 + 4 * i)
    sz = p.read32(SART + 0xc0 + 4 * i)
    if fl or pa or sz:
        print(f"  entry {i:2}: flags={fl:#04x} paddr={pa << 12:#013x} size={sz << 12:#x}")
print("done")
