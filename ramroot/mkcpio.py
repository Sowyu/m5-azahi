#!/usr/bin/env python3
"""
mkcpio.py - build a Linux newc cpio archive on macOS with correct metadata.

Why: extracting-and-repacking a rootfs on macOS destroys ownership (everything
becomes uid 501), which breaks systemd/dbus/polkit on boot.  This writes newc
headers directly, forcing uid/gid 0, and streams large files so multi-GB
payloads never sit in Python memory.

Manifest line formats (one entry per line, '#' comments allowed):
    dir   PATH [MODE]                  # default 0755
    file  PATH SRC [MODE]              # default 0644; SRC is a host path
    exec  PATH SRC                     # file with mode 0755
    slink PATH TARGET                  # symlink
    nod   PATH c|b MAJOR MINOR [MODE]  # device node, default 0600
    split PATH SRC CHUNK_MB            # SRC emitted as PATH.part000.. pieces

newc limits honoured: per-file size < 4 GiB (asserted); 'split' exists for
bigger sources.  Usage:  mkcpio.py manifest.txt output.cpio
"""
import sys, os, stat
if not __debug__: raise SystemExit('Refusing python -O: assert statements here are safety checks')

ALIGN = 4

class Writer:
    def __init__(self, f):
        self.f = f
        self.pos = 0
        self.ino = 721  # arbitrary, unique per entry

    def _w(self, b):
        self.f.write(b)
        self.pos += len(b)

    def _pad(self):
        r = (-self.pos) % ALIGN
        if r:
            self._w(b"\0" * r)

    def _header(self, name, mode, filesize, nlink=1, rdev=(0, 0)):
        assert filesize < 0x100000000, f"{name}: {filesize} exceeds newc 4GiB file limit"
        self.ino += 1
        fields = [self.ino, mode, 0, 0, nlink, 0, filesize,
                  0, 0, rdev[0], rdev[1], len(name) + 1, 0]
        hdr = b"070701" + b"".join(b"%08X" % x for x in fields)
        self._w(hdr + name.encode() + b"\0")
        self._pad()

    def dir(self, path, mode=0o755):
        self._header(path.lstrip("/"), stat.S_IFDIR | mode, 0, nlink=2)

    def symlink(self, path, target):
        t = target.encode()
        self._header(path.lstrip("/"), stat.S_IFLNK | 0o777, len(t))
        self._w(t)
        self._pad()

    def node(self, path, kind, major, minor, mode=0o600):
        typ = stat.S_IFCHR if kind == "c" else stat.S_IFBLK
        self._header(path.lstrip("/"), typ | mode, 0, rdev=(major, minor))

    def file(self, path, src, mode=0o644, offset=0, length=None):
        size = os.path.getsize(src)
        if length is None:
            length = size - offset
        self._header(path.lstrip("/"), stat.S_IFREG | mode, length)
        with open(src, "rb") as f:
            f.seek(offset)
            left = length
            while left:
                chunk = f.read(min(1 << 22, left))
                assert chunk, f"short read on {src}"
                self._w(chunk)
                left -= len(chunk)
        self._pad()

    def trailer(self):
        self._header("TRAILER!!!", 0, 0)
        # pad archive to 512 for tidiness (kernel doesn't require it)
        r = (-self.pos) % 512
        if r:
            self._w(b"\0" * r)


def ensure_parents(w, path, seen):
    parts = path.lstrip("/").split("/")[:-1]
    cur = ""
    for p in parts:
        cur = f"{cur}/{p}" if cur else p          # no leading slash: must
        if cur not in seen:                        # match the 'dir' branch key
            seen.add(cur)
            w.dir(cur)


def main(manifest, out):
    seen = set()
    with open(out, "wb") as f:
        w = Writer(f)
        for ln in open(manifest):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            t = ln.split()
            kind = t[0]
            if kind == "dir":
                ensure_parents(w, t[1] + "/x", seen)
                if t[1].lstrip("/") not in seen:
                    seen.add(t[1].lstrip("/"))
                    w.dir(t[1], int(t[2], 8) if len(t) > 2 else 0o755)
            elif kind in ("file", "exec"):
                ensure_parents(w, t[1], seen)
                mode = 0o755 if kind == "exec" else (int(t[3], 8) if len(t) > 3 else 0o644)
                w.file(t[1], t[2], mode)
            elif kind == "slink":
                ensure_parents(w, t[1], seen)
                w.symlink(t[1], t[2])
            elif kind == "nod":
                ensure_parents(w, t[1], seen)
                w.node(t[1], t[2], int(t[3]), int(t[4]),
                       int(t[5], 8) if len(t) > 5 else 0o600)
            elif kind == "split":
                src, chunk_mb = t[2], int(t[3])
                size = os.path.getsize(src)
                chunk = chunk_mb << 20
                n = (size + chunk - 1) // chunk
                for i in range(n):
                    name = f"{t[1]}.part{i:03d}"
                    ensure_parents(w, name, seen)
                    length = min(chunk, size - i * chunk)
                    w.file(name, src, offset=i * chunk, length=length)
                print(f"  split {src}: {n} pieces of <= {chunk_mb} MiB", file=sys.stderr)
            else:
                sys.exit(f"bad manifest line: {ln}")
        w.trailer()
    print(f"wrote {out}: {os.path.getsize(out)} bytes", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
