#!/usr/bin/env python3
"""Reuse the verified input RAM root with the exact native kernel candidate.

Loader code and existing initramfs stay byte-for-byte unchanged. Never
install this payload; it is a one-boot RAM test with no SSD device nodes.
"""
from pathlib import Path
import gzip
import hashlib
import io
import runpy
import shutil
import struct
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
runpy.run_path(str(root / "probe/verify-native-candidate.py"))
source_path = root / "guest-hv-input-v2power.bin"
output_path = root / "native-input-v2-20260906.bin"
sys.path.insert(0, str(root / "ramroot"))
from mkcpio import Writer, ensure_parents
archive = io.BytesIO()
writer = Writer(archive)
seen = set()
for name, local in (
    ("usr/local/bin/native-input-check", "native-input-check.sh"),
    ("etc/systemd/system/native-input-check.service", "native-input-check.service"),
):
    name = "ramroot/sysroot-overlay/" + name
    ensure_parents(writer, name, seen)
    writer.file(name, root / "probe" / local)
link = "ramroot/sysroot-overlay/etc/systemd/system/multi-user.target.wants/native-input-check.service"
ensure_parents(writer, link, seen)
writer.symlink(link, "../native-input-check.service")
writer.trailer()
extra = subprocess.run(["zstd", "-q", "-c"], input=archive.getvalue(), capture_output=True, check=True).stdout
dtb = (root / "t6050-j714s-native-input.dtb").read_bytes()
assert b"earlycon=" not in dtb
assert b"console=ttySAC0" not in dtb
assert b"nvme" not in dtb
bootargs = (
    "console=tty0 fbcon=nodefer fbcon=font:TER16x32 ignore_loglevel "
    "maxcpus=1 arm64.nomte arm64.nosme cpuidle.off=1 pd_ignore_unused "
    "root=/dev/loop0 rootfstype=btrfs rw selinux=0 plymouth.enable=0 "
    "modprobe.blacklist=pinctrl_apple_gpio,nvme_apple,apple_nvme "
    "rd.driver.blacklist=pinctrl_apple_gpio,nvme_apple,apple_nvme "
    "systemd.mask=boot.mount systemd.mask=boot-efi.mount "
    "systemd.mask=initial-setup.service systemd.mask=udisks2.service "
    "systemd.mask=serial-getty@ttySAC0.service panic=0"
    " module_blacklist=macsmc_power,macsmc_input,macsmc_hwmon,rtc_macsmc"
)
with source_path.open("rb") as source:
    header = source.read(64 << 20)
    args_start = header.index(b"chosen.bootargs=")
    dtb_start = header.index(b"\n", args_start) + 1
    assert header[dtb_start:dtb_start+4] == bytes.fromhex("d00dfeed")
    kernel_start = dtb_start + struct.unpack_from(">I", header, dtb_start+4)[0]
    marker = header.index(b"m1n1_initramfs", kernel_start)
    initrd_start = marker + len(b"m1n1_initramfs") + 4
    size = struct.unpack_from("<I", header, initrd_start-4)[0]
    assert initrd_start + size == source_path.stat().st_size
    kernel = gzip.compress((root / "Image-baremetal.bin").read_bytes(), mtime=0)
    new_header = (header[:args_start] + b"chosen.bootargs=" + bootargs.encode()
                  + b"\n" + dtb + kernel + b"m1n1_initramfs"
                  + struct.pack("<I", size + len(extra)))
    with output_path.open("xb") as output:
        output.write(new_header)
        source.seek(initrd_start)
        shutil.copyfileobj(source, output)
        output.write(extra)
with source_path.open("rb") as source, output_path.open("rb") as output:
    source.seek(initrd_start)
    output.seek(len(new_header))
    while data := source.read(1 << 20):
        assert output.read(len(data)) == data
    assert output.read() == extra
with output_path.open("rb") as output:
    digest = hashlib.file_digest(output, "sha256").hexdigest()
print(f"NATIVE_INPUT_INITRD_UNCHANGED bytes={size}")
print(f"NATIVE_INPUT_IMAGE {output_path} bytes={output_path.stat().st_size} sha256={digest}")
