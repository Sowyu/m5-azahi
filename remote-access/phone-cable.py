#!/usr/bin/env python3
"""Create a loopback-only USB ADB tunnel for phone SSH or laptop web access.

Run on the J714s after `adb -d get-state` reports device. No key, service,
firewall or driver changes. Default: phone 2222 to laptop SSH 2222.
--internet: laptop 8118 to an existing phone HTTP proxy on 8118.
The stock adb CLI rejects host-qualified TCP endpoints even though the daemon
supports them. This sends the same framed request to its local server.
"""
import argparse
import os
from pathlib import Path
import re
import socket
import sys

KERNEL = '7.0.13-400.asahi.fc44.aarch64+16k'
REQUEST = b'reverse:forward:norebind:tcp:localhost:2222;tcp:localhost:2222'
INTERNET_REQUEST = b'host-usb:forward:norebind:tcp:localhost:8118;tcp:localhost:8118'


def receive(sock, count, *, optional=False):
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            if optional and not data:
                return None
            raise ValueError('ADB reply ended before its frame was complete')
        data.extend(chunk)
    return bytes(data)


def read_frame(sock, *, optional=False):
    length = receive(sock, 4, optional=optional)
    if length is None:
        return None
    if not re.fullmatch(rb'[0-9a-fA-F]{4}', length) or int(length, 16) > 4096:
        raise ValueError('ADB reply has an invalid or oversized length')
    return receive(sock, int(length, 16))


def okay(sock, stage):
    status = receive(sock, 4)
    if status == b'FAIL':
        read_frame(sock)  # Consume the bounded error, without printing device identifiers.
        raise ValueError(f'ADB refused {stage}; inspect get-state and the mapping list')
    if status != b'OKAY':
        raise ValueError(f'Invalid ADB status during {stage}')


def request(sock, command):
    sock.sendall(f'{len(command):04x}'.encode('ascii') + command)


def create_reverse(*, server_port=5037):
    with socket.create_connection(('127.0.0.1', server_port), timeout=5) as sock:
        request(sock, b'host:transport-usb')
        okay(sock, 'USB selection')
        request(sock, REQUEST)
        okay(sock, 'reverse service connection')
        okay(sock, 'loopback listener creation')
        resolved = read_frame(sock, optional=True)
        if resolved not in (None, b'', b'2222'):
            raise ValueError('ADB returned an unexpected listener port')


def create_internet(*, server_port=5037):
    with socket.create_connection(('127.0.0.1', server_port), timeout=5) as sock:
        request(sock, INTERNET_REQUEST)
        okay(sock, 'USB proxy forward request')
        okay(sock, 'loopback proxy listener creation')
        resolved = read_frame(sock, optional=True)
        if resolved not in (None, b'', b'8118'):
            raise ValueError('ADB returned an unexpected proxy listener port')


def require_target():
    if (os.uname().release != KERNEL or b'apple,j714s' not in
            Path('/proc/device-tree/compatible').read_bytes().split(b'\0')):
        raise ValueError('Requires the J714s laptop and pinned kernel')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--internet', action='store_true',
                        help='forward laptop loopback 8118 to the phone proxy')
    args = parser.parse_args()
    try:
        require_target()
        if args.internet:
            create_internet()
        else:
            with socket.create_connection(('127.0.0.1', 2222), timeout=5) as ssh:
                banner = bytearray()
                while len(banner) < 255 and not banner.endswith(b'\n'):
                    banner.extend(receive(ssh, 1))
                if not banner.startswith(b'SSH-2.0-') or not banner.endswith(b'\n'):
                    raise ValueError('The existing loopback service did not send an SSH banner')
            create_reverse()
    except (OSError, ValueError) as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        mapping = 'forward' if args.internet else 'reverse'
        print(f'If a request was sent, inspect adb -d {mapping} --list before retrying.',
              file=sys.stderr)
        return 1
    if args.internet:
        print('ADB_PROXY_CREATED: laptop localhost:8118 -> phone localhost:8118')
        print('The phone proxy and verified HTTPS request still need testing.')
        return 0
    print('ADB_LOOPBACK_CREATED: phone localhost:2222 -> laptop localhost:2222')
    print('SSH authentication and cable stability still need the phone-side test.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
