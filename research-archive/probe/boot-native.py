#!/usr/bin/env python3
"""RAM-only native boot via existing APIs and the established T6050 memory fence.

No hypervisor. No disk operations, MMIO scans, loader source/binary patches,
or huge staging allocation. First chainload the unchanged prefix extracted
from the tested native payload with --extract-loader.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("image", type=Path)
parser.add_argument("--extract-loader", type=Path)
parser.add_argument("--panic-screen", choices=("qr_code", "kmsg", "user"), default="qr_code")
parser.add_argument("--offline", action="store_true", help="Validate payload and RAM layout without connecting")
ssd_mode = parser.add_mutually_exclusive_group()
ssd_mode.add_argument("--ssd-readonly", action="store_true", help="Require the pinned native SSD read-only diagnostic")
ssd_mode.add_argument("--rootguard-test", action="store_true", help="Pinned RAM diagnostic: bounded root-padding write/restore")
ssd_mode.add_argument("--ssd-root", action="store_true", help="Verified fixed-root guard with actual SSD root filesystem")
args = parser.parse_args()
with args.image.open("rb") as source:
    head = source.read(64 << 20)
arg_start = head.index(b"chosen.bootargs=")
dt_start = head.index(b"\n", arg_start) + 1
assert head[dt_start:dt_start+4] == bytes.fromhex("d00dfeed")
dt_size = struct.unpack_from(">I", head, dt_start+4)[0]
kernel_start = dt_start + dt_size
marker = head.index(b"m1n1_initramfs", kernel_start)
initrd_start = marker + len(b"m1n1_initramfs") + 4
initrd_size = struct.unpack_from("<I", head, initrd_start-4)[0]
assert initrd_start + initrd_size == args.image.stat().st_size
prefix_hash = hashlib.sha256(head[:arg_start]).hexdigest()
if args.extract_loader:
    assert prefix_hash == "ecffcf08622e64ad616d7b4e4bd6050cca44c9647df311ffb20efcc8f792a604"
    with args.extract_loader.open("xb") as output:
        output.write(head[:arg_start])
    print("UNCHANGED_NATIVE_LOADER_EXTRACTED", args.extract_loader)
    raise SystemExit(0)
assert prefix_hash in ("ecffcf08622e64ad616d7b4e4bd6050cca44c9647df311ffb20efcc8f792a604",
                       "3ca38299f547ec792f343aa0b0604ba54a462587ac9cace701360c30a9879cd3")

kernel = gzip.decompress(head[kernel_start:marker])
assert hashlib.sha256(kernel).hexdigest() == "d2ec67ab79aea96292869f66e83c50d0fdb354d237d9787a9d6c238f0b7bffe7"
dtb = head[dt_start:kernel_start]
bootargs = head[arg_start:dt_start-1].decode().split("=", 1)[1]
bootargs += " drm.panic_screen=" + args.panic_screen
required_blacklist = {"macsmc_power", "macsmc_input", "macsmc_hwmon", "rtc_macsmc"}
present_blacklist = set()
for token in bootargs.split():
    if token.startswith("module_blacklist="):
        present_blacklist.update(token.split("=", 1)[1].split(","))
if not required_blacklist <= present_blacklist:
    # The working input payload requires these exclusions; keep the SMC core
    # and GPIO driver available for MTP, not the unsafe power/sensor clients.
    bootargs += " module_blacklist=" + ",".join(sorted(required_blacklist | present_blacklist))
assert required_blacklist <= set(next(token.split("=", 1)[1] for token in reversed(bootargs.split())
                                     if token.startswith("module_blacklist=")).split(","))
assert "earlycon" not in bootargs and "ttySAC0" not in bootargs.replace("systemd.mask=serial-getty@ttySAC0.service", "")
if args.ssd_readonly:
    manifest = json.loads(args.image.with_suffix('.json').read_text())
    assert manifest['readonly'] is True and manifest['base_initrd_unchanged'] is True
    assert manifest['modules'] == {
        'nvme-apple': '94755503e7677412fa63e23cbe42c03cc9c2a44308abeea1aa930c021e55b46e',
        'apple-sart': '58ba58e4a6dd0b4574751d224772d9bfe447fa3f4e8bdba8cfa9e7c52b80305d',
    }
    with args.image.open('rb') as source:
        assert hashlib.file_digest(source, 'sha256').hexdigest() == manifest['image_sha256']
    assert hashlib.sha256(dtb).hexdigest() == manifest['dtb_sha256']
    assert b'azahi,j714s-nvme-readonly\0' in dtb and b'azahi,j714s-sart-v4\0' in dtb
    assert b'apple,t8103-nvme-ans2\0' not in dtb
    assert 'azahi.native_ssd_ro=1' in bootargs
    for unit in ('home.mount', 'systemd-repart.service', 'systemd-repart.socket', 'udisks2.service'):
        assert 'systemd.mask=' + unit in bootargs
elif args.rootguard_test:
    manifest = json.loads(args.image.with_suffix('.json').read_text())
    assert manifest['rootguard'] is True and manifest['write_test_only'] is True
    assert manifest['base_initrd_unchanged'] is True
    assert manifest['modules'] == {
        'nvme-apple': '696d0fded6a47bb9929e1f49b1a38d166d6c539e573696c3c206b84c13c6708c',
        'apple-sart': '58ba58e4a6dd0b4574751d224772d9bfe447fa3f4e8bdba8cfa9e7c52b80305d',
    }
    assert manifest['test'] == dict(partuuid='PRIVATE-UUID-REMOVED',
                                    offset=32 << 30, bytes=16384)
    with args.image.open('rb') as source:
        assert hashlib.file_digest(source, 'sha256').hexdigest() == manifest['image_sha256']
    assert hashlib.sha256(dtb).hexdigest() == manifest['dtb_sha256']
    assert b'azahi,j714s-nvme-rootguard\0' in dtb and b'azahi,j714s-sart-v4\0' in dtb
    assert b'azahi,j714s-nvme-readonly\0' not in dtb and b'apple,t8103-nvme-ans2\0' not in dtb
    assert 'azahi.native_rootguard_test=1' in bootargs.split()
    assert 'root=/dev/loop0' in bootargs.split() and 'maxcpus=1' in bootargs.split()
    assert not any('root_write_armed' in token for token in bootargs.split())
    for unit in ('boot.mount', 'boot-efi.mount', 'home.mount', 'systemd-repart.service',
                 'systemd-repart.socket', 'udisks2.service'):
        assert 'systemd.mask=' + unit in bootargs
elif args.ssd_root:
    manifest = json.loads(args.image.with_suffix('.json').read_text())
    assert manifest['ssd_root'] is True and manifest['ram_root_image'] is False
    assert manifest['initrd_bytes'] == initrd_size and initrd_size < 100 << 20
    assert manifest['modules'] == {
        'nvme-apple': '696d0fded6a47bb9929e1f49b1a38d166d6c539e573696c3c206b84c13c6708c',
        'apple-sart': '58ba58e4a6dd0b4574751d224772d9bfe447fa3f4e8bdba8cfa9e7c52b80305d',
    }
    with args.image.open('rb') as source:
        assert hashlib.file_digest(source, 'sha256').hexdigest() == manifest['image_sha256']
    assert hashlib.sha256(dtb).hexdigest() == manifest['dtb_sha256'] == 'ddd855503c88b8b3b0afe64b4f3862dee2ec328c347b6c7eca5664bdf1fee5f8'
    assert b'azahi,j714s-nvme-rootguard\0' in dtb
    for token in ('root=PARTUUID=PRIVATE-UUID-REMOVED',
                  'rootflags=subvol=root,nodiscard', 'azahi.ssd_root=1', 'maxcpus=1'):
        assert token in bootargs.split()
    assert 'root=/dev/loop0' not in bootargs and 'root_write_armed' not in bootargs
    if manifest.get('diagnostic_console') == 2:
        assert 'azahi.ssd_diagnostics=2' in bootargs.split()
        assert 'loglevel=3' in bootargs.split() and 'ignore_loglevel' not in bootargs.split()
    for unit in ('boot.mount', 'boot-efi.mount', 'home.mount', 'systemd-repart.service',
                 'systemd-repart.socket', 'udisks2.service', 'fstrim.service', 'fstrim.timer'):
        assert 'systemd.mask=' + unit in bootargs.split()
else:
    assert b"nvme" not in dtb
KERNEL, DTB, INITRD = 0x10800000000, 0x10900000000, 0x10a00000000
LOW, HIGH = 0x1010a960000, 0x10f4ab00000
for base, size in ((KERNEL, len(kernel)), (DTB, len(dtb)), (INITRD, initrd_size)):
    assert LOW <= base < base + size <= HIGH
assert KERNEL + len(kernel) < DTB and DTB + len(dtb) < INITRD
if args.offline:
    print(f"NATIVE_LAYOUT_PASS kernel={KERNEL:#x}+{len(kernel):#x} "
          f"dtb={DTB:#x}+{len(dtb):#x} initrd={INITRD:#x}+{initrd_size:#x}")
    print("BOOTARGS", bootargs)
    raise SystemExit(0)

sys.path[:0] = ["/PRIVATE-USER/azahi/lib", "/PRIVATE-USER/azahi/proxyclient"]
os.environ["M1N1DEVICE"] = "/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED"
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port
signal.alarm(900)
iface = UartInterface()
iface.dev.timeout = 15
iface.dev.write_timeout = 15
try:
    proxy = M1N1Proxy(iface)
    bootstrap_port(iface, proxy)
    util = ProxyUtils(proxy, heap_size=128 << 20)
    assert util.adt["/chosen"].chip_id == 0x6050
    assert (util.mrs("MPIDR_EL1") & 0xffffff) == 0x40000
    assert util.heap_top < LOW
    assert not any(proxy.smp_is_alive(cpu) for cpu in range(18))
    if args.ssd_readonly or args.rootguard_test or args.ssd_root:
        import runpy
        prepare_ans = runpy.run_path(str(Path(__file__).with_name('prepare-native-ans.py')))['prepare']
        prepare_ans(proxy, util, activate=True)
    for base, blob, label in ((KERNEL, kernel, "KERNEL"), (DTB, dtb, "DTB")):
        iface.writemem(base, blob)
        assert iface.readmem(base, 64) == blob[:64]
        assert iface.readmem(base + len(blob)-64, 64) == blob[-64:]
        proxy.dc_cvau(base, len(blob))
        print(f"NATIVE_{label}_LOADED {base:#x} bytes={len(blob)}", flush=True)
    proxy.ic_ivau(KERNEL, len(kernel))
    with args.image.open("rb") as source:
        source.seek(initrd_start)
        position = 0
        while position < initrd_size:
            chunk = source.read(min(8 << 20, initrd_size-position))
            assert chunk
            iface.writemem(INITRD + position, chunk)
            assert iface.readmem(INITRD + position + len(chunk)-32, 32) == chunk[-32:]
            position += len(chunk)
            if position % (64 << 20) == 0 or position == initrd_size:
                print(f"NATIVE_INITRD_TRANSFER {position}/{initrd_size}", flush=True)
    proxy.dc_cvau(INITRD, initrd_size)
    proxy.kboot_set_initrd(INITRD, initrd_size)
    proxy.kboot_set_chosen("bootargs", bootargs)
    # Establish boot_cpu_idx through the loader's bounded path; no SMP calls
    # or claim that the secondary cores work. This boot stays maxcpus=1.
    proxy.smp_set_wfe_mode(True)
    proxy.smp_start_secondaries()
    assert not any(proxy.smp_is_alive(cpu) for cpu in range(18))
    assert proxy.dapf_init("/arm-io/dart-mtp") == 0
    assert proxy.kboot_prepare_dt(DTB) == 0
    print("NATIVE_HANDOFF_READY; expect USB proxy to disappear, inspect panel", flush=True)
    util.msr("DAIF", 0xc0)
    proxy.kboot_boot(KERNEL)
    # P_KBOOT_BOOT itself exits the proxy into next_stage on success.
    print("NATIVE_HANDOFF_SENT; panel verification required", flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
