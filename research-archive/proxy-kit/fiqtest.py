#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Does the M5 Pro deliver timer FIQs to EL2 at all?

This is the single unproven link in the Linux boot chain. m1n1 has never
needed timer interrupts (it polls CNTPCT), so nothing on this machine has
ever demonstrated FIQ delivery. If Sotra gates FIQs the way it gates the
CPU-start registers, Linux goes tickless right after time_init and parks
in WFI forever - which looks exactly like the hang we have.

Arm the EL2 physical timer for 1ms and see whether m1n1's own FIQ handler
catches it. m1n1's exc_fiq() masks a firing phys timer by writing CTL=7
(src/exception.c:402-406), so the readback tells us everything:

    CTL -> 7   FIQ delivered and handled. Timer interrupts work.
    CTL -> 5   ISTATUS set (timer fired) but no FIQ was ever taken.
               That is the bug, and it is not in Linux.
    CTL -> 1   Timer never even reached its deadline. Different problem.

exc_fiq() also prints "Exception: FIQ" BEFORE it touches IPI_SR/PMCR0
(src/exception.c:400 vs 427-437), so if the machine dies mid-test but that
line appeared, delivery works and one of those reads is the landmine.

Nothing here is destructive: the timer is disabled again on the way out.
"""

import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parents[0] / "proxyclient"))

from m1n1.setup import *
from m1n1.sysreg import *

CTL_ENABLE = 1 << 0
CTL_IMASK = 1 << 1
CTL_ISTATUS = 1 << 2


def show(label, val):
    print(f"  {label:<16} 0x{val:x}")


print("=== M5 Pro (T6050 Sotra) EL2 timer-FIQ delivery test ===\n")

print("Context:")
el = u.mrs(CurrentEL) >> 2
show("CurrentEL", el)
show("DAIF", u.mrs(DAIF))
show("HCR_EL2", u.mrs(HCR_EL2)) if el == 2 else None
freq = u.mrs(CNTFRQ_EL0)
show("CNTFRQ_EL0", freq)

# FIQ must be unmasked (DAIF bit 6) or the test proves nothing.
daif = u.mrs(DAIF)
if daif & (1 << 6):
    print("\n  !! FIQ is MASKED in DAIF - unmasking for the test")
    u.msr(DAIF, daif & ~(1 << 6))

# Is the counter even running?
t0 = u.mrs(CNTPCT_EL0)
time.sleep(0.2)
t1 = u.mrs(CNTPCT_EL0)
print(f"\nCounter: {t0:#x} -> {t1:#x}  (delta {t1 - t0}, ~{(t1-t0)/freq:.3f}s)")
if t1 == t0:
    print("  !! COUNTER IS NOT RUNNING - stop here, nothing else is meaningful")
    sys.exit(1)
print("  counter is running")

print(f"\nCNTP_CTL_EL0 before: 0x{u.mrs(CNTP_CTL_EL0):x}   (7 = m1n1 masked it at init)")

# Arm: deadline 1ms out, ENABLE set, IMASK clear -> should raise a FIQ.
ticks = freq // 1000
print(f"\nArming EL2 phys timer: TVAL={ticks} (~1ms), CTL=ENABLE, IMASK clear ...")
u.msr(CNTP_TVAL_EL0, ticks)
u.msr(CNTP_CTL_EL0, CTL_ENABLE)

result = None
for i in range(10):
    time.sleep(0.1)
    ctl = u.mrs(CNTP_CTL_EL0, silent=True)
    print(f"  poll {i}: CNTP_CTL_EL0 = 0x{ctl:x}"
          f"  [{'ENABLE ' if ctl & CTL_ENABLE else ''}"
          f"{'IMASK ' if ctl & CTL_IMASK else ''}"
          f"{'ISTATUS' if ctl & CTL_ISTATUS else ''}]")
    if ctl & CTL_IMASK:
        result = "masked"
        break
    if ctl & CTL_ISTATUS:
        result = "fired-no-fiq"

# Leave the timer off no matter what.
u.msr(CNTP_CTL_EL0, CTL_IMASK)

print("\n=== VERDICT ===")
if result == "masked":
    print("FIQ DELIVERED AND HANDLED. Timer interrupts work at EL2 on Sotra.")
    print("m1n1's exc_fiq ran, masked the timer, and survived reading IPI_SR")
    print("and PMCR0 - so the FIQ path is NOT what is hanging Linux.")
elif result == "fired-no-fiq":
    print("TIMER FIRED BUT NO FIQ WAS EVER TAKEN (ISTATUS set, IMASK never set).")
    print("This SoC does not deliver timer FIQs to EL2 under these conditions.")
    print("That is the hang: Linux goes tickless right after time_init.")
    print("No amount of kernel patching fixes this - the gate is below EL2.")
else:
    print("TIMER NEVER REACHED ITS DEADLINE (ISTATUS never set).")
    print("The comparator or the arming path is wrong - investigate before")
    print("drawing any conclusion about FIQ delivery.")

print("\nIf the M5's screen printed 'Exception: FIQ ... PHYS timer IRQ, masking',")
print("copy that line too - it confirms the handler ran end to end.")
