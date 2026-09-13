#!/usr/bin/env python3
"""Read-only, bounded validation of the fresh pre-install V5 backup.

This checks the raw loader, UUIDs and reported Recovery policy. It does NOT
verify Apple's IMG4 signature or derive coih; the current coih is recorded
for an independently reviewed installer to pin. No archive extraction.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import re
import subprocess
import tarfile

SYSTEM = 'PRIVATE-UUID-REMOVED'
VG = 'PRIVATE-UUID-REMOVED'
PREBOOT = 'PRIVATE-UUID-REMOVED'
CONTAINER = 'PRIVATE-UUID-REMOVED'
V5 = '7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef'
ORIGINAL = 'f2f234d99be7bdd0181366ec16c055ac14bdfa48cb2774c238836462521d2505'
ORIGINAL_WRAPPED = 'fed0eb4d7ea1eaf6ba10d0487840bb59f4940edcc986b029b3b5753630bf7e31'
EXPECTED = set(('linux.plist preboot.plist linux-container.plist volume-groups.txt '
                'disks.txt boot-policy.txt paths.nul manifest.tsv source-checksums.txt '
                'copy-checksums.txt custom-01.bin').split())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def items(data):
    """Bounded DER TLVs; retain original encoding for audit hashes."""
    cursor = 0
    result = []
    while cursor < len(data):
        require(len(result) < 128, 'Too many DER fields')
        start = cursor
        tag = data[cursor]
        cursor += 1
        if tag & 31 == 31:
            for _ in range(8):
                require(cursor < len(data), 'Truncated DER tag')
                more = data[cursor] & 128
                cursor += 1
                if not more:
                    break
            else:
                raise ValueError('Oversized DER tag')
        require(cursor < len(data), 'Truncated DER length')
        length = data[cursor]
        cursor += 1
        if length & 128:
            count = length & 127
            require(0 < count <= 4 and cursor + count <= len(data), 'Bad DER length')
            require(data[cursor] != 0, 'Nonminimal DER length')
            length = int.from_bytes(data[cursor:cursor + count], 'big')
            require(length >= 128, 'Nonminimal DER long length')
            cursor += count
        require(cursor + length <= len(data), 'Truncated DER value')
        result.append((tag, data[cursor:cursor + length], data[start:cursor + length]))
        cursor += length
    return result


def only(data, tag):
    fields = items(data)
    require(len(fields) == 1 and fields[0][0] == tag, 'Unexpected DER wrapper')
    return fields[0][1]


def raw_loader(blob):
    image4 = items(only(blob, 0x30))
    require(len(image4) >= 2 and image4[0][:2] == (0x16, b'IMG4')
            and image4[1][0] == 0x30, 'Not IMG4')
    im4p = items(image4[1][1])
    require(len(im4p) == 5 and [x[:2] for x in im4p[:2]] ==
            [(0x16, b'IM4P'), (0x16, b'fuos')]
            and im4p[2][0] == 0x16 and im4p[3][0] == 4
            and im4p[4][0] == 0xa0, 'Unexpected fuOS payload layout')
    payp = items(only(im4p[4][1], 0x30))
    require(len(payp) == 2 and payp[0][:2] == (0x16, b'PAYP')
            and payp[1][0] == 0x31, 'Unexpected PAYP layout')
    props = {}
    for _, entry, _ in items(payp[1][1]):
        fields = items(only(entry, 0x30))
        require(len(fields) == 2 and fields[0][0] == 0x16 and fields[1][0] == 2,
                'Malformed raw-loader property')
        key = fields[0][1].decode('ascii')
        value = fields[1][1]
        require(key not in props and 0 < len(value) <= 8 and not value[0] & 128,
                'Duplicate, negative or oversized property')
        props[key] = int.from_bytes(value, 'big')
    size = len(im4p[3][1])
    require(props == dict(kcep=2048, kclf=size, kclo=0, kclz=0,
                          kcrf=0, kcrz=0, kcwf=0, kcwz=size),
            'Unexpected raw entry/load layout')
    return im4p[3][1], props


def fingerprint(data):
    return subprocess.check_output(['/usr/bin/cksum'], input=data).decode().strip()


def validate(path):
    require(0 < path.stat().st_size <= 40 * 1024 * 1024, 'Oversized archive')
    blob = path.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    receipt = (path.parent / 'receipt.txt').read_text().splitlines()
    require(receipt == ['CKSUM ' + fingerprint(blob), 'SHA256 ' + digest],
            'Receiver receipt mismatch')
    data = {}
    total = 0
    with tarfile.open(path, 'r:gz') as archive:
        for m in archive:
            require(m.name in EXPECTED | {'custom-02.bin'} and m.name not in data and m.isfile(),
                    'Unexpected, duplicate or non-regular archive member')
            limit = 2 * 1024 * 1024 if m.name.startswith('custom-') else 1024 * 1024
            require(0 <= m.size <= limit, 'Oversized member')
            total += m.size
            require(total <= 12 * 1024 * 1024, 'Oversized expanded archive')
            data[m.name] = archive.extractfile(m).read()
    require(set(data) in (EXPECTED, EXPECTED | {'custom-02.bin'}), 'Missing backup members')
    linux = plistlib.loads(data['linux.plist'])
    preboot = plistlib.loads(data['preboot.plist'])
    containers = plistlib.loads(data['linux-container.plist'])['Containers']
    require(linux['VolumeUUID'] == SYSTEM and linux['APFSVolumeGroupID'] == VG
            and linux['VolumeName'] == 'Linux' and linux['MountPoint'] == '/Volumes/Linux',
            'Linux identity mismatch')
    require(preboot['VolumeUUID'] == PREBOOT and preboot['VolumeName'] == 'Preboot'
            and preboot['WritableVolume'] is False
            and preboot['DeviceIdentifier'] == linux['BooterDeviceIdentifier']
            and preboot['APFSContainerReference'] == linux['APFSContainerReference'],
            'Preboot identity or read-only state mismatch')
    require(len(containers) == 1 and containers[0]['APFSContainerUUID'] == CONTAINER
            and containers[0]['ContainerReference'] == linux['APFSContainerReference']
            and containers[0]['CapacityCeiling'] == 96000000000,
            'Linux container mismatch')
    mount = preboot['MountPoint']
    require(mount.startswith('/Volumes/') and '\n' not in mount and '\t' not in mount,
            'Unexpected Preboot mount point')
    manifest = data['manifest.tsv'].decode().splitlines()
    require(len(manifest) == 1 + ('custom-02.bin' in data), 'Ambiguous custom files')
    prefix = mount + '/' + VG + '/'
    sources, source_sums, copy_sums, objects = [], [], [], []
    for index, line in enumerate(manifest, 1):
        fields = line.split('\t')
        name = f'custom-{index:02d}.bin'
        require(len(fields) == 2 and fields[0] == name, 'Bad manifest')
        source = fields[1]
        require(source.startswith(prefix) and '..' not in PurePosixPath(source).parts
                and re.fullmatch(r'kernelcache\.custom\.[0-9A-F]{96}', PurePosixPath(source).name),
                'Source outside Linux group or unexpected object name')
        require(source not in sources, 'Duplicate source')
        sources.append(source)
        wrapped = data[name]
        checksum = fingerprint(wrapped)
        source_sums.append(f'{checksum}\t{source}\n')
        copy_sums.append(f'{checksum}\t{name}\n')
        raw, props = raw_loader(wrapped)
        raw_sha = hashlib.sha256(raw).hexdigest()
        wrapped_sha = hashlib.sha256(wrapped).hexdigest()
        require(len(raw) == 1114112 and raw_sha in (V5, ORIGINAL), 'Unknown raw loader')
        if raw_sha == ORIGINAL:
            require(wrapped_sha == ORIGINAL_WRAPPED, 'Original wrapped backup changed')
        objects.append(dict(source=source, member=name, raw_sha256=raw_sha,
                            wrapped_sha256=wrapped_sha, raw_properties=props))
    require(data['paths.nul'] == b''.join(s.encode() + b'\0' for s in sources), 'Source list mismatch')
    require(data['source-checksums.txt'].decode() == ''.join(source_sums)
            and data['copy-checksums.txt'].decode() == ''.join(copy_sums), 'Source/copy checksums mismatch')
    require(sum(o['raw_sha256'] == V5 for o in objects) == 1,
            'Expected exactly one pinned V5 loader')
    policy = data['boot-policy.txt'].decode()
    require(policy.startswith('Operating on Volume Group UUID ' + VG + '\n'),
            'Policy report target mismatch')
    for label, value in [('OS Type', 'one true recoveryOS'),
                         ('OS Pairing Status', 'Paired'), ('Pairing Integrity', 'Valid'),
                         ('Volume Group UUID                       (vuid)', VG),
                         ('Board ID                                (BORD)', '0x8'),
                         ('Chip ID                                 (CHIP)', '0x6050')]:
        require(len(re.findall(r'^' + re.escape(label) + r'\s*:\s*' +
                               re.escape(value) + r'\s*$', policy, re.M)) == 1,
                'Policy mismatch: ' + label)
    for text in ['Permissive (smb0 && smb1): 1',
                 'SIP Status:                  Enabled    (sip0): absent',
                 'Signed System Volume Status: Enabled    (sip1): absent',
                 'Kernel CTRR Status:          Disabled   (sip2): 1']:
        require(text in policy, 'Existing security policy changed: ' + text)
    coih = re.findall(r'^CustomKC or fuOS Image4 Hash\s+\(coih\): ([0-9A-F]{96})$', policy, re.M)
    require(len(coih) == 1, 'Missing/ambiguous current coih')
    selected = [o for o in objects if o['source'].endswith('kernelcache.custom.' + coih[0])]
    require(len(selected) == 1 and selected[0]['raw_sha256'] == V5,
            'Reported coih does not select the pinned V5 object')
    active = selected[0]
    return dict(status='V5_BACKUP_VALIDATED_NOT_INSTALLED', archive_sha256=digest,
                wrapped_sha256=active['wrapped_sha256'], raw_sha256=V5,
                raw_properties=active['raw_properties'], source=active['source'], reported_coih=coih[0],
                objects=objects,
                policy_sha256=hashlib.sha256(data['boot-policy.txt']).hexdigest(),
                linux_device=linux['DeviceIdentifier'], preboot_device=preboot['DeviceIdentifier'],
                signature_verified=False, coih_derived=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.archive), indent=2))
