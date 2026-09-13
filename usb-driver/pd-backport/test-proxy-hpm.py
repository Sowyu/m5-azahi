#!/usr/bin/env python3
"""Offline FFI and HPM policy tests. Never open a serial device."""
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('hpm', HERE / 'proxy-hpm.py')
hpm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hpm)


class FakeProxy:
    def __init__(self, replies=()):
        self.replies = list(replies)
        self.writes = []
        self.reads = []
        self.fail = False

    def read32(self, address):
        self.reads.append(address)
        if self.fail:
            raise OSError('synthetic failure')
        if address == hpm.BASE + 0x200:
            return 0x4000 if self.writes and self.replies else 0x40004000
        if address != hpm.BASE + 0x220 or not self.replies:
            raise RuntimeError('Unexpected fake MMIO read')
        return self.replies.pop(0)

    def write32(self, address, value):
        if address != hpm.BASE + 0x210:
            raise RuntimeError('Unexpected fake MMIO write')
        self.writes.append(value)


class FakeHPM:
    def __init__(self):
        self.regs = {0: bytes.fromhex('51040000'), 3: b'APP ', 8: bytes(4),
                     9: b'\0', 0x1a: bytes(4), 0x20: b'\x05',
                     0x3f: bytes(2), 0x5f: bytes(4)}
        self.selected = None
        self.calls = []
        self.busy = 0
        self.wrong = False
        self.short = False
        self.reject = False
        self.pending = False
        self.sleeping = False

    def transfer(self, op, address=0, out=b'', count=0):
        self.calls.append((op, address, out, count))
        if op == 0x80:
            self.selected = out[0]
            return b''
        if op == 0x60 and address == 0:
            if self.sleeping: return b'\0'
            if self.wrong: return b'\x7e'
            if self.busy:
                self.busy -= 1
                return bytes([self.selected | 0x80])
            return bytes([self.selected])
        if op == 0x60 and address == 0x1f:
            return bytes([0 if self.short else 64])
        if op == 0x20 and address == 0x20:
            return self.regs[self.selected][:count]
        if op == 0 and address == 0xa0:
            if self.selected == 9 and out == b'\0':
                self.regs[9] = out
            elif self.selected == 8 and out == b'SSPS':
                if self.reject: self.regs[8] = b'!CMD'
                elif self.pending: self.regs[8] = b'SSPS'
                else:
                    self.regs[8] = bytes(4)
                    self.regs[0x20] = b'\0'
            else:
                raise RuntimeError('Unexpected logical write')
            return b''
        raise RuntimeError('Unexpected transaction')


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.lib = hpm.build_bridge()

    def test_ffi_uses_real_c_wire_encoding(self):
        p = FakeProxy([0x8c13])
        t = hpm.Transport(self.lib, p)
        self.assertEqual(t.transfer(0x13), b'')
        self.assertEqual(p.writes, [0xc13])

    def test_ffi_read_and_latched_bad_reply(self):
        p = FakeProxy([0x10c60, 0x5a])
        t = hpm.Transport(self.lib, p)
        self.assertEqual(t.transfer(0x60, count=1), b'\x5a')
        p = FakeProxy([0x8d13])
        t = hpm.Transport(self.lib, p)
        with self.assertRaises(RuntimeError): t.transfer(0x13)
        self.assertEqual(p.writes, [0xc13])
        counts = len(p.reads), len(p.writes)
        with self.assertRaises(RuntimeError): t.transfer(0x13)
        self.assertEqual(counts, (len(p.reads), len(p.writes)))

    def test_callback_exception_blocks_all_subsequent_io(self):
        p = FakeProxy(); p.fail = True
        t = hpm.Transport(self.lib, p)
        with self.assertRaises(RuntimeError): t.transfer(0x13)
        self.assertEqual(len(p.reads), 1)
        self.assertEqual(p.writes, [])
        with self.assertRaises(RuntimeError): t.transfer(0x13)
        self.assertEqual(len(p.reads), 1)

    def test_status_snapshot_has_no_logical_writes(self):
        p = FakeHPM(); c = Clock(); q = hpm.HPM(p, c, c.sleep)
        self.assertEqual(q.snapshot()['03'], b'APP '.hex())
        self.assertEqual(p.calls[0], (0x80, 0, b'\x03', 0))
        self.assertFalse(any(op == 0 for op, *_ in p.calls))

    def test_selector_delayed_success(self):
        p = FakeHPM(); p.busy = 3; c = Clock(); q = hpm.HPM(p, c, c.sleep)
        self.assertEqual(q.read(3), b'APP ')
        self.assertAlmostEqual(c.now, 0.03)

    def test_selector_timeout_latches(self):
        p = FakeHPM(); p.busy = 1000; c = Clock(); q = hpm.HPM(p, c, c.sleep)
        with self.assertRaises(TimeoutError): q.read(3)
        count = len(p.calls)
        with self.assertRaises(RuntimeError): q.read(3)
        self.assertEqual(count, len(p.calls))
        self.assertLessEqual(count, 101)

    def test_bad_selector_size_and_sleeping_rejected(self):
        for flag in ('wrong', 'short', 'sleeping'):
            p = FakeHPM(); setattr(p, flag, True); q = hpm.HPM(p)
            with self.assertRaises(RuntimeError): q.snapshot()
            self.assertTrue(q.failed)
            self.assertFalse(any(op == 0 for op, *_ in p.calls))

    def test_s0_exact_writes_and_readback(self):
        p = FakeHPM(); q = hpm.HPM(p)
        self.assertIn('readback confirmed', q.enter_s0())
        self.assertEqual([call for call in p.calls if call[0] == 0],
                         [(0, 0xa0, b'\0', 0), (0, 0xa0, b'SSPS', 0)])
        count = len(p.calls)
        with self.assertRaises(RuntimeError): q.enter_s0()
        self.assertEqual(len(p.calls), count)

    def test_already_s0_no_write(self):
        p = FakeHPM(); p.regs[0x20] = b'\0'; q = hpm.HPM(p)
        self.assertIn('already-S0', q.enter_s0())
        self.assertFalse(any(op == 0 for op, *_ in p.calls))

    def test_wrong_identity_mode_fault_state_or_busy_no_write(self):
        for reg, value in ((0, bytes(4)), (0, b'\xff'*4), (3, b'BOOT'),
                           (0x1a, (1 << 16).to_bytes(4, 'little')),
                           (0x20, b'\x99'), (8, b'TEST')):
            p = FakeHPM(); p.regs[reg] = value; q = hpm.HPM(p)
            with self.assertRaises(RuntimeError): q.enter_s0()
            self.assertTrue(q.failed)
            self.assertFalse(any(op == 0 for op, *_ in p.calls))

    def test_reject_and_timeout_no_retry(self):
        for flag in ('reject', 'pending'):
            p = FakeHPM(); setattr(p, flag, True); c = Clock(); q = hpm.HPM(p, c, c.sleep)
            with self.assertRaises((RuntimeError, TimeoutError)): q.enter_s0()
            self.assertEqual(len([call for call in p.calls if call[0] == 0]), 2)
            count = len(p.calls)
            with self.assertRaises(RuntimeError): q.enter_s0()
            self.assertEqual(len(p.calls), count)

    def test_unlisted_register_no_io(self):
        p = FakeHPM(); q = hpm.HPM(p)
        for reg in (0x15, 0x17, 0x19, 0x80, -1):
            with self.assertRaises(RuntimeError): q.read(reg)
        self.assertEqual(p.calls, [])

    def test_saved_tree_identity(self):
        sys.path[:0] = [str(hpm.ROOT / 'pylib'), str(hpm.ROOT / 'proxy-kit/proxyclient')]
        from m1n1.adt import load_adt
        tree = load_adt((hpm.ROOT / 'adt-real-t6050.bin').read_bytes())
        hpm.verify_tree(tree)
        tree['/arm-io/nub-spmi-a1']._properties['gen'] = 1
        with self.assertRaises(RuntimeError): hpm.verify_tree(tree)


if __name__ == '__main__': unittest.main(verbosity=2)
