#!/usr/bin/env python3
"""Offline corruption/invariance checks for the courier-v2 boot image."""
import hashlib
import json
from pathlib import Path
import runpy
import unittest

HERE = Path(__file__).resolve().parent
V = runpy.run_path(str(HERE / 'build-transfer-v6.py'))


class ImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = V['OUTPUT'].read_bytes()
        cls.receipt = json.loads(V['OUTPUT'].with_suffix('.json').read_text())

    def test_full_image_invariants(self):
        V['inspect'](self.data, self.receipt)

    def test_wrong_hash_rejected(self):
        report = dict(self.receipt, image_sha256='0' * 64)
        with self.assertRaises(AssertionError):
            V['inspect'](self.data, report)

    def test_outer_padding_corruption_rejected(self):
        data = self.data[:-1] + bytes([self.data[-1] ^ 1])
        with self.assertRaises(AssertionError):
            V['inspect'](data, dict(self.receipt, image_sha256=hashlib.sha256(data).hexdigest()))

    def test_new_header_corruption_rejected(self):
        data = bytearray(self.data)
        data[V['B']['LOADER_SIZE'] + 24] ^= 1
        with self.assertRaises(AssertionError):
            V['inspect'](bytes(data), self.receipt)

    def test_no_driver_autoload_claim(self):
        self.assertIs(self.receipt['driver_auto_load'], False)
        self.assertIs(self.receipt['installed'], False)
        shell = (HERE / 'boot-stage-v2.sh').read_text()
        self.assertIn('PATH=/nonexistent', shell)
        for command in ('mktemp', 'cp', 'sha256sum', 'mv'):
            self.assertIn('"$BB" ' + command, shell)
        self.assertNotIn('insmod ', shell)
        self.assertNotIn('modprobe ', shell)


if __name__ == '__main__':
    unittest.main(verbosity=2)
