#!/usr/bin/env python3
"""Offline verification of the right-socket USB2 host candidate.

Checks the built overlays against the saved real ADT (addresses, IRQs,
tunables, PMGR offsets), merges them onto the installed rootguard DTB with
libfdt (fdtoverlay), and checks the modules' vermagic/header/undefined symbols
against the exact kernel devel package. No device access, no network.
"""
import re
import struct
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(ROOT / "pylib"), str(ROOT / "proxy-kit/proxyclient")]
from m1n1.adt import load_adt  # noqa: E402

HEADERS = ROOT / "input-driver/build/headers/usr/src/kernels/7.0.13-400.asahi.fc44.aarch64+16k"
BASE_DTB = ROOT / "t6050-j714s-native-rootguard.dtb"
BASE_DTB_SHA = "ddd855503c88b8b3b0afe64b4f3862dee2ec328c347b6c7eca5664bdf1fee5f8"
LLVM = Path("/opt/homebrew/opt/llvm/bin")
INSTANCE = 2  # right socket: /arm-io/usb-drd2, port-number 3, hpm2 "right"


def dts(path):
    return subprocess.run(["dtc", "-q", "-I", "dtb", "-O", "dts", str(path)], check=True,
                          capture_output=True, text=True).stdout


def node_block(text, name):
    m = re.search(r"\n(\t+)" + re.escape(name) + r" \{\n(.*?)\n\1\};", text, re.S)
    assert m, name
    return m.group(2)


def prop_raw(block, name):
    m = re.search(r"(?m)^\s*" + re.escape(name) + r" = (.*?);", block, re.S)
    assert m, name
    return m.group(1)


def prop_cells_multi(block, name):
    return [int(x, 16) for x in re.findall(r"0x[0-9a-f]+", prop_raw(block, name))]


class CandidateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adt = load_adt((ROOT / "adt-real-t6050.bin").read_bytes())
        assert cls.adt.model == "Mac17,9"
        cls.usb = cls.adt[f"/arm-io/usb-drd{INSTANCE}"]
        cls.phy = cls.adt[f"/arm-io/atc-phy{INSTANCE}"]
        cls.dart = cls.adt[f"/arm-io/dart-usb{INSTANCE}"]
        cls.hpm = cls.adt["/arm-io/nub-spmi-a1/hpm2"]
        cls.minimal = dts(HERE / "stage/t6050-j714s-usb-right-minimal.dtbo")
        cls.pmgr = dts(HERE / "stage/t6050-j714s-usb-right-pmgr.dtbo")
        import hashlib
        assert hashlib.sha256(BASE_DTB.read_bytes()).hexdigest() == BASE_DTB_SHA

    def test_port_identity(self):
        self.assertEqual(self.usb._properties["port-number"], 3)
        self.assertEqual(self.hpm._properties["port-number"], 3)
        self.assertEqual(self.hpm._properties["port-location"], "right")
        self.assertIn("usb-drd,t6050", self.usb.compatible)
        self.assertIn("atc-phy,t6050", self.phy.compatible)

    def check_addresses(self, text):
        usb = node_block(text, "usb@382280000")
        reg = prop_cells_multi(usb, "reg")
        core = self.usb.get_reg(0)
        self.assertEqual(reg[0] << 32 | reg[1], core[0])
        self.assertEqual(reg[3], 0xcd00)
        self.assertEqual(reg[4] << 32 | reg[5], core[0] + 0xcd00)
        self.assertLessEqual(core[0] + 0xcd00 + 0x3200, core[0] + core[1])
        irq = prop_cells_multi(usb, "interrupts")
        self.assertEqual(irq, [0, self.usb.interrupts[0], 4])
        self.assertEqual(prop_cells_multi(usb, "interrupt-parent"), [2])
        phy = node_block(text, "phy@382a90000")
        preg = prop_cells_multi(phy, "reg")
        self.assertEqual(preg[0] << 32 | preg[1], self.phy.get_reg(0)[0])
        self.assertEqual(preg[3], self.phy.get_reg(0)[1])
        self.assertEqual(preg[4] << 32 | preg[5], self.phy.get_reg(1)[0])
        self.assertEqual(preg[7], self.phy.get_reg(1)[1])
        for i, name in enumerate(["iommu@382f00000", "iommu@382f80000"]):
            d = node_block(text, name)
            dreg = prop_cells_multi(d, "reg")
            self.assertEqual(dreg[0] << 32 | dreg[1], self.dart.get_reg(i)[0])
            self.assertEqual(dreg[3], self.dart.get_reg(i)[1])
            self.assertEqual(prop_cells_multi(d, "interrupts"), [0, self.dart.interrupts[0], 4])
            self.assertEqual(prop_cells_multi(d, "interrupt-parent"), [2])
        self.assertEqual(self.adt[f"/arm-io/dart-usb{INSTANCE}/mapper-usb{INSTANCE}"]._properties["reg"], 1)

    def test_minimal_addresses(self):
        self.check_addresses(self.minimal)

    def test_pmgr_addresses(self):
        self.check_addresses(self.pmgr)

    def check_tunables(self, text):
        phy = node_block(text, "phy@382a90000")
        def adt_tunable(name):
            raw = self.phy._properties[name]
            return list(struct.unpack("<%dI" % (len(raw) // 4), raw))
        self.assertEqual(prop_cells_multi(phy, "azahi,tunable-usb2phy-default"), adt_tunable("tunable_USB2PHY_DFLT"))
        self.assertEqual(prop_cells_multi(phy, "azahi,tunable-usb2phy-host"), adt_tunable("tunable_USB2PHY_HOST"))
        for word in prop_cells_multi(phy, "azahi,tunable-usb2phy-default")[0::3]:
            self.assertEqual(word >> 27, 4)
            self.assertLess(word & 0x7ffffff, 0x4000)
        usb = node_block(text, "usb@382280000")
        phys = prop_raw(usb, "phys")  # dtc renders the local reference as a path
        self.assertIn("phy@382a90000", phys)
        self.assertEqual(prop_cells_multi(usb, "phys")[-1], 3)  # PHY_TYPE_USB2 in this kernel
        hdr = (HEADERS / "include/dt-bindings/phy/phy.h").read_text()
        self.assertRegex(hdr, r"#define PHY_TYPE_USB2\s+3\b")

    def test_minimal_tunables(self):
        self.check_tunables(self.minimal)

    def test_pmgr_tunables(self):
        self.check_tunables(self.pmgr)

    def test_pmgr_offsets_match_adt(self):
        pm = self.adt["/arm-io/pmgr"]
        groups = pm._properties["ps-groups"]
        byname = {d.name: d for d in pm._properties["devices"]}
        expect = {
            "power-controller@1f0": ("FAB5_SOC", "power-management@280600000"),
            "power-controller@238": ("ATC2_COMMON", "power-management@280600000"),
            "power-controller@178": ("ATC2_USB_AON", "power-management@288300000"),
            "power-controller@180": ("ATC2_USB", "power-management@288300000"),
        }
        for node, (name, block) in expect.items():
            d = byname[name]
            base = pm.get_reg(groups[d.group].reg)[0]
            blk = node_block(self.pmgr, block)
            breg = prop_cells_multi(blk, "reg")
            self.assertEqual(breg[0] << 32 | breg[1], base, name)
            self.assertEqual(prop_cells_multi(node_block(self.pmgr, node), "reg")[0], d.offset, name)
        usb_gate = list(self.usb.clock_gates)
        self.assertEqual(usb_gate, [byname["ATC2_USB"].id2])
        self.assertEqual(list(byname["ATC2_USB"].parents_un.u16id.parents),
                         [byname["ATC2_COMMON"].id2, byname["ATC2_USB_AON"].id2])

    def test_no_external_fixups(self):
        for text in (self.minimal, self.pmgr):
            self.assertNotIn("__fixups__ {", text.replace("__local_fixups__", ""))
            self.assertNotIn("__symbols__ {", text)
            self.assertIn("__local_fixups__ {", text)

    def test_base_aic_phandle(self):
        base = dts(BASE_DTB)
        aic = node_block(base, "interrupt-controller@280400000")
        self.assertEqual(prop_cells_multi(aic, "phandle"), [2])
        self.assertIn('"apple,t6050-aic3"', aic)
        self.assertNotIn("__symbols__", base)
        self.assertNotIn("usb@382280000", base)
        self.assertNotIn("power-management@", base)

    def test_fdtoverlay_merge(self):
        for v in ("minimal", "pmgr"):
            out = HERE / f"build/test-merged-{v}.dtb"
            subprocess.run(["fdtoverlay", "-i", str(BASE_DTB), "-o", str(out),
                            str(HERE / f"stage/t6050-j714s-usb-right-{v}.dtbo")], check=True)
            merged = dts(out)
            usb = node_block(merged, "usb@382280000")
            phy = node_block(merged, "phy@382a90000")
            d0 = node_block(merged, "iommu@382f00000")
            d1 = node_block(merged, "iommu@382f80000")
            phandles = {n: prop_cells_multi(b, "phandle")[0] for n, b in (("phy", phy), ("d0", d0), ("d1", d1))}
            self.assertEqual(prop_cells_multi(usb, "phys"), [phandles["phy"], 3])
            self.assertEqual(prop_cells_multi(usb, "iommus"),
                             [phandles["d0"], 0, phandles["d0"], 1, phandles["d1"], 0, phandles["d1"], 1])
            self.assertEqual(prop_cells_multi(usb, "interrupt-parent"), [2])
            self.assertTrue(all(p > 0xe for p in phandles.values()))
            if v == "pmgr":
                ps_usb = prop_cells_multi(node_block(merged, "power-controller@180"), "phandle")[0]
                for b in (usb, phy, d0, d1):
                    self.assertEqual(prop_cells_multi(b, "power-domains"), [ps_usb])

    def test_modules(self):
        readelf = LLVM / "llvm-readelf"
        nm = LLVM / "llvm-nm"
        exported = set(line.split()[1] for line in (HEADERS / "Module.symvers").read_text().splitlines() if line.strip())
        expect_depends = {"phy-apple-t6050-usb2.ko": "", "azahi-usb-overlay.ko": "", "dwc3-apple-t6050.ko": "dwc3"}
        for name, dep in expect_depends.items():
            ko = HERE / "stage" / name
            info = subprocess.run([str(readelf), "-p", ".modinfo", str(ko)], check=True, capture_output=True, text=True).stdout
            self.assertIn("vermagic=7.0.13-400.asahi.fc44.aarch64+16k SMP preempt mod_unload aarch64", info, name)
            self.assertIn(f"depends={dep}\n", info, name)
            sections = subprocess.run([str(readelf), "-S", str(ko)], check=True, capture_output=True, text=True).stdout
            m = re.search(r"\.gnu\.linkonce\.this_module\s+\S+\s+\S+\s+\S+\s+(\S+)", sections)
            self.assertEqual(int(m.group(1), 16), 0x540, name)
            undef = [l.split()[1] for l in subprocess.run([str(nm), "-u", str(ko)], check=True, capture_output=True, text=True).stdout.splitlines() if l.strip()]
            missing = sorted(set(undef) - exported)
            self.assertEqual(missing, [], name)

    def test_embedded_blobs(self):
        h = (HERE / "build/overlay-blobs.h").read_text()
        for v in ("minimal", "pmgr"):
            m = re.search(rf"static const u8 overlay_{v}\[\] __aligned\(8\) = \{{(.*?)\}};\nstatic const u32 overlay_{v}_size = (\d+);", h, re.S)
            data = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-f]{2})", m.group(1)))
            self.assertEqual(data, (HERE / f"stage/t6050-j714s-usb-right-{v}.dtbo").read_bytes())
            self.assertEqual(int(m.group(2)), len(data))
            magic, total = struct.unpack(">II", data[:8])
            self.assertEqual((magic, total), (0xd00dfeed, len(data)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
