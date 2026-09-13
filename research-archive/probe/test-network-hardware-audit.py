#!/usr/bin/env python3
"""Offline identity, linkage and privacy regression checks."""
from pathlib import Path
import runpy
import plistlib
import unittest

HERE = Path(__file__).resolve().parent
audit = runpy.run_path(str(HERE / "network-hardware-audit.py"))


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.adt = audit["load_adt"]((HERE.parent / "adt-real-t6050.bin").read_bytes())

    def test_saved_board(self):
        result = audit["inventory"](self.adt)
        self.assertEqual([p["adt_port_number"] for p in result["ports"]], [1, 2, 3])
        port = result["ports"][2]
        self.assertEqual(port["usb_registers"][0]["address"], "0x382280000")
        self.assertEqual(port["phy_usb2_candidate_banks"][0]["address"], "0x382a90000")
        self.assertEqual(port["mapper_sid"], 1)
        self.assertEqual(result["wireless_node_names"],
                         ["centauri-control", "centauri-alpha", "centauri-beta"])
        text = str(result).lower()
        for private_field in ["local-mac-address", "device-mac-address", "serial-number"]:
            self.assertNotIn(private_field, text)

    def test_wrong_board(self):
        self.adt._properties["model"] = "Mac16,6"
        with self.assertRaisesRegex(ValueError, "limited"):
            audit["inventory"](self.adt)

    def test_wrong_phy_parent(self):
        self.adt["/arm-io/usb-drd2"]._properties["atc-phy-parent"] = 0
        with self.assertRaisesRegex(ValueError, "phandle mismatch"):
            audit["inventory"](self.adt)

    def test_wrong_mapper(self):
        self.adt["/arm-io/usb-drd2"]._properties["iommu-parent"] = 0
        with self.assertRaisesRegex(ValueError, "mapper phandle mismatch"):
            audit["inventory"](self.adt)

    def test_real_pci_identity(self):
        result = audit["wireless_pci_identity"](
            (HERE.parent / "adt-m5pro-mac17,9.plist").read_bytes())
        self.assertEqual([r["device"] for r in result], ["1901", "1902", "1903"])
        self.assertTrue(all(r["vendor"] == "106b" for r in result))

    def test_ioreg_private_fields_not_returned(self):
        children = [{"IORegistryEntryName": name, "vendor-id": 0x106b,
                     "device-id": device, "local-mac-address": b"secret",
                     "IOConsoleUsers": "private-session", "serial-number": "private-serial"}
                    for name, device in [("centauri-control", 0x1901),
                                         ("centauri-alpha", 0x1902),
                                         ("centauri-beta", 0x1903)]]
        result = audit["wireless_pci_identity"](plistlib.dumps(children))
        self.assertTrue(all(set(r) == {"node", "vendor", "device"} for r in result))

    def test_wrong_pci_vendor(self):
        blob = plistlib.dumps({"IORegistryEntryName": "centauri-alpha",
                              "vendor-id": 0x14e4, "device-id": 0x1902})
        with self.assertRaisesRegex(ValueError, "Unexpected Centauri PCI identity"):
            audit["wireless_pci_identity"](blob)

    def test_missing_pci_endpoint(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            audit["wireless_pci_identity"](plistlib.dumps([]))


if __name__ == "__main__":
    unittest.main()
