#!/usr/bin/env python3
"""Decode the observed T6050 iBootData 1.0 layout without executing anything.

Input is an already extracted raw payload, not an IM4P or a hardware device.
Opcodes, conditions and flags remain raw. Records are not MMIO instructions
for a user to replay. See docs/audit-2026-09-25/smp.md for firmware provenance.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

MAX_INPUT = 8 * 1024 * 1024
HEADER = (0xb001da1a, 0x100, 1, 0, 0x40, 0x80, 1, 0x100)


def decode(data):
    def span(offset, size):
        if offset < 0 or size < 0 or offset + size > len(data):
            raise ValueError(f'truncated range at {offset:#x}, size {size:#x}')
        return data[offset:offset + size]

    def unpack(fmt, offset):
        return struct.unpack(fmt, span(offset, struct.calcsize(fmt)))

    def string(offset, size):
        raw = span(offset, size)
        end = raw.find(b'\0')
        if end <= 0 or any(c < 32 or c > 126 for c in raw[:end]):
            raise ValueError(f'invalid ASCII string at {offset:#x}')
        return raw[:end].decode('ascii')

    if len(data) > MAX_INPUT or unpack('<8I', 0) != HEADER:
        raise ValueError('unsupported iBootData header; requires observed 1.0 layout')
    banner = string(0x40, 0x80)
    first, end = unpack('<QQ', 0x100)
    if first % 8 or end <= first or (end - first) % 8 or (end - first) // 8 > 64:
        raise ValueError('invalid target pointer table')
    span(first, end - first)
    targets = []
    configs = set()
    for slot in range(first, end, 8):
        pointer, = unpack('<Q', slot)
        chip, revision, selector, count, config = unpack('<IIIIQ', pointer)
        if pointer % 4 or chip != 0x6050 or count != 1:
            raise ValueError('unsupported target or config count')
        target = {'chip': chip, 'revision': revision, 'selector': selector}
        if target in targets:
            raise ValueError('duplicate target')
        targets.append(target)
        configs.add(config)
    # ponytail: one shared RCfg block; extend only with another verified layout.
    if len(configs) != 1:
        raise ValueError('targets do not share one RCfg block')
    config = configs.pop()
    magic, count, table = unpack('<IIQ', config)
    if config % 4 or table % 4 or magic != 0x52436667 or count != 5:
        raise ValueError('unsupported RCfg directory')
    sections = {}
    for entry in range(table, table + count * 16, 16):
        kind, size, offset = unpack('<IIQ', entry)
        if kind not in range(5) or kind in sections or offset % 4 or not size:
            raise ValueError('invalid RCfg section')
        span(offset, size)
        sections[kind] = {'kind': kind, 'offset': offset, 'size': size}
    ranges = sorted((s['offset'], s['offset'] + s['size']) for s in sections.values())
    if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
        raise ValueError('overlapping RCfg sections')
    names = {}
    section = sections[4]
    if section['size'] % 66:
        raise ValueError('partial sequence name')
    for offset in range(section['offset'], section['offset'] + section['size'], 66):
        seq, = unpack('<H', offset)
        if seq in names or seq > 1023:
            raise ValueError('duplicate or oversized sequence ID')
        names[seq] = string(offset + 2, 64)
    for kind in range(4):
        section = sections[kind]
        offset, size = section['offset'], section['size']
        end = offset + size
        records = []
        if size % 4:
            raise ValueError('partial instruction word')
        while offset < end:
            header, = unpack('<I', offset)
            count = header & 0xff
            seq = (header >> 18) & 0x3ff
            if count > 32 or offset + 4 * (count + 1) > end:
                raise ValueError(f'truncated or oversized instruction at {offset:#x}')
            if seq not in names or names[seq] == 'MAX_SEQ':
                raise ValueError(f'unknown sequence ID at {offset:#x}')
            records.append({'offset': offset, 'sequence': seq, 'name': names[seq],
                            'opcode': (header >> 8) & 0x3ff, 'flags': header >> 28,
                            'operands': list(unpack(f'<{count}I', offset + 4))})
            offset += 4 * (count + 1)
        section['records'] = records
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
            'banner': banner, 'targets': targets, 'names': names,
            'sections': [sections[k] for k in range(4)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payload', type=Path)
    parser.add_argument('--sequence', help='include records for this exact sequence name')
    parser.add_argument('--word', type=lambda value: int(value, 0),
                        help='include records containing this raw operand, e.g. 0x80688008')
    args = parser.parse_args()
    try:
        if not args.payload.is_file():
            raise ValueError('input must be a regular extracted file')
        with args.payload.open('rb') as source:
            data = source.read(MAX_INPUT + 1)
        report = decode(data)
        if args.sequence is not None and args.sequence not in report['names'].values():
            raise ValueError('sequence name was not found')
        if args.word is not None and not 0 <= args.word <= 0xffffffff:
            raise ValueError('operand must fit in 32 bits')
        for section in report['sections']:
            records = section.pop('records')
            section['instruction_count'] = len(records)
            section['sequence_counts'] = dict(sorted(Counter(r['name'] for r in records).items()))
            if args.sequence is not None or args.word is not None:
                section['records'] = [r for r in records
                                      if (args.sequence is None or r['name'] == args.sequence)
                                      and (args.word is None or args.word in r['operands'])]
        report.pop('names')
        print(json.dumps(report, indent=2))
    except (OSError, ValueError) as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
