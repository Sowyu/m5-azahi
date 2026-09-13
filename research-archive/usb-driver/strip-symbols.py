#!/usr/bin/env python3
"""Drop the __symbols__ node from a decompiled overlay (dtc -@ output).

The kernel's of_overlay refuses an overlay that has __symbols__ when the live
tree has no /__symbols__ (drivers/of/overlay.c: "symbols in overlay, but not
in live tree"). __local_fixups__ must stay: it is what lets the kernel rebase
the overlay-internal phandle references (iommus, phys, power-domains).
"""
import re
import sys

text = sys.stdin.read()
out, n = re.subn(r"\n\t__symbols__ \{\n.*?\n\t\};\n", "\n", text, flags=re.S)
assert n == 1, n
assert "__local_fixups__ {" in out
assert "__symbols__" not in out
sys.stdout.write(out)
