#!/usr/bin/env python3
"""Regression for the exact loader check missed in the v4 packaging tests."""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
F = runpy.run_path(str(HERE / 'build-transfer-fixed.py'))
B = F['B']


class FixedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = F['OUTPUT'].read_bytes()
        cls.receipt = json.loads(F['OUTPUT'].with_suffix('.json').read_text())

    def test_fixed_image_invariants(self):
        F['inspect'](self.data, self.receipt)

    def test_actual_loader_bounds_reject_v4_accept_fixed(self):
        source = (HERE.parent / 'standalone-loader/m1n1-20260911/src/azahi_standalone.c').read_text()
        start = source.index('    if (h->version != 1')
        end = source.index('    u64 end =', start)
        condition = source[start:end]
        original = B['parts'](B['BASE'].read_bytes())
        bad = B['parts'](F['SOURCE'].read_bytes())
        fixed = B['parts'](self.data)
        definitions = '''
#include <assert.h>
#include <stdint.h>
typedef uint32_t u32;
struct bundle_header {
 char magic[8]; u32 version, args_len, dt_len, gzip_len, initrd_len;
 u32 args_crc, dt_crc, gzip_crc, initrd_crc;
};
static int stop(const char *s) { (void)s; return -1; }
'''
        code = definitions + f'#define INITRD_BYTES {F["loader_length"]()}U\n'
        code += 'static int check(const struct bundle_header *h) {\n' + condition + 'return 0; }\n'
        code += 'int main(void) {\n'
        for parts, result in ((original, 0), (bad, -1), (fixed, 0)):
            code += ('{ struct bundle_header h = {.version=1, '
                     + ', '.join(f'.{field}_len={len(parts[field])}' for field in ('args', 'dt', 'gzip', 'initrd'))
                     + f'}}; assert(check(&h)=={result}); }}\n')
        code += 'return 0; }\n'
        with tempfile.TemporaryDirectory(prefix='usb-loader-bounds-') as temp:
            path = Path(temp)
            (path / 'test.c').write_text(code)
            subprocess.run(['/usr/bin/cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            str(path / 'test.c'), '-o', str(path / 'test')], check=True)
            subprocess.run([str(path / 'test')], check=True)

    def test_initrd_matches_loader_length(self):
        self.assertEqual(len(B['parts'](self.data)['initrd']), F['loader_length']())
        self.assertNotEqual(len(B['parts'](F['SOURCE'].read_bytes())['initrd']), F['loader_length']())

    def test_corrupted_padding_rejected(self):
        data = bytearray(self.data)
        # The outer alignment padding and initrd zero padding are checked.
        for offset in (-1, -200):
            corrupt = bytearray(data)
            corrupt[offset] ^= 1
            receipt = dict(self.receipt, image_sha256=hashlib.sha256(corrupt).hexdigest())
            with self.assertRaises(AssertionError):
                F['inspect'](bytes(corrupt), receipt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
