#!/usr/bin/env python3
"""Inspect N1 FTAB/IM4M and prepare a private manifest-first boot candidate.

No hardware access. Payloads and the supplied signature ticket are preserved.
Hash consistency is checked; this does not authenticate the certificate chain
or establish that the chip will accept the ticket. Firmware stays private.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct


@dataclass(frozen=True)
class DER:
    tag: int
    cls: int
    constructed: bool
    content: bytes
    raw: bytes


def der_items(data):
    """Bounded definite-length DER reader; children are decoded on demand."""
    pos = 0
    while pos < len(data):
        start = pos
        first = data[pos]
        pos += 1
        tag = first & 31
        if tag == 31:
            tag = 0
            for i in range(5):
                if pos >= len(data):
                    raise ValueError("truncated DER tag")
                octet = data[pos]
                pos += 1
                if i == 0 and octet == 0x80:
                    raise ValueError("noncanonical DER tag")
                tag = (tag << 7) | (octet & 127)
                if not octet & 128:
                    break
            else:
                raise ValueError("DER tag too long")
            if tag < 31:
                raise ValueError("noncanonical high DER tag")
        if pos >= len(data):
            raise ValueError("missing DER length")
        size = data[pos]
        pos += 1
        if size & 128:
            n = size & 127
            if not 1 <= n <= 4 or pos + n > len(data) or data[pos] == 0:
                raise ValueError("invalid DER length")
            size = int.from_bytes(data[pos:pos+n], "big")
            pos += n
            if size < 128:
                raise ValueError("noncanonical DER length")
        end = pos + size
        if end > len(data):
            raise ValueError("truncated DER content")
        yield DER(tag, first >> 6, bool(first & 32), data[pos:end], data[start:end])
        pos = end


def expect(node, tag, constructed=False):
    if node.cls != 0 or node.tag != tag or node.constructed != constructed:
        raise ValueError(f"unexpected DER type; expected {tag}")
    return node.content


def only(data):
    nodes = list(der_items(data))
    if len(nodes) != 1:
        raise ValueError("expected one DER item")
    return nodes[0]


def properties(node):
    result = {}
    for item in der_items(expect(node, 17, True)):
        if item.cls != 3 or not item.constructed:
            raise ValueError("expected named private property")
        pair = list(der_items(expect(only(item.content), 16, True)))
        if len(pair) != 2:
            raise ValueError("invalid property pair")
        name_bytes = expect(pair[0], 22)
        if len(name_bytes) != 4 or int.from_bytes(name_bytes, "big") != item.tag:
            raise ValueError("property tag/name mismatch")
        name = name_bytes.decode("ascii")
        if name in result:
            raise ValueError(f"duplicate property {name}")
        result[name] = pair[1]
    return result


def scalar(node):
    if node.cls or node.constructed:
        raise ValueError("expected scalar property")
    if node.tag == 2:
        b = node.content
        if not b or b[0] & 128 or (len(b) > 1 and b[0] == 0 and not b[1] & 128):
            raise ValueError("invalid positive DER integer")
        return int.from_bytes(b, "big")
    if node.tag == 1 and node.content in (b"\x00", b"\xff"):
        return node.content == b"\xff"
    if node.tag == 4:
        return node.content
    raise ValueError("unsupported scalar property")


def manifest(data):
    if len(data) > 1024 * 1024:
        raise ValueError("ticket too large")
    seq = list(der_items(expect(only(data), 16, True)))
    if (len(seq) != 5 or expect(seq[0], 22) != b"IM4M" or
            expect(seq[1], 2) != b"\x00"):
        raise ValueError("expected IM4M version 0")
    expect(seq[3], 4)  # Signature and certificate bytes are never rewritten.
    expect(seq[4], 16, True)
    body = properties(seq[2])
    if set(body) != {"MANB"}:
        raise ValueError("expected one MANB")
    entries = properties(body["MANB"])
    manp = {k: scalar(v) for k, v in properties(entries.pop("MANP")).items()}
    images = {k: {a: scalar(b) for a, b in properties(v).items()}
              for k, v in entries.items()}
    return manp, images


def ftab(data):
    if len(data) < 48 or data[32:40] != b"rkosftab":
        raise ValueError("expected rkos FTAB header")
    count = struct.unpack_from("<I", data, 40)[0]
    table_end = 48 + count * 16
    if not 1 <= count <= 4096 or table_end > len(data):
        raise ValueError("invalid FTAB entry count")
    manifest_off, manifest_size = struct.unpack_from("<II", data, 16)
    spans = [(0, table_end, "header")]
    if bool(manifest_off) != bool(manifest_size):
        raise ValueError("incomplete FTAB manifest range")
    if manifest_size:
        spans.append((manifest_off, manifest_off + manifest_size, "manifest"))
    result = {}
    for i in range(count):
        tag, off, size, flags = struct.unpack_from("<4sIII", data, 48 + 16*i)
        if any(c < 32 or c > 126 for c in tag):
            raise ValueError("invalid FTAB tag")
        name = tag.decode("ascii")
        if name in result or not size or flags != 0:
            raise ValueError(f"duplicate, empty or unsupported FTAB entry {name}")
        result[name] = (off, size)
        spans.append((off, off + size, name))
    spans.sort()
    for i, (start, end, name) in enumerate(spans):
        if end > len(data) or (i and start < spans[i-1][1]):
            raise ValueError(f"overlapping or out-of-bounds FTAB range {name}")
    return result


def secondary_ftab(header):
    """Expand a header-only 2ftb into bounded, zero-filled host memory.

    This is a separate allocation, not a replacement firmware image. The
    primary FTAB and ticket remain unchanged. T2026 supports all three
    memswap regions; the control driver limits the allocation to 32 MiB.
    """
    if len(header) < 48 or header[32:40] != b"rkosftab":
        raise ValueError("expected secondary rkos FTAB header")
    count = struct.unpack_from("<I", header, 40)[0]
    if not 1 <= count <= 4096 or len(header) != 48 + count * 16:
        raise ValueError("secondary FTAB must contain only its complete record table")
    if struct.unpack_from("<II", header, 16) != (0, 0):
        raise ValueError("secondary FTAB must not contain a manifest range")
    required = max(off + size for off, size in
                   (struct.unpack_from("<II", header, 52 + i * 16)
                    for i in range(count)))
    if not len(header) < required <= 32 * 1024 * 1024:
        raise ValueError("secondary FTAB allocation outside supported bounds")
    expanded = header + bytes(required - len(header))
    entries = ftab(expanded)  # Also checks overlap, flags, tags and duplicates.
    if not {"mswc", "msww", "mswb"} <= entries.keys():
        raise ValueError("secondary FTAB missing T2026 memswap regions")
    return expanded


def secondary_from_primary(data):
    entries = ftab(data)
    if "2ftb" not in entries:
        raise ValueError("primary FTAB has no 2ftb header")
    off, size = entries["2ftb"]
    return secondary_ftab(data[off:off+size])


def inspect(data, ticket):
    entries = ftab(data)
    manp, images = manifest(ticket)
    required = {"CHIP": 0x2026, "BORD": 0x841, "SDOM": 1,
                "CEPO": 1, "CPRO": True, "CSEC": True}
    for name, value in required.items():
        if type(manp.get(name)) is not type(value) or manp[name] != value:
            raise ValueError(f"ticket {name} does not match production J714s N1")
    if "BNCH" in manp or "ECID" in manp:
        raise ValueError("device-bound ticket requires a separate identity/nonce workflow")
    if "rkos" not in images:
        raise ValueError("ticket does not cover rkos")
    verified = []
    for tag, props in images.items():
        if tag not in entries:
            raise ValueError(f"ticket component {tag} absent from FTAB")
        digest = props.get("DGST")
        if not isinstance(digest, bytes) or len(digest) != 48:
            raise ValueError(f"unsupported digest for {tag}")
        off, size = entries[tag]
        if hashlib.sha384(data[off:off+size]).digest() != digest:
            raise ValueError(f"SHA-384 mismatch: {tag}")
        verified.append(tag)
    report = {"chip": "0x2026", "board": "0x0841", "entries": len(entries),
            "hash_matched_components": sorted(verified),
            "components_without_ticket_hash": sorted(set(entries) - set(images)),
            "ticket_has_ecid_or_nonce_binding": False,
            "certificate_chain_verified": False,
            "ftab_sha256": hashlib.sha256(data).hexdigest(),
            "ticket_sha256": hashlib.sha256(ticket).hexdigest()}
    if "2ftb" in entries:
        secondary = secondary_from_primary(data)
        regions = ftab(secondary)
        report["secondary_memory"] = {
            "bytes": len(secondary), "entries": len(regions),
            "sha256": hashlib.sha256(secondary).hexdigest(),
            "memswap": {name: {"offset": regions[name][0], "bytes": regions[name][1]}
                        for name in ("mswc", "msww", "mswb")},
            "hardware_tested": False,
        }
    return report


def package(data, ticket):
    """ACFUFTABFile optimization 1: ticket before first payload, align to 4."""
    inspect(data, ticket)
    entries = ftab(data)
    if struct.unpack_from("<II", data, 16) != (0, 0):
        raise ValueError("input already has a manifest; refusing to replace it")
    ordered = list(entries.values())
    if ordered != sorted(ordered) or ordered[-1][0] + ordered[-1][1] != len(data):
        raise ValueError("requires ordered FTAB with no unexplained trailing data")
    first = ordered[0][0]
    if first != 48 + len(entries) * 16 or first % 4:
        raise ValueError("requires packed, 4-byte-aligned FTAB table")
    padded_ticket = ticket + bytes((-len(ticket)) % 4)
    out = bytearray(data[:first] + padded_ticket + data[first:])
    struct.pack_into("<II", out, 16, first, len(ticket))
    for i, (off, size) in enumerate(ordered):
        struct.pack_into("<I", out, 52 + i * 16, off + len(padded_ticket))
    # Match CentauriTransport::sendImage: zero padding to 4096-byte length.
    out.extend(bytes((-len(out)) % 4096))
    inspect(out, ticket)
    for tag, (off, size) in ftab(out).items():
        old_off, old_size = entries[tag]
        if size != old_size or out[off:off+size] != data[old_off:old_off+size]:
            raise ValueError(f"payload changed during packaging: {tag}")
    if out[first:first+len(ticket)] != ticket:
        raise ValueError("ticket changed during packaging")
    return bytes(out)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("ftab", type=Path)
    p.add_argument("ticket", type=Path)
    p.add_argument("--output", type=Path, help="private candidate path; must not exist")
    p.add_argument("--secondary-output", type=Path,
                   help="private zero-filled secondary allocation; must not exist")
    args = p.parse_args()
    try:
        data, ticket = args.ftab.read_bytes(), args.ticket.read_bytes()
        report = inspect(data, ticket)
        secondary = secondary_from_primary(data) if args.secondary_output else None
        if args.output:
            candidate = package(data, ticket)
            with args.output.open("xb") as f:
                f.write(candidate)
            report["candidate_size"] = len(candidate)
            report["candidate_sha256"] = hashlib.sha256(candidate).hexdigest()
        if secondary is not None:
            with args.secondary_output.open("xb") as f:
                f.write(secondary)
        print(json.dumps(report, indent=2))
    except (ValueError, KeyError, OSError, UnicodeError) as e:
        p.exit(1, f"n1_fw: {e}\n")


if __name__ == "__main__":
    main()
