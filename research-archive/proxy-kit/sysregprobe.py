#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Which Apple IMP-DEF system registers exist on T6050 (M5 Pro, Sotra)?

m1n1's hypervisor died with an UNDEF (ESR 0x2000000, EC=0) inside hv_start,
which reads a run of IMP-DEF registers unconditionally to snapshot state for
secondary CPUs (src/hv.c:132-153). One of them does not exist on M5.

Rather than guess, probe every register hv_start touches. The proxy's
exception guard (GUARD.SKIP) catches the UNDEF, skips the instruction and
bumps a counter instead of taking down the machine - so this enumerates the
whole set in one pass with no reboot.

Anything reported MISSING has to be guarded behind cpu_features before the
hypervisor can run on this SoC.
"""

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[0] / "proxyclient"))

from m1n1.setup import *
from m1n1.sysreg import *

# (encoding, name, source line in src/hv.c, notes)
REGS = [
    ("HCR_EL2",         "HCR_EL2",                  132, "architectural"),
    ("HACR_EL2",        "HACR_EL2",                 133, "architectural"),
    ("VTCR_EL2",        "VTCR_EL2",                 134, "architectural"),
    ("VTTBR_EL2",       "VTTBR_EL2",                135, "architectural"),
    ("MDCR_EL2",        "MDCR_EL2",                 136, "architectural"),
    ("MDSCR_EL1",       "MDSCR_EL1",                137, "architectural"),
    ("s3_4_c15_c4_7",   "SYS_IMP_APL_AMX_CTL_EL2",  138, "AMX - replaced by SME in M4"),
    ("s3_6_c15_c14_4",  "SYS_IMP_APL_APVMKEYLO_EL2", 139, "PAC VM key"),
    ("s3_6_c15_c14_5",  "SYS_IMP_APL_APVMKEYHI_EL2", 140, "PAC VM key"),
    ("s3_6_c15_c14_7",  "SYS_IMP_APL_APSTS_EL12",   141, "PAC status"),
    ("ACTLR_EL2",       "ACTLR_EL2",                142, "architectural"),
    ("s3_5_c1_c0_1",    "ACTLR_EL12",               144, "taken when actlr_el2 (M4/M5 path)"),
    ("s3_6_c15_c14_6",  "SYS_IMP_APL_ACTLR_EL12",   146, "legacy path, not taken on M5"),
    ("CNTHCTL_EL2",     "CNTHCTL_EL2",              147, "architectural"),
    ("s3_6_c15_c1_0",   "SYS_IMP_APL_SPRR_CONFIG_EL1", 148, "UNGUARDED despite no SPRR on M4/M5"),
    ("s3_6_c15_c1_2",   "SYS_IMP_APL_GXF_CONFIG_EL1",  149, "UNGUARDED despite no GXF on M4/M5"),
    ("s3_1_c15_c1_5",   "SYS_IMP_APL_AGTCNTRDIR_EL1",  151, "only if counter_redirect"),
    ("s3_4_c15_c14_6",  "SYS_IMP_APL_AGTCNTRDIR_EL12", 152, "only if counter_redirect"),
    # Extra context: registers we already rely on elsewhere.
    ("s3_5_c15_c1_1",   "SYS_IMP_APL_IPI_SR_EL1",   0,   "read by Linux aic_handle_fiq"),
    ("s3_5_c15_c1_3",   "SYS_IMP_APL_VM_TMR_FIQ_ENA", 0, "read by Linux aic_init_cpu"),
    ("s3_7_c15_c0_4",   "SYS_IMP_APL_UPMCR0",       0,   "read by Linux aic_init_cpu"),
]

print("=== T6050 (M5 Pro Sotra) IMP-DEF sysreg probe ===")
print(f"CurrentEL {u.mrs(CurrentEL) >> 2}, MIDR {u.mrs(MIDR_EL1):#x}\n")

p.set_exc_guard(GUARD.SKIP | GUARD.SILENT)

missing, present = [], []
try:
    for enc, name, line, note in REGS:
        before = p.get_exc_count()
        try:
            val = u.mrs(enc, silent=True)
        except Exception as e:
            print(f"  {name:<32} PROXY ERROR: {e}")
            continue
        gone = p.get_exc_count() > before
        (missing if gone else present).append((name, line, note))
        src = f"hv.c:{line}" if line else "-"
        if gone:
            print(f"  {name:<32} {src:<10} *** UNDEF / MISSING ***   {note}")
        else:
            print(f"  {name:<32} {src:<10} = 0x{val:016x}   {note}")
finally:
    p.set_exc_guard(GUARD.OFF)

print("\n=== SUMMARY ===")
if missing:
    print(f"{len(missing)} register(s) do NOT exist on T6050:")
    for name, line, note in missing:
        where = f"src/hv.c:{line}" if line else "(not in hv_start)"
        print(f"  - {name}   {where}   {note}")
    hv = [m for m in missing if m[1]]
    if hv:
        print("\nThese are what killed the hypervisor in hv_start. Each needs a")
        print("cpu_features guard before hv can run on this SoC.")
    else:
        print("\nNone of these are in hv_start - the hv crash is something else.")
else:
    print("Every register read by hv_start exists. The UNDEF is NOT a missing")
    print("register - look for a trapped access or an unimplemented instruction.")
print(f"\n({len(present)} present, {len(missing)} missing)")
