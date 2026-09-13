#!/usr/bin/env python3
"""Validate the pinned M5 Recovery storage report without extracting or writing it."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import tarfile
import uuid
import zlib

PARTITIONS = [
    ('PRIVATE-UUID-REMOVED', 6, 140800),
    ('PRIVATE-UUID-REMOVED', 140806, 180324745),
    ('PRIVATE-UUID-REMOVED', 180465551, 62500000),
    ('PRIVATE-UUID-REMOVED', 242965551, 1310709),
]
CONTAINER = 'PRIVATE-UUID-REMOVED'
DISK = 'PRIVATE-UUID-REMOVED'
EXPECTED = set('linux.plist partition-1.plist partition-2.plist partition-3.plist '
               'partition-4.plist disk.plist disks.txt disk-list.plist '
               'linux-container.plist linux-container.txt gpt.txt limits.plist '
               'limits-error.txt limits-status.txt gpt-primary.bin gpt-backup.bin '
               'linux-superblock.bin'.split())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(path, linux_bytes=256000000000, require_unlocked=False):
    require(linux_bytes in (256000000000, 96000000000), 'Unapproved Linux size')
    partitions = list(PARTITIONS)
    identity, start, _ = partitions[2]
    partitions[2] = (identity, start, linux_bytes // 4096)
    require(path.stat().st_size <= 40 * 1024 * 1024, 'Oversized archive')
    archive_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = (path.parent / 'receipt.txt').read_text().splitlines()
    require(f'SHA256 {archive_sha}' in receipt, 'Receipt SHA mismatch')
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        require(len(members) == len(EXPECTED), 'Unexpected member count')
        require({m.name for m in members} == EXPECTED, 'Unexpected archive paths')
        require(all(m.isfile() and 0 <= m.size <= 1048576 for m in members),
                'Non-regular or oversized member')
        data = {m.name: archive.extractfile(m).read() for m in members}
    plists = {name: plistlib.loads(value) for name, value in data.items()
              if name.endswith('.plist') and name != 'limits.plist'}
    disk = plists['disk.plist']
    require(disk['DeviceIdentifier'] == 'disk0' and disk['Internal']
            and disk['WholeDisk'] and disk['DeviceBlockSize'] == 4096,
            'Unexpected disk identity/geometry')
    sectors, remainder = divmod(disk['TotalSize'], 4096)
    require(not remainder and sectors == 244276265, 'Disk size changed')
    for index, (identity, start, count) in enumerate(partitions, 1):
        part = plists[f'partition-{index}.plist']
        require(part['DiskUUID'].lower() == identity
                and part['PartitionMapPartitionOffset'] == start * 4096
                and part['TotalSize'] == count * 4096
                and part['DeviceBlockSize'] == 4096
                and part['ParentWholeDisk'] == 'disk0',
                f'Partition {index} changed')

    def gpt(blob, base, header_lba):
        require(len(blob) == 24576, 'Short GPT backup')
        offset = (header_lba - base) * 4096
        header = blob[offset:offset + 4096]
        fields = struct.unpack_from('<8sIIIIQQQQ16sQIII', header)
        (signature, revision, size, checksum, reserved, current, other,
         first, last, guid, table_lba, count, entry_size, table_crc) = fields
        require(signature == b'EFI PART' and revision == 0x10000 and size == 92
                and reserved == 0 and current == header_lba
                and other == (sectors - 1 if current == 1 else 1)
                and first == 6 and last == sectors - 6
                and str(uuid.UUID(bytes_le=guid)) == DISK,
                'GPT header geometry/identity mismatch')
        checked = bytearray(header[:size])
        checked[16:20] = b'\0' * 4
        require(zlib.crc32(checked) == checksum, 'GPT header CRC failed')
        require(count == 128 and entry_size == 128, 'Unexpected GPT table size')
        table_offset = (table_lba - base) * 4096
        table_size = count * entry_size
        require(0 <= table_offset <= len(blob) - table_size, 'GPT table out of bounds')
        table = blob[table_offset:table_offset + table_size]
        require(zlib.crc32(table) == table_crc, 'GPT table CRC failed')
        for index, (identity, start, length) in enumerate(partitions):
            entry = table[index * entry_size:(index + 1) * entry_size]
            require(entry[:16] != bytes(16)
                    and str(uuid.UUID(bytes_le=entry[16:32])) == identity
                    and struct.unpack_from('<QQ', entry, 32) == (start, start + length - 1),
                    f'GPT partition {index + 1} mismatch')
        require(table[4 * entry_size:] == bytes((count - 4) * entry_size),
                'Extra GPT entries')
        return table

    primary = data['gpt-primary.bin']
    require(primary[510:512] == b'\x55\xaa' and primary[450] == 0xee,
            'Invalid protective MBR')
    table = gpt(primary, 0, 1)
    require(table == gpt(data['gpt-backup.bin'], sectors - 6, sectors - 1),
            'Primary/backup GPT tables differ')
    # Everything in the GPT entries except Linux p3's ending LBA must remain exact.
    protected = primary[:512] + table[:296] + table[304:]

    block = data['linux-superblock.bin']
    require(len(block) == 4096 and block[32:36] == b'NXSB'
            and struct.unpack_from('<IQ', block, 36) == (4096, linux_bytes // 4096)
            and str(uuid.UUID(bytes=block[72:88])) == CONTAINER,
            'Linux APFS superblock identity/geometry mismatch')
    lo = hi = 0
    modulus = 0xffffffff
    for word, in struct.iter_unpack('<I', block[8:]):
        lo = (lo + word) % modulus
        hi = (hi + lo) % modulus
    check_lo = modulus - ((lo + hi) % modulus)
    check_hi = modulus - ((lo + check_lo) % modulus)
    require(struct.unpack_from('<Q', block)[0] == (check_hi << 32 | check_lo),
            'Linux APFS superblock checksum failed')
    container, = plists['linux-container.plist']['Containers']
    require(container['APFSContainerUUID'].lower() == CONTAINER,
            'APFS container plist mismatch')
    require(container['CapacityCeiling'] == linux_bytes
            and container['DesignatedPhysicalStore'] == 'disk0s3',
            'APFS capacity/store mismatch')
    expected_volumes = {
        'PRIVATE-UUID-REMOVED': ['Data'],
        'PRIVATE-UUID-REMOVED': ['Update'],
        'PRIVATE-UUID-REMOVED': ['System'],
        'PRIVATE-UUID-REMOVED': ['Preboot'],
        'PRIVATE-UUID-REMOVED': ['Recovery'],
        'PRIVATE-UUID-REMOVED': ['VM'],
    }
    volumes = container['Volumes']
    require(len(volumes) == len(expected_volumes)
            and {v['APFSVolumeUUID']: v['Roles'] for v in volumes} == expected_volumes,
            'Linux volume identities/roles changed')
    unlocked = all(v['Locked'] is False and v['CryptoMigrationOn'] is False for v in volumes)
    require(not require_unlocked or unlocked, 'Linux volumes locked or crypto migration active')
    require(data['limits-status.txt'].strip() == b'LIMITS_QUERY_OK', 'Limits query failed')
    limits = plistlib.loads(data['limits.plist'])
    require(limits['ContainerCurrentSize'] == linux_bytes
            and limits['CurrentSize'] == linux_bytes
            and limits['Type'] == 'APFSPhysicalStore', 'Wrong limits target')
    return {
        'status': 'VALIDATED_READ_ONLY_REPORT',
        'archive_sha256': archive_sha,
        'gpt_headers_and_tables_crc_valid': True,
        'gpt_tables_identical': True,
        'protected_gpt_and_mbr_sha256': hashlib.sha256(protected).hexdigest(),
        'four_partition_identities_and_extents_match': True,
        'linux_bytes': linux_bytes,
        'linux_volumes_unlocked': unlocked,
        'linux_apfs_superblock_checksum_valid': True,
        'linux_apfs_superblock_sha256': hashlib.sha256(block).hexdigest(),
        'limits': limits,
        'candidate_apfs_bytes': 96000000000,
        'candidate_above_preferred_minimum': 96000000000 > limits['MinimumSizePreferred'],
        'candidate_freed_bytes': 160000000000,
        'note': 'Metadata backup only; not a full filesystem backup or permission to restore GPT after resize.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--linux-bytes', type=int, choices=(256000000000, 96000000000),
                        default=256000000000)
    parser.add_argument('--require-unlocked', action='store_true')
    args = parser.parse_args()
    print(json.dumps(validate(args.archive, args.linux_bytes, args.require_unlocked), indent=2))
