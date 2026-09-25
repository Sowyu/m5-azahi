#!/usr/bin/env python3
"""Synthetic fixtures only. No genuine credentials or hardware access."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('guard', HERE / 'check-publication.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class ContentTests(unittest.TestCase):
    def problems(self, data=b'ordinary source\n', path='README.md', mode=b'100644'):
        return guard.content_issues(path, mode, data, {'README.md', path} if path != 'unreviewed.md' else {'README.md'})

    def test_normal_source(self):
        self.assertEqual(self.problems(), [])

    def test_redacted_serial_placeholder(self):
        self.assertEqual(self.problems(b'usbmodemPRIVATE_01'), [])

    def test_gpl_page_break_only_in_license(self):
        self.assertEqual(self.problems(b'page\fnext', path='LICENSES/GPL-2.0.txt'), [])
        self.assertIn('binary-control-bytes', self.problems(b'page\fnext'))

    def test_unreviewed_path(self):
        self.assertIn('path-not-reviewed', self.problems(path='unreviewed.md'))

    def test_forbidden_extensions_case_insensitive(self):
        for suffix in ('JPG', 'bin', 'im4p', 'plist', 'zip', 'pem', 'log'):
            with self.subTest(suffix=suffix):
                self.assertIn('binary-or-private-extension', self.problems(path='file.' + suffix))

    def test_private_paths(self):
        for path in ('logs/readme.md', '.env.production', 'backups/a.md', '.ssh/config'):
            with self.subTest(path=path):
                self.assertIn('private-path', self.problems(path=path))

    def test_binary_renamed_as_text(self):
        self.assertIn('binary-control-bytes', self.problems(b'header\0payload'))
        self.assertIn('not-utf8-text', self.problems(b'\xff\xfe'))

    def test_symlink_and_submodule(self):
        for mode in (b'120000', b'160000'):
            self.assertIn('symlink-submodule-or-unsupported-mode', self.problems(mode=mode))

    def test_oversize(self):
        self.assertIn('file-too-large', self.problems(b'x' * (guard.MAX_FILE + 1)))

    def test_fake_secret_rules(self):
        samples = {
            'github-token': b'gh' + b'p_' + b'A' * 32,
            'cloud-key': b'AK' + b'IA' + b'Z' * 16,
            'private-key': b'-----BEGIN ' + b'OPENSSH PRIVATE KEY-----',
            'api-token': b'sk-' + b'proj-' + b'A' * 30,
            'slack-token': b'xox' + b'b-' + b'A' * 25,
            'device-uuid': b'-'.join([b'a' * 8, b'b' * 4, b'c' * 4, b'd' * 4, b'e' * 12]),
            'private-lan': b'.'.join([b'192', b'168', b'55', b'44']),
            'device-ecid': b'ECID: ' + b'0x' + b'B' * 14,
            'serial-port-id': b'usbmodem' + b'EXAMPLE123',
            'mac-address': b':'.join([b'ab'] * 6),
            'personal-home': b'/Users' + b'/example/Documents/',
            'flattened-personal-home': b'-Users' + b'-example-Documents-',
            'upload-capability': b'/upload/' + b'a' * 32,
            'url-credentials': b'https://' + b'user:example-password@host.invalid',
            'literal-secret': b'password' + b'="synthetic-value-only"',
            'private-net': b'.'.join([b'100', b'101', b'102', b'103']),
            'quoted-secret': b'{"pass' + b'word": "synthetic-value-only"}',
        }
        for rule, data in (('private-net', b'fd12' + b':3456:789a::1'), ('private-net', b'fe80' + b'::1'),
                           ('private-net', b'169.' + b'254.10.5'),
                           ('literal-secret', b'PASSWORD' + b'="synthetic-value" # note'),
                           ('private-key', b'-----BEGIN PGP ' + b'PRIVATE KEY BLOCK-----'),
                           ('private-key', b'b3BlbnNzaC1r' + b'ZXktdjEAAAAA'),
                           ('mac-address', b'-'.join([b'a4'] * 6)), ('mac-address', b'a483.' + b'e711.2233')):
            with self.subTest(rule=rule, data=data):
                self.assertIn(rule, self.problems(data))
        for rule, data in samples.items():
            with self.subTest(rule=rule):
                self.assertIn(rule, self.problems(data))


class GitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='publication-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic test')
        self.git('config', 'user.email', 'test@example.invalid')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True)

    def check(self, *args):
        return subprocess.run(['python3', str(HERE / 'check-publication.py'), *args],
                              cwd=self.root, capture_output=True, text=True)

    def stage(self, data):
        (self.root / 'README.md').write_bytes(data)
        self.git('add', 'README.md')

    def test_index_not_working_tree(self):
        self.stage(b'gh' + b'p_' + b'Z' * 32)
        (self.root / 'README.md').write_text('clean working tree, secret still staged\n')
        result = self.check('--staged')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('github-token', result.stderr)
        self.assertNotIn('Z' * 32, result.stderr)

    def test_removed_secret_still_blocks_history(self):
        self.stage(b'gh' + b'p_' + b'Z' * 32)
        self.git('commit', '-qm', 'synthetic bad history')
        self.stage(b'clean replacement\n')
        self.git('commit', '-qm', 'remove synthetic secret')
        self.assertEqual(self.check('--staged').returncode, 0)
        self.assertNotEqual(self.check('--history').returncode, 0)

    def test_force_added_unreviewed_file(self):
        (self.root / 'unknown.md').write_text('harmless but not reviewed\n')
        self.git('add', '-f', 'unknown.md')
        self.assertNotEqual(self.check('--staged').returncode, 0)

    def test_symlink_does_not_read_target(self):
        (self.root / 'README.md').symlink_to('/nonexistent-private-fixture')
        self.git('add', 'README.md')
        result = self.check('--staged')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unsupported-mode', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
