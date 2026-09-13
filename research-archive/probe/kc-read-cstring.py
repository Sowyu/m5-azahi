import struct, sys
from pathlib import Path
b = Path("probe/firmware-analysis/kernelcache.mac17j.macho").read_bytes()
def commands(offset):
    ncmds = struct.unpack_from("<I", b, offset + 16)[0]; q = offset + 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", b, q); yield cmd, q, size; q += size
segments=[]
for cmd,q,size in commands(0):
    if cmd != 0x80000035: continue
    va, offset, nameoff, _ = struct.unpack_from("<QQII", b, q+8)
    entry = b[q+nameoff:q+size].split(b"\0")[0].decode()
    if entry not in ("com.apple.driver.AppleT6050TypeCPhy",): continue
    for cc,r,sz in commands(offset):
        if cc == 0x19:
            segva, vmsize, fileoff, filesize = struct.unpack_from("<4Q", b, r+24); segments.append((segva,fileoff,filesize))
def read_va(va,size):
    for base,off,length in segments:
        if base<=va and va+size<=base+length: return b[off+va-base:off+va-base+size]
    raise ValueError(hex(va))
for a in sys.argv[1:]:
    va = int(a,0); raw = read_va(va, 96)
    print(hex(va), raw.split(b"\0")[0])
