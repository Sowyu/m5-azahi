#!/usr/bin/env python3
"""Assemble native KDE in RAM using the verified input payload and existing KDE archive.

Only replace the minimal RAM-root archive, preserving the stock initramfs
and all existing input firmware/module overlays exactly. Never install or
chainload this large image; use boot-native.py's fixed-address transfer.
"""
from pathlib import Path
import hashlib
import io
import shutil
import struct
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "ramroot"))
from mkcpio import Writer, ensure_parents
input_image = root / "native-input-v2-20260906.bin"
output_image = root / "native-kde-20260906.bin"
stock = root / "initramfs-asahi.img"
minimal = root / "ramroot/work/ramroot.cpio.zst"
kde = root / "ramroot/work-kde/ramroot.cpio.zst"
with input_image.open("rb") as source:
    head = source.read(64 << 20)
dt_start = head.index(b"\n", head.index(b"chosen.bootargs=")) + 1
kernel_start = dt_start + struct.unpack_from(">I", head, dt_start+4)[0]
marker = head.index(b"m1n1_initramfs", kernel_start)
start = marker + len(b"m1n1_initramfs") + 4
size = struct.unpack_from("<I", head, start-4)[0]
assert start + size == input_image.stat().st_size
with input_image.open("rb") as source:
    source.seek(start)
    for original in (stock, minimal):
        with original.open("rb") as reference:
            while data := reference.read(4 << 20):
                assert source.read(len(data)) == data, f"Input initramfs differs from {original}"
    input_overlays = source.read()
assert 0 < len(input_overlays) < 4 << 20

archive = io.BytesIO()
writer = Writer(archive)
seen = set()
for target, source in (
    ("root/.bash_profile", "native-kde-profile.sh"),
    ("usr/local/bin/native-kde-start", "native-kde-start.sh"),
    ("usr/local/bin/basic-kde-session", "basic-kde-session.sh"),
    ("mnt/inputfiles/bringup-20260906/basic-kde-clients.sh", "basic-kde-clients.sh"),
):
    target = "ramroot/sysroot-overlay/" + target
    ensure_parents(writer, target, seen)
    writer.file(target, root / "probe" / source)
writer.trailer()
extra = subprocess.run(["zstd", "-q", "-c"], input=archive.getvalue(), capture_output=True, check=True).stdout
new_size = stock.stat().st_size + kde.stat().st_size + len(input_overlays) + len(extra)
assert new_size < 0xffffffff
# Keep all existing exclusions and explicitly preserve the required SMC guard.
arg_start = head.index(b"chosen.bootargs=")
bootargs = head[arg_start:dt_start-1].decode().split("=", 1)[1]
bootargs += (" module_blacklist=macsmc_power,macsmc_input,macsmc_hwmon,rtc_macsmc"
             " systemd.mask=uinject.service systemd.mask=bluetooth.service"
             " systemd.mask=initial-setup-graphical.service drm.panic_screen=qr_code")
new_head = (head[:arg_start] + b"chosen.bootargs=" + bootargs.encode() + b"\n"
            + head[dt_start:marker] + b"m1n1_initramfs" + struct.pack("<I", new_size))
with output_image.open("xb") as output:
    output.write(new_head)
    for source in (stock, kde):
        with source.open("rb") as data:
            shutil.copyfileobj(data, output)
    output.write(input_overlays)
    output.write(extra)
assert output_image.stat().st_size == len(new_head) + new_size
with output_image.open("rb") as output:
    digest = hashlib.file_digest(output, "sha256").hexdigest()
print(f"NATIVE_KDE_IMAGE {output_image} bytes={output_image.stat().st_size} sha256={digest}")
print(f"NATIVE_KDE_INITRD bytes={new_size}; input overlays preserved bytes={len(input_overlays)}")
print("RAM-only native test. No SSD installation or GPU acceleration claim.")
