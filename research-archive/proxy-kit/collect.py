#!/usr/bin/env python3
# Connect to the M5 running m1n1, collect everything useful, write it to files
# next to this script (i.e. onto the USB stick). Nothing is written to the M5.
# Run from the host Mac:   sh run.sh collect.py
import os, sys, pathlib, traceback

HERE = pathlib.Path(__file__).resolve().parent
REPORT = HERE / "collect-report.txt"
out = open(REPORT, "w")

def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    out.write(s + "\n")
    out.flush()

def step(name, fn):
    log(f"\n=== {name} ===")
    try:
        fn()
    except Exception:
        log("FAILED:")
        log(traceback.format_exc())

log("m1n1 proxy collection")
log("host python:", sys.version.split()[0])
log("device:", os.environ.get("M1N1DEVICE", "?"))

# Connecting happens on import — if this fails, the link is the problem.
from m1n1.setup import *          # noqa: F401,F403  (gives us p, u, iface, mon)

log("\nCONNECTED.")

def _aic():
    v = p.read32(0x280400000)
    log(f"AIC version reg @0x280400000 = {v:#x}")

def _midr():
    try:
        from m1n1.utils import MIDR_EL1
        reg = MIDR_EL1
    except Exception:
        reg = "MIDR_EL1"
    v = u.mrs(reg)
    log(f"MIDR_EL1 = {v:#x}   (part = {(v >> 4) & 0xfff:#x})")

def _wdt():
    log(f"WDT   @0x28836c000 = {p.read32(0x28836c000):#x}")

def _adt():
    data = u.get_adt()
    path = HERE / "adt-real-t6050.bin"
    path.write_bytes(data)
    log(f"REAL ADT dumped: {len(data)} bytes -> {path.name}")

def _mem():
    # Where m1n1 thinks RAM lives; useful for kernel loading later.
    for name in ("base", "phys_base", "ram_base"):
        v = getattr(u, name, None)
        if v is not None:
            log(f"u.{name} = {v:#x}")

step("AIC", _aic)
step("CPU identity", _midr)
step("Watchdog", _wdt)
step("Memory layout", _mem)
step("FULL DEVICE TREE (the important one)", _adt)

log("\nDONE. Take the stick back to the M5, boot macOS, and let Claude read")
log("collect-report.txt and adt-real-t6050.bin.")
out.close()
