#!/usr/bin/env python3
"""Real loopback SSH tests, no target or non-loopback network access."""
import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import socket
import asyncssh

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('relay', HERE / 'relay.py')
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertEqual(relay.FORWARD_PORT, 22022)
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            self.forward_port = reservation.getsockname()[1]
        relay.FORWARD_PORT = self.forward_port
        self.temp = tempfile.TemporaryDirectory(prefix='azahi-relay-test-')
        self.folder = Path(self.temp.name)
        relay.initialize(self.folder, '127.0.0.1', '-'.join('1' * n for n in (8, 4, 4, 4, 12)))
        self.state = relay.State(self.folder)
        self.server = await asyncssh.create_server(lambda: relay.Server(self.state),
            '127.0.0.1', 0, server_host_keys=[self.folder / 'relay_key'],
            process_factory=lambda p: relay.process(self.state, p))
        self.port = self.server.get_port()
        self.known = self.folder / 'known'
        self.known.write_text(f'[127.0.0.1]:{self.port} ' + self.state.config['relay_public'])

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        self.temp.cleanup()
        relay.FORWARD_PORT = 22022

    async def connect(self, user, **kwargs):
        return await asyncssh.connect('127.0.0.1', self.port, username=user,
            known_hosts=str(self.known), agent_path=None, **kwargs)

    async def test_bad_identity_and_password_rejected(self):
        for user in ('root', 'tunnel', 'setup'):
            with self.assertRaises(asyncssh.PermissionDenied):
                async with await self.connect(user, password='wrong', client_keys=[]):
                    pass
        with self.assertRaises(asyncssh.PermissionDenied):
            async with await self.connect('tunnel', client_keys=[self.folder / 'controller_key']):
                pass

    async def test_bootstrap_single_use_and_no_other_privileges(self):
        async with await self.connect('setup', password=self.state.config['password'], client_keys=[]) as conn:
            result = await conn.run('id')
            self.assertEqual(result.exit_status, 1)
            with self.assertRaises(asyncssh.ChannelOpenError):
                await conn.open_connection('127.0.0.1', 22)
            with self.assertRaises(asyncssh.ChannelListenError):
                await conn.forward_remote_port('127.0.0.1', self.forward_port, '127.0.0.1', 22)
            result = await conn.run('bootstrap', check=True)
            compile(result.stdout, '<bootstrap>', 'exec')
            self.assertNotIn(self.state.config['password'], result.stdout)
            result = await conn.run('bootstrap')
            self.assertEqual(result.exit_status, 1)
            self.assertTrue(relay.State(self.folder).used)
        with self.assertRaises(asyncssh.PermissionDenied):
            async with await self.connect('setup', password=self.state.config['password'], client_keys=[]):
                pass

    async def test_tunnel_register_pin_and_exact_forward(self):
        async with await self.connect('tunnel', client_keys=[self.folder / 'tunnel_key']) as conn:
            self.assertEqual((await conn.run('id')).exit_status, 1)
            with self.assertRaises(asyncssh.ChannelListenError):
                await conn.forward_remote_port('127.0.0.1', self.forward_port, '127.0.0.1', 22)
            native_key = asyncssh.generate_private_key('ssh-ed25519')
            value = dict(key=native_key.export_public_key().decode().strip(),
                         runtime='/run/azahi-remote-TEST', tag=self.state.config['tag'])
            result = await conn.run('register', input=json.dumps(value), check=True)
            self.assertIn('HOST_KEY_PINNED', result.stdout)
            self.assertEqual(json.loads((self.folder / 'registration.json').read_text()), value)
            self.assertEqual(relay.State(self.folder).registration, value)
            value['key'] = asyncssh.generate_private_key('ssh-ed25519').export_public_key().decode().strip()
            self.assertEqual((await conn.run('register', input=json.dumps(value))).exit_status, 1)
            for host, port in [('0.0.0.0', self.forward_port), ('', self.forward_port), ('127.0.0.1', 0)]:
                with self.assertRaises(asyncssh.ChannelListenError):
                    await conn.forward_remote_port(host, port, '127.0.0.1', 22)
            with self.assertRaises(asyncssh.ChannelOpenError):
                await conn.open_connection('127.0.0.1', 22)
            async def echo(reader, writer):
                writer.write(await reader.readexactly(4))
                await writer.drain()
                writer.close()
                await writer.wait_closed()
            endpoint = await asyncio.start_server(echo, '127.0.0.1', 0)
            try:
                port = endpoint.sockets[0].getsockname()[1]
                listener = await conn.forward_remote_port('127.0.0.1', self.forward_port, '127.0.0.1', port)
                reader, writer = await asyncio.open_connection('127.0.0.1', self.forward_port)
                writer.write(b'test'); await writer.drain()
                self.assertEqual(await asyncio.wait_for(reader.readexactly(4), 5), b'test')
                writer.close(); await writer.wait_closed()
                listener.close(); await listener.wait_closed()
            finally:
                endpoint.close(); await endpoint.wait_closed()

    async def test_unpinned_host_refused(self):
        wrong = self.folder / 'wrong'
        wrong.write_text(f'[127.0.0.1]:{self.port} ' + asyncssh.generate_private_key('ssh-ed25519').export_public_key().decode())
        with self.assertRaises(asyncssh.HostKeyNotVerifiable):
            async with await asyncssh.connect('127.0.0.1', self.port, username='setup',
                    known_hosts=str(wrong), password=self.state.config['password'], client_keys=[], agent_path=None):
                pass


if __name__ == '__main__': unittest.main(verbosity=2)
