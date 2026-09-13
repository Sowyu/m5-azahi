#!/usr/bin/env python3
"""Validate free-space-only partition creation against the verified post-resize GPT."""
import hashlib
import argparse
import importlib.util
import json
from pathlib import Path
import plistlib
import re
import struct
import tarfile
import uuid
import zlib

SECTORS = 244276265
GAP_START, GAP_END = 203903051, 242965551
ESP_BYTES, ROOT_BYTES, BOOTER_BYTES = 536870912, 158913789952, 134217728
ESP_TYPE = 'PRIVATE-UUID-REMOVED'
ROOT_TYPE = 'PRIVATE-UUID-REMOVED'
BOOTER_TYPE = 'PRIVATE-UUID-REMOVED'
ORIGINALS = {
    'PRIVATE-UUID-REMOVED': (6, 140800),
    'PRIVATE-UUID-REMOVED': (140806, 180324745),
    'PRIVATE-UUID-REMOVED': (180465551, 23437500),
    'PRIVATE-UUID-REMOVED': (242965551, 1310709),
}
FILES = {'disk.plist', 'disk-list.plist', 'linux.plist', 'linux-container.plist',
         'gpt-primary.bin', 'gpt-backup.bin', 'linux-superblock.bin', 'gpt.txt'}


def require(test, message):
    if not test:
        raise ValueError(message)


def read_archive(path):
    require(path.stat().st_size <= 1048576, 'Archive too large')
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    require(f'SHA256 {sha}' in (path.parent / 'receipt.txt').read_text().splitlines(), 'Receipt mismatch')
    data = {}
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            require(member.isfile() and 0 <= member.size <= 262144, 'Invalid archive member')
            require(member.name in FILES or re.fullmatch(r'part-[0-6]\.plist', member.name), 'Invalid archive path')
            require(member.name not in data and len(data) < 15, 'Duplicate/excess members')
            data[member.name] = archive.extractfile(member).read()
    count = len(data) - len(FILES)
    require(4 <= count <= 7 and set(data) == FILES | {f'part-{i}.plist' for i in range(count)},
            'Missing/noncontiguous report files')
    return data, sha


def parse_gpt(primary, backup):
    def table(blob, base, current):
        require(len(blob) == 24576, 'Short GPT')
        offset = (current - base) * 4096
        header = bytearray(blob[offset:offset + 92])
        f = struct.unpack('<8sIIIIQQQQ16sQIII', header)
        require(f[0:3] == (b'EFI PART', 0x10000, 92) and f[4] == 0
                and f[5] == current and f[6] == (SECTORS - 1 if current == 1 else 1)
                and f[7:9] == (6, SECTORS - 6)
                and str(uuid.UUID(bytes_le=f[9])) == 'PRIVATE-UUID-REMOVED'
                and f[10] == (2 if current == 1 else SECTORS - 5)
                and f[11:13] == (128, 128), 'GPT identity/geometry changed')
        struct.pack_into('<I', header, 16, 0)
        require(zlib.crc32(header) == f[3], 'GPT header CRC failed')
        start = (f[10] - base) * 4096
        result = blob[start:start + 16384]
        require(len(result) == 16384 and zlib.crc32(result) == f[13], 'GPT table CRC failed')
        return result
    entries = table(primary, 0, 1)
    require(entries == table(backup, SECTORS - 6, SECTORS - 1), 'GPT copies differ')
    require(primary[510:512] == b'\x55\xaa' and primary[450] == 0xee, 'Invalid PMBR')
    result = {}
    for slot in range(128):
        raw = entries[slot * 128:(slot + 1) * 128]
        if raw[:16] == bytes(16):
            require(raw == bytes(128), 'Nonzero unused GPT entry')
            continue
        identity = str(uuid.UUID(bytes_le=raw[16:32]))
        require(identity not in result and identity != str(uuid.UUID(int=0)), 'Duplicate/empty GPT UUID')
        start, end, flags = struct.unpack_from('<QQQ', raw, 32)
        require(6 <= start <= end < SECTORS - 5, 'Invalid GPT extent')
        result[identity] = dict(type=str(uuid.UUID(bytes_le=raw[:16])), start_lba=start,
                                end_lba=end, bytes=(end - start + 1) * 4096,
                                flags=flags, raw_entry=raw.hex(), slot=slot + 1)
    ordered = sorted(result.values(), key=lambda p: p['start_lba'])
    require(all(a['end_lba'] < b['start_lba'] for a, b in zip(ordered, ordered[1:])), 'Overlapping partitions')
    return result


def load_baseline(path):
    spec = importlib.util.spec_from_file_location('storage', Path(__file__).with_name('validate-recovery-storage.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate(path, 96000000000)
    with tarfile.open(path) as archive:
        primary = archive.extractfile('gpt-primary.bin').read()
        backup = archive.extractfile('gpt-backup.bin').read()
        container = plistlib.loads(archive.extractfile('linux-container.plist').read())['Containers'][0]
    return dict(entries=parse_gpt(primary, backup), mbr=primary[:512].hex(),
                volumes={v['APFSVolumeUUID']: v['Roles'] for v in container['Volumes']})


def validate(path, stage, baseline, previous=None, *, root_allocation='exact-root'):
    # The host's 512-byte-sector image added the helper outside the requested
    # root size. M5 Recovery with 4096-byte sectors instead included it in that
    # allocation. Require an explicit reviewed mode; never accept arbitrary sizes.
    require(root_allocation in ('exact-root', 'includes-helper'), 'Unknown root allocation mode')
    require(stage in ('before', 'esp', 'root'), 'Unknown stage')
    data, sha = read_archive(path)
    entries = parse_gpt(data['gpt-primary.bin'], data['gpt-backup.bin'])
    require(data['gpt-primary.bin'][:512].hex() == baseline['mbr'], 'Protective MBR changed')
    for identity, (start, count) in ORIGINALS.items():
        require(identity in entries and entries[identity]['raw_entry'] == baseline['entries'][identity]['raw_entry'],
                'Original partition entry changed: ' + identity)
        require((entries[identity]['start_lba'], entries[identity]['end_lba']) == (start, start + count - 1),
                'Original partition extent changed')
    new = {k: v for k, v in entries.items() if k not in ORIGINALS}
    require(len(new) in {'before': (0,), 'esp': (1,), 'root': (2, 3)}[stage], 'Unexpected new partition count')
    for part in new.values():
        require(GAP_START <= part['start_lba'] <= part['end_lba'] < GAP_END and part['flags'] == 0,
                'New partition outside approved free space or has flags')
    if stage != 'before':
        esp, = [p for p in new.values() if p['type'] == ESP_TYPE]
        require(esp['start_lba'] == GAP_START and esp['bytes'] == ESP_BYTES, 'Unexpected EFI extent')
    if stage == 'root':
        require(previous is not None, 'Previous EFI validation required')
        for identity, part in previous['new_partitions'].items():
            require(identity in entries and part['raw_entry'] == entries[identity]['raw_entry'], 'EFI entry changed')
        root, = [p for p in new.values() if p['type'] == ROOT_TYPE]
        expected_root = ROOT_BYTES if root_allocation == 'exact-root' else ROOT_BYTES - BOOTER_BYTES
        require(root['start_lba'] == esp['end_lba'] + 1 and root['bytes'] == expected_root, 'Unexpected Linux root extent')
        other = [p for p in new.values() if p['type'] not in (ESP_TYPE, ROOT_TYPE)]
        require(root_allocation != 'includes-helper' or len(other) == 1,
                'Included helper allocation requires its exact helper partition')
        if other:
            helper, = other
            require(helper['type'] == BOOTER_TYPE and helper['bytes'] == BOOTER_BYTES
                    and helper['start_lba'] == root['end_lba'] + 1, 'Unexpected auxiliary partition')
    disk = plistlib.loads(data['disk.plist'])
    require(disk['DeviceIdentifier'] == 'disk0' and disk['Internal'] is True and disk['WholeDisk'] is True
            and disk['DeviceBlockSize'] == 4096 and disk['TotalSize'] == SECTORS * 4096, 'Wrong disk')
    seen = set()
    devices = set()
    type_names = {ESP_TYPE: 'EFI', ROOT_TYPE: 'Linux Filesystem', BOOTER_TYPE: 'Apple_Boot'}
    for name, blob in data.items():
        if not name.startswith('part-'):
            continue
        info = plistlib.loads(blob)
        identity = info['DiskUUID'].lower()
        require(identity in entries and identity not in seen, 'Unexpected/duplicate partition plist')
        seen.add(identity)
        device = info['DeviceIdentifier']
        require(re.fullmatch(r'disk0s[1-9][0-9]*', device) and device not in devices, 'Invalid/duplicate device')
        devices.add(device)
        part = entries[identity]
        require(info['ParentWholeDisk'] == 'disk0' and info['DeviceBlockSize'] == 4096
                and info['PartitionMapPartitionOffset'] == part['start_lba'] * 4096
                and info['TotalSize'] == part['bytes'], 'Plist/GPT extent mismatch')
        if identity in new:
            require(info['Content'] == type_names[part['type']] and not info.get('MountPoint'), 'Wrong/mounted new partition')
            part['device'] = device
    require(seen == set(entries), 'GPT/report partition mismatch')
    listed = plistlib.loads(data['disk-list.plist'])['AllDisksAndPartitions']
    require(len(listed) == 1 and listed[0]['DeviceIdentifier'] == 'disk0'
            and {p['DeviceIdentifier'] for p in listed[0]['Partitions']} == devices,
            'Disk list/device mismatch')
    linux = plistlib.loads(data['linux.plist'])
    require(linux['VolumeUUID'] == 'PRIVATE-UUID-REMOVED'
            and linux['APFSVolumeGroupID'] == 'PRIVATE-UUID-REMOVED'
            and linux['APFSPhysicalStores'] == [{'APFSPhysicalStore': 'disk0s3'}], 'Wrong Linux system/store')
    container, = plistlib.loads(data['linux-container.plist'])['Containers']
    require(container['APFSContainerUUID'] == 'PRIVATE-UUID-REMOVED'
            and container['CapacityCeiling'] == 96000000000
            and len(container['Volumes']) == len(baseline['volumes'])
            and {v['APFSVolumeUUID']: v['Roles'] for v in container['Volumes']} == baseline['volumes'],
            'Linux APFS identity/volumes changed')
    block = data['linux-superblock.bin']
    require(len(block) == 4096 and block[32:36] == b'NXSB'
            and struct.unpack_from('<IQ', block, 36) == (4096, 23437500)
            and str(uuid.UUID(bytes=block[72:88])) == container['APFSContainerUUID'].lower(), 'Wrong APFS superblock')
    lo = hi = 0
    for word, in struct.iter_unpack('<I', block[8:]):
        lo = (lo + word) % 0xffffffff
        hi = (hi + lo) % 0xffffffff
    low = 0xffffffff - ((lo + hi) % 0xffffffff)
    high = 0xffffffff - ((lo + low) % 0xffffffff)
    require(struct.unpack_from('<Q', block)[0] == (high << 32 | low), 'APFS checksum failed')
    return dict(stage=stage, archive_sha256=sha, original_entries_unchanged=True,
                root_allocation=root_allocation,
                gpt_crcs_valid=True, apfs_superblock_valid=True, new_partitions=new,
                free_bytes_in_approved_gap=(GAP_END - GAP_START) * 4096 - sum(p['bytes'] for p in new.values()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--stage', choices=('before', 'esp', 'root'), required=True)
    parser.add_argument('--esp-report', type=Path)
    parser.add_argument('--root-allocation', choices=('exact-root', 'includes-helper'), default='exact-root')
    args = parser.parse_args()
    baseline = load_baseline(args.baseline)
    previous = validate(args.esp_report, 'esp', baseline) if args.esp_report else None
    print(json.dumps(validate(args.archive, args.stage, baseline, previous,
                              root_allocation=args.root_allocation), indent=2))
