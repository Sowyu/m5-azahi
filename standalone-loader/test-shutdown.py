#!/usr/bin/env python3
"""Run the v8 shutdown builder on a synthetic bundle; no target access."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib

sys.dont_write_bytecode = True  # keep the source tree clean
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('build_shutdown', HERE / 'build-shutdown.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

DTS = '''/dts-v1/;
/ {
	compatible = "apple,j714s", "apple,t6050", "apple,arm-platform";
	#address-cells = <2>;
	#size-cells = <2>;
	soc {
		compatible = "simple-bus";
		#address-cells = <2>;
		#size-cells = <2>;
		ranges;
		smc@28c600000 {
			compatible = "apple,t6050-smc", "apple,t8103-smc";
			reg = <0x2 0x8c600000 0x0 0x4000>, <0x2 0x8de00000 0x0 0x140000>;
			reg-names = "smc", "sram";
			gpio {
				compatible = "apple,smc-low-gpio";
				gpio-controller;
				#gpio-cells = <2>;
			};
		};
	};
};
'''


def bundle(dtb):
    # A loader that contains the magic literal, like the real one does.
    loader = b'\x00' * 2048 + b'AZAHI1\0\0' + os.urandom(5000)
    sections = [b'maxcpus=1 azahi.ssd_root=1\0', dtb, os.urandom(96), os.urandom(4000)]
    header = builder.HEADER.pack(b'AZAHI1\0\0', 1, *(len(s) for s in sections),
                                 *(zlib.crc32(s) for s in sections))
    data = loader + header + b''.join(sections)
    return data + bytes((-len(data)) % 16384), len(loader)


@unittest.skipUnless(all(shutil.which(t) for t in ('dtc', 'fdtget', 'fdtput')), 'needs dtc, fdtget, fdtput')
class ShutdownCandidate(unittest.TestCase):
    def compile(self, source):
        return subprocess.run(['dtc', '-q', '-I', 'dts', '-O', 'dtb'], input=source.encode(),
                              capture_output=True, check=True).stdout

    def test_adds_only_reboot_node(self):
        data, loader_bytes = bundle(self.compile(DTS))
        image, offset, previous, new = builder.build(data)
        self.assertEqual(offset, loader_bytes)
        self.assertEqual(image[:offset], data[:offset])
        self.assertEqual(len(image) % 16384, 0)
        for name in ('args', 'gzip', 'initrd'):
            self.assertEqual(new[name], previous[name])
        with tempfile.NamedTemporaryFile(suffix='.dtb') as dt:
            dt.write(new['dt'])
            dt.flush()
            compatible = subprocess.check_output(['fdtget', '-t', 's', dt.name, builder.NODE,
                                                  'compatible'], text=True).strip()
            self.assertEqual(compatible, 'apple,smc-reboot')
            listed = subprocess.check_output(['fdtget', '-p', dt.name, builder.NODE], text=True)
            self.assertEqual(listed.split(), ['compatible'])  # no nvmem cells, no status
        # A second run must refuse rather than add a duplicate or edit further.
        with self.assertRaises(RuntimeError):
            builder.build(image)

    def test_refuses_unexpected_trees(self):
        for source in (DTS.replace('smc@28c600000', 'smc@28c700000'),
                       DTS.replace('"apple,t6050-smc", "apple,t8103-smc"', '"apple,other"'),
                       DTS.replace('gpio {', 'rtc { compatible = "apple,smc-rtc"; };\n\t\t\tgpio {')):
            with self.subTest(source=source[-400:]), self.assertRaises(RuntimeError):
                builder.build(bundle(self.compile(source))[0])
        data, loader_bytes = bundle(self.compile(DTS))
        end = loader_bytes + builder.HEADER.size + sum(len(v) for v in builder.split(data)[1].values())
        corrupt = data[:end - 1] + bytes([data[end - 1] ^ 1]) + data[end:]
        with self.assertRaises(RuntimeError):  # last initrd byte flipped: no valid header
            builder.build(corrupt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
