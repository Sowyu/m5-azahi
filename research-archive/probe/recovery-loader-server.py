#!/usr/bin/env python3
"""Read-only server for three pinned CPU diagnostic/restore artifacts."""
import argparse
import hashlib
import http.server
from pathlib import Path
import socketserver


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bind', required=True)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    files = {
        '/loader.sh': (root / 'probe/recovery-loader.sh').read_bytes(),
        '/diag.bin': (root / 'probe/m1n1-smp-diag-v5-20260906.bin').read_bytes(),
        '/original.bin': (root / 'logs/recovery-backup-20260906.eTn0av/original-loader.bin').read_bytes(),
    }
    assert hashlib.sha256(files['/diag.bin']).hexdigest() == '7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef'
    assert hashlib.sha256(files['/original.bin']).hexdigest() == 'f2f234d99be7bdd0181366ec16c055ac14bdfa48cb2774c238836462521d2505'

    class Handler(http.server.BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def do_GET(self):
            if self.path not in files:
                self.send_error(404)
                return
            payload = files[self.path]
            self.send_response(200)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Content-Type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(payload)

    class Server(http.server.HTTPServer):
        def server_bind(self):
            socketserver.TCPServer.server_bind(self)
            self.server_name = args.bind
            self.server_port = self.server_address[1]

    print(f'Serving ONLY loader.sh, diag.bin, original.bin at {args.bind}:{args.port}', flush=True)
    Server((args.bind, args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
