#!/usr/bin/env python3
"""Allowlisted LAN courier/enrollment server, installer gated by fresh RO backup.

No target commands executed by host. GET only immutable validated bytes; PUT
only bounded backup/readback archives. Never extracts or executes uploads.
"""
import argparse
import hashlib
import http.server
import json
from pathlib import Path
import re
import runpy
import secrets
import socketserver
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
S = runpy.run_path(str(ROOT / 'standalone-loader/install-server.py'))
B = runpy.run_path(str(HERE / 'build-transfer.py'))
V = S['V']
require = V['require']
CURRENT_COIH = 'B422A78B3E396F05C3C08A7AD9ADD7D406EBF641225BAEACCA3D95F5AF24F3FEE89D3A7A87D0B614BF2EAD97C9C5F1ED'
CURRENT = ROOT / 'logs/standalone-aligned-enroll-20260912.n8zyi1/install-after.tar.gz'
CANDIDATE_SHA = '0ca32c0df14ce714d32029ede06a428722616da0711fc5d0b85a98f1a77d77d0'


def profile():
    old, _ = S['aligned_profile'](
        ROOT / 'logs/standalone-preinstall-backup-20260911.T0uKOR/backup.tar.gz',
        ROOT / 'logs/standalone-enroll-20260911.AO0gTd/rollback-after.tar.gz')
    report = S['validate_after'](CURRENT, 'install', old, B['BASE_SHA'], 92651520)
    require(report['reported_coih'] == CURRENT_COIH, 'Saved current KDE coih mismatch')
    with tarfile.open(CURRENT, 'r:gz') as archive:
        baseline = S['policy_fields'](archive.extractfile('policy-after.txt').read())
        wrapped_sum = archive.extractfile('installed-cksum.txt').read().decode().strip()
    candidate = B['OUTPUT'].read_bytes()
    require(hashlib.sha256(candidate).hexdigest() == CANDIDATE_SHA, 'Transfer image pin mismatch')
    B['inspect'](candidate, json.loads(B['OUTPUT'].with_suffix('.json').read_text()))
    rollback = B['BASE'].read_bytes()
    require(hashlib.sha256(rollback).hexdigest() == B['BASE_SHA'], 'KDE rollback image mismatch')
    return baseline, wrapped_sum, candidate, rollback


def validate(path, mode, baseline):
    return S['validate_after'](path, mode, baseline, CANDIDATE_SHA, 92946432,
                               rollback=B['BASE_SHA'], rollback_size=92651520)


def render(baseline, wrapped_sum, candidate, base_url, upload_url, enabled=False):
    script = (HERE / 'recovery-transfer.sh').read_text()
    values = {'NSIH': baseline['Next Stage Image4 Hash                  (nsih)'],
              'BASELINE_COIH': baseline[S['COIH']], 'BASELINE_WRAPPED': wrapped_sum,
              'CANDIDATE_CKSUM': V['fingerprint'](candidate),
              'BASE_URL': base_url, 'UPLOAD_URL': upload_url,
              'ENABLE_INSTALL': 'yes' if enabled else 'no'}
    require(re.fullmatch(r'[0-9]+ [0-9]+', wrapped_sum), 'Invalid wrapper fingerprint')
    for key, value in values.items():
        require("'" not in value and '\n' not in value, 'Unsafe template value')
        require('@' + key + '@' in script, 'Template drift: ' + key)
        script = script.replace('@' + key + '@', value)
    require(not re.search(r'@[A-Z_]+@', script), 'Unrendered template token')
    return script.encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', required=True)
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    require(re.fullmatch(r'[0-9.]+', args.bind) and args.bind != '0.0.0.0', 'Bind a specific IPv4 address')
    destination = args.destination.resolve(strict=True)
    require(destination.is_dir() and not any(destination.iterdir()), 'Use a new empty receipt directory')
    baseline, wrapped_sum, candidate, rollback = profile()
    token = secrets.token_hex(16)
    base = f'http://{args.bind}:{args.port}'
    upload = '/upload/' + token
    snapshot_script = render(baseline, wrapped_sum, candidate, base, base + upload)
    install_script = render(baseline, wrapped_sum, candidate, base, base + upload, True)
    fresh_backup = False

    class Handler(http.server.BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(60)

        def do_GET(self):
            payloads = {'/usb.sh': snapshot_script}
            if fresh_backup:
                payloads.update({'/usb-install.sh': install_script,
                                 '/candidate.bin': candidate, '/rollback.bin': rollback})
            if self.path not in payloads:
                self.send_error(404, 'Unavailable until fresh backup is verified')
                return
            data = payloads[self.path]
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_PUT(self):
            nonlocal fresh_backup
            allowed = {upload + '/' + m: m for m in ('snapshot', 'install', 'rollback')}
            if self.path not in allowed:
                self.send_error(404)
                return
            mode = allowed[self.path]
            if mode != 'snapshot' and not fresh_backup:
                self.send_error(403, 'Fresh backup required')
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                length = 0
            if not 0 < length <= 110 * 1024 * 1024:
                self.send_error(413)
                return
            path = destination / (mode + '-after.tar.gz')
            partial = path.with_suffix(path.suffix + '.partial')
            if path.exists() or partial.exists():
                self.send_error(409, 'Prior upload preserved; review before retry')
                return
            try:
                with partial.open('xb') as output:
                    while length:
                        chunk = self.rfile.read(min(length, 1024 * 1024))
                        require(chunk, 'Incomplete upload')
                        output.write(chunk)
                        length -= len(chunk)
                partial.rename(path)
                report = validate(path, mode, baseline)
                with (destination / (mode + '-verified.json')).open('x') as output:
                    json.dump(report, output, indent=2)
                receipt = (f'CKSUM {V["fingerprint"](path.read_bytes())}\n'
                           f'SHA256 {report["archive_sha256"]}\nVALIDATED {mode}\n')
                with (destination / (mode + '-receipt.txt')).open('x') as output:
                    output.write(receipt)
                if mode == 'snapshot':
                    fresh_backup = True
                print(f'VALIDATED {mode}: {report["raw_sha256"]}', flush=True)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(receipt.encode())
            except Exception as error:
                print(f'STOP: {mode} validation failed: {error}; files preserved', flush=True)
                self.send_error(422, 'Host validation failed; do not reboot')

        def log_message(self, fmt, *values):
            print(f'{self.client_address[0]} {self.command} {self.path.split("/")[1]}', flush=True)

    class Server(http.server.HTTPServer):
        def server_bind(self):
            socketserver.TCPServer.server_bind(self)
            self.server_name = args.bind
            self.server_port = self.server_address[1]

    server = Server((args.bind, args.port), Handler)
    print(f'READ-ONLY backup helper: {base}/usb.sh', flush=True)
    print(f'Installer withheld until fresh backup; receipts: {destination}', flush=True)
    print('No target command, mount, enrollment or reboot performed by server.', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
