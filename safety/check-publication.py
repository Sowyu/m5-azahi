#!/usr/bin/env python3
"""Fail-closed source publication guard. Never print matched secret values.

Installed hooks run a separately copied version in .git/privacy-guard, so
editing the tracked scanner or allowlist does not disable installed protection.
"""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import sys

MAX_FILE = 2 * 1024 * 1024
MAX_TREE = 12 * 1024 * 1024
MAX_COMMITS = 2000
POLICY = Path(__file__).with_name('allowed-paths.txt')
ALLOWED_MODES = {b'100644', b'100755'}
BAD_SUFFIX = re.compile(r'\.(?:bin|ko|o|elf|img|dtb|dtbo|plist|im4p|im4m|ipsw|dmg|'
                        r'jpg|jpeg|png|gif|heic|webp|pdf|mp4|mov|wav|aiff|mp3|'
                        r'zip|gz|xz|zst|tar|7z|pem|key|p12|pfx|db|sqlite\d*|pcap\w*|log)$', re.I)
BAD_COMPONENTS = {'.git', '.ssh', '.aws', 'secrets', 'private', 'backups',
                  'captures', 'screenshots', 'logs', 'evidence'}
RULES = [
    ('private-key', rb'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----|b3BlbnNzaC1rZXktdjE[A]'),
    ('github-token', rb'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})'),
    ('cloud-key', rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    ('api-token', rb'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}'),
    ('slack-token', rb'\bxox[baprs]-[A-Za-z0-9-]{20,}'),
    ('jwt', rb'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}'),
    ('personal-home', rb'/(?:Users|home)/[A-Za-z0-9_.-]+/'),
    ('flattened-personal-home', rb'[-_](?:Users|home)[-_][A-Za-z0-9_.]+[-_]'),
    ('device-uuid', rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'),
    ('private-lan', rb'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b'),
    # Link-local and CGNAT (Tailscale-style) IPv4, IPv6 unique-local and link-local.
    ('private-net', rb'\b(?:169\.254|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7]))\.\d{1,3}\.\d{1,3}\b|'
                    rb'\bf[cd][0-9a-f]{2}:[0-9a-f]{0,4}:|\bfe80::'),
    ('device-ecid', rb'\becid\W*(?:0x)?[0-9a-f]{10,}\b'),
    ('serial-port-id', rb'usbmodem(?!PRIVATE(?:_[0-9]+)?\b)[A-Za-z0-9]{5,}'),
    ('mac-address', rb'\b(?:[0-9a-f]{2}([:-]))(?:[0-9a-f]{2}\1){4}[0-9a-f]{2}\b|\b[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}\b'),
    ('upload-capability', rb'/(?:upload|transfer)/[0-9a-f]{16,}'),
    ('url-credentials', rb'https?://[^\s/@:]+:[^\s/@]+@'),
    ('literal-secret', rb'''(?m)^\s*(?:export\s+)?(?:password|passwd|api_key|access_token|client_secret)\s*=\s*["'][^"'\r\n]{8,}["']\s*(?:#.*)?$'''),
    # JSON/YAML form, e.g. the relay's private config.json.
    ('quoted-secret', rb'''["']?\b(?:password|passwd|secret|token|api_key)["']?\s*:\s*["'][^"'\r\n]{8,}["']'''),
]


def git(*args):
    return subprocess.check_output(['git', *args], stderr=subprocess.PIPE)


def content_issues(path, mode, data, allowed):
    issues = []
    if path not in allowed:
        issues.append('path-not-reviewed')
    parts = Path(path).parts
    if any(p.lower() in BAD_COMPONENTS for p in parts) or any(p.lower().startswith('.env') for p in parts):
        issues.append('private-path')
    if BAD_SUFFIX.search(path):
        issues.append('binary-or-private-extension')
    if mode not in ALLOWED_MODES:
        issues.append('symlink-submodule-or-unsupported-mode')
    if len(data) > MAX_FILE:
        issues.append('file-too-large')
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        issues.append('not-utf8-text')
    # The verbatim GPL text contains form feeds (ASCII page separators).
    permitted_controls = (9, 10, 12, 13) if path == 'LICENSES/GPL-2.0.txt' else (9, 10, 13)
    if any(c < 32 and c not in permitted_controls for c in data):
        issues.append('binary-control-bytes')
    for label, pattern in RULES:
        if re.search(pattern, data, re.I):
            issues.append(label)
    return issues


def records(tree=None):
    raw = git('ls-tree', '-r', '-z', tree) if tree else git('ls-files', '--stage', '-z')
    for record in raw.split(b'\0'):
        if not record:
            continue
        metadata, name = record.split(b'\t', 1)
        fields = metadata.split()
        if tree:
            mode, kind, oid = fields
        else:
            mode, oid, stage = fields
            if stage != b'0':
                raise RuntimeError('unmerged index rejected')
        yield name.decode('utf-8'), mode, oid.decode('ascii')


def scan(history=False):
    allowed = set(POLICY.read_text().splitlines())
    if not allowed or any(not p or p.startswith('/') or '..' in Path(p).parts for p in allowed):
        raise RuntimeError('invalid allowlist')
    trees = [None]
    if history:
        commits = git('rev-list', '--all').decode().splitlines()
        if len(commits) > MAX_COMMITS:
            raise RuntimeError('history exceeds audit bound; explicit review required')
        trees += commits
    seen = set()
    sizes = {}
    failures = 0
    for tree in trees:
        total = 0
        for path, mode, oid in records(tree):
            if oid not in sizes:
                sizes[oid] = int(git('cat-file', '-s', oid))
            size = sizes[oid]
            total += size
            key = (path, mode, oid)
            if key in seen:
                continue
            seen.add(key)
            # Do not load a giant file just to reject it.
            data = git('cat-file', 'blob', oid) if size <= MAX_FILE and mode in ALLOWED_MODES else b''
            problems = content_issues(path, mode, data, allowed)
            if size > MAX_FILE:
                problems.append('file-too-large')
            if problems:
                print('BLOCKED', repr(path), ','.join(sorted(set(problems))), file=sys.stderr)
                failures += 1
        if total > MAX_TREE:
            print('BLOCKED tree exceeds source-only size limit', file=sys.stderr)
            failures += 1
    if failures:
        raise RuntimeError(f'{failures} publication policy violations; no secret values printed')
    print(f'Publication guard passed: {len(seen)} unique file versions checked.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    try:
        scan(history=args.history)
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print('PUBLICATION REFUSED:', type(error).__name__, str(error)[:160], file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
