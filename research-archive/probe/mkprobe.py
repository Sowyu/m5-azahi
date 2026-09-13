#!/usr/bin/env python3
"""Plant a paint-and-halt breadcrumb at a kernel symbol.
   usage: mkprobe.py <file_off_hex> <row> <color_hex> <outfile>
   Paints 96 rows starting at <row>, then halts. Clobbers registers freely
   because it never returns - so the result is unambiguous."""
import struct, subprocess, sys, os
AZ = "/PRIVATE-USER/PRIVATE-PROJECT/Azahi"
FB, STRIDE, WIDTH = 0x10fd310c000, 0x2f40, 3024
STUB_OFF = 0x40                     # unused PE-header space in a DT boot

target = int(sys.argv[1], 16); row = int(sys.argv[2]); color = int(sys.argv[3], 16)
out = sys.argv[4]
addr = FB + row * STRIDE
asm = f"""
.section .text
.globl _s
_s:
    movz x1, #{addr & 0xffff}
    movk x1, #{(addr >> 16) & 0xffff}, lsl #16
    movk x1, #{(addr >> 32) & 0xffff}, lsl #32
    mov  x2, #96
    movz x4, #{STRIDE}
1:  mov  x3, #{WIDTH}
    mov  x5, x1
2:  movz w6, #{color & 0xffff}
    movk w6, #{(color >> 16) & 0xffff}, lsl #16
    str  w6, [x5], #4
    subs x3, x3, #1
    b.ne 2b
    add  x1, x1, x4
    subs x2, x2, #1
    b.ne 1b
3:  wfe
    b    3b
"""
open("/tmp/p.S","w").write(asm)
env = dict(os.environ, PATH="/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:" + os.environ["PATH"])
subprocess.run("clang --target=aarch64-linux-gnu -c -o /tmp/p.o /tmp/p.S", shell=True, check=True, env=env)
subprocess.run("ld.lld -maarch64elf --image-base=0 --Ttext=0 -o /tmp/p.elf /tmp/p.o", shell=True, check=True, env=env)
subprocess.run("llvm-objcopy -O binary /tmp/p.elf /tmp/p.bin", shell=True, check=True, env=env)
stub = open("/tmp/p.bin","rb").read()
assert len(stub) <= 0x1c0, f"stub too big ({len(stub)})"

img = bytearray(open(f"{AZ}/Image-asahi","rb").read())
img[STUB_OFF:STUB_OFF+len(stub)] = stub
# redirect the target symbol's first instruction to the stub
off = (STUB_OFF - target) // 4
struct.pack_into("<I", img, target, 0x14000000 | (off & 0x03FFFFFF))
open(out,"wb").write(bytes(img))
print(f"probe at {target:#x} -> stub {STUB_OFF:#x} ({len(stub)} B), row {row}, colour {color:#x} -> {out}")
