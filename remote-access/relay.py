#!/usr/bin/env python3
"""Dedicated SSH bootstrap/loopback reverse relay, not a host login service.

Runtime secrets/configs belong in a private directory, never publication.
Bootstrap password expires after 20 minutes and one successful transfer.
Tunnel key may only register a native host key and forward fixed loopback
port 22022. No local forwarding, host shell, SFTP or arbitrary commands.
"""
import argparse
import asyncio
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import asyncssh

HERE = Path(__file__).resolve().parent
FORWARD_PORT = 22022  # Fixed in production; isolated tests substitute a free port.


def fingerprint(folder):
    """SHA256 form printed by OpenSSH clients on first connection."""
    return asyncssh.read_public_key(folder / 'relay_key.pub').get_fingerprint()


def initialize(folder, host, root_uuid):
    ipaddress.IPv4Address(host)
    if not re.fullmatch('[0-9a-f-]{36}', root_uuid):
        raise ValueError('Expected private Linux root UUID')
    if any(folder.iterdir()):
        raise ValueError('Initialization directory must be empty')
    os.chmod(folder, 0o700)
    for name in ('relay_key', 'controller_key', 'tunnel_key'):
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '',
                        '-C', 'azahi-task', '-f', str(folder / name)], check=True)
    config = dict(host=host, port=8022, root_uuid=root_uuid,
                  tag=secrets.token_hex(4), password=secrets.token_hex(8),
                  relay_public=(folder / 'relay_key.pub').read_text(),
                  controller_public=(folder / 'controller_key.pub').read_text(),
                  tunnel_private=(folder / 'tunnel_key').read_text())
    fd = os.open(folder / 'config.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(config, out)
    target_config = {k: v for k, v in config.items() if k != 'password'}
    (folder / 'bootstrap.py').write_text('CONFIG = ' + repr(target_config) + '\n' +
                                        (HERE / 'bootstrap.py').read_text())
    os.chmod(folder / 'bootstrap.py', 0o600)
    print('Created private task keys/config. No listeners started.')
    print('RELAY_HOST_KEY', fingerprint(folder), '(compare before accepting)')


class State:
    def __init__(self, folder):
        self.folder = folder
        self.config = json.loads((folder / 'config.json').read_text())
        self.tunnel_key = asyncssh.read_public_key(folder / 'tunnel_key.pub')
        # Window and failure count live on disk: a relay restart must not
        # reopen an expired or locked-out bootstrap password.
        try:
            with (folder / 'bootstrap-expires').open('x') as out:
                out.write(repr(time.time() + 1200))
        except FileExistsError:
            pass
        self.deadline = float((folder / 'bootstrap-expires').read_text())
        failures = folder / 'bootstrap-failures'
        self.failures = failures.stat().st_size if failures.exists() else 0
        self.used = (folder / 'bootstrap-delivered').exists()
        self.registration = None
        if (folder / 'registration.json').exists():
            value = json.loads((folder / 'registration.json').read_text())
            key = asyncssh.import_public_key(value['key'])
            if value['tag'] != self.config['tag'] or key.get_algorithm() != 'ssh-ed25519':
                raise ValueError('Invalid saved registration')
            if (folder / 'native_known_hosts').read_text() != 'azahi-native ' + key.export_public_key().decode():
                raise ValueError('Saved host-key pin mismatch')
            self.registration = value


class Server(asyncssh.SSHServer):
    def __init__(self, state):
        self.state = state
        self.user = None

    def connection_made(self, conn):
        self.conn = conn

    def begin_auth(self, username):
        self.user = username
        return True

    def password_auth_supported(self):
        return (self.user == 'setup' and not self.state.used and
                self.state.failures < 5 and time.time() < self.state.deadline)

    def kbdint_auth_supported(self):
        return False

    def validate_password(self, username, password):
        if not self.password_auth_supported() or username != 'setup':
            return False
        if hmac.compare_digest(password, self.state.config['password']):
            return True
        self.state.failures += 1
        with (self.state.folder / 'bootstrap-failures').open('ab') as out:
            out.write(b'x')  # One byte per failure; size is the count.
        return False

    def public_key_auth_supported(self):
        return self.user == 'tunnel'

    def validate_public_key(self, username, key):
        return username == 'tunnel' and key == self.state.tunnel_key

    def server_requested(self, listen_host, listen_port):
        return (self.user == 'tunnel' and self.state.registration is not None and
                listen_host == '127.0.0.1' and listen_port == FORWARD_PORT)


async def process(state, proc):
    user = proc.get_extra_info('username')
    if user == 'setup' and proc.command == 'bootstrap' and not state.used and time.time() < state.deadline:
        with (state.folder / 'bootstrap-delivered').open('x'):
            pass
        state.used = True
        proc.stdout.write((state.folder / 'bootstrap.py').read_text())
        proc.exit(0)
        print('BOOTSTRAP_DELIVERED; password bootstrap disabled', flush=True)
    elif user == 'tunnel' and proc.command == 'register':
        try:
            payload = await asyncio.wait_for(proc.stdin.read(4097), 10)
            if len(payload) > 4096:
                raise ValueError('Oversized registration')
            value = json.loads(payload)
            if set(value) != {'key', 'runtime', 'tag'}:
                raise ValueError('Wrong registration fields')
            if value['tag'] != state.config['tag'] or not re.fullmatch('/run/azahi-remote-[a-zA-Z0-9_]+', value['runtime']):
                raise ValueError('Wrong task/runtime')
            key = asyncssh.import_public_key(value['key'])
            if key.get_algorithm() != 'ssh-ed25519':
                raise ValueError('Wrong host-key algorithm')
            if state.registration is not None and value != state.registration:
                raise ValueError('Host registration already pinned; no replacement')
            if state.registration is None:
                with (state.folder / 'registration.json').open('x') as out:
                    json.dump(value, out)
                with (state.folder / 'native_known_hosts').open('x') as out:
                    out.write('azahi-native ' + key.export_public_key().decode())
                state.registration = value
            proc.stdout.write('HOST_KEY_PINNED\n')
            proc.exit(0)
            print('NATIVE_HOST_KEY_REGISTERED', flush=True)
        except (ValueError, OSError, asyncio.TimeoutError):
            proc.stderr.write('Registration refused\n')
            proc.exit(1)
    else:
        proc.stderr.write('No shell or requested command on this relay\n')
        proc.exit(1)


async def serve(folder):
    state = State(folder)
    server = await asyncssh.create_server(lambda: Server(state), state.config['host'],
                                         state.config['port'],
                                         server_host_keys=[folder / 'relay_key'],
                                         process_factory=lambda p: process(state, p),
                                         login_timeout=30, encoding='utf-8')
    print('RELAY_HOST_KEY', fingerprint(folder), flush=True)
    print('RELAY_LISTENING; bootstrap window from first start is persistent; no host shell', flush=True)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('init', 'serve'))
    parser.add_argument('folder', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--root-uuid')
    args = parser.parse_args()
    if args.mode == 'init':
        initialize(args.folder, args.host, args.root_uuid)
    else:
        asyncio.run(serve(args.folder))
