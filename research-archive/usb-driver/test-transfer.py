#!/usr/bin/env python3
"""Offline transfer-image, initrd courier and Recovery validator regression tests."""
import copy
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import runpy
import subprocess
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
P = runpy.run_path(str(HERE / 'transfer-server.py'))
B = P['B']
S = P['S']
T = runpy.run_path(str(HERE.parent / 'standalone-loader/test-install.py'))


class TransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline, cls.wrapped_sum, cls.image, cls.rollback = P['profile']()
        cls.receipt = json.loads(B['OUTPUT'].with_suffix('.json').read_text())
        with tarfile.open(P['CURRENT']) as archive:
            cls.snapshot = {m.name: archive.extractfile(m).read() for m in archive}
        for name in ('policy-before.txt', 'policy-rechecked.txt'):
            cls.snapshot[name] = cls.snapshot['policy-after.txt']
        cls.snapshot['mode.txt'] = b'snapshot\n'

    def validate(self, data, mode='snapshot'):
        with tempfile.TemporaryDirectory(prefix='usb-transfer-receipt-test-') as temp:
            path = Path(temp) / 'test.tar.gz'
            with tarfile.open(path, 'w:gz', compresslevel=1) as archive:
                for name, blob in data.items():
                    member = tarfile.TarInfo(name)
                    member.size = len(blob)
                    archive.addfile(member, io.BytesIO(blob))
            return P['validate'](path, mode, self.baseline)

    def test_image_byte_invariants(self):
        B['inspect'](self.image, self.receipt)
        self.assertEqual(len(self.image) % 16384, 0)

    def test_reproducible_image(self):
        image, receipt = B['build']()
        self.assertEqual(image, self.image)
        self.assertEqual(receipt, self.receipt)

    def test_corrupt_unchanged_component_or_padding_rejected(self):
        for offset in (2048, B['LOADER_SIZE'] + 44 + 1026, len(self.image)-1):
            with self.subTest(offset=offset), self.assertRaises(AssertionError):
                image = bytearray(self.image)
                image[offset] ^= 1
                receipt = dict(self.receipt, image_sha256=hashlib.sha256(image).hexdigest())
                B['inspect'](bytes(image), receipt)

    def test_truncation_rejected(self):
        with self.assertRaises(AssertionError):
            B['inspect'](self.image[:-1], self.receipt)

    def test_real_current_boot_as_snapshot(self):
        report = self.validate(self.snapshot)
        self.assertEqual(report['raw_sha256'], B['BASE_SHA'])
        self.assertEqual(report['status'], 'CURRENT_BOOT_BACKUP_VERIFIED')
        self.assertFalse(report['signature_verified'])

    def test_snapshot_policy_change_rejected(self):
        for name in ('policy-before.txt', 'policy-after.txt'):
            data = dict(self.snapshot)
            data[name] = data[name].replace(P['CURRENT_COIH'].encode(), b'A'*96)
            with self.assertRaises(ValueError):
                self.validate(data)

    def test_wrong_volume_or_rw_preboot_rejected(self):
        for field, value in [('WritableVolume', True), ('VolumeUUID', 'wrong')]:
            data = dict(self.snapshot)
            info = plistlib.loads(data['preboot.plist'])
            info[field] = value
            data['preboot.plist'] = plistlib.dumps(info)
            with self.assertRaises(ValueError):
                self.validate(data)

    def test_wrong_security_policy_rejected(self):
        data = dict(self.snapshot)
        for name in ('policy-before.txt', 'policy-rechecked.txt', 'policy-after.txt'):
            data[name] = data[name].replace(b': Paired', b': Unpaired')
        with self.assertRaises(ValueError):
            self.validate(data)

    def test_synthetic_candidate_readback(self):
        with tarfile.open(T['BACKUP']) as archive:
            original = archive.extractfile('custom-02.bin').read()
        data = dict(self.snapshot)
        data['installed.bin'] = T['wrap_candidate'](original, self.image)
        data['installed-cksum.txt'] = (S['V']['fingerprint'](data['installed.bin']) + '\n').encode()
        data['mode.txt'] = b'install\n'
        for name in ('policy-after.txt', 'installed-path.txt'):
            data[name] = data[name].replace(P['CURRENT_COIH'].encode(), b'A'*96)
        report = self.validate(data, 'install')
        self.assertEqual(report['raw_sha256'], P['CANDIDATE_SHA'])
        self.assertFalse(report['signature_verified'])

    def test_rollback_is_kde_not_proxy(self):
        data = dict(self.snapshot, **{'mode.txt': b'rollback\n'})
        self.assertEqual(self.validate(data, 'rollback')['raw_sha256'], B['BASE_SHA'])

    def test_wrong_archive_path_rejected(self):
        data = dict(self.snapshot)
        data['../escape'] = b'x'
        with self.assertRaises(ValueError):
            self.validate(data)

    def test_corrupted_raw_with_updated_crc_rejected(self):
        data = dict(self.snapshot)
        wrapped = bytearray(data['installed.bin'])
        position = wrapped.index(self.rollback[:4096])
        wrapped[position+2048] ^= 1
        data['installed.bin'] = bytes(wrapped)
        data['installed-cksum.txt'] = (S['V']['fingerprint'](wrapped) + '\n').encode()
        with self.assertRaises(ValueError):
            self.validate(data)

    def test_rendered_helper_syntax_and_gate(self):
        for enabled in (False, True):
            script = P['render'](self.baseline, self.wrapped_sum, self.image,
                                 'http://127.0.0.1:8767', 'http://127.0.0.1:8767/upload/test', enabled)
            self.assertNotRegex(script.decode(), r'@[A-Z_]+@')
            self.assertIn(b"[[ 'yes' == yes ]]" if enabled else b"[[ 'no' == yes ]]", script)
            subprocess.run(['/bin/bash', '-n'], input=script, check=True)

    def test_courier_ignored_on_error_by_boot_unit(self):
        text = (HERE / 'boot-stage.conf').read_text()
        self.assertIn('ExecStartPre=-/bin/bash /azahi-usb-stage.sh', text)
        self.assertNotIn('ExecStart=', text)

    def test_recovery_real_shell_with_hardware_mocks(self):
        # Reuse the existing mock definitions, not the original installer.
        tree = ast.parse((HERE.parent / 'standalone-loader/test-install.py').read_text())
        function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                        and n.name == 'test_recovery_shell_mock_paths')
        assignment = next(n for n in function.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'mocks' for t in n.targets))
        mocks = ast.literal_eval(assignment.value)
        preboot_device = plistlib.loads(self.snapshot['preboot.plist'])['DeviceIdentifier']
        mocks = mocks.replace('disk3s4', preboot_device).replace('standalone.bin', 'candidate.bin').replace('v5.bin', 'rollback.bin')
        cases = ('snapshot', 'install', 'rollback', 'wrong_uuid', 'wrong_policy',
                 'cancel', 'corrupt', 'kmutil_fail', 'upload_fail', 'disabled')
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix='usb-recovery-mock-') as temp:
                directory = Path(temp)
                (directory / 'objects').mkdir()
                for name in ('linux.plist', 'linux-container.plist'):
                    (directory / name).write_bytes(self.snapshot[name])
                if case == 'wrong_uuid':
                    data = plistlib.loads(self.snapshot['linux.plist'])
                    data['VolumeUUID'] = 'wrong'
                    (directory / 'linux.plist').write_bytes(plistlib.dumps(data))
                for writable in (False, True):
                    data = plistlib.loads(self.snapshot['preboot.plist'])
                    data['WritableVolume'] = writable
                    (directory / f'preboot-{str(writable).lower()}.plist').write_bytes(plistlib.dumps(data))
                policy = self.snapshot['policy-after.txt']
                if case == 'wrong_policy':
                    policy = policy.replace(b': Paired', b': Unpaired')
                (directory / 'policy-before.txt').write_bytes(policy)
                mode = case if case in ('snapshot', 'rollback') else 'install'
                new_coih = P['CURRENT_COIH'] if mode == 'rollback' else 'A'*96
                (directory / 'policy-after.txt').write_bytes(policy.replace(P['CURRENT_COIH'].encode(), new_coih.encode()))
                (directory / 'objects' / ('kernelcache.custom.' + P['CURRENT_COIH'])).write_bytes(self.snapshot['installed.bin'])
                (directory / 'current-rollback.bin').write_bytes(self.snapshot['installed.bin'])
                (directory / 'candidate.bin').symlink_to(B['OUTPUT'])
                (directory / 'rollback.bin').symlink_to(B['BASE'])
                (directory / 'mocks').write_text(mocks)
                script = P['render'](self.baseline, self.wrapped_sum, self.image,
                                     'http://127.0.0.1:8767', 'http://127.0.0.1:8767/upload/test',
                                     case != 'disabled').decode()
                old = 'bootdir="$mountpoint/$vg/boot/$nsih/System/Library/Caches/com.apple.kernelcaches"'
                self.assertEqual(script.count(old), 1)
                script = script.replace(old, 'bootdir="$TEST_DIR/objects"')
                script = script.replace('/tmp/azahi-usb-transfer.XXXXXX', temp + '/work.XXXXXX')
                (directory / 'helper.sh').write_text(script)
                env = dict(os.environ, BASH_ENV=str(directory / 'mocks'), TEST_DIR=temp,
                           TEST_CASE=case, TEST_NEW_COIH=new_coih, TEST_MODE=mode)
                answer = 'CANCEL\n' if case == 'cancel' else 'RESTORE\n' if mode == 'rollback' else 'INSTALL\n'
                result = subprocess.run(['/bin/bash', str(directory / 'helper.sh'), mode],
                                        input=answer, text=True, capture_output=True, env=env, timeout=60)
                events = (directory / 'events').read_text()
                if case in ('snapshot', 'install', 'rollback'):
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    if case == 'snapshot':
                        self.assertIn('BACKUP HOST-VERIFIED', result.stdout)
                        self.assertNotIn('kmutil', events)
                        self.assertNotIn('diskutil unmount', events)
                        self.assertNotIn('diskutil mount', events)
                    else:
                        self.assertEqual(events.count('kmutil configure-boot'), 1)
                        self.assertIn('INSTALLED AND HOST-VERIFIED', result.stdout)
                        self.assertIn('diskutil mount readOnly ' + preboot_device, events)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertNotIn('INSTALLED AND HOST-VERIFIED', result.stdout)
                    if case in ('wrong_uuid', 'wrong_policy', 'cancel', 'corrupt', 'disabled'):
                        self.assertNotIn('kmutil', events)
                        self.assertNotIn('diskutil unmount', events)

    def test_courier_real_shell_with_relocated_tmpfs_fixture(self):
        for case in ('pass', 'corrupt', 'existing', 'wrong_mount'):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix='usb-courier-test-') as temp:
                root = Path(temp)
                source = root / 'source'; source.mkdir()
                runtime = root / 'run'; runtime.mkdir()
                for name in B['FILES']:
                    (source / name).write_bytes((HERE / 'deliver' / name).read_bytes())
                if case == 'corrupt':
                    (source / 'azahi-usb-overlay.ko').write_bytes(b'corrupt')
                dest = runtime / 'azahi-usb-20260913'
                if case == 'existing':
                    dest.mkdir(); (dest / 'keep').write_text('preserve')
                sentinel = root / 'initrd-release'; sentinel.touch()
                script = (HERE / 'boot-stage.sh').read_text()
                script = script.replace('/etc/initrd-release', str(sentinel))
                script = script.replace('source_dir=/azahi-usb-20260913', 'source_dir=' + str(source))
                script = script.replace('/run/', str(runtime) + '/')
                script = script.replace('/usr/local/libexec/busybox.static sha256sum', 'hash_files')
                mocks = ('findmnt() { echo ' + ('ext4' if case == 'wrong_mount' else 'tmpfs') + '; }\n'
                         'hash_files() { /usr/bin/shasum -a 256 "$@"; }\n'
                         'mv() { /bin/mv -n "$3" "$4"; }\n')
                (root / 'mocks').write_text(mocks)
                result = subprocess.run(['/bin/bash', '-c', script], capture_output=True,
                                        env=dict(os.environ, BASH_ENV=str(root / 'mocks')))
                if case == 'pass':
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual({p.name for p in dest.iterdir()}, set(B['FILES']))
                else:
                    self.assertNotEqual(result.returncode, 0)
                    if case == 'existing':
                        self.assertEqual((dest / 'keep').read_text(), 'preserve')
                    else:
                        self.assertFalse(dest.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
