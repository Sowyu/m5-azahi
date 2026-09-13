#!/usr/bin/env python3
"""Read-only static file server for the USB-tether delivery bundle.

Serves ONLY usb-driver/deliver/ over HTTP on the M1 Pro host (PRIVATE-LAN-ENDPOINT-REMOVED),
so a Recovery / paired-Linux terminal on the M5 can fetch the modules and
test script. No uploads, no writes, no directory traversal, single folder.

    python3 usb-driver/deliver-server.py            # random port + token
    python3 usb-driver/deliver-server.py 8765 TOKEN  # fixed (for a retry)

Prints the exact fetch command to run on the target. Ctrl-C to stop.
"""
import http.server
import secrets
import socketserver
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / "deliver"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 0
TOKEN = sys.argv[2] if len(sys.argv) > 2 else secrets.token_hex(8)
FILES = ["phy-apple-t6050-usb2.ko", "dwc3-apple-t6050.ko",
         "azahi-usb-overlay.ko", "usb-tether-test.sh", "SHA256SUMS"]
for f in FILES:
    assert (ROOT / f).is_file(), f


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parts = self.path.lstrip("/").split("/", 1)
        if len(parts) != 2 or parts[0] != TOKEN or parts[1] not in FILES:
            self.send_error(404)
            return
        data = (ROOT / parts[1]).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        sys.stderr.write("[serve] %s - %s\n" % (self.address_string(), fmt % args))


with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
    port = httpd.server_address[1]
    base = f"PRIVATE-LAN-ENDPOINT-REMOVED:{port}/{TOKEN}"
    print(f"Serving {ROOT} at {base}\n")
    print("On the M5 target (Recovery / Linux terminal), run:")
    print(f"  cd /tmp && for f in {' '.join(FILES)}; do curl -fsSLO {base}/$f; done && sha256sum -c SHA256SUMS")
    print("\nCtrl-C to stop.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
