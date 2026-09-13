# Which ANS/NVMe sub-blocks answer, host-side, coproc NOT booted?
#
# Motivated by nvme-sartv4.log: with the SARTv4 shim working, RTKit boots,
# BOOT_STATUS reaches 0xde71ce55, and then the guest's very first write past
# the poll - APPLE_ANS_LINEAR_SQ_CTRL = nvme+0x24908 - bus-errors (all 189
# repeating SErrors latch L2C_ERR_ADR 0x...41dce4908). CAP/CC/CSTS at the
# BAR base work. So probe the untested sub-blocks in escalating-risk order,
# flushing each line, and STOP at the first 0xabad1dea (each fault dumps
# registers over the UART and may desync the link; M5 self-recovers).
#
# Run:  sh ~/azahi/run.sh ~/azahi/anscfgprobe.py
from m1n1.setup import *
import sys, time

PS = {"fab6_soc": 0x280600138, "ans": 0x280600140,
      "apcie_st0": 0x280600128, "apcie_sys_st0": 0x280600150}
AUTO_ENABLE, WAS_CLKGATED, WAS_PWRGATED = 1 << 28, 1 << 9, 1 << 8
PS_ACTIVE = 0xF
FAULT = 0xabad1dea

def power_on(name):
    addr = PS[name]
    if (p.read32(addr) >> 4) & 0xF == PS_ACTIVE:
        print(f"  {name}: already ACTIVE", flush=True)
        return True
    p.mask32(addr, AUTO_ENABLE | WAS_CLKGATED | WAS_PWRGATED | 0xF, PS_ACTIVE)
    for _ in range(200):
        if (p.read32(addr) >> 4) & 0xF == PS_ACTIVE:
            print(f"  {name}: -> ACTIVE", flush=True)
            return True
        time.sleep(0.01)
    print(f"  {name}: TIMEOUT 0x{p.read32(addr):08x}", flush=True)
    return False

print("power (parents first):", flush=True)
for n in ("fab6_soc", "apcie_st0", "ans", "apcie_sys_st0"):
    if not power_on(n):
        sys.exit(1)

NVME = 0x41dcc0000
ASC  = 0x419600000

def rd(name, addr):
    v = p.read32(addr)
    tag = "  <-- FAULT" if v == FAULT else ""
    print(f"  {name:<30} {addr:#011x} = {v:#010x}{tag}", flush=True)
    if v == FAULT:
        print("STOP at first fault; M5 may desync/self-recover now.", flush=True)
        sys.exit(2)
    return v

print("escalating-risk reads (safe -> suspect):", flush=True)
rd("nvme CAP.lo   (known good)", NVME + 0x000)
rd("coproc BOOT_STATUS (known)", ASC + 0x1300)
rd("nvme CC             +0x14", NVME + 0x014)
rd("nvme CSTS           +0x1c", NVME + 0x01c)
rd("nvme +0x1210 MAX_PEND", NVME + 0x1210)
rd("nvme +0x13e8 sart-power-reg?", NVME + 0x13e8)
rd("nvme +0x28100 NVMMU_NUM", NVME + 0x28100)
rd("nvme +0x28108 NVMMU_ASQ.lo", NVME + 0x28108)
rd("nvme +0x24000", NVME + 0x24000)
rd("nvme +0x24900", NVME + 0x24900)
rd("nvme +0x24008 UNKNOWN_CTRL", NVME + 0x24008)
rd("nvme +0x24908 LINEAR_SQ_CTRL", NVME + 0x24908)
rd("ans reg[9] secure-bar? +0x0", 0x45dcc0000 + 0x0)
rd("ans reg[9] +0x8", 0x45dcc0000 + 0x8)
print("ALL READS OK - nothing faulted host-side, coproc not booted.", flush=True)
