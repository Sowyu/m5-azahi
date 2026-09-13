#!/usr/bin/env python3
"""Explicit NVMe probe with automounters blocked and all namespaces read-only.

Run inside the RAM-root guest. Does not mount, format, fsck, or write disk data.
"""
import glob
from pathlib import Path
import subprocess
import time

def run(*argv, timeout=10, check=True):
    print("SSD_CMD", *argv, flush=True)
    return subprocess.run(argv, timeout=timeout, check=check)

if glob.glob("/sys/block/nvme*"):
    raise SystemExit("Refusing an uncontrolled re-probe: NVMe block devices already exist")
run("systemctl", "mask", "--runtime", "--now", "systemd-repart.service", "systemd-repart.socket")
for unit in ("boot.mount", "boot-efi.mount", "home.mount", "udisks2.service"):
    result = subprocess.run(["systemctl", "is-enabled", unit], capture_output=True, text=True)
    if result.stdout.strip() not in ("masked", "masked-runtime"):
        raise SystemExit(f"Expected {unit} masked, got {result.stdout!r}")

run("udevadm", "control", "--stop-exec-queue")
readonly = set()
try:
    run("modprobe", "nvme_apple", timeout=15)
    deadline = time.monotonic() + 45
    first = None
    while time.monotonic() < deadline:
        disks = sorted(Path("/sys/block").glob("nvme*n*"))
        for disk in disks:
            if disk.name not in readonly:
                run("blockdev", "--setro", "/dev/" + disk.name, timeout=5)
                assert (disk / "ro").read_text().strip() == "1"
                readonly.add(disk.name)
                print("SSD_READONLY", disk.name, flush=True)
                first = first or time.monotonic()
        if first and time.monotonic() - first > 2:
            break
        time.sleep(.05)
    if not readonly:
        raise RuntimeError("No NVMe namespace appeared within 45 seconds")
finally:
    run("udevadm", "control", "--start-exec-queue", check=False)

run("udevadm", "settle", "--timeout=10", timeout=12, check=False)
run("lsblk", "-o", "NAME,PATH,SIZE,TYPE,RO,FSTYPE,LABEL,PARTLABEL,PARTUUID,MOUNTPOINTS")
for name in sorted(readonly):
    if not Path("/sys/block", name).exists():
        raise RuntimeError(f"{name} disappeared during probe; not a successful SSD result")
    run("sfdisk", "--json", "/dev/" + name, timeout=10, check=False)
print("SSD_READONLY_PROBE_DONE", flush=True)
