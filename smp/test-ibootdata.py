#!/usr/bin/env python3
"""In-memory format/bounds checks; no Apple firmware or hardware required."""
import importlib.util
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('ibootdata', Path(__file__).with_name('decode-ibootdata.py'))
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)


def fixture():
    data = bytearray(0x300)
    struct.pack_into('<8I', data, 0, *decoder.HEADER)
    data[0x40:0x47] = b'test-1\0'
    struct.pack_into('<QQ', data, 0x100, 0x200, 0x208)
    struct.pack_into('<IIQ', data, 0x110, 0x52436667, 5, 0x1b0)
    struct.pack_into('<IIIIQ', data, 0x120, 0x6050, 0x21, 0, 1, 0x110)
    struct.pack_into('<Q', data, 0x200, 0x120)
    for kind in range(4):
        offset = 0x240 + kind * 16
        struct.pack_into('<IIQ', data, 0x1b0 + kind * 16, kind, 16, offset)
        # All ten opcode and sequence bits must survive, including flags.
        struct.pack_into('<4I', data, offset,
                         (0xa << 28) | (1023 << 18) | (0x3ab << 8) | 3,
                         2, 0x80688008, 1)
    struct.pack_into('<IIQ', data, 0x1f0, 4, 66, 0x280)
    struct.pack_into('<H', data, 0x280, 1023)
    data[0x282:0x289] = b'SAMPLE\0'
    return data[:0x2c2]


class FormatChecks(unittest.TestCase):
    def test_cli_preserves_guards_from_another_sequence(self):
        data = fixture()
        # A guard and end marker can carry a different name from their body.
        data.extend(bytes(66))
        struct.pack_into('<I', data, 0x1f4, 132)
        struct.pack_into('<H', data, 0x2c2, 1)
        data[0x2c4:0x2ca] = b'GUARD\0'
        struct.pack_into('<IIQ', data, 0x1b0, 0, 24, len(data))
        data.extend(struct.pack('<6I', (1 << 18) | (0xba << 8) | 2, 16, 0,
                                (1023 << 18) | (0xda << 8) | 1, 1448,
                                (1 << 18) | (0xc8 << 8)))
        for flags, names in (([], None), (['--sequence', 'SAMPLE'], ['SAMPLE']),
                             (['--all-records'], ['GUARD', 'SAMPLE', 'GUARD'])):
            with self.subTest(flags=flags), \
                    patch.object(sys, 'argv', ['decode-ibootdata.py', 'fixture', *flags]), \
                    patch.object(Path, 'is_file', return_value=True), \
                    patch.object(Path, 'open', return_value=io.BytesIO(data)), \
                    redirect_stdout(io.StringIO()) as output:
                self.assertEqual(decoder.main(), 0)
            section = json.loads(output.getvalue())['sections'][0]
            self.assertEqual(section['instruction_count'], 3)
            if names is None:
                self.assertNotIn('records', section)
            else:
                self.assertEqual([r['name'] for r in section['records']], names)
        for flag, value in (('--sequence', 'SAMPLE'), ('--word', '1448')):
            with patch.object(sys, 'argv', ['decode-ibootdata.py', 'fixture',
                                           '--all-records', flag, value]), \
                    redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit) as failure:
                decoder.main()
            self.assertEqual(failure.exception.code, 2)
            self.assertIn('cannot be combined', error.getvalue())

    def test_fields_and_full_section_consumption(self):
        result = decoder.decode(fixture())
        self.assertEqual(result['banner'], 'test-1')
        self.assertEqual(result['targets'], [{'chip': 0x6050, 'revision': 0x21, 'selector': 0}])
        for section in result['sections']:
            self.assertEqual(section['records'], [
                {'offset': 0x240 + section['kind'] * 16, 'sequence': 1023,
                 'name': 'SAMPLE', 'opcode': 0x3ab, 'flags': 0xa,
                 'operands': [2, 0x80688008, 1]}])

    def test_every_truncation_is_refused(self):
        data = fixture()
        for length in range(len(data)):
            with self.subTest(length=length), self.assertRaises(ValueError):
                decoder.decode(data[:length])

    def test_malformed_structure_and_instruction_boundaries(self):
        for offset, fmt, value in (
            (0, '<I', 0), (8, '<I', 2), (0x100, '<Q', 0xffffffffffffffff),
            (0x108, '<Q', 0x1f8), (0x200, '<Q', 0xffffffffffffffff),
            (0x120, '<I', 0x9999), (0x12c, '<I', 2),
            (0x118, '<Q', 0xffffffffffffffff), (0x114, '<I', 6),
            (0x1c0, '<I', 0), (0x1c8, '<Q', 0x240),
            (0x1b4, '<I', 15), (0x1f4, '<I', 65),
            (0x240, '<B', 4), (0x240, '<B', 33),
            (0x240, '<I', 3), (0x282, '<B', 0),
        ):
            data = fixture()
            struct.pack_into(fmt, data, offset, value)
            with self.subTest(offset=hex(offset), value=value), self.assertRaises(ValueError):
                decoder.decode(data)


if __name__ == '__main__':
    unittest.main()
