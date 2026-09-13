#!/usr/bin/env python3
"""Offline, allowlisted J714s USB inventory. Never opens a device or writes MMIO.

Uses the already saved real ADT and only allowlisted PCI identity fields from
the saved ioreg plist. Output excludes user/session information, MAC addresses,
serials, calibration and secrets.
This report is NOT an enabling DT or permission to execute PHY sequences.
"""
from pathlib import Path
import hashlib
import json
import plistlib
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "pylib"), str(ROOT / "proxy-kit/proxyclient")]
from m1n1.adt import load_adt


def require(ok, message):
    if not ok:
        raise ValueError(message)


def regs(node, indices):
    return [{"index": i, "address": hex(node.get_reg(i)[0]),
             "size": hex(node.get_reg(i)[1])} for i in indices]


def inventory(adt):
    require(adt.model == "Mac17,9" and "J714sAP" in adt.compatible,
            "This audit is limited to the saved J714s/Mac17,9 board")
    ports = []
    for i in range(3):
        usb = adt[f"/arm-io/usb-drd{i}"]
        phy = adt[f"/arm-io/atc-phy{i}"]
        dart = adt[f"/arm-io/dart-usb{i}"]
        mapper = adt[f"/arm-io/dart-usb{i}/mapper-usb{i}"]
        require("usb-drd,t6050" in usb.compatible, "Unexpected USB generation")
        require("atc-phy,t6050" in phy.compatible and
                "atc-phy,t6040" in phy.compatible, "Unexpected PHY generation")
        require(usb._properties["atc-phy-parent"] == phy._properties["AAPL,phandle"],
                "USB/PHY phandle mismatch")
        require(usb._properties["iommu-parent"] == mapper._properties["AAPL,phandle"],
                "USB/mapper phandle mismatch")
        require(usb._properties["port-number"] == phy._properties["port-number"],
                "USB/PHY port mismatch")
        ports.append({
            "controller": i,
            "adt_port_number": usb._properties["port-number"],
            "physical_socket": "not independently verified",
            "usb_compatible": list(usb.compatible),
            "usb_registers": regs(usb, [0, 1, 2]),
            "usb_interrupts": list(usb.interrupts),
            "usb_clock_gate_ids": list(usb.clock_gates),
            "phy_compatible": list(phy.compatible),
            "phy_usb2_candidate_banks": regs(phy, [0, 1]),
            "phy_clock_gate_ids": list(phy.clock_gates),
            "dart_compatible": list(dart.compatible),
            "dart_registers": regs(dart, range(len(dart.reg))),
            "dart_interrupts": list(dart.interrupts),
            "mapper_sid": int(mapper.reg),
            "dart_vm_base": hex(dart._properties["vm-base"]),
            "dart_vm_size": hex(dart._properties["vm-size"]),
            "usb2_host_tunable": phy._properties["tunable_USB2PHY_HOST"].hex(),
        })
    bridge = adt["/arm-io/apcie0/pci-bridge0"]
    wireless = [n.name for n in bridge if n.name.startswith("centauri-")]
    return {"model": adt.model, "ports": ports, "wireless_node_names": wireless,
            "warning": "No M5 PHY/PD init, DMA, USB enumeration or network validated"}


def configured_drivers(path):
    wanted = {"USB_DWC3", "USB_DWC3_APPLE", "USB_XHCI_PLATFORM", "PHY_APPLE_ATC",
              "PHY_APPLE_T6040_USB2", "TYPEC_SN201202X", "TYPEC_TPS6598X",
              "SPMI_APPLE", "APPLE_DART", "PCIE_APPLE", "USB_RTL8152",
              "USB_NET_CDCETHER", "USB_NET_RNDIS_HOST", "USB_IPHETH"}
    result = {k: "absent/unset" for k in wanted}
    for line in path.read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line[7:].split("=", 1)
            if key in result:
                result[key] = value
    return dict(sorted(result.items()))


def wireless_pci_identity(blob):
    """Read only the three named endpoints; never return arbitrary properties."""
    expected = {"centauri-control": 0x1901, "centauri-alpha": 0x1902,
                "centauri-beta": 0x1903}
    found = {}

    def integer(value):
        if isinstance(value, bytes):
            require(len(value) == 4, "Unexpected PCI identity width")
            return int.from_bytes(value, "little")
        require(isinstance(value, int), "Unexpected PCI identity type")
        return value

    def walk(node):
        if isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            name = node.get("IORegistryEntryName")
            if name in expected and "vendor-id" in node and "device-id" in node:
                vendor = integer(node["vendor-id"])
                device = integer(node["device-id"])
                require(vendor == 0x106b and device == expected[name],
                        "Unexpected Centauri PCI identity")
                row = {"node": name, "vendor": f"{vendor:04x}",
                       "device": f"{device:04x}"}
                if "class-code" in node:
                    row["class"] = f'{integer(node["class-code"]):06x}'
                require(name not in found or found[name] == row,
                        "Conflicting saved PCI identities")
                found[name] = row
            for child in node.get("IORegistryEntryChildren", []):
                walk(child)

    walk(plistlib.loads(blob))
    require(set(found) == set(expected), "Incomplete saved Centauri PCI identity")
    return [found[name] for name in expected]


def main():
    blob = (ROOT / "adt-real-t6050.bin").read_bytes()
    report = inventory(load_adt(blob))
    report["saved_adt_sha256"] = hashlib.sha256(blob).hexdigest()
    report["kernel_config"] = configured_drivers(ROOT / "kconfig.txt")
    ioreg = (ROOT / "adt-m5pro-mac17,9.plist").read_bytes()
    report["saved_ioreg_sha256"] = hashlib.sha256(ioreg).hexdigest()
    report["wireless_pci_identity"] = wireless_pci_identity(ioreg)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
