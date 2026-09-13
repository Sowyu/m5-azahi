#!/usr/bin/env python3
"""Offline board-ADT and fail-closed power preparation tests."""
from pathlib import Path
import runpy
import sys
import types
import unittest

sys.path[:0] = ['/PRIVATE-USER/azahi/lib', '/PRIVATE-USER/azahi/proxyclient']
from m1n1.adt import load_adt
root = Path(__file__).resolve().parent.parent
helper = runpy.run_path(str(root / 'probe/prepare-native-ans.py'))
prepare, domains = helper['prepare'], helper['DOMAINS']


class Proxy:
    def __init__(self):
        self.regs = {addr: 0xf0000ff for _, addr in domains}
        self.regs[domains[-1][1]] = 0x1000030f
        self.regs[0x419600044] = 16
        self.writes = []
    def read32(self, addr):
        return self.regs[addr]
    def mask32(self, addr, clear, value):
        self.writes.append((addr, clear, value))
        self.regs[addr] = 0xf0003ff
    def nop(self):
        pass


class Tests(unittest.TestCase):
    def setUp(self):
        self.util = types.SimpleNamespace(adt=load_adt((root / 'adt-real-t6050.bin').read_bytes()))
        self.proxy = Proxy()
    def test_cold_readonly_refuses(self):
        with self.assertRaises(RuntimeError):
            prepare(self.proxy, self.util)
        self.assertEqual(self.proxy.writes, [])
    def test_one_exact_activation(self):
        prepare(self.proxy, self.util, activate=True)
        self.assertEqual(self.proxy.writes, [(0x280900150, 0x1000030f, 15)])
    def test_active_no_write(self):
        self.proxy.regs[0x280900150] = 0xf0003ff
        prepare(self.proxy, self.util, activate=True)
        self.assertEqual(self.proxy.writes, [])
    def test_bad_parent_refuses_before_write(self):
        self.proxy.regs[0x280900140] = 0
        with self.assertRaises(RuntimeError):
            prepare(self.proxy, self.util, activate=True)
        self.assertEqual(self.proxy.writes, [])
    def test_fault_refuses(self):
        self.proxy.regs[0x280900128] = 0xabad1dea
        with self.assertRaises(RuntimeError):
            prepare(self.proxy, self.util, activate=True)
        self.assertEqual(self.proxy.writes, [])
    def test_unknown_link_refuses(self):
        self.proxy.regs[0x280900150] = 0
        with self.assertRaises(RuntimeError):
            prepare(self.proxy, self.util, activate=True)
        self.assertEqual(self.proxy.writes, [])
    def test_off_firmware_never_reset(self):
        self.proxy.regs[0x280900150] = 0xf0003ff
        self.proxy.regs[0x419600044] = 0
        with self.assertRaises(RuntimeError):
            prepare(self.proxy, self.util, activate=True)
        self.assertEqual(self.proxy.writes, [])


if __name__ == '__main__':
    unittest.main()
