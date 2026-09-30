#!/usr/bin/env python3
"""Synthetic format/corruption tests. No Apple firmware or target required."""
import hashlib
import struct
import unittest

import n1_fw


def tlv(tag, data):
    if len(data) < 128:
        length = bytes([len(data)])
    else:
        length = len(data).to_bytes((len(data).bit_length() + 7) // 8, "big")
        length = bytes([128 + len(length)]) + length
    return tag + length + data


def named(name, value):
    number = int.from_bytes(name.encode(), "big")
    groups = [number & 127]
    number >>= 7
    while number:
        groups.insert(0, 128 | (number & 127))
        number >>= 7
    return tlv(bytes([0xff] + groups), tlv(b"\x30", tlv(b"\x16", name.encode()) + value))


def prop(name, value):
    if type(value) is bool:
        encoded = tlv(b"\x01", b"\xff" if value else b"\x00")
    elif isinstance(value, int):
        b = value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")
        encoded = tlv(b"\x02", (b"\x00" if b[0] & 128 else b"") + b)
    else:
        encoded = tlv(b"\x04", value)
    return named(name, encoded)


def fixture(board=0x841, bound=False):
    payload = b"synthetic firmware payload" * 5
    data = bytearray(64)
    data[32:40] = b"rkosftab"
    struct.pack_into("<I", data, 40, 1)
    struct.pack_into("<4sIII", data, 48, b"rkos", 64, len(payload), 0)
    data += payload
    props = {"CHIP": 0x2026, "BORD": board, "CEPO": 1, "SDOM": 1,
             "CPRO": True, "CSEC": True}
    if bound:
        props["BNCH"] = bytes(32)
    manp = named("MANP", tlv(b"\x31", b"".join(prop(k, v) for k, v in props.items())))
    image = named("rkos", tlv(b"\x31", prop("DGST", hashlib.sha384(payload).digest())))
    body = tlv(b"\x31", named("MANB", tlv(b"\x31", manp + image)))
    ticket = tlv(b"\x30", tlv(b"\x16", b"IM4M") + tlv(b"\x02", b"\x00") +
                 body + tlv(b"\x04", b"synthetic signature") + tlv(b"\x30", b""))
    return bytes(data), ticket


class FirmwareTest(unittest.TestCase):
    def test_manifest_first_preserves_payload_and_ticket(self):
        data, ticket = fixture()
        out = n1_fw.package(data, ticket)
        off, length = struct.unpack_from("<II", out, 16)
        self.assertEqual(off, 64)
        self.assertEqual(out[off:off+length], ticket)
        payload_off, payload_len = n1_fw.ftab(out)["rkos"]
        self.assertEqual(payload_off, (64 + len(ticket) + 3) & ~3)
        self.assertEqual(out[payload_off:payload_off+payload_len], data[64:])
        self.assertEqual(len(out) % 4096, 0)
        self.assertEqual(set(out[payload_off+payload_len:]), {0})

    def test_corruption_rejected(self):
        data, ticket = fixture()
        with self.assertRaisesRegex(ValueError, "SHA-384 mismatch"):
            n1_fw.package(data[:-1] + bytes([data[-1] ^ 1]), ticket)

    def test_wrong_board_rejected(self):
        with self.assertRaisesRegex(ValueError, "BORD"):
            n1_fw.package(*fixture(board=0x842))

    def test_bound_ticket_rejected(self):
        with self.assertRaisesRegex(ValueError, "device-bound"):
            n1_fw.package(*fixture(bound=True))

    def test_boolean_is_not_an_integer_version(self):
        data, ticket = fixture()
        ticket = ticket.replace(b"\x16\x04IM4M\x02\x01\x00",
                                b"\x16\x04IM4M\x01\x01\x00", 1)
        with self.assertRaisesRegex(ValueError, "DER type"):
            n1_fw.package(data, ticket)

    def test_overlap_rejected(self):
        data, ticket = fixture()
        data = bytearray(data)
        struct.pack_into("<I", data, 52, 48)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            n1_fw.package(data, ticket)

    def test_all_ticket_truncations_rejected(self):
        data, ticket = fixture()
        for n in range(len(ticket)):
            with self.subTest(n=n), self.assertRaises(ValueError):
                n1_fw.manifest(ticket[:n])

    def test_manifest_replacement_rejected(self):
        data, ticket = fixture()
        out = n1_fw.package(data, ticket)
        with self.assertRaisesRegex(ValueError, "already has a manifest"):
            n1_fw.package(out, ticket)

    def test_bad_entry_count_rejected(self):
        data, ticket = fixture()
        data = bytearray(data)
        struct.pack_into("<I", data, 40, 0xffffffff)
        with self.assertRaisesRegex(ValueError, "entry count"):
            n1_fw.package(data, ticket)


class SecondaryTest(unittest.TestCase):
    def header(self):
        header = bytearray(96)
        header[32:40] = b"rkosftab"
        struct.pack_into("<I", header, 40, 3)
        for i, tag in enumerate((b"msww", b"mswb", b"mswc")):
            struct.pack_into("<4sIII", header, 48 + i * 16,
                             tag, 128 + i * 256, 128, 0)
        return bytes(header)

    def test_expands_without_rewriting_header(self):
        header = self.header()
        expanded = n1_fw.secondary_ftab(header)
        self.assertEqual(len(expanded), 768)
        self.assertEqual(expanded[:len(header)], header)
        self.assertEqual(expanded[len(header):], bytes(768 - len(header)))
        self.assertEqual(n1_fw.ftab(expanded)["mswc"], (640, 128))
        with self.assertRaises(ValueError):
            n1_fw.ftab(header)  # A normal image must still contain its payloads.

    def test_truncations_and_trailing_data_rejected(self):
        header = self.header()
        for n in range(len(header)):
            with self.subTest(n=n), self.assertRaises(ValueError):
                n1_fw.secondary_ftab(header[:n])
        with self.assertRaises(ValueError):
            n1_fw.secondary_ftab(header + b"\x00")

    def test_excessive_extent_rejected_before_allocation(self):
        for off, size in ((0xffffffff, 128), (640, 32 * 1024 * 1024)):
            header = bytearray(self.header())
            struct.pack_into("<II", header, 84, off, size)
            with self.subTest(off=off, size=size), self.assertRaisesRegex(ValueError, "bounds"):
                n1_fw.secondary_ftab(header)

    def test_invalid_regions_rejected(self):
        mutations = ((84, "<I", 400), (84, "<I", 64), (92, "<I", 1),
                     (80, "<4s", b"msww"), (80, "<4s", b"fake"),
                     (16, "<II", (96, 16)), (88, "<I", 0))
        for off, fmt, value in mutations:
            header = bytearray(self.header())
            values = value if isinstance(value, tuple) else (value,)
            struct.pack_into(fmt, header, off, *values)
            with self.subTest(off=off, value=value), self.assertRaises(ValueError):
                n1_fw.secondary_ftab(header)


if __name__ == "__main__":
    unittest.main()
