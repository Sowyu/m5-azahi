"""Filter capstone output of AppleT6050TypeCPhy methods down to register traffic and control flow.
Bank pointers: [x19,#0x210]=bank0, [x19,#0x230]=bank1, [x19,#0x250]=bank2 ... (stride 0x20).
Keeps: bank loads, address adds, ml_io_read32/write32, value ops on w1/w8, IOSleep/IODelay + their w0,
branches on the bool args (w20/w21/x20/x21) and unresolved virtual calls."""
import re, sys
CALLS = {"0xfffffe000b493380":"READ32","0xfffffe000b493640":"WRITE32","0xfffffe000bc0ec58":"IOSleep(ms)","0xfffffe000bc0ec78":"IODelay(us)",
         "0xfffffe000b602a28":None,"0xfffffe000bc0ec90":None,"0xfffffe000bbe52e4":None,"0xfffffe000bb98a10":None}
lines = open(sys.argv[1]).read().splitlines()
targets = set()
for l in lines:
    m = re.search(r"\b(b|b\.\w+|cbz|cbnz|tbz|tbnz)\s+.*#(0x[0-9a-f]+)", l)
    if m: targets.add(int(m.group(2),16))
last_w0 = None
for l in lines:
    m = re.match(r"([0-9a-f]{16}): (\S+)\s*(.*)", l)
    if not m:
        print(l); continue
    addr, mn, ops = int(m.group(1),16), m.group(2), m.group(3)
    lab = f"L_{addr:x}:" if addr in targets else ""
    out = None
    if mn == "bl":
        t = ops.split(";")[0].strip().lstrip("#")
        name = CALLS.get(t, "?")
        if name is None: pass
        elif name in ("IOSleep(ms)","IODelay(us)"): out = f"{name} {last_w0}"
        else: out = name + ("" if name == "READ32" else "")
    elif mn == "blraa":
        out = "VCALL " + ops
    elif mn == "ldr" and re.search(r"\[x19, #0x2[0-9a-f]0\]", ops):
        out = f"{mn} {ops}"
    elif mn in ("add","mov") and re.match(r"x0, x(22|8|9|20|21|23|24), #", ops) or re.match(r"x0, x(22|8)$", ops):
        out = f"{mn} {ops}"
    elif mn == "mov" and re.match(r"w0, #", ops):
        last_w0 = int(ops.split("#")[1].split(",")[0],0); out = f"{mn} {ops}"
    elif mn in ("orr","and","eor","bic","mov","movz","csel","cset","tst","cmp","lsl","bfi","bfxil","ubfx","cinc","csinc","ands","bics") and re.search(r"\bw(1|8|9|10|11|20|21|23|24)\b|\bx(20|21)\b", ops):
        out = f"{mn} {ops}"
    elif mn.startswith("b") and mn not in ("bl","blraa","bti","brk") and re.search(r"\b(w|x)(20|21|23)\b|^#", ops):
        out = f"{mn} {ops}"
    elif mn in ("b",) :
        out = f"{mn} {ops}"
    elif mn in ("cbz","cbnz","tbz","tbnz") and re.search(r"\b(w|x)(0|8|9|20|21|23|24|19)\b", ops):
        if "w8, #0xe" in ops or "w8, #0x1e" in ops: continue
        out = f"{mn} {ops}"
    elif mn in ("ret","retab"):
        out = "RET"
    elif mn == "ldr" and re.search(r"\[x19, #0x148\]", ops):
        continue
    elif mn in ("ldr","ldrb","str","strb") and re.search(r"\[x19, #0x[0-9a-f]+\]", ops):
        out = f"{mn} {ops}"
    if out:
        print(f"{lab:14s} {addr:x}: {out}")
    elif lab:
        print(f"{lab:14s} {addr:x}: ({mn} {ops})")
