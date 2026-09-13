#!/usr/bin/env python3
"""Offline fixtures only; never accesses the target or runs Recovery commands."""
import copy
import hashlib
import io
from pathlib import Path
import plistlib
import runpy
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
V = runpy.run_path(str(HERE / 'validate-backup.py'))
OLD = ROOT / 'logs/recovery-backup-20260906.eTn0av'


class BackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (OLD / 'custom-01.bin').read_bytes()
        raw, _ = V['raw_loader'](cls.original)
        v5 = (ROOT / 'probe/m1n1-smp-diag-v5-20260906.bin').read_bytes()
        assert hashlib.sha256(v5).hexdigest() == V['V5']
        assert cls.original.count(raw) == 1 and len(raw) == len(v5)
        # Synthetic wrapper ONLY. Original signature is intentionally invalid.
        # Validator must never claim to verify IMG4 signatures or derive coih.
        wrapped = cls.original.replace(raw, v5)
        linux = plistlib.loads((OLD / 'linux.plist').read_bytes())
        preboot = plistlib.loads((OLD / 'preboot.plist').read_bytes())
        linux.update(DeviceIdentifier='disk9s3', BooterDeviceIdentifier='disk9s4',
                     APFSContainerReference='disk9')
        preboot.update(DeviceIdentifier='disk9s4', APFSContainerReference='disk9',
                       WritableVolume=False)
        cls.fixture = {n: (OLD / n).read_bytes() for n in V['EXPECTED']
                       if (OLD / n).exists()}
        cls.fixture.update({'linux.plist': plistlib.dumps(linux),
                            'preboot.plist': plistlib.dumps(preboot),
                            'custom-01.bin': wrapped,
                            'linux-container.plist': plistlib.dumps({'Containers': [{
                                'APFSContainerUUID': V['CONTAINER'],
                                'ContainerReference': 'disk9',
                                'CapacityCeiling': 96000000000}]})})
        cls.fix_checksums(cls.fixture)

    @staticmethod
    def fix_checksums(data):
        source = data['manifest.tsv'].decode().strip().split('\t')[1]
        checksum = V['fingerprint'](data['custom-01.bin'])
        data['copy-checksums.txt'] = f'{checksum}\tcustom-01.bin\n'.encode()
        data['source-checksums.txt'] = f'{checksum}\t{source}\n'.encode()

    def check(self, data=None, extra=None, bad_receipt=False):
        if data is None:
            data = self.fixture
        with tempfile.TemporaryDirectory(prefix='azahi-backup-test-') as temp:
            path = Path(temp) / 'backup.tar.gz'
            with tarfile.open(path, 'w:gz') as archive:
                for name, content in data.items():
                    member = tarfile.TarInfo(name)
                    member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
                if extra:
                    archive.addfile(extra)
            blob = path.read_bytes()
            receipt = ('CKSUM ' + V['fingerprint'](blob) + '\nSHA256 ' +
                       hashlib.sha256(blob).hexdigest() + '\n')
            (path.parent / 'receipt.txt').write_text('bad\n' if bad_receipt else receipt)
            return V['validate'](path)

    def test_valid_with_renumbered_devices(self):
        result = self.check()
        self.assertEqual(result['preboot_device'], 'disk9s4')
        self.assertFalse(result['signature_verified'])
        self.assertFalse(result['coih_derived'])
        self.assertEqual(result['raw_sha256'], V['V5'])

    def test_real_original_img4(self):
        raw, props = V['raw_loader'](self.original)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         'f2f234d99be7bdd0181366ec16c055ac14bdfa48cb2774c238836462521d2505')
        self.assertEqual(props['kcep'], 2048)

    def test_wrong_uuid_and_writable(self):
        for name, field, value in [('linux.plist', 'VolumeUUID', V['PREBOOT']),
                                    ('preboot.plist', 'WritableVolume', True),
                                    ('preboot.plist', 'VolumeUUID', V['SYSTEM']),
                                    ('preboot.plist', 'APFSContainerReference', 'disk1')]:
            with self.subTest(field=field, value=value):
                data = copy.copy(self.fixture)
                info = plistlib.loads(data[name])
                info[field] = value
                data[name] = plistlib.dumps(info)
                with self.assertRaises(ValueError):
                    self.check(data)

    def test_wrong_container(self):
        data = copy.copy(self.fixture)
        info = plistlib.loads(data['linux-container.plist'])
        info['Containers'][0]['APFSContainerUUID'] = V['SYSTEM']
        data['linux-container.plist'] = plistlib.dumps(info)
        with self.assertRaises(ValueError):
            self.check(data)

    def test_policy_failures(self):
        for old, new in [(b': Paired', b': Not Paired'), (b': one true recoveryOS', b': macOS'),
                         (b'(sip0): absent', b'(sip0): 1'), (b'(CHIP): 0x6050', b'(CHIP): 0x6040'),
                         (b'(coih): ', b'(coih): invalid')]:
            with self.subTest(change=new):
                data = copy.copy(self.fixture)
                self.assertIn(old, data['boot-policy.txt'])
                data['boot-policy.txt'] = data['boot-policy.txt'].replace(old, new)
                with self.assertRaises(ValueError):
                    self.check(data)

    def test_old_loader_rejected(self):
        data = copy.copy(self.fixture)
        data['custom-01.bin'] = self.original
        self.fix_checksums(data)
        with self.assertRaisesRegex(ValueError, 'pinned V5'):
            self.check(data)

    def test_bad_receipt(self):
        with self.assertRaisesRegex(ValueError, 'receipt'):
            self.check(bad_receipt=True)

    def test_bad_copy_checksum(self):
        data = copy.copy(self.fixture)
        data['copy-checksums.txt'] = b'0 0\tcustom-01.bin\n'
        with self.assertRaisesRegex(ValueError, 'checksums'):
            self.check(data)

    def test_manifest_escape(self):
        data = copy.copy(self.fixture)
        data['manifest.tsv'] = b'custom-01.bin\t/Volumes/macOS/custom\n'
        with self.assertRaisesRegex(ValueError, 'outside Linux'):
            self.check(data)

    def test_missing_extra_duplicate_and_symlink(self):
        data = copy.copy(self.fixture)
        del data['linux.plist']
        with self.assertRaises(ValueError):
            self.check(data)
        for name in ['../escape', 'custom-01.bin', 'unexpected']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.check(extra=tarfile.TarInfo(name))
        link = tarfile.TarInfo('custom-01.bin')
        link.type = tarfile.SYMTYPE
        link.linkname = '/etc/passwd'
        with self.assertRaises(ValueError):
            self.check(extra=link)

    def test_bad_der(self):
        for blob in [b'', b'\x30', b'\x30\x80', b'\x30\x82\x01',
                     b'\x30\x81\x01x', b'\x30\x02x', b'\xff' * 20,
                     self.original[:-1], self.original + b'\x05\x00']:
            with self.subTest(size=len(blob)), self.assertRaises(ValueError):
                V['raw_loader'](blob)

    def test_real_two_object_backup(self):
        path = ROOT / 'logs/standalone-preinstall-backup-20260911.T0uKOR/backup.tar.gz'
        result = V['validate'](path)
        self.assertEqual(len(result['objects']), 2)
        self.assertEqual(result['preboot_device'], 'disk3s4')
        self.assertEqual(result['wrapped_sha256'],
                         'ce3151fffd46379ed093a58a15791e11af02a81533e2f5c58dfcafc54fd91e45')

    def test_policy_selects_wrong_object(self):
        path = ROOT / 'logs/standalone-preinstall-backup-20260911.T0uKOR/backup.tar.gz'
        with tarfile.open(path) as archive:
            data = {m.name: archive.extractfile(m).read() for m in archive}
        coih = V['validate'](path)['reported_coih'].encode()
        old = data['manifest.tsv'].splitlines()[0].rsplit(b'.', 1)[1]
        data['boot-policy.txt'] = data['boot-policy.txt'].replace(coih, old)
        with self.assertRaisesRegex(ValueError, 'does not select'):
            self.check(data)


if __name__ == '__main__':
    unittest.main()
