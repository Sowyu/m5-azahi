"""Read-only: resolve AppleT6050TypeCPhy vtable slots to method symbols in the saved kernelcache."""
import struct, sys, re
from pathlib import Path
b = Path("probe/firmware-analysis/kernelcache.mac17j.macho").read_bytes()
def commands(offset):
    ncmds = struct.unpack_from("<I", b, offset + 16)[0]; q = offset + 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", b, q); yield cmd, q, size; q += size
segments=[]; symbols={}; want=set(sys.argv[1].split(","))
for cmd,q,size in commands(0):
    if cmd != 0x80000035: continue
    va, offset, nameoff, _ = struct.unpack_from("<QQII", b, q+8)
    entry = b[q+nameoff:q+size].split(b"\0")[0].decode()
    if entry not in want: continue
    for cc,r,sz in commands(offset):
        if cc == 0x19:
            segva, vmsize, fileoff, filesize = struct.unpack_from("<4Q", b, r+24); segments.append((segva,fileoff,filesize))
        if cc == 2:
            symoff,count,stroff,strsize = struct.unpack_from("<4I", b, r+8)
            for i in range(count):
                nameidx,ty,sect,desc,value = struct.unpack_from("<IBBHQ", b, symoff+16*i)
                if value==0 or not (ty&0xe): continue
                name=b[stroff+nameidx:b.find(b"\0",stroff+nameidx)].decode(errors="replace")
                symbols.setdefault(value,[]).append(name)
def read_va(va,size):
    for base,off,length in segments:
        if base<=va and va+size<=base+length: return b[off+va-base:off+va-base+size]
    raise ValueError(hex(va))
base = min(s[0] for s in segments)
vt = [v for v,n in symbols.items() if any(x==sys.argv[2] for x in n)]
print("vtable symbol", sys.argv[2], [hex(v) for v in vt], "kc base", hex(base))
vtva = vt[0]
for slot in [int(x,0) for x in sys.argv[3:]]:
    raw = struct.unpack_from("<Q", read_va(vtva+0x10+slot, 8))[0]
    tgt30 = raw & 0x3fffffff
    cand = [base + tgt30, 0xfffffe0007004000 + tgt30, raw & 0xffffffffffff | 0xfffffe0000000000, raw]
    names = []
    for c in cand:
        if c in symbols: names.append((hex(c), symbols[c]))
    print(f"slot {slot:#x}: raw {raw:#018x} -> {names}")
