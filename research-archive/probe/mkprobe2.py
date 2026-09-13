#!/usr/bin/env python3
"""Post-MMU paint-and-halt probe (design C).

mkprobe.py (design A) is ONLY valid for symbols that run with the MMU off
(primary_entry .. __enable_mmu): its stub at file offset 0x40 lives in the
Image header [_text,_stext), which is unmapped once the MMU is on (init
idmap and init_pg_dir both start at _stext), and the framebuffer PA is not
mapped either -> guaranteed false negative for any post-MMU symbol.

This probe works for ANY symbol executed after __enable_mmu (asm or C, boot
CPU) up to free_initmem():
  patch @ symbol: mask DAIF, install init_idmap_pg_dir in TTBR0 (identity
  map of the kernel image, kept alive until initmem is freed), br to the
  stub's PHYSICAL address.
  stub: placed in the zero padding after __idmap_text_end (mapped ROX by
  both the init and the permanent idmap), turns the MMU off (VA==PA there,
  so the fetch stream survives), paints, halts.

usage: mkprobe2.py <file_off_hex> <row> <color_hex> <outfile>
Constants below are for Image-asahi 7.0.13-400.asahi.fc44.aarch64+16k
loaded at phys 0x10800000000 (chainload path). Re-derive from System.map
for any other kernel: STUB_OFF = padding after __idmap_text_end,
IDMAP_PG = init_idmap_pg_dir (== __initdata_begin).
"""
import struct, subprocess, sys, os

AZ = "/PRIVATE-USER/PRIVATE-PROJECT/Azahi"
FB, STRIDE, WIDTH = 0x10fd310c000, 0x2f40, 3024
LOAD = 0x10800000000
STUB_OFF = 0x2a8a000          # zero padding: __idmap_text_end..idmap_pg_dir
STUB_MAX = 0x2a8c000 - STUB_OFF   # must not touch idmap_pg_dir @0x2a8c000
IDMAP_PG = LOAD + 0x2bd0000   # init_idmap_pg_dir (= __initdata_begin)
STUB_PA  = LOAD + STUB_OFF

def build(src):
    open("/tmp/p2.S", "w").write(src)
    env = dict(os.environ, PATH="/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:" + os.environ["PATH"])
    subprocess.run("clang --target=aarch64-linux-gnu -c -o /tmp/p2.o /tmp/p2.S", shell=True, check=True, env=env)
    subprocess.run("ld.lld -maarch64elf --image-base=0 --Ttext=0 -o /tmp/p2.elf /tmp/p2.o", shell=True, check=True, env=env)
    subprocess.run("llvm-objcopy -O binary /tmp/p2.elf /tmp/p2.bin", shell=True, check=True, env=env)
    return open("/tmp/p2.bin", "rb").read()

target = int(sys.argv[1], 16); row = int(sys.argv[2]); color = int(sys.argv[3], 16)
out = sys.argv[4]
addr = FB + row * STRIDE

def mat(reg, val):  # movz/movk an absolute 48-bit constant
    s = f"    movz {reg}, #{val & 0xffff}\n"
    for sh in (16, 32):
        s += f"    movk {reg}, #{(val >> sh) & 0xffff}, lsl #{sh}\n"
    return s

# patch planted AT the symbol (clobbers 13 insns; probe never returns)
patch = build(f"""
.section .text
.globl _p
_p:
    msr daifset, #0xf
{mat('x17', IDMAP_PG)}
    msr ttbr0_el1, x17
    isb
    tlbi vmalle1
    dsb nsh
    isb
{mat('x16', STUB_PA)}
    br x16
""")

# stub: entered at PA via the idmap; kill the MMU (PC is VA==PA), paint, halt
stub = build(f"""
.section .text
.globl _s
_s:
    mrs x0, sctlr_el1
    and x0, x0, #0xfffffffffffffffe
    msr sctlr_el1, x0
    isb
{mat('x1', addr)}
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
""")
assert len(stub) <= STUB_MAX, f"stub too big ({len(stub)})"

img = bytearray(open(f"{AZ}/Image-asahi", "rb").read())
assert img[STUB_OFF:STUB_OFF+len(stub)] == b"\0" * len(stub), "stub area not empty?!"
img[STUB_OFF:STUB_OFF+len(stub)] = stub
img[target:target+len(patch)] = patch
open(out, "wb").write(bytes(img))
print(f"post-MMU probe at {target:#x} ({len(patch)}B patch) -> stub PA {STUB_PA:#x} ({len(stub)}B), row {row}, colour {color:#x} -> {out}")
