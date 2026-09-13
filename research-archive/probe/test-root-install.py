#!/usr/bin/env python3
"""Mocked 4KiB installation and real local HTTP chunk verification; never writes target SSD."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import select
import socket
import subprocess
import sys
import tarfile
import tempfile
import unittest
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('server', HERE / 'recovery-root-server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def cksum(data):
    return subprocess.run(['/usr/bin/cksum'], input=data, capture_output=True, check=True).stdout.decode().strip()


class Tests(unittest.TestCase):
    def test_rendered_script_syntax_and_host_rejection(self):
        script = server.render_script('http://127.0.0.1/transfer/test', '1 2')
        self.assertNotIn(b'@TRANSFER_URL@', script)
        self.assertNotIn(b'addPartition', script)
        subprocess.run(['/bin/bash', '-n'], input=script, check=True)
        result = subprocess.run(['/bin/bash', '-s', '--', 'install-kde-root'], input=script, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Not the M5 target', result.stderr)

    def shell_case(self, mode, writes):
        with tempfile.TemporaryDirectory(prefix='azahi-root-shell-') as tmp:
            root = Path(tmp).resolve()
            with tarfile.open(server.PARTITIONS / 'root/backup.tar.gz') as archive:
                data = {m.name: archive.extractfile(m).read() for m in archive.getmembers()}
            if mode == 'wrong_root':
                for name in data:
                    if name.startswith('part-'):
                        info = plistlib.loads(data[name])
                        if info['DiskUUID'].lower() == server.ROOT_UUID:
                            info['DiskUUID'] = 'PRIVATE-UUID-REMOVED'
                            data[name] = plistlib.dumps(info)
            for name, blob in data.items(): (root / name).write_bytes(blob)
            blob = bytes(range(256)) * 16
            sha = hashlib.sha256(blob).hexdigest()
            crc = cksum(blob).split()[0]
            manifest = f'0 0 4096 {crc} {sha}\n'.encode()
            (root / 'source.bin').write_bytes(blob)
            (root / 'corrupt.bin').write_bytes(b'!' * 4096)
            (root / 'zeros.bin').write_bytes(bytes(4096))
            (root / 'prefix.bin').write_bytes(bytes(69632))
            (root / 'manifest.txt').write_bytes(manifest)
            # Scale only the temporary test copy to one 4KiB chunk. Production source remains pinned.
            script = server.render_script('http://127.0.0.1/transfer/test', cksum(manifest)).decode()
            script = script.replace('14248030208', '4096').replace('/425', '/1').replace('== 425', '== 1').replace(server.IMAGE_SHA, sha)
            (root / 'install.sh').write_text(script)
            result = subprocess.run(['/bin/bash', '-c', 'source "$1"; /bin/bash "$2" install-kde-root',
                'test', str(HERE / 'test-root-install-mocks.sh'), str(root / 'install.sh')],
                env=dict(os.environ, ROOT_TEST_DIR=str(root), ROOT_TEST_MODE=mode),
                capture_output=True, text=True, timeout=30)
            mutations = (root / 'mutations').read_text().splitlines() if (root / 'mutations').exists() else []
            self.assertEqual(len(mutations), writes, result.stdout + result.stderr)
            if mode == 'success':
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual((root / 'device.bin').read_bytes(), blob)
                self.assertIn('KDE_ROOT_IMAGE_INSTALLED_AND_VERIFIED', result.stdout)
            else:
                self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_shell_success(self): self.shell_case('success', 1)
    def test_wrong_root_no_write(self): self.shell_case('wrong_root', 0)
    def test_failed_preflight_no_write(self): self.shell_case('bad_preflight', 0)
    def test_bad_download_no_write(self): self.shell_case('corrupt_download', 0)
    def test_bad_readback_stops(self): self.shell_case('corrupt_readback', 1)
    def test_bad_host_sha_stops(self): self.shell_case('bad_sha', 1)

    def test_http_real_chunk_verification(self):
        with tempfile.TemporaryDirectory(prefix='azahi-root-http-') as tmp:
            destination = Path(tmp)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            process = subprocess.Popen([sys.executable, '-u', str(HERE / 'recovery-root-server.py'),
                '--bind', '127.0.0.1', '--port', str(port), '--destination', str(destination)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            try:
                self.assertTrue(select.select([process.stdout], [], [], 10)[0])
                self.assertIn('KDE root installer:', process.stdout.readline())
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(f'http://127.0.0.1:{port}/install-root.sh', timeout=10) as response:
                    script = response.read().decode()
                route = re.search(r'http://127\.0\.0\.1:\d+/transfer/[0-9a-f]{32}', script).group()
                def put(suffix, data):
                    request = urllib.request.Request(route + suffix, data=data, method='PUT')
                    with opener.open(request, timeout=30) as response: return response.read()
                with self.assertRaises(urllib.error.HTTPError) as error:
                    opener.open(route + '/chunk/0', timeout=5)
                self.assertEqual(error.exception.code, 404); error.exception.close()
                self.assertIn(b'VALIDATED_ROOT_INSTALL preflight',
                              put('/preflight', (server.PARTITIONS / 'root/backup.tar.gz').read_bytes()))
                self.assertEqual(put('/prefix', bytes(69632)), b'BLANK_ROOT_PREFIX_BACKED_UP\n')
                with opener.open(route + '/chunk/0', timeout=10) as response: chunk = response.read()
                expected = json.loads((HERE / 'kde-root-transfer-20260906.json').read_text())['chunks'][0]['sha256']
                self.assertEqual(hashlib.sha256(chunk).hexdigest(), expected)
                bad = bytearray(chunk); bad[0] ^= 1
                with self.assertRaises(urllib.error.HTTPError) as error: put('/verify/0', bytes(bad))
                self.assertEqual(error.exception.code, 422); error.exception.close()
                self.assertFalse((destination / 'progress.json').exists())
                self.assertEqual(put('/verify/0', chunk), f'VERIFIED_CHUNK 0 {expected}\n'.encode())
                self.assertEqual(put('/verify/0', chunk), f'VERIFIED_CHUNK 0 {expected}\n'.encode())
                self.assertEqual(json.loads((destination / 'progress.json').read_text())['verified_chunks'], 1)
                with self.assertRaises(urllib.error.HTTPError) as error: opener.open(route + '/complete', timeout=5)
                self.assertEqual(error.exception.code, 404); error.exception.close()
            finally:
                process.terminate(); process.communicate(timeout=5)


if __name__ == '__main__': unittest.main(verbosity=2)
