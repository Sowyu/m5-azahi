#!/usr/bin/env python3
"""RAM-root-only test: 16 KiB write/flush/read/restore in unused root space.

Never mount any SSD filesystem writable. Never issue negative write tests to
protected regions. The kernel's fixed-LBA guard, not these checks alone,
restricts writes. Hardware correctness remains experimental.
"""
import hashlib
import json
import mmap
import os
from pathlib import Path
import stat
import struct
import subprocess
import uuid

DISK_BYTES = 1000555581440
ROOT_START = 835723767808
ROOT_BYTES = 158779572224
ROOT_UUID = 'PRIVATE-UUID-REMOVED'
FS_UUID = 'PRIVATE-UUID-REMOVED'
IMAGE_BYTES = 14248030208
TEST_OFFSET = 32 << 30
TEST_BYTES = 16384
PARAM = Path('/sys/module/nvme_apple/parameters/root_write_armed')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(*args):
    print('ROOTGUARD_CMD', *args, flush=True)
    subprocess.run(args, check=True, timeout=20)


def read_at(fd, offset, length):
    require(offset % 4096 == 0 and length % 4096 == 0, 'Unaligned verification region')
    with mmap.mmap(-1, length) as buffer:
        require(os.preadv(fd, [buffer], offset) == length, 'Short direct device read')
        return buffer[:]


def check_superblock(data):
    sb = data[65536:69632]
    require(len(sb) == 4096 and sb[64:72] == b'_BHRfS_M', 'Btrfs superblock absent')
    require(str(uuid.UUID(bytes=bytes(sb[32:48]))) == FS_UUID, 'Wrong filesystem UUID')
    require(struct.unpack_from('<Q', sb, 112)[0] == IMAGE_BYTES, 'Unexpected Btrfs total_bytes')
    require(struct.unpack_from('<Q', sb, 136)[0] == 1, 'Not a single-device filesystem')
    require(struct.unpack_from('<II', sb, 144) == (4096, 16384), 'Wrong Btrfs geometry')
    require(IMAGE_BYTES < TEST_OFFSET < TEST_OFFSET + TEST_BYTES <= ROOT_BYTES,
            'Test is not beyond filesystem and inside root partition')


def verify_regions(fd, manifest):
    for item in manifest['regions']:
        data = read_at(fd, item['offset'], item['bytes'])
        require(hashlib.sha256(data).hexdigest() == item['sha256'],
                'SSD region differs: ' + item['name'])
        if item['name'] == 'root-prefix':
            check_superblock(data)
        print('ROOTGUARD_READ_VERIFIED', item['name'], flush=True)


def direct_read(fd, offset):
    with mmap.mmap(-1, TEST_BYTES) as buffer:
        require(os.preadv(fd, [buffer], offset) == TEST_BYTES, 'Short direct read')
        return buffer[:]


def direct_write(fd, offset, data):
    require(len(data) == TEST_BYTES and offset == TEST_OFFSET, 'Invalid bounded test write')
    with mmap.mmap(-1, TEST_BYTES) as buffer:
        buffer[:] = data
        require(os.pwritev(fd, [buffer], offset) == TEST_BYTES, 'Short direct write')
    os.fsync(fd)  # real synchronous NVMe flush; no early-ack/deferred patch


def exercise(fd, backup_path):
    old = direct_read(fd, TEST_OFFSET)
    with backup_path.open('xb') as backup:
        backup.write(old)
    pattern = hashlib.shake_256(b'azahi-rootguard-padding-v1').digest(TEST_BYTES)
    require(pattern != old, 'Test pattern unexpectedly matches old bytes')
    # Restore even if write/fsync/readback fails. If controller dies, only
    # padding outside the current filesystem may retain the test pattern.
    try:
        direct_write(fd, TEST_OFFSET, pattern)
        require(direct_read(fd, TEST_OFFSET) == pattern, 'Native direct read-back differs')
        print('ROOTGUARD_NATIVE_WRITE_FLUSH_READ_PASS', flush=True)
    finally:
        direct_write(fd, TEST_OFFSET, old)
        require(direct_read(fd, TEST_OFFSET) == old, 'PADDING RESTORE FAILED')
        print('ROOTGUARD_PADDING_RESTORED', flush=True)


def main():
    require(os.geteuid() == 0, 'Root required')
    require(os.uname().machine == 'aarch64', 'Target Linux only')
    model = Path('/proc/device-tree/compatible').read_bytes().split(b'\0')
    require(b'apple,j714s' in model, 'Wrong machine')
    require('azahi.native_rootguard_test=1' in Path('/proc/cmdline').read_text().split(),
            'Missing explicit test boot argument')
    root_source = subprocess.check_output(['findmnt', '-n', '-o', 'SOURCE', '/'], text=True).strip()
    require(root_source.startswith('/dev/loop0'), 'This test requires the established RAM root')
    require(PARAM.read_text().strip() == 'N', 'Driver is already armed')
    manifest = json.loads(Path('/usr/local/libexec/native-rootguard-regions.json').read_text())
    disks = list(Path('/sys/block').glob('nvme*n*'))
    main_disks = [d for d in disks if int((d / 'size').read_text()) * 512 == DISK_BYTES]
    require(len(main_disks) == 1, 'Main namespace not uniquely identified by exact capacity')
    disk = main_disks[0]
    for d in disks:
        require((d / 'ro').read_text().strip() == '1', 'Namespace not read-only')
        require(int((d / 'stat').read_text().split()[6]) == 0, 'Unexpected prior namespace writes')
    nsids = [p for p in (disk / 'nsid', disk / 'device/nsid') if p.exists()]
    require(nsids and all(int(p.read_text()) == 1 for p in nsids), 'Main namespace NSID is not 1')
    require(int((disk / 'queue/logical_block_size').read_text()) == 4096, 'Not 4K logical blocks')
    root = Path('/dev/disk/by-partuuid') / ROOT_UUID
    require(root.exists(), 'Root PARTUUID absent')
    root = root.resolve(strict=True)
    require(stat.S_ISBLK(root.stat().st_mode), 'Root is not a block device')
    sysroot = Path('/sys/class/block', root.name).resolve(strict=True)
    require(sysroot.parent == disk.resolve(), 'Root belongs to wrong namespace')
    require(int((sysroot / 'start').read_text()) * 512 == ROOT_START, 'Wrong root start')
    require(int((sysroot / 'size').read_text()) * 512 == ROOT_BYTES, 'Wrong root size')
    # Reject any mounted/swap NVMe volume; do not unmount someone else's data.
    mountinfo = Path('/proc/self/mountinfo').read_text().splitlines()
    swaps = Path('/proc/swaps').read_text()
    for node in [*disks, *Path('/sys/class/block').glob('nvme*n*p*')]:
        devno = (node / 'dev').read_text().strip()
        require(not any(line.split()[2] == devno for line in mountinfo), 'NVMe filesystem mounted')
        require('/dev/' + node.name not in swaps, 'NVMe swap active')
    disk_fd = os.open('/dev/' + disk.name, os.O_RDONLY | os.O_DIRECT | os.O_CLOEXEC)
    try:
        verify_regions(disk_fd, manifest)
        # Compare protected partition headers within THIS native boot, not
        # against stale Recovery filesystem state. Reads only; never open
        # the whole namespace or a protected partition for writing.
        protected = {lba: read_at(disk_fd, lba * 4096, 4096)
                     for lba in (6, 140806, 180465551, 242965551)}
    finally:
        os.close(disk_fd)
    print('ROOTGUARD_IDENTITIES_VERIFIED; bounded padding test only', flush=True)
    root_fd = None
    try:
        # Clearing namespace RO propagates to partitions; re-protect every
        # other partition before arming the independent command-level filter.
        run('blockdev', '--setrw', '/dev/' + disk.name)
        for part in disk.glob(disk.name + 'p*'):
            if part.name != root.name:
                run('blockdev', '--setro', '/dev/' + part.name)
        run('blockdev', '--setrw', str(root))
        PARAM.write_text('Y\n')
        require(PARAM.read_text().strip() == 'Y', 'Driver did not arm')
        root_fd = os.open(root, os.O_RDWR | os.O_DIRECT | os.O_SYNC | os.O_CLOEXEC | os.O_EXCL)
        exercise(root_fd, Path('/run/rootguard-padding-before.bin'))
    finally:
        if root_fd is not None:
            os.close(root_fd)
        PARAM.write_text('N\n')
        run('blockdev', '--setro', '/dev/' + disk.name)
        require(PARAM.read_text().strip() == 'N', 'Driver did not disarm')
    # Direct reads bypass the host page cache for both before/after checks.
    disk_fd = os.open('/dev/' + disk.name, os.O_RDONLY | os.O_DIRECT | os.O_CLOEXEC)
    try:
        verify_regions(disk_fd, manifest)
        for lba, before in protected.items():
            require(read_at(disk_fd, lba * 4096, 4096) == before,
                    'Protected partition header changed during native test')
    finally:
        os.close(disk_fd)
    for d in disks:
        require((d / 'ro').read_text().strip() == '1', 'Namespace left writable')
        if d != disk:
            require(int((d / 'stat').read_text().split()[6]) == 0, 'Other namespace has writes')
        else:
            require(int((d / 'stat').read_text().split()[6]) == 2 * TEST_BYTES // 512,
                    'Main namespace write sectors differ from bounded test plus restore')
    print('ROOTGUARD_TEST_PASS: 16KiB padding restored; all namespaces RO; disk root not mounted', flush=True)


if __name__ == '__main__':
    main()
