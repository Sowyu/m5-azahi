#!/usr/bin/env python3
"""Host-only padding and immutable-content regression tests."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import unittest

A = runpy.run_path(str(Path(__file__).with_name('build-aligned.py')))


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = A['OUTPUT'].read_bytes()
        cls.receipt = json.loads(A['OUTPUT'].with_suffix('.json').read_text())

    def test_exact_v2_plus_170_zeros(self):
        A['inspect'](self.data, self.receipt)
        self.assertEqual(self.data, A['SOURCE'].read_bytes() + bytes(170))

    def test_bad_padding_and_content(self):
        for offset in (2048, 1114112, 92651349, 92651350, len(self.data) - 1):
            data = bytearray(self.data)
            data[offset] ^= 1
            receipt = copy.deepcopy(self.receipt)
            receipt['image_sha256'] = hashlib.sha256(data).hexdigest()
            with self.assertRaises(AssertionError):
                A['inspect'](data, receipt)

    def test_unaligned_or_extra_page_refused(self):
        for data in (self.data[:-1], self.data[:-170], self.data + bytes(16384)):
            receipt = copy.deepcopy(self.receipt)
            receipt['image_sha256'] = hashlib.sha256(data).hexdigest()
            receipt['image_bytes'] = len(data)
            with self.assertRaises(AssertionError):
                A['inspect'](data, receipt)


if __name__ == '__main__':
    unittest.main()
