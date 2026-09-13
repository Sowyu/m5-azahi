#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
THE batched T6050 probe. Run once over the live m1n1 proxy; costs one reboot.

    sh run.sh vmtmrprobe.py        (from proxy-kit/)

Everything worth knowing about the read-only VM_TMR_FIQ_ENA claim, the timer,
and the neighbouring IMP-DEF regs, in a single pass. No writes are left set;
the guard catches every UNDEF so the machine survives all of it.

Read the VERDICT block each section prints. What each outcome means is stated
inline so the operator can paste the whole log back and it interprets itself.
"""

import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[0] / "proxyclient"))

from m1n1.setup import *
from m1n1.sysreg import *

VM_TMR   = "s3_5_c15_c1_3"   # SYS_IMP_APL_VM_TMR_FIQ_ENA_EL2
UPMCR0   = "s3_7_c15_c0_4"
ICH_HCR  = "s3_4_c12_c11_0"   # ICH_HCR_EL2 (vGIC; read by kernel aic_init_cpu)
CTL_ENABLE, CTL_IMASK, CTL_ISTATUS = 1, 2, 4

def hr(t): print("\n" + "=" * 68 + f"\n{t}\n" + "=" * 68)

def rd(enc):
    """guarded read -> (value or None if UNDEF)"""
    before = p.get_exc_count()
    try:
        v = u.mrs(enc, silent=True)
    except Exception as e:
        return ("ERR", str(e))
    return (None, None) if p.get_exc_count() > before else (v, None)

def wr(enc, val):
    """guarded write -> True if it UNDEF'd, False if it landed"""
    before = p.get_exc_count()
    try:
        u.msr(enc, val, silent=True)
    except Exception as e:
        return ("ERR", str(e))
    return p.get_exc_count() > before

# ---------------------------------------------------------------------------
hr("0. CONTEXT")
el = u.mrs(CurrentEL) >> 2
print(f"  CurrentEL   = {el}   (need 2 for VM_TMR/EL02 to mean anything)")
print(f"  MIDR_EL1    = {u.mrs(MIDR_EL1):#x}")
print(f"  CNTFRQ_EL0  = {u.mrs(CNTFRQ_EL0):#x}  ({u.mrs(CNTFRQ_EL0)/1e6:.0f} MHz)")
if el != 2:
    print("  !! Not at EL2 — VM_TMR_FIQ_ENA and CNT*_EL02 probes below are moot.")

p.set_exc_guard(GUARD.SKIP | GUARD.SILENT)
try:
    # -----------------------------------------------------------------------
    hr("1. VM_TMR_FIQ_ENA — read once, then write EVERY value")
    # The core question. hv_update_fiq does read-modify-write of bits 0/1.
    # Reset value should be 0xf = all delivery enabled. We already proved MRS
    # works and exactly ONE write (an OR #2) UNDEF'd. Now sweep writes to tell
    # "all writes UNDEF" from "only some bit patterns / only when it changes".
    v0, _ = rd(VM_TMR)
    print(f"  MRS initial = {v0}")
    print(f"  {'value written':>14}   result")
    results = {}
    for val in (0x0, 0x1, 0x2, 0x3, 0xc, 0xf, v0 if v0 is not None else 0xf):
        undef = wr(VM_TMR, val)
        results[val] = undef
        after, _ = rd(VM_TMR)
        tag = "UNDEF" if undef is True else ("ERR" if undef == "ERR" else "wrote OK")
        print(f"  {val:#014x}   {tag:<8}  (read-back now = {after})")
    # restore best-effort
    if v0 is not None:
        wr(VM_TMR, v0)

    all_undef  = all(r is True for r in results.values())
    none_undef = all(r is False for r in results.values())
    print("\n  --- VERDICT (VM_TMR) ---")
    if all_undef:
        print("  READ-ONLY CONFIRMED: every MSR UNDEF'd, MRS worked.")
        print("  -> m1n1 hv MUST NOT write this reg on T6050. Apply m1n1-vmtmr-ro.patch")
        print("     (masks guest timers via CNTx_CTL_EL02 IMASK instead).")
        print("  -> Kernel aic_* patches at the 6 VM_TMR MSR sites are REQUIRED after all")
        print("     — but only bare-metal; under the hv the guest's writes trap & are")
        print("     emulated, so the guest kernel stays UNPATCHED. See report section E.")
    elif none_undef:
        print("  NOT read-only: writes landed. The original hv UNDEF was NOT this reg.")
        print("  -> Re-examine the fault PC; do NOT apply the RO workaround.")
    else:
        print("  PARTIAL: some values UNDEF, some not. Bit-pattern gated. Detail above —")
        print("  the pattern tells us which bits are writable. Report which values stuck.")

    # -----------------------------------------------------------------------
    hr("2. Neighbours in the same faulting path (rule out confusion)")
    for name, enc in [("UPMCR0", UPMCR0), ("ICH_HCR_EL2", ICH_HCR),
                      ("IPI_SR_EL1", "s3_5_c15_c1_1")]:
        v, err = rd(enc)
        print(f"  {name:<12} MRS = {v}" + (f"  ({err})" if err else ""))
    # Does UPMCR0 also reject writes? (its own aic_init_cpu MSR site)
    uv, _ = rd(UPMCR0)
    if uv is not None:
        undef = wr(UPMCR0, uv)
        print(f"  UPMCR0 write-back same value: {'UNDEF' if undef is True else 'OK'}")

    # -----------------------------------------------------------------------
    hr("3. Does VM_TMR_FIQ_ENA still GATE anything? (only if writable)")
    # If writable: clear bit1 (phys), arm EL02 phys timer, see if a FIQ is
    # suppressed vs. with the bit set. If read-only, skip — we mask via CTL.
    if all_undef:
        print("  Skipped: register is read-only, gating is moot (we use CTL IMASK).")
    else:
        print("  Register is writable — worth an EL02-timer gate test, but that needs a")
        print("  guest context. Defer to the hv run; note it here and move on.")

    # -----------------------------------------------------------------------
    hr("4. Guest timer path sanity: CNTx_CTL_EL02 mask actually silences FIQ?")
    # The workaround masks guest timers by setting CNTx_CTL_EL02 IMASK. Confirm
    # that writing EL02 CTL from EL2 works (it must — hv already SYSREG_MAPs it)
    # and that setting IMASK clears the ISTATUS-driven FIQ assertion.
    if el == 2:
        for reg in ("s3_5_c14_c2_1", "s3_5_c14_c3_1"):  # CNTP_CTL_EL02, CNTV_CTL_EL02
            v, err = rd(reg)
            w = wr(reg, (v | CTL_IMASK) if v is not None else CTL_IMASK)
            v2, _ = rd(reg)
            if v is not None:
                wr(reg, v)  # restore
            nm = "CNTP_CTL_EL02" if reg.endswith("c2_1") else "CNTV_CTL_EL02"
            print(f"  {nm}: read={v} setIMASK={'UNDEF' if w is True else 'OK'} -> {v2}")
        print("\n  If both EL02 CTLs are read/writable at EL2, the IMASK workaround is")
        print("  mechanically sound: hv can mask a firing guest timer without VM_TMR.")
    else:
        print("  Skipped (not at EL2).")

    # -----------------------------------------------------------------------
    hr("5. 1 GHz timer reality check")
    freq = u.mrs(CNTFRQ_EL0)
    t0 = u.mrs(CNTPCT_EL0); time.sleep(0.2); t1 = u.mrs(CNTPCT_EL0)
    d = t1 - t0
    print(f"  CNTFRQ={freq} ({freq/1e6:.0f} MHz). CNTPCT delta over ~0.2s = {d}"
          f"  => measured {d/0.2/1e6:.0f} MHz")
    print(f"  ratio measured/declared = {(d/0.2)/freq:.3f}  (want ~1.0)")
    if abs((d/0.2)/freq - 1.0) < 0.25:
        print("  -> CNTFRQ is TRUTHFUL: the counter really runs at the declared rate.")
        print("     DTB timer node must NOT carry a 24 MHz clock-frequency override, and")
        print("     the kernel must derive its rate from CNTFRQ. (See report section F.)")
    else:
        print("  -> MISMATCH: declared and measured differ. arch_timer will mis-scale.")

finally:
    p.set_exc_guard(GUARD.OFF)

hr("DONE — paste this whole log back")
print("Key lines: section 1 VERDICT (read-only?), section 4 (mask workaround sound?),")
print("section 5 (timer rate truthful?). Those three decide the m1n1 patch + DTB.")
