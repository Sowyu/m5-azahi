#!/usr/bin/env python3
"""Offline partition fixtures and mocked shell tests; no target device access."""
import copy
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import plistlib
import re
import select
import socket
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
import urllib.error
import urllib.request
import uuid
import zlib

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / 'logs/recovery-resize-20260906.yS45qc/after/backup.tar.gz'
spec = importlib.util.spec_from_file_location('validator', HERE / 'validate-recovery-partitions.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
BASE = validator.load_baseline(BASELINE)
ESP_UUID = 'PRIVATE-UUID-REMOVED'
ROOT_UUID = 'PRIVATE-UUID-REMOVED'
HELPER_UUID = 'PRIVATE-UUID-REMOVED'


def fixtures(stage, helper=True, alter_original=False, outside=False, included_helper=False):
    with tarfile.open(BASELINE) as archive:
        original = {m.name: archive.extractfile(m).read() for m in archive.getmembers()}
    data = {name: original[name] for name in validator.FILES}
    entries = {identity: bytes.fromhex(part['raw_entry']) for identity, part in BASE['entries'].items()}
    infos = {plistlib.loads(original[f'partition-{i}.plist'])['DiskUUID'].lower():
             plistlib.loads(original[f'partition-{i}.plist']) for i in range(1, 5)}
    if alter_original:
        identity = 'PRIVATE-UUID-REMOVED'
        raw = bytearray(entries[identity]); raw[60] ^= 1; entries[identity] = bytes(raw)

    def add(identity, kind, start, size, device):
        raw = bytearray(128)
        raw[:16] = uuid.UUID(kind).bytes_le
        raw[16:32] = uuid.UUID(identity).bytes_le
        struct.pack_into('<QQ', raw, 32, start, start + size // 4096 - 1)
        entries[identity] = bytes(raw)
        infos[identity] = dict(DiskUUID=identity.upper(), DeviceIdentifier=device, ParentWholeDisk='disk0',
            DeviceBlockSize=4096, PartitionMapPartitionOffset=start * 4096, TotalSize=size,
            Content={validator.ESP_TYPE: 'EFI', validator.ROOT_TYPE: 'Linux Filesystem',
                     validator.BOOTER_TYPE: 'Apple_Boot'}[kind])

    if stage != 'before':
        add(ESP_UUID, validator.ESP_TYPE, validator.GAP_START, validator.ESP_BYTES, 'disk0s6')
    if stage == 'root':
        root_start = validator.GAP_START + validator.ESP_BYTES // 4096
        root_size = validator.ROOT_BYTES - (validator.BOOTER_BYTES if included_helper else 0)
        add(ROOT_UUID, validator.ROOT_TYPE, root_start, root_size, 'disk0s5')
        if helper:
            add(HELPER_UUID, validator.BOOTER_TYPE,
                validator.GAP_END if outside else root_start + root_size // 4096,
                validator.BOOTER_BYTES, 'disk0s8')
    ordered = sorted(entries, key=lambda identity: struct.unpack_from('<Q', entries[identity], 32)[0])
    table = b''.join(entries[identity] for identity in ordered).ljust(16384, b'\0')
    for name, hoff, toff in [('gpt-primary.bin', 4096, 8192), ('gpt-backup.bin', 20480, 4096)]:
        blob = bytearray(data[name])
        blob[toff:toff + 16384] = table
        struct.pack_into('<I', blob, hoff + 88, zlib.crc32(table))
        struct.pack_into('<I', blob, hoff + 16, 0)
        struct.pack_into('<I', blob, hoff + 16, zlib.crc32(blob[hoff:hoff + 92]))
        data[name] = bytes(blob)
    for index, identity in enumerate(ordered):
        data[f'part-{index}.plist'] = plistlib.dumps(infos[identity])
    listed = plistlib.loads(data['disk-list.plist'])
    listed['AllDisksAndPartitions'][0]['Partitions'] = [dict(DeviceIdentifier=infos[i]['DeviceIdentifier'],
        DiskUUID=i.upper(), Content=infos[i]['Content'], Size=infos[i]['TotalSize']) for i in ordered]
    data['disk-list.plist'] = plistlib.dumps(listed)
    return data


def archive_fixture(folder, data):
    path = folder / 'backup.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        for name, blob in data.items():
            member = tarfile.TarInfo(name); member.size = len(blob)
            archive.addfile(member, io.BytesIO(blob))
    (folder / 'receipt.txt').write_text(f'SHA256 {hashlib.sha256(path.read_bytes()).hexdigest()}\n')
    return path


class Tests(unittest.TestCase):
    def validate_fixture(self, stage, previous=None, **kwargs):
        with tempfile.TemporaryDirectory(prefix='azahi-part-test-') as tmp:
            return validator.validate(archive_fixture(Path(tmp), fixtures(stage, **kwargs)), stage, BASE, previous)

    def test_before(self):
        self.assertEqual(self.validate_fixture('before')['new_partitions'], {})

    def test_esp_and_root_with_helper_and_renumbered_recovery(self):
        esp = self.validate_fixture('esp')
        result = self.validate_fixture('root', esp)
        self.assertEqual(result['new_partitions'][ROOT_UUID]['bytes'], validator.ROOT_BYTES)
        self.assertEqual(result['free_bytes_in_approved_gap'], 415121408)

    def test_root_without_helper(self):
        self.assertEqual(len(self.validate_fixture('root', self.validate_fixture('esp'), helper=False)['new_partitions']), 2)

    def test_included_helper_requires_explicit_mode(self):
        with tempfile.TemporaryDirectory(prefix='azahi-part-test-') as tmp:
            path = archive_fixture(Path(tmp), fixtures('root', included_helper=True))
            esp = self.validate_fixture('esp')
            with self.assertRaisesRegex(ValueError, 'root extent'):
                validator.validate(path, 'root', BASE, esp)
            result = validator.validate(path, 'root', BASE, esp, root_allocation='includes-helper')
            self.assertEqual(result['new_partitions'][ROOT_UUID]['bytes'], 158779572224)
            self.assertEqual(result['free_bytes_in_approved_gap'], 549339136)

    def test_included_helper_must_exist(self):
        with tempfile.TemporaryDirectory(prefix='azahi-part-test-') as tmp:
            path = archive_fixture(Path(tmp), fixtures('root', included_helper=True, helper=False))
            with self.assertRaisesRegex(ValueError, 'requires its exact helper'):
                validator.validate(path, 'root', BASE, self.validate_fixture('esp'), root_allocation='includes-helper')

    def test_real_m5_root_report_review(self):
        folder = HERE.parent / 'logs/recovery-partitions-20260906.Zrp24U'
        esp = validator.validate(folder / 'esp/backup.tar.gz', 'esp', BASE)
        path = folder / 'root/backup.tar.gz'
        with self.assertRaisesRegex(ValueError, 'root extent'):
            validator.validate(path, 'root', BASE, esp)
        result = validator.validate(path, 'root', BASE, esp, root_allocation='includes-helper')
        self.assertTrue(result['original_entries_unchanged'])
        self.assertEqual(result['free_bytes_in_approved_gap'], 549339136)

    def test_original_entry_change(self):
        with self.assertRaisesRegex(ValueError, 'Original partition'):
            self.validate_fixture('before', alter_original=True)

    def test_helper_outside_gap(self):
        with self.assertRaises(ValueError):
            self.validate_fixture('root', self.validate_fixture('esp'), outside=True)

    def test_existing_partition_script_rerun(self):
        with tempfile.TemporaryDirectory(prefix='azahi-part-test-') as tmp:
            with self.assertRaisesRegex(ValueError, 'partition count'):
                validator.validate(archive_fixture(Path(tmp), fixtures('esp')), 'before', BASE)

    def shell_case(self, mode, expected_mutations):
        with tempfile.TemporaryDirectory(prefix='azahi-part-shell-') as tmp:
            root = Path(tmp).resolve()
            for stage in ('before', 'esp', 'root'):
                (root / stage).mkdir()
                data = fixtures(stage)
                if mode == 'wrong_extent':
                    info = plistlib.loads(data['part-1.plist'])
                    info['TotalSize'] += 4096
                    data['part-1.plist'] = plistlib.dumps(info)
                for name, blob in data.items():
                    (root / stage / name).write_bytes(blob)
            result = subprocess.run(['/bin/bash', '-c', 'source "$1"; /bin/bash "$2" create-linux-partitions',
                'test', str(HERE / 'test-recovery-partitions-mocks.sh'), str(HERE / 'recovery-create-partitions.sh')],
                env=dict(os.environ, RESIZE_TEST_DIR=str(root), PART_TEST_MODE=mode),
                capture_output=True, text=True, timeout=30)
            mutations = (root / 'mutations').read_text().splitlines() if (root / 'mutations').exists() else []
            self.assertEqual(len(mutations), expected_mutations, result.stdout + result.stderr)
            if mode == 'success':
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('LINUX_PARTITIONS_VERIFIED', result.stdout)
            else:
                self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_shell_success_dynamic_slice(self): self.shell_case('success', 2)
    def test_shell_bad_initial_receipt(self): self.shell_case('bad_before', 0)
    def test_shell_bad_esp_receipt_blocks_root(self): self.shell_case('bad_esp', 1)
    def test_shell_protected_extent_changed(self): self.shell_case('wrong_extent', 0)
    def test_shell_gpt_changed_after_validation(self): self.shell_case('changed_gpt', 0)

    def test_http_stages_and_download(self):
        with tempfile.TemporaryDirectory(prefix='azahi-part-http-') as tmp:
            root = Path(tmp)
            destination = root / 'reports'; destination.mkdir()
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            process = subprocess.Popen([sys.executable, '-u', str(HERE / 'recovery-resize-server.py'),
                '--partitioning', '--bind', '127.0.0.1', '--port', str(port), '--destination', str(destination),
                '--baseline', str(BASELINE)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            try:
                self.assertTrue(select.select([process.stdout], [], [], 10)[0])
                self.assertIn('Resize helper:', process.stdout.readline())
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(f'http://127.0.0.1:{port}/partitions.sh', timeout=5) as response:
                    script = response.read().decode()
                upload = re.search(r'http://127\.0\.0\.1:\d+/upload/[0-9a-f]{32}', script).group()
                self.assertEqual(script.replace(upload, '@UPLOAD_URL@'), (HERE / 'recovery-create-partitions.sh').read_text())
                for stage in ('before', 'esp', 'root'):
                    folder = root / stage; folder.mkdir()
                    archive = archive_fixture(folder, fixtures(stage))
                    request = urllib.request.Request(upload + '/' + stage, data=archive.read_bytes(), method='PUT')
                    with opener.open(request, timeout=5) as response:
                        self.assertIn(f'VALIDATED_PARTITIONS {stage}', response.read().decode())
                self.assertTrue((destination / 'root/validation.json').is_file())
            finally:
                process.terminate(); process.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
