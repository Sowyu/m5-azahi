#!/usr/bin/env python3
"""Real localhost protocol checks. No ADB daemon, USB device or SSH service used."""
import contextlib
import importlib.util
import io
from pathlib import Path
import socket
import sys
import threading
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('cable', Path(__file__).with_name('phone-cable.py'))
cable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cable)


class CableChecks(unittest.TestCase):
    def exchange(self, replies, expected_error=None, *, internet=False):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(3)
        port = listener.getsockname()[1]
        received, errors = [], []

        def server():
            try:
                with listener:
                    conn, address = listener.accept()
                    self.assertEqual(address[0], '127.0.0.1')
                    with conn:
                        conn.settimeout(3)
                        for reply in replies:
                            received.append(cable.read_frame(conn))
                            conn.sendall(reply)
                        conn.shutdown(socket.SHUT_WR)
                        self.assertEqual(conn.recv(1), b'')
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=server)
        thread.start()
        create = cable.create_internet if internet else cable.create_reverse
        try:
            if expected_error:
                with self.assertRaisesRegex(ValueError, expected_error):
                    create(server_port=port)
            else:
                create(server_port=port)
        finally:
            thread.join(timeout=4)
        self.assertFalse(thread.is_alive(), 'Protocol test failed to close its connection')
        if errors:
            raise errors[0]
        expected = ([b'host-usb:forward:norebind:tcp:localhost:8118;tcp:localhost:8118']
                    if internet else [b'host:transport-usb'])
        if not internet and len(replies) == 2:
            expected.append(b'reverse:forward:norebind:tcp:localhost:2222;tcp:localhost:2222')
        self.assertEqual(received, expected)

    def test_success_requires_service_and_listener_acks(self):
        self.exchange([b'OKAY', b'OKAYOKAY00042222'])

    def test_older_daemon_may_omit_resolved_port(self):
        self.exchange([b'OKAY', b'OKAYOKAY'])

    def test_internet_requires_both_acks_and_expected_port(self):
        for reply in (b'OKAYOKAY00048118', b'OKAYOKAY0000', b'OKAYOKAY'):
            with self.subTest(reply=reply):
                self.exchange([reply], internet=True)

    def test_internet_refuses_errors_without_rebinding_or_another_transport(self):
        for reply, reason in ((b'FAIL0004busy', 'refused USB proxy'),
                              (b'OKAYFAIL0004nope', 'refused loopback proxy'),
                              (b'OKAY', 'frame was complete'),
                              (b'OKAYOKAY00042222', 'unexpected proxy listener port'),
                              (b'OKAYOKAYzzzz', 'invalid or oversized')):
            with self.subTest(reply=reply):
                self.exchange([reply], reason, internet=True)

    def test_internet_uses_target_guard_and_does_not_require_ssh(self):
        for target_error in (None, ValueError('Requires the J714s laptop')):
            with self.subTest(refused=bool(target_error)), \
                    patch.object(sys, 'argv', ['phone-cable.py', '--internet']), \
                    patch.object(cable, 'require_target', side_effect=target_error) as guard, \
                    patch.object(cable.socket, 'create_connection') as connect, \
                    patch.object(cable, 'create_internet') as internet, \
                    patch.object(cable, 'create_reverse') as reverse, \
                    contextlib.redirect_stderr(io.StringIO()), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cable.main(), 1 if target_error else 0)
                guard.assert_called_once_with()
                connect.assert_not_called()
                reverse.assert_not_called()
                if target_error:
                    internet.assert_not_called()
                else:
                    internet.assert_called_once_with()
                    self.assertIn('ADB_PROXY_CREATED', output.getvalue())
                    self.assertNotIn('ADB_LOOPBACK_CREATED', output.getvalue())

    def test_unauthorized_or_multiple_usb_devices_do_not_send_a_mapping(self):
        for message in (b'unauthorized', b'more than one device'):
            with self.subTest(message=message):
                self.exchange([b'FAIL' + f'{len(message):04x}'.encode() + message],
                              'refused USB selection')

    def test_service_refusal_has_no_broader_fallback(self):
        self.exchange([b'OKAY', b'FAIL0004nope'], 'refused reverse service')

    def test_listener_refusal_is_not_success(self):
        self.exchange([b'OKAY', b'OKAYFAIL0004busy'], 'refused loopback listener')

    def test_malformed_status_and_port_rejected(self):
        for reply, reason in ((b'NOPE', 'Invalid ADB status'),
                              (b'OKAYOKAYzzzz', 'invalid or oversized'),
                              (b'OKAYOKAYffff', 'invalid or oversized'),
                              (b'OKAYOKAY00049999', 'unexpected listener port')):
            with self.subTest(reply=reply):
                self.exchange([b'OKAY', reply], reason)

    def test_fragmented_and_truncated_frames(self):
        class Fragmented:
            def __init__(self, data):
                self.data = io.BytesIO(data)

            def recv(self, count):
                return self.data.read(min(count, 1))

        self.assertEqual(cable.read_frame(Fragmented(b'00042222')), b'2222')
        self.assertIsNone(cable.read_frame(Fragmented(b''), optional=True))
        for data in (b'0', b'000', b'00042'):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, 'frame was complete'):
                cable.read_frame(Fragmented(data), optional=True)

    def test_wrong_machine_refuses_before_any_connection(self):
        with patch.object(sys, 'argv', ['phone-cable.py']), \
                patch.object(cable.os, 'uname') as uname, \
                patch.object(cable.socket, 'create_connection') as connect, \
                contextlib.redirect_stderr(io.StringIO()):
            uname.return_value.release = 'not-the-target-kernel'
            self.assertEqual(cable.main(), 1)
            connect.assert_not_called()

    def test_wrong_board_refuses_before_any_connection(self):
        with patch.object(sys, 'argv', ['phone-cable.py']), \
                patch.object(cable.os, 'uname') as uname, \
                patch.object(cable.Path, 'read_bytes', return_value=b'apple,other\0'), \
                patch.object(cable.socket, 'create_connection') as connect, \
                contextlib.redirect_stderr(io.StringIO()):
            uname.return_value.release = cable.KERNEL
            self.assertEqual(cable.main(), 1)
            connect.assert_not_called()

    def test_existing_ssh_banner_is_required_before_mapping(self):
        for banner in (b'SSH-2.0-OpenSSH_10.0\r\n', b'HTTP/1.1 200 OK\r\n',
                       b'SSH-2.0-truncated', b'SSH-2.0-' + b'a' * 255):
            with self.subTest(banner=banner[:32]), \
                    patch.object(sys, 'argv', ['phone-cable.py']), \
                    patch.object(cable, 'require_target'), \
                    patch.object(cable.socket, 'create_connection') as connect, \
                    patch.object(cable, 'create_reverse') as reverse, \
                    contextlib.redirect_stderr(io.StringIO()), \
                    contextlib.redirect_stdout(io.StringIO()):
                data = io.BytesIO(banner)
                connect.return_value.__enter__.return_value.recv.side_effect = data.read
                self.assertEqual(cable.main(), 0 if banner.endswith(b'10.0\r\n') else 1)
                connect.assert_called_once_with(('127.0.0.1', 2222), timeout=5)
                if banner.endswith(b'10.0\r\n'):
                    reverse.assert_called_once_with()
                else:
                    reverse.assert_not_called()


if __name__ == '__main__':
    unittest.main()
