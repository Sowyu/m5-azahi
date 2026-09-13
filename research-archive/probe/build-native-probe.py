#!/usr/bin/env python3
"""Assemble a RAM-only native boot test using an unchanged existing loader.

No loader code edits, installation, or disk writes on the target. The stock
initramfs has no root filesystem; reaching its shell is a bring-up milestone,
not a working native desktop. Run verify-native-candidate.py first.
"""
from pathlib import Path
import gzip
import hashlib
import runpy
import struct

root = Path(__file__).resolve().parent.parent
runpy.run_path(str(root / "probe/verify-native-candidate.py"))
with (root / "guest-hv-initrd.bin").open("rb") as source:
    prefix = source.read(64 << 20)
offset = prefix.index(b"chosen.bootargs=")
assert 0x10000 < offset < 4 << 20, offset
loader = prefix[:offset]
kernel = (root / "Image-baremetal.bin").read_bytes()
dtb = (root / "t6050-j714s-bare.dtb").read_bytes()
initrd = (root / "initramfs-asahi.img").read_bytes()
bootargs = (
    "console=tty0 fbcon=nodefer keep_bootcon debug ignore_loglevel "
    "initcall_debug maxcpus=1 arm64.nomte arm64.nosme cpuidle.off=1 "
    "pd_ignore_unused rd.shell rd.info rd.break=pre-udev "
    "rd.driver.blacklist=nvme_apple,apple_nvme,pinctrl_apple_gpio "
    "modprobe.blacklist=nvme_apple,apple_nvme,pinctrl_apple_gpio "
    "panic=0"
)
output = root / "native-probe-20260906.bin"
payload = (loader + b"chosen.bootargs=" + bootargs.encode() + b"\n" + dtb
           + gzip.compress(kernel, mtime=0)
           + b"m1n1_initramfs" + struct.pack("<I", len(initrd)) + initrd)
with output.open("xb") as target:
    target.write(payload)
print(f"UNCHANGED_LOADER_PREFIX bytes={len(loader)} sha256={hashlib.sha256(loader).hexdigest()}")
print(f"NATIVE_PROBE {output} bytes={len(payload)} sha256={hashlib.sha256(payload).hexdigest()}")
print("RAM boot test only; no target SSD/rootfs installation")
