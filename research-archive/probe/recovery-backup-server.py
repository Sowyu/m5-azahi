#!/usr/bin/env python3
"""Narrow, single-backup LAN receiver; never executes uploaded content."""
import argparse
import hashlib
import http.server
from pathlib import Path
import secrets
import socketserver
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bind', required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--script', type=Path, default=Path(__file__).with_name('recovery-backup.sh'),
                        help='Reviewed local Recovery helper to serve; uploads remain bounded')
    args = parser.parse_args()
    root = args.destination.resolve(strict=True)
    token = secrets.token_hex(16)
    upload_path = '/upload/' + token
    script = args.script.read_text().replace(
        '@UPLOAD_URL@', f'http://{args.bind}:{args.port}{upload_path}').encode()

    class Handler(http.server.BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def do_GET(self):
            if self.path != '/check.sh':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(script)))
            self.end_headers()
            self.wfile.write(script)

        def do_PUT(self):
            if self.path != upload_path:
                self.send_error(404)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                length = 0
            if not 0 < length <= 40 * 1024 * 1024:
                self.send_error(413)
                return
            partial = root / 'backup.tar.gz.partial'
            final = root / 'backup.tar.gz'
            if partial.exists() or final.exists():
                self.send_error(409, 'Backup already received or pending review')
                return
            digest = hashlib.sha256()
            remaining = length
            with partial.open('xb') as output:
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ConnectionError('Incomplete upload; partial preserved')
                    output.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
            partial.rename(final)
            checksum = subprocess.check_output(['/usr/bin/cksum', str(final)], text=True).split()
            receipt = f'CKSUM {checksum[0]} {checksum[1]}\nSHA256 {digest.hexdigest()}\n'
            with (root / 'receipt.txt').open('x') as output:
                output.write(receipt)
            print(receipt, flush=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(receipt.encode())

        def log_message(self, fmt, *values):
            # Keep the capability token out of the log.
            print(f'{self.client_address[0]} {self.command} {self.path.split("/")[1]}', flush=True)

    class Server(http.server.HTTPServer):
        def server_bind(self):
            # Avoid a reverse-DNS lookup delaying the local receiver startup.
            socketserver.TCPServer.server_bind(self)
            self.server_name = args.bind
            self.server_port = self.server_address[1]

    server = Server((args.bind, args.port), Handler)
    print(f'Read-only helper: http://{args.bind}:{args.port}/check.sh', flush=True)
    print(f'Backup destination: {root}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
