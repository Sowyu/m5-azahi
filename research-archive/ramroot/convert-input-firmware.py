#!/usr/bin/env python3
"""Convert J714 input firmware XML to the dockchannel-hid HIDF container.

Format reference: AsahiLinux/asahi-installer asahi_firmware/multitouch.py.
Only uncompressed IM4P input is accepted; no firmware is flashed to disk.
"""
import argparse
import copy
from pathlib import Path
import plistlib
import struct
import xml.etree.ElementTree as ET


def tlv(data, offset):
    tag, length = data[offset:offset + 2]
    offset += 2
    if length & 0x80:
        count = length & 0x7f
        assert 0 < count <= 4
        length = int.from_bytes(data[offset:offset + count], "big")
        offset += count
    end = offset + length
    assert end <= len(data)
    return tag, data[offset:end], end


def decode_xml(path):
    tag, sequence, end = tlv(path.read_bytes(), 0)
    assert tag == 0x30
    fields, offset = [], 0
    for _ in range(4):
        tag, data, offset = tlv(sequence, offset)
        fields.append((tag, data))
    assert fields[0] == (0x16, b"IM4P")
    assert fields[1][1] in (b"mtfw", b"ipdf")
    assert fields[3][0] == 4 and fields[3][1].startswith(b"<dict>")
    root = ET.fromstring(fields[3][1].rstrip(b"\0"))
    ids = {node.attrib["ID"]: node for node in root.iter() if "ID" in node.attrib}

    def expand(node):
        if "IDREF" in node.attrib:
            return expand(ids[node.attrib["IDREF"]])
        result = ET.Element(node.tag)
        result.text = node.text
        result.extend(expand(child) for child in node)
        return result

    wrapper = ET.Element("plist")
    wrapper.append(expand(root))
    return plistlib.loads(ET.tostring(wrapper))


def encode_hidf(configuration):
    configuration = copy.deepcopy(configuration)
    for item in configuration:
        if item.get("Type") == "Config":
            for interface in item["Config"].get("Interface Config", []):
                if "HIDRecorder Descriptor" not in interface:
                    interface["bInterfaceNumber"] = None
    body, interface_offsets = bytearray(), []

    def header(major, value):
        if value < 24:
            return bytes([(major << 5) | value])
        for additional, width in ((24, 1), (25, 2), (26, 4), (27, 8)):
            if value < 1 << (width * 8):
                return bytes([(major << 5) | additional]) + value.to_bytes(width, "big")
        raise ValueError("CBOR integer overflow")

    def encode(value):
        if value is None:
            interface_offsets.append(len(body))
            body.append(0)
        elif isinstance(value, bool):
            body.append(0xf5 if value else 0xf4)
        elif isinstance(value, int):
            body.extend(header(0 if value >= 0 else 1, value if value >= 0 else -1 - value))
        elif isinstance(value, str):
            text = value.encode() + b"\0"
            body.extend(header(3, len(text)))
            body.extend(text)
        elif isinstance(value, bytes):
            # Apple's parser expects binary payloads on a four-byte boundary
            # and permits 0xd3 padding before the fixed-width bytes header.
            if len(value) <= 0xffff:
                prefix = b"\x59" + struct.pack(">H", len(value))
            else:
                prefix = b"\x5a" + struct.pack(">I", len(value))
            body.extend(b"\xd3" * (-(len(body) + len(prefix)) % 4))
            body.extend(prefix)
            body.extend(value)
        elif isinstance(value, list):
            body.extend(header(4, len(value)))
            for child in value:
                encode(child)
        elif isinstance(value, dict):
            body.extend(header(5, len(value)))
            for key, child in value.items():
                encode(key)
                encode(child)
        else:
            raise TypeError(type(value))

    encode(configuration)
    assert len(interface_offsets) <= 1, interface_offsets
    interface_offset = interface_offsets[0] if interface_offsets else 0
    return struct.pack("<4sIIII12x", b"HIDF", 1, 32, len(body), interface_offset) + body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("key", help="Exact firmware personality from the target ADT")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    firmware = decode_xml(args.source)
    print("Available personalities:", ", ".join(firmware))
    data = encode_hidf(firmware[args.key])
    with args.output.open("xb") as output:
        output.write(data)
    print(f"HIDF {args.key}: {len(data)} bytes, interface offset {struct.unpack_from('<I', data, 16)[0]}")


if __name__ == "__main__":
    main()
