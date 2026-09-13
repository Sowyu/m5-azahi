#!/usr/bin/env python3
"""Serve one reviewed resize helper; validate bounded before/after metadata uploads."""
import argparse
import hashlib
import http.server
import importlib.util
import json
from pathlib import Path
import secrets
import socketserver
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--partitioning', action='store_true', help='Serve the separate free-space partition-creation workflow')
    args = parser.parse_args()
    root = args.destination.resolve(strict=True)
    if any(root.iterdir()):
        raise ValueError('Destination must be empty')
    spec = importlib.util.spec_from_file_location(
        'storage_validator', Path(__file__).with_name('validate-recovery-partitions.py' if args.partitioning else 'validate-recovery-storage.py'))
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    baseline = validator.load_baseline(args.baseline) if args.partitioning else validator.validate(args.baseline)
    stage_names = ('before', 'esp', 'root') if args.partitioning else ('before', 'after')
    endpoint = '/partitions.sh' if args.partitioning else '/resize.sh'
    helper = Path(__file__).with_name('recovery-create-partitions.sh' if args.partitioning else 'recovery-resize-linux.sh')
    for stage in stage_names:
        (root / stage).mkdir()
    upload_path = '/upload/' + secrets.token_hex(16)
    script = helper.read_text().replace(
        '@UPLOAD_URL@', f'http://{args.bind}:{args.port}{upload_path}').encode()
    validated = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def do_GET(self):
            if self.path != endpoint:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(script)))
            self.end_headers()
            self.wfile.write(script)

        def do_PUT(self):
            stages = {upload_path + '/' + stage: stage for stage in stage_names}
            if self.path not in stages:
                self.send_error(404)
                return
            stage = stages[self.path]
            if any(name not in validated for name in stage_names[:stage_names.index(stage)]):
                self.send_error(409, 'Validated previous reports required')
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                length = 0
            if not 0 < length <= 1024 * 1024:
                self.send_error(413)
                return
            folder = root / stage
            partial = folder / 'backup.tar.gz.partial'
            final = folder / 'backup.tar.gz'
            if partial.exists() or final.exists():
                self.send_error(409, 'Report already received; review before retry')
                return
            digest = hashlib.sha256()
            remaining = length
            with partial.open('xb') as output:
                while remaining:
                    chunk = self.rfile.read(min(65536, remaining))
                    if not chunk:
                        raise ConnectionError('Incomplete upload; partial preserved')
                    output.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
            partial.rename(final)
            checksum = subprocess.check_output(['/usr/bin/cksum', str(final)], text=True).split()
            receipt = f'CKSUM {checksum[0]} {checksum[1]}\nSHA256 {digest.hexdigest()}\n'
            with (folder / 'receipt.txt').open('x') as output:
                output.write(receipt)
            try:
                if args.partitioning:
                    result = validator.validate(final, stage, baseline, validated.get('esp'))
                else:
                    result = validator.validate(final, 256000000000 if stage == 'before' else 96000000000,
                                                require_unlocked=True)
                    if result['protected_gpt_and_mbr_sha256'] != baseline['protected_gpt_and_mbr_sha256']:
                        raise ValueError('Protected GPT/MBR bytes changed')
                    if not result['candidate_above_preferred_minimum']:
                        raise ValueError('96GB does not exceed preferred minimum')
            except Exception as error:
                print(f'{stage} VALIDATION_FAILED: {error}', flush=True)
                self.send_error(422, 'Storage validation failed; do not resize or retry')
                return
            with (folder / 'validation.json').open('x') as output:
                json.dump(result, output, indent=2)
                output.write('\n')
            validated[stage] = result
            receipt += f'{"VALIDATED_PARTITIONS" if args.partitioning else "VALIDATED_STORAGE"} {stage}\n'
            print(f'{stage}: {receipt}', flush=True)
            self.send_response(200)
            self.send_header('Content-Length', str(len(receipt)))
            self.end_headers()
            self.wfile.write(receipt.encode())

        def log_message(self, fmt, *values):
            # Never log the upload capability or malformed request contents.
            path = getattr(self, 'path', '')
            route = endpoint if path == endpoint else 'upload' if path.startswith('/upload/') else 'other'
            print(f'{self.client_address[0]} {getattr(self, "command", None)} {route}', flush=True)

    class Server(http.server.HTTPServer):
        def server_bind(self):
            socketserver.TCPServer.server_bind(self)
            self.server_name = args.bind
            self.server_port = self.server_address[1]

    server = Server((args.bind, args.port), Handler)
    print(f'Resize helper: http://{args.bind}:{args.port}{endpoint}', flush=True)
    print(f'Metadata destination: {root}', flush=True)
    print(f'Reviewed local helper SHA256: {hashlib.sha256(helper.read_bytes()).hexdigest()}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
