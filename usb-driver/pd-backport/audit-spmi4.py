#!/usr/bin/env python3
"""Host-only, private-fixture audit of T6050 SPMI generation compatibility.

Never opens a device, executes firmware, writes MMIO, emits a device tree or
publishes firmware bytes. Requires the private workspace fixtures and the
Capstone environment used by probe/inspect-kernelcache.py. Facts established
here are not authorization to initialize the bus or proof of working VBUS.
"""
from pathlib import Path
import hashlib
import re
import runpy
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'pylib'), str(ROOT / 'proxy-kit/proxyclient')]
from m1n1.adt import load_adt


class Spmi4Audit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        image = ROOT / 'probe/firmware-analysis/kernelcache.mac17j.macho'
        adt_file = ROOT / 'adt-real-t6050.bin'
        assert hashlib.sha256(image.read_bytes()).hexdigest() == (
            '26ddfbe95c7e6ac9a76aedac424576bf00467e7c13da49dd82f8010efdb75093')
        assert hashlib.sha256(adt_file.read_bytes()).hexdigest() == (
            '5a87c2ee23c945694303a4396fbbf197918220f87441a41505838a3c37277a24')
        cls.adt = load_adt(adt_file.read_bytes())
        previous = sys.argv
        try:
            sys.argv = ['inspect-kernelcache.py', str(image), '--entry',
                        'com.apple.driver.AppleSPMI', '--symbol', '^$', '--symbols-only']
            cls.kc = runpy.run_path(str(ROOT / 'probe/inspect-kernelcache.py'))
        finally:
            sys.argv = previous
        cls.stock = (HERE / 'build/exact/linux-7.0.13/drivers/spmi/'
                     'spmi-apple-controller.c').read_text()
        assert hashlib.sha256(cls.stock.encode()).hexdigest() == (
            '7c8d712b594258e5231dd1dfbb99029bde289ebea60eb1a7f59e5367b0b827f3')

    def words(self, address, count, fmt='Q'):
        size = struct.calcsize('<' + fmt * count)
        return struct.unpack('<' + fmt * count, self.kc['read_va'](address, size))

    def instructions(self, address, size):
        return [(i.mnemonic, i.op_str) for i in self.kc['dis'].disasm(
            self.kc['read_va'](address, size), address)]

    def test_target_and_generation(self):
        self.assertEqual(self.adt.model, 'Mac17,9')
        n = self.adt['/arm-io/nub-spmi-a1']
        self.assertEqual(n._properties['gen'], 4)
        self.assertEqual([n.get_reg(i) for i in range(3)], [
            (0x28a1a8000, 0x4000), (0x28a1a4000, 0x4000), (0x28a1a0000, 0x4000)])

    def test_right_hpm_identity_and_missing_select_entry(self):
        h = self.adt['/arm-io/nub-spmi-a1/hpm2']
        self.assertEqual(h._properties['port-location'], 'right')
        self.assertEqual(h._properties['port-number'], 3)
        self.assertEqual(list(h.interrupts), [11, 17, 19])
        self.assertEqual(struct.unpack('<3I', h._properties['interrupt-type']), (0, 2, 3))
        # No interpolation of an unlisted select interrupt is performed.

    def test_fifo_offsets_and_initializer_binding(self):
        self.assertEqual(self.words(0xfffffe00075e2a80, 2), (0x200, 0x210))
        ins = self.instructions(0xfffffe00096b5a10, 0x1c8)
        self.assertIn(('ldr', 'q1, [x8, #0xa80]'), ins)
        self.assertIn(('str', 'q1, [x0, #0x30]'), ins)
        self.assertIn(('add', 'x8, x2, #0x220'), ins)
        self.assertIn(('str', 'x8, [x0, #0x40]'), ins)

    def test_status_masks(self):
        self.assertEqual(self.words(0xfffffe00075e2a90, 4, 'I'),
                         (1 << 15, 1 << 14, 1 << 31, 1 << 30))

    def test_interrupt_layout_and_stride(self):
        self.assertEqual(self.words(0xfffffe00075e2aa0, 2), (0x400, 0x600))
        ins = self.instructions(0xfffffe00096b5a10, 0x1c8)
        self.assertIn(('ldr', 'q1, [x8, #0xaa0]'), ins)
        self.assertIn(('stur', 'q1, [x0, #0x78]'), ins)
        self.assertIn(('mov', 'w8, #4'), ins)
        self.assertIn(('str', 'w8, [x0, #0x70]'), ins)
        # The register view starts 0x28 into the handler object.
        self.assertIn(('add', 'x0, x0, #0x28'),
                      self.instructions(0xfffffe00096b5bd8, 0xc))
        # clearInterrupt uses the second pointer and the stored bank stride.
        ins = self.instructions(0xfffffe00096b6020, 0x64)
        self.assertIn(('ldr', 'x8, [x0, #0x80]'), ins)
        self.assertIn(('ldr', 'w9, [x0, #0x70]'), ins)

    def test_old_controller_is_not_generation4(self):
        for name, value in [('STATUS', '0'), ('CMD', '0x4'), ('RSP', '0x8')]:
            self.assertRegex(self.stock, rf'#define SPMI_{name}_REG {value}\s')
        self.assertIn('#define SPMI_RX_FIFO_EMPTY BIT(24)', self.stock)
        self.assertNotRegex(self.stock, r'ctrl->cmd\s*=')
        self.assertNotIn('irq_domain', self.stock)

    def test_fedora_patchsets_do_not_change_spmi_controller(self):
        for name in ['patch-7.0-redhat.patch', 'linux-kernel-test.patch']:
            patch = (ROOT / 'input-driver/build/srpm' / name).read_text()
            self.assertIsNone(re.search(r'^diff --git a/drivers/spmi/', patch, re.M))


if __name__ == '__main__':
    unittest.main(verbosity=2)
