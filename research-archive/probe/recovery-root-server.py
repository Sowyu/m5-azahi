#!/usr/bin/env python3
"""Narrow KDE-root transfer with pinned source and per-chunk SSD read-back SHA256."""
import argparse
import hashlib
import http.server
import importlib.util
import json
from pathlib import Path
import re
import secrets
import socketserver
import subprocess

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
IMAGE = PROJECT / 'ramroot/work-kde/root.img'
IMAGE_BYTES = 14248030208
IMAGE_SHA = 'bc33421d52f06288c53cba128ccc79b13c077fb90f957fea048a5048cd955f7b'
ROOT_UUID = 'PRIVATE-UUID-REMOVED'
RESIZE = PROJECT / 'logs/recovery-resize-20260906.yS45qc/after/backup.tar.gz'
PARTITIONS = PROJECT / 'logs/recovery-partitions-20260906.Zrp24U'


def load_validator():
    spec = importlib.util.spec_from_file_location('partitions', HERE / 'validate-recovery-partitions.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_script(transfer_url, manifest_checksum):
    # Reuse only the already-reviewed READ-ONLY collector, excluding its action tail.
    original = (HERE / 'recovery-create-partitions.sh').read_bytes()
    if hashlib.sha256(original).hexdigest() != '396cfc7c9e67f96db978860bfa41cf2ed528edb7fc4ed6944cb7f225be878501':
        raise ValueError('Collector source changed; review before use')
    original = original.decode()
    collector = original[original.index('get() {'):original.index('upload() {')]
    if any(word in collector for word in ('addPartition', 'eraseVolume', 'resizeContainer')):
        raise ValueError('Unexpected mutation in collector')
    prelude = '''#!/bin/bash
set -Eeuo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
fail() { echo "STOP: $*" >&2; exit 1; }
[[ $(sysctl -n hw.model) == Mac17,9 ]] || fail 'Not the M5 target'
[[ $# == 1 && $1 == install-kde-root ]] || fail 'Explicit install-kde-root argument required'
for required in diskutil plutil gpt dd cksum mktemp tar curl stat mkdir df awk; do
    command -v "$required" >/dev/null || fail "Missing tool: $required"
done
work=$(mktemp -d /tmp/azahi-install-kde-root.XXXXXX)
trap 'echo "STOP: Install stopped. Keep Recovery open; do not rerun or reboot. Logs: $work" >&2' ERR
available=$(df -Pk "$work" | awk 'NR==2 {print $4}')
[[ $available =~ ^[0-9]+$ && $available -ge 131072 ]] || fail 'Need at least 128MiB Recovery scratch space'
echo "KDE installer logs: $work"
echo 'Only the NEW Linux root UUIDPRIVATE-UUID-REMOVED will be written.'
echo 'Boot EFI, Linux APFS, daily macOS and Recovery are not write targets.'
'''
    script = prelude + collector + (HERE / 'recovery-install-root-tail.sh').read_text()
    return script.replace('@TRANSFER_URL@', transfer_url).replace('@MANIFEST_CKSUM@', manifest_checksum).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    destination = args.destination.resolve(strict=True)
    if any(destination.iterdir()):
        raise ValueError('New empty destination required; no automatic install resume')
    manifest = json.loads((HERE / 'kde-root-transfer-20260906.json').read_text())
    chunks = manifest['chunks']
    if (manifest['image_sha256'] != IMAGE_SHA or manifest['image_bytes'] != IMAGE_BYTES
            or manifest['chunk_bytes'] != 33554432 or len(chunks) != 425):
        raise ValueError('Unexpected image manifest')
    for index, chunk in enumerate(chunks):
        if (chunk['index'] != index or chunk['offset'] != index * 33554432
                or chunk['bytes'] != min(33554432, IMAGE_BYTES - chunk['offset'])
                or not 0 <= chunk['cksum'] <= 0xffffffff
                or not re.fullmatch('[0-9a-f]{64}', chunk['sha256'])):
            raise ValueError('Malformed chunk manifest')
    source = IMAGE.open('rb')
    source_stat = IMAGE.stat()
    def identity(stat):
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
    source_identity = identity(source_stat)
    if source_stat.st_size != IMAGE_BYTES:
        raise ValueError('Image size changed')
    manifest_text = ''.join(f"{c['index']} {c['offset']} {c['bytes']} {c['cksum']} {c['sha256']}\n" for c in chunks).encode()
    checksum = subprocess.run(['/usr/bin/cksum'], input=manifest_text, capture_output=True, check=True).stdout.decode().strip()
    route = '/transfer/' + secrets.token_hex(16)
    script = render_script(f'http://{args.bind}:{args.port}{route}', checksum)
    with (destination / 'served-script.sh').open('xb') as output:
        output.write(script)
    # The saved script contains only this LAN server's scoped transfer capability.
    (destination / 'served-script.sh').chmod(0o600)
    validator = load_validator()
    baseline = validator.load_baseline(RESIZE)
    esp = validator.validate(PARTITIONS / 'esp/backup.tar.gz', 'esp', baseline)
    pinned = validator.validate(PARTITIONS / 'root/backup.tar.gz', 'root', baseline, esp,
                                root_allocation='includes-helper')
    for stage in ('preflight', 'after'):
        (destination / stage).mkdir()
    preflight_valid = prefix_valid = image_verified = False
    next_index = 0
    whole_readback = hashlib.sha256()

    class Handler(http.server.BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(120)

        def send_bytes(self, data, content_type='text/plain'):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def read_exact(self, expected):
            if self.headers.get('Transfer-Encoding'):
                raise ValueError('Chunked HTTP uploads not accepted; use a bounded regular file')
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                size = 0
            if size != expected:
                raise ValueError('Upload length mismatch')
            result = bytearray()
            while len(result) < size:
                data = self.rfile.read(min(1048576, size - len(result)))
                if not data:
                    raise ValueError('Short upload')
                result.extend(data)
            return bytes(result)

        def do_GET(self):
            nonlocal image_verified
            if self.path == '/install-root.sh':
                self.send_bytes(script)
                return
            if self.path == route + '/manifest' and prefix_valid:
                self.send_bytes(manifest_text)
                return
            if self.path == route + '/complete' and next_index == len(chunks):
                if whole_readback.hexdigest() != IMAGE_SHA:
                    self.send_error(422, 'Full image SHA256 mismatch')
                    return
                image_verified = True
                self.send_bytes(f'VERIFIED_IMAGE {IMAGE_SHA}\n'.encode())
                print('FULL_SSD_READBACK_SHA256_VERIFIED', IMAGE_SHA, flush=True)
                return
            match = re.fullmatch(re.escape(route) + r'/chunk/(\d+)', self.path)
            if match and prefix_valid:
                index = int(match.group(1))
                if index != next_index or not 0 <= index < len(chunks):
                    self.send_error(409, 'Unexpected chunk order')
                    return
                if identity(IMAGE.stat()) != source_identity:
                    self.send_error(409, 'Source image changed')
                    return
                chunk = chunks[index]
                source.seek(chunk['offset'])
                blob = source.read(chunk['bytes'])
                if len(blob) != chunk['bytes'] or hashlib.sha256(blob).hexdigest() != chunk['sha256']:
                    self.send_error(422, 'Source chunk checksum failed')
                    return
                self.send_bytes(blob, 'application/octet-stream')
                return
            self.send_error(404)

        def do_PUT(self):
            nonlocal preflight_valid, prefix_valid, next_index
            try:
                if self.path in (route + '/preflight', route + '/after'):
                    stage = self.path.rsplit('/', 1)[1]
                    if stage == 'after' and not image_verified:
                        raise ValueError('Full read-back required before final report')
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 1048576:
                        raise ValueError('Metadata report too large/empty')
                    path = destination / stage / 'backup.tar.gz'
                    if path.exists():
                        raise ValueError('Metadata report already received; review before retry')
                    blob = self.read_exact(size)
                    with path.open('xb') as output:
                        output.write(blob)
                    crc = subprocess.run(['/usr/bin/cksum'], input=blob, capture_output=True, check=True).stdout.decode().strip()
                    receipt = f'CKSUM {crc}\nSHA256 {hashlib.sha256(blob).hexdigest()}\n'
                    with path.with_name('receipt.txt').open('x') as output:
                        output.write(receipt)
                    result = validator.validate(path, 'root', baseline, esp, root_allocation='includes-helper')
                    if ({k: p['raw_entry'] for k, p in result['new_partitions'].items()}
                            != {k: p['raw_entry'] for k, p in pinned['new_partitions'].items()}):
                        raise ValueError('Created partition identities/entries changed')
                    with path.with_name('validation.json').open('x') as output:
                        json.dump(result, output, indent=2)
                    if stage == 'preflight':
                        preflight_valid = True
                    receipt += f'VALIDATED_ROOT_INSTALL {stage}\n'
                    print(receipt, flush=True)
                    self.send_bytes(receipt.encode())
                    return
                if self.path == route + '/prefix' and preflight_valid and not prefix_valid:
                    blob = self.read_exact(69632)
                    path = destination / 'root-header-before.bin'
                    with path.open('xb') as output:
                        output.write(blob)
                    if blob[65600:65608] == b'_BHRfS_M':
                        raise ValueError('Root already contains Btrfs; refusing automatic overwrite/retry')
                    if blob[:4096] != bytes(4096):
                        raise ValueError('New root prefix is not wiped; inspect backup before any write')
                    prefix_valid = True
                    self.send_bytes(b'BLANK_ROOT_PREFIX_BACKED_UP\n')
                    print('ROOT_PREFIX_BACKED_UP; transfer enabled', flush=True)
                    return
                match = re.fullmatch(re.escape(route) + r'/verify/(\d+)', self.path)
                if match and prefix_valid:
                    index = int(match.group(1))
                    if not 0 <= index < len(chunks) or index not in (next_index, next_index - 1):
                        raise ValueError('Unexpected read-back chunk order')
                    chunk = chunks[index]
                    blob = self.read_exact(chunk['bytes'])
                    if hashlib.sha256(blob).hexdigest() != chunk['sha256']:
                        raise ValueError(f'SSD read-back SHA256 failed at chunk {index}')
                    if index == next_index:
                        whole_readback.update(blob)
                        next_index += 1
                        with (destination / 'progress.json').open('w') as output:
                            json.dump(dict(verified_chunks=next_index, total_chunks=len(chunks),
                                verified_bytes=chunk['offset'] + chunk['bytes'], image_bytes=IMAGE_BYTES), output)
                        print(f'SSD_VERIFIED {next_index}/{len(chunks)} bytes={chunk["offset"] + chunk["bytes"]}', flush=True)
                    self.send_bytes(f'VERIFIED_CHUNK {index} {chunk["sha256"]}\n'.encode())
                    return
                self.send_error(404)
            except (ValueError, OSError, KeyError) as error:
                print(f'TRANSFER_STOP: {error}', flush=True)
                self.send_error(422, 'Transfer validation failed; keep Recovery open and report the error')

        def log_message(self, fmt, *values):
            # No capability tokens or binary data in logs.
            path = getattr(self, 'path', '')
            if path == '/install-root.sh':
                print(f'{self.client_address[0]} GET install-root.sh', flush=True)

    class Server(http.server.HTTPServer):
        def server_bind(self):
            socketserver.TCPServer.server_bind(self)
            self.server_name = args.bind
            self.server_port = self.server_address[1]

    server = Server((args.bind, args.port), Handler)
    print(f'KDE root installer: http://{args.bind}:{args.port}/install-root.sh', flush=True)
    print(f'Receipts: {destination}; source {IMAGE_BYTES}B SHA256 {IMAGE_SHA}', flush=True)
    print('READY; no target access until user explicitly runs install-kde-root', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
