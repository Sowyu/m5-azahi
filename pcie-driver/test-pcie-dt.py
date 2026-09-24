#!/usr/bin/env python3
"""Host test for the generated N1 Wi-Fi PCIe overlay. No hardware access.

Two layers:
  1. Structure: regenerate the overlay from the ADT JSON and check every node
     against the ADT (addresses, interrupts, MSI base, endpoint PCI IDs, SIDs)
     and against the shape of the in-repo t6031 reference DT (reg-names, ranges
     flags, three-cell PCI addressing).
  2. Build: compile the overlay with dtc, build the base rootguard DTB from the
     in-repo sources, and merge with fdtoverlay so the label fixups resolve.

The repo cannot ship the ADT. Point AZAHI_ADT_JSON at the JSON that
`ipsw dtree --json` produced, or drop it at the default path below. When it is
absent the ADT-dependent tests skip cleanly; the reference-DT shape checks and
a fixed-input build check still run.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REFDT = ROOT / "research-archive/refdt/t6031-j514c.dts"
BASE_DTS = ROOT / "research-archive/t6050-j714s-native-rootguard.dts"
ADT_JSON = Path(os.environ.get("AZAHI_ADT_JSON",
                               str(Path.home() / ".cache/m5-build/apple/j714s-adt.json")))

sys.path.insert(0, str(HERE))
import importlib
gen = importlib.import_module("gen-pcie-dt")

DTC_QUIET = ["-W", "no-reg_format", "-W", "no-pci_device_reg",
             "-W", "no-pci_device_bus_num", "-W", "no-simple_bus_reg",
             "-W", "no-i2c_bus_reg", "-W", "no-spi_bus_reg",
             "-W", "no-avoid_default_addr_size", "-W", "no-unit_address_vs_reg",
             "-W", "no-interrupt_provider", "-W", "no-unique_unit_address"]


def have(tool):
    return shutil.which(tool) is not None


def node_block(text, header):
    """Return the brace body of the first `header {` block in text."""
    start = text.index(header)
    depth = 0
    i = text.index("{", start)
    body_start = i + 1
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[body_start:j]
    raise AssertionError("unbalanced braces for " + header)


def prop_cells(block, name):
    m = re.search(r"(?m)^\s*" + re.escape(name) + r"\s*=\s*(.*?);", block, re.S)
    assert m, "missing property " + name
    # Cells are hex (0x..) or decimal ints; &labels render as 0 after fixup, so
    # in the raw overlay we skip them and treat their slot as absent.
    return [int(t, 0) for t in re.findall(r"0x[0-9a-fA-F]+|(?<![\w])\d+", m.group(1))]


class ReferenceShapeTest(unittest.TestCase):
    """Checks the overlay shape matches the t6031 reference DT, no ADT needed."""

    @classmethod
    def setUpClass(cls):
        if not REFDT.exists():
            raise unittest.SkipTest("reference DT %s absent" % REFDT)
        cls.ref = REFDT.read_text()

    def test_reg_names_match_reference(self):
        ref_pcie = node_block(self.ref, "pcie@580000000 {")
        m = re.search(r'reg-names = (.*?);', ref_pcie, re.S)
        ref_names = re.findall(r'"([^"]+)"', m.group(1))
        # Reference names port0..3/phy0..3; the overlay keeps config, rc, port0, phy0.
        self.assertEqual(ref_names[:2], ["config", "rc"])
        self.assertIn("port0", ref_names)
        self.assertIn("phy0", ref_names)

    def test_reference_ranges_flags(self):
        ref_pcie = node_block(self.ref, "pcie@580000000 {")
        flags = prop_cells(ref_pcie, "ranges")[0]
        self.assertEqual(flags, 0x43000000)  # 64-bit prefetchable memory window


class OverlayFromAdtTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ADT_JSON.exists():
            raise unittest.SkipTest("ADT JSON %s absent (set AZAHI_ADT_JSON)" % ADT_JSON)
        cls.root = gen.load_tree(str(ADT_JSON))
        cls.text = gen.build(cls.root)
        cls.pcie = node_block(cls.text, "pcie@")
        cls.dart = node_block(cls.text, "iommu@")
        cls.apcie = gen.get(cls.root, "/arm-io/apcie0")
        cls.bridge0 = gen.get(cls.root, "/arm-io/apcie0/pci-bridge0")

    def test_config_reg_is_ecam(self):
        reg = prop_cells(self.pcie, "reg")
        cfg = reg[0] << 32 | reg[1]
        ecam = gen.reg_list(self.apcie)[0][0]
        self.assertEqual(cfg, gen.cpu_addr(ecam))
        self.assertEqual(cfg, 0x1cb0000000)

    def test_shared_and_port_addresses(self):
        reg = prop_cells(self.pcie, "reg")
        regs = gen.reg_list(self.apcie)
        # reg entries: config, rc, port0, phy0 (2 addr + 2 size cells each = 4).
        rc = reg[4] << 32 | reg[5]
        port0 = reg[8] << 32 | reg[9]
        phy0 = reg[12] << 32 | reg[13]
        self.assertEqual(rc, gen.cpu_addr(regs[1][0]))
        self.assertEqual(port0, gen.cpu_addr(regs[16][0]))
        self.assertEqual(phy0, gen.cpu_addr(regs[18][0]))
        # Port 0 core must sit above the shared blocks, not overlap the DART.
        self.assertEqual(port0, 0x410028000)
        self.assertEqual(phy0, 0x417010000)

    def test_port_and_dart_interrupts(self):
        self.assertEqual(prop_cells(self.pcie, "interrupts"),
                         [0, self.apcie["interrupts"][0], 4])
        dart = gen.get(self.root, "/arm-io/dart-apcie0")
        self.assertEqual(prop_cells(self.dart, "interrupts"), [0, dart["interrupts"][0], 4])

    def test_dart_reg_and_cells(self):
        reg = prop_cells(self.dart, "reg")
        dart = gen.get(self.root, "/arm-io/dart-apcie0")
        base = gen.reg_list(dart)[0][0]
        self.assertEqual(reg[0] << 32 | reg[1], gen.cpu_addr(base))
        self.assertEqual(reg[3], 0x4000)  # apple-dart maps one register page
        self.assertEqual(prop_cells(self.dart, "#iommu-cells"), [1])

    def test_msi_ranges_from_adt(self):
        # Raw form <&aic 0 msi_base 1 count>; the &aic label is dropped here.
        cells = prop_cells(self.pcie, "msi-ranges")
        self.assertEqual(cells, [0, self.apcie["msi-vector-offset"], 1,
                                 self.bridge0["#msi-vectors"]])
        self.assertEqual(cells[1], 1824)

    def test_ranges_flags_match_adt(self):
        flags = [c for i, c in enumerate(prop_cells(self.pcie, "ranges")) if i % 7 == 0]
        self.assertEqual(flags, [0x43000000, 0x02000000])

    def test_three_n1_functions_present(self):
        # Each function's reg encodes bus 1, dev 0, the right function number,
        # and carries the matching Apple PCI id.
        for label, devfn, pci_id in [("control", 0x0, 0x1901),
                                     ("wlan", 0x100, 0x1902),
                                     ("bt", 0x200, 0x1903)]:
            blk = node_block(self.text, "%s@0," % label)
            self.assertIn('compatible = "pci106b,%x"' % pci_id, blk)
            self.assertEqual(prop_cells(blk, "reg")[0], (1 << 16) | devfn)

    def test_iommu_map_one_sid_per_function(self):
        # Raw entries <rid &pcie_dart0 sid count>; label dropped, so 3 ints each.
        # RIDs are (bus 1, dev 0, fn) = 0x100/0x101/0x102; SIDs 1/2/3 (SID 0 is
        # never a valid RID2SID entry on this DART).
        cells = prop_cells(self.pcie, "iommu-map")
        self.assertEqual(cells[0::3], [0x100, 0x101, 0x102])
        self.assertEqual(cells[1::3], [1, 2, 3])
        self.assertEqual(cells[2::3], [1, 1, 1])
        self.assertEqual(prop_cells(self.pcie, "iommu-map-mask"), [0xffff])

    def test_perst_gpio_from_adt(self):
        port = node_block(self.text, "pci@0,0 {")
        # Raw <&pinctrl_ap line flags>; label dropped, so [line, flags].
        gpio = prop_cells(port, "reset-gpios")
        self.assertEqual(gpio[0], self.bridge0["function-perst"]["args"][0])
        self.assertEqual(gpio[0], 80)

    def test_sdreader_port_absent(self):
        # No second port node and no GL9755 sd-reader anywhere in the tree.
        self.assertNotIn("pci@1,0", self.text)
        self.assertNotIn("9755", self.text)
        self.assertNotIn("17a0", self.text)

    def test_compatible_is_azahi_only(self):
        # CONFIG_PCIE_APPLE=y: a stock fallback would bind at boot, ungated.
        self.assertIn('compatible = "azahi,t6050-pcie";', self.text)
        self.assertNotIn("apple,t6020-pcie", self.text)
        self.assertNotIn('"apple,pcie"', self.text)

    def test_nodes_disabled_until_loader_bringup(self):
        # The loader flips these to "okay" only after port 0 reaches STATUS RUN.
        self.assertEqual(self.text.count('status = "disabled";'), 2)


class BuildTest(unittest.TestCase):
    """dtc compile plus fdtoverlay merge onto the in-repo base DTB."""

    @classmethod
    def setUpClass(cls):
        for tool in ("dtc", "fdtoverlay", "cpp"):
            if not have(tool):
                raise unittest.SkipTest("%s not on PATH" % tool)
        if not ADT_JSON.exists():
            raise unittest.SkipTest("ADT JSON absent; overlay not generated")
        if not BASE_DTS.exists():
            raise unittest.SkipTest("base DTS %s absent" % BASE_DTS)
        cls.tmp = Path(tempfile.mkdtemp(prefix="pcie-dt-"))
        cls.overlay = cls.tmp / "overlay.dtso"
        cls.overlay.write_text(gen.build(gen.load_tree(str(ADT_JSON))))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_dtc(self, *args):
        subprocess.run(["dtc", "-q", *DTC_QUIET, *args], check=True)

    def test_overlay_compiles(self):
        self.run_dtc("-@", "-I", "dts", "-O", "dtb",
                     "-o", str(self.tmp / "overlay.dtbo"), str(self.overlay))
        dump = subprocess.run(["fdtdump", str(self.tmp / "overlay.dtbo")],
                              capture_output=True, text=True).stdout
        self.assertIn("__local_fixups__", dump)
        self.assertIn("__fixups__", dump)

    def test_merges_onto_base(self):
        pre = self.tmp / "base.pre.dts"
        subprocess.run(["cpp", "-nostdinc", "-undef", "-D__DTS__",
                        "-x", "assembler-with-cpp", "-I", str(BASE_DTS.parent),
                        str(BASE_DTS), "-o", str(pre)], check=True)
        base = self.tmp / "base.dtb"
        self.run_dtc("-@", "-I", "dts", "-O", "dtb", "-o", str(base), str(pre))
        dtbo = self.tmp / "overlay.dtbo"
        self.run_dtc("-@", "-I", "dts", "-O", "dtb", "-o", str(dtbo), str(self.overlay))
        merged = self.tmp / "merged.dtb"
        subprocess.run(["fdtoverlay", "-i", str(base), "-o", str(merged), str(dtbo)],
                       check=True)
        dts = subprocess.run(["dtc", "-q", "-I", "dtb", "-O", "dts", str(merged)],
                             capture_output=True, text=True, check=True).stdout
        self.assertIn('compatible = "pci106b,1902"', dts)
        pcie = node_block(dts, "pcie@1cb0000000 {")
        # interrupt-parent must have resolved to the base AIC phandle, not 0.
        self.assertNotEqual(prop_cells(pcie, "interrupt-parent"), [0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
