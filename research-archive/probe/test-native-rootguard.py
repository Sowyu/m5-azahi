#!/usr/bin/env python3
"""Host-only validation/failure-path tests; never opens any device."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import uuid

spec = importlib.util.spec_from_file_location('rootguard', Path(__file__).with_name('native-rootguard-test.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def superblock():
    data = bytearray(69632)
    data[65536 + 32:65536 + 48] = uuid.UUID(mod.FS_UUID).bytes
    data[65536 + 64:65536 + 72] = b'_BHRfS_M'
    struct.pack_into('<Q', data, 65536 + 112, mod.IMAGE_BYTES)
    struct.pack_into('<QII', data, 65536 + 136, 1, 4096, 16384)
    return data


class Tests(unittest.TestCase):
    def test_superblock(self):
        mod.check_superblock(superblock())

    def test_bad_superblocks(self):
        for offset in (32, 64, 112, 136, 144, 148):
            data = superblock()
            data[65536 + offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(RuntimeError):
                mod.check_superblock(data)

    def test_short_superblock(self):
        with self.assertRaises(RuntimeError):
            mod.check_superblock(superblock()[:-1])

    def test_test_extent_refuses_overlap(self):
        for offset in (0, mod.IMAGE_BYTES, mod.ROOT_BYTES):
            with patch.object(mod, 'TEST_OFFSET', offset), self.assertRaises(RuntimeError):
                mod.check_superblock(superblock())

    def test_region_hash(self):
        data = bytes(superblock())
        item = dict(name='root-prefix', offset=mod.ROOT_START, bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest())
        with patch.object(mod, 'read_at', return_value=data):
            mod.verify_regions(-1, dict(regions=[item]))
        with patch.object(mod, 'read_at', return_value=b'wrong'), self.assertRaises(RuntimeError):
            mod.verify_regions(-1, dict(regions=[item]))

    def exercise_case(self, failure=None):
        old = bytes(mod.TEST_BYTES)
        state = [old]
        calls = []

        def read(fd, offset):
            self.assertEqual(offset, mod.TEST_OFFSET)
            if failure == 'readback' and len(calls) == 1:
                return b'wrong'
            return state[0]

        def write(fd, offset, data):
            self.assertEqual(offset, mod.TEST_OFFSET)
            self.assertEqual(len(data), mod.TEST_BYTES)
            calls.append(data)
            state[0] = data
            if failure == 'flush' and len(calls) == 1:
                raise OSError('simulated flush error after write')
            if failure == 'restore' and len(calls) == 2:
                state[0] = b'failed restore'

        with tempfile.TemporaryDirectory(prefix='azahi-rootguard-test-') as directory:
            backup = Path(directory) / 'backup.bin'
            with patch.object(mod, 'direct_read', side_effect=read), patch.object(mod, 'direct_write', side_effect=write):
                if failure:
                    with self.assertRaises((RuntimeError, OSError)):
                        mod.exercise(-1, backup)
                else:
                    mod.exercise(-1, backup)
            self.assertEqual(backup.read_bytes(), old)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1], old)
        if failure != 'restore':
            self.assertEqual(state[0], old)

    def test_success_restores(self):
        self.exercise_case()

    def test_failed_flush_restores(self):
        self.exercise_case('flush')

    def test_failed_readback_restores(self):
        self.exercise_case('readback')

    def test_failed_restore_is_not_success(self):
        self.exercise_case('restore')

    def test_unbounded_write_refused_before_syscall(self):
        for offset, data in ((0, bytes(mod.TEST_BYTES)), (mod.TEST_OFFSET, b'x')):
            with self.assertRaises(RuntimeError):
                mod.direct_write(-1, offset, data)

    def test_read_alignment(self):
        with self.assertRaises(RuntimeError):
            mod.read_at(-1, 1, 4096)


if __name__ == '__main__':
    unittest.main()
