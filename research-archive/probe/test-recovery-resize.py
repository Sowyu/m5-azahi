#!/usr/bin/env python3
"""Offline synthetic fixtures and shell mocks; NEVER accesses target block devices."""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import plistlib
import re
import socket
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
import urllib.error
import urllib.request
import zlib

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / 'logs/recovery-storage-20260906.4VxUyx/backup.tar.gz'
spec = importlib.util.spec_from_file_location('validator', HERE / 'validate-recovery-storage.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def fixtures(after=False, locked=False):
    validator.validate(BASELINE)
    with tarfile.open(BASELINE) as archive:
        data = {m.name: archive.extractfile(m).read() for m in archive.getmembers()}
    container = plistlib.loads(data['linux-container.plist'])
    for volume in container['Containers'][0]['Volumes']:
        volume['Locked'] = locked
    if after:
        container['Containers'][0]['CapacityCeiling'] = 96000000000
        container['Containers'][0]['PhysicalStores'][0]['Size'] = 96000000000
    data['linux-container.plist'] = plistlib.dumps(container)
    if not after:
        return data
    part = plistlib.loads(data['partition-3.plist'])
    part['TotalSize'] = part['Size'] = 96000000000
    data['partition-3.plist'] = plistlib.dumps(part)
    limits = plistlib.loads(data['limits.plist'])
    limits['CurrentSize'] = limits['ContainerCurrentSize'] = 96000000000
    data['limits.plist'] = plistlib.dumps(limits)
    for name, hoff, toff in [('gpt-primary.bin', 4096, 8192), ('gpt-backup.bin', 20480, 4096)]:
        blob = bytearray(data[name])
        struct.pack_into('<Q', blob, toff + 2 * 128 + 40, 180465551 + 96000000000 // 4096 - 1)
        struct.pack_into('<I', blob, hoff + 88, zlib.crc32(blob[toff:toff + 16384]))
        struct.pack_into('<I', blob, hoff + 16, 0)
        struct.pack_into('<I', blob, hoff + 16, zlib.crc32(blob[hoff:hoff + 92]))
        data[name] = bytes(blob)
    block = bytearray(data['linux-superblock.bin'])
    struct.pack_into('<Q', block, 40, 96000000000 // 4096)
    lo = hi = 0
    modulus = 0xffffffff
    for word, in struct.iter_unpack('<I', block[8:]):
        lo = (lo + word) % modulus
        hi = (hi + lo) % modulus
    low = modulus - (lo + hi) % modulus
    high = modulus - (lo + low) % modulus
    struct.pack_into('<Q', block, 0, high << 32 | low)
    data['linux-superblock.bin'] = bytes(block)
    return data


def archive_fixture(folder, data):
    path = folder / 'backup.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        for name, blob in data.items():
            member = tarfile.TarInfo(name)
            member.size = len(blob)
            archive.addfile(member, io.BytesIO(blob))
    (folder / 'receipt.txt').write_text(f'SHA256 {hashlib.sha256(path.read_bytes()).hexdigest()}\n')
    return path


class Tests(unittest.TestCase):
    def test_existing_report(self):
        self.assertFalse(validator.validate(BASELINE)['linux_volumes_unlocked'])

    def test_unlock_required(self):
        with self.assertRaisesRegex(ValueError, 'locked'):
            validator.validate(BASELINE, require_unlocked=True)

    def test_synthetic_after_and_protected_bytes(self):
        with tempfile.TemporaryDirectory(prefix='azahi-resize-test-') as tmp:
            result = validator.validate(archive_fixture(Path(tmp), fixtures(after=True)),
                                        96000000000, True)
            self.assertEqual(result['protected_gpt_and_mbr_sha256'],
                             validator.validate(BASELINE)['protected_gpt_and_mbr_sha256'])

    def test_corrupt_gpt(self):
        data = fixtures()
        blob = bytearray(data['gpt-primary.bin'])
        blob[9000] ^= 1
        data['gpt-primary.bin'] = bytes(blob)
        with tempfile.TemporaryDirectory(prefix='azahi-resize-test-') as tmp:
            with self.assertRaisesRegex(ValueError, 'CRC'):
                validator.validate(archive_fixture(Path(tmp), data))

    def test_archive_path_rejected(self):
        data = fixtures()
        data['../escape'] = data.pop('disks.txt')
        with tempfile.TemporaryDirectory(prefix='azahi-resize-test-') as tmp:
            with self.assertRaisesRegex(ValueError, 'paths'):
                validator.validate(archive_fixture(Path(tmp), data))

    def shell_case(self, mode, expected_success=False):
        with tempfile.TemporaryDirectory(prefix='azahi-resize-shell-') as tmp:
            root = Path(tmp).resolve()
            for stage in ('before', 'after'):
                (root / stage).mkdir()
                data = fixtures(after=stage == 'after', locked=mode == 'locked')
                if mode == 'wrong_partition':
                    part = plistlib.loads(data['partition-2.plist'])
                    part['DiskUUID'] = 'WRONG'
                    data['partition-2.plist'] = plistlib.dumps(part)
                if mode == 'minimum':
                    limits = plistlib.loads(data['limits.plist'])
                    limits['MinimumSizePreferred'] = 100000000000
                    data['limits.plist'] = plistlib.dumps(limits)
                for name, blob in data.items():
                    (root / stage / name).write_bytes(blob)
            env = dict(os.environ, RESIZE_TEST_DIR=str(root),
                       RESIZE_TEST_BAD_RECEIPT='1' if mode == 'receipt' else '0')
            result = subprocess.run(['/bin/bash', '-c',
                'source "$1"; /bin/bash "$2" resize-linux-96gb', 'test',
                str(HERE / 'test-recovery-resize-mocks.sh'), str(HERE / 'recovery-resize-linux.sh')],
                env=env, capture_output=True, text=True, timeout=30)
            if expected_success:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('LINUX_RESIZE_VERIFIED', result.stdout)
                self.assertEqual((root / 'mutations').read_text(),
                                 'apfs resizeContainer disk0s3 96000000000\n')
                # Same script cannot resize again after the size changed.
                rerun = subprocess.run(['/bin/bash', '-c',
                    'source "$1"; /bin/bash "$2" resize-linux-96gb', 'test',
                    str(HERE / 'test-recovery-resize-mocks.sh'), str(HERE / 'recovery-resize-linux.sh')],
                    env=env, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(rerun.returncode, 0)
                self.assertEqual(len((root / 'mutations').read_text().splitlines()), 1)
            else:
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertFalse((root / 'mutations').exists(), result.stdout + result.stderr)

    def test_shell_success_and_no_repeat(self):
        self.shell_case('success', True)

    def test_shell_locked(self):
        self.shell_case('locked')

    def test_shell_protected_partition_changed(self):
        self.shell_case('wrong_partition')

    def test_shell_minimum_changed(self):
        self.shell_case('minimum')

    def test_shell_bad_receipt(self):
        self.shell_case('receipt')

    def test_server_stages_and_exact_download(self):
        with tempfile.TemporaryDirectory(prefix='azahi-resize-server-test-') as tmp:
            root = Path(tmp)
            destination = root / 'reports'
            destination.mkdir()
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            process = subprocess.Popen([sys.executable, '-u', str(HERE / 'recovery-resize-server.py'),
                '--bind', '127.0.0.1', '--port', str(port), '--destination', str(destination),
                '--baseline', str(BASELINE)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True)
            try:
                import select
                ready, _, _ = select.select([process.stdout], [], [], 10)
                self.assertTrue(ready, 'Server did not start')
                line = process.stdout.readline()
                self.assertIn('Resize helper:', line, line)
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                url = f'http://127.0.0.1:{port}'
                with opener.open(url + '/resize.sh', timeout=5) as response:
                    script = response.read().decode()
                match = re.search(r'http://127\.0\.0\.1:\d+/upload/[0-9a-f]{32}', script)
                self.assertIsNotNone(match)
                upload = match.group()
                self.assertEqual(script.replace(upload, '@UPLOAD_URL@'),
                                 (HERE / 'recovery-resize-linux.sh').read_text())

                def put(stage, archive):
                    request = urllib.request.Request(upload + '/' + stage, data=archive.read_bytes(), method='PUT')
                    with opener.open(request, timeout=5) as response:
                        return response.read().decode()

                before_folder = root / 'before-fixture'
                after_folder = root / 'after-fixture'
                before_folder.mkdir()
                after_folder.mkdir()
                before = archive_fixture(before_folder, fixtures())
                after = archive_fixture(after_folder, fixtures(after=True))
                with self.assertRaises(urllib.error.HTTPError) as error:
                    put('after', after)
                self.assertEqual(error.exception.code, 409)
                error.exception.close()
                self.assertIn('VALIDATED_STORAGE before', put('before', before))
                with self.assertRaises(urllib.error.HTTPError) as error:
                    put('before', before)
                self.assertEqual(error.exception.code, 409)
                error.exception.close()
                self.assertIn('VALIDATED_STORAGE after', put('after', after))
                self.assertTrue((destination / 'before/validation.json').is_file())
                self.assertTrue((destination / 'after/validation.json').is_file())
            finally:
                process.terminate()
                process.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
