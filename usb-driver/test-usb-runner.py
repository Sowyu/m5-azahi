#!/usr/bin/env python3
"""Host-only regression tests. All driver/network commands are shell mocks.

Temporary fixture writes are confined to TemporaryDirectory; no hardware access.
"""
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "usb-tether-test.sh"


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="usb-runner-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def shell(self, code):
        prefix = f'source {shlex.quote(str(SCRIPT))}\nLOG={shlex.quote(str(self.root / "test.log"))}\n'
        return subprocess.run(["/bin/bash", "-c", prefix + code], text=True, capture_output=True)

    def test_logging_preserves_command_failure(self):
        result = self.shell('bad() { echo failed; return 37; }; run bad')
        self.assertEqual(result.returncode, 37)
        self.assertIn("failed", result.stdout)

    def test_logging_failure_is_failure(self):
        result = self.shell('tee() { return 42; }; run true')
        self.assertEqual(result.returncode, 42)

    def test_https_failure_and_binding(self):
        result = self.shell('NEWIF=usb0; curl() { printf "arg=%s\\n" "$@"; return 60; }; https_test')
        self.assertEqual(result.returncode, 60)
        for argument in ('--interface', 'usb0', '--noproxy', '*', '-q', '--fail'):
            self.assertIn(f'arg={argument}\n', result.stdout)
        self.assertNotIn('arg=--insecure', result.stdout)

    def test_https_success(self):
        self.assertEqual(self.shell('NEWIF=usb0; curl() { return 0; }; https_test').returncode, 0)

    def manifest(self):
        lines = []
        for name in ('phy-apple-t6050-usb2.ko', 'dwc3-apple-t6050.ko',
                     'azahi-usb-overlay.ko', 'usb-tether-test.sh'):
            data = name.encode()
            (self.root / name).write_bytes(data)
            lines.append(f'{hashlib.sha256(data).hexdigest()}  {name}\n')
        (self.root / 'SHA256SUMS').write_text(''.join(lines))

    def verify(self):
        # macOS has shasum, not necessarily sha256sum. Preserve actual hashing.
        return self.shell(f'DIR={shlex.quote(str(self.root))}; sha256sum() {{ shasum -a 256 "$@"; }}; verify_bundle')

    def test_manifest_valid(self):
        self.manifest()
        self.assertEqual(self.verify().returncode, 0)

    def test_manifest_corrupt_file(self):
        self.manifest()
        (self.root / 'azahi-usb-overlay.ko').write_text('corrupted')
        self.assertNotEqual(self.verify().returncode, 0)

    def test_manifest_rejects_duplicate_and_traversal(self):
        self.manifest()
        manifest = self.root / 'SHA256SUMS'
        good = manifest.read_text()
        for bad in (good + good.splitlines()[0] + '\n', good.replace('azahi-usb-overlay.ko', '../escape')):
            manifest.write_text(bad)
            self.assertNotEqual(self.verify().returncode, 0)

    def test_manifest_rejects_missing_entry(self):
        self.manifest()
        manifest = self.root / 'SHA256SUMS'
        manifest.write_text('\n'.join(manifest.read_text().splitlines()[:3]) + '\n')
        self.assertNotEqual(self.verify().returncode, 0)

    def fixture(self):
        usb = self.root / 'usb'
        net = self.root / 'net'
        usb.mkdir(); net.mkdir()
        hub = self.root / 'devices/platform/soc/382280000.usb/xhci/usb7'
        hub.mkdir(parents=True)
        (usb / 'usb7').symlink_to(hub)
        other = self.root / 'devices/other/wifi'
        other.mkdir(parents=True)
        (net / 'wlan0').mkdir()
        (net / 'wlan0/device').symlink_to(other)
        return usb, net, hub

    def test_selects_only_right_port_usb_interface(self):
        usb, net, hub = self.fixture()
        phone = hub / '7-1/7-1:1.0'
        phone.mkdir(parents=True)
        (net / 'usb0').mkdir()
        (net / 'usb0/device').symlink_to(phone)
        result = self.shell(f'SYS_USB={usb}; SYS_NET={net}; candidate_interface')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'usb0')

    def test_unrelated_interface_is_not_tethering(self):
        usb, net, _ = self.fixture()
        self.assertNotEqual(self.shell(f'SYS_USB={usb}; SYS_NET={net}; candidate_interface').returncode, 0)

    def test_ambiguous_usb_interfaces_fail(self):
        usb, net, hub = self.fixture()
        for name in ('usb0', 'usb1'):
            child = hub / name
            child.mkdir()
            (net / name).mkdir()
            (net / name / 'device').symlink_to(child)
        self.assertNotEqual(self.shell(f'SYS_USB={usb}; SYS_NET={net}; candidate_interface').returncode, 0)

    def test_bad_mode_never_runs_module_command(self):
        result = self.shell('insmod() { echo UNSAFE; }; main typo')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('UNSAFE', result.stdout)

    def test_wrong_kernel_never_runs_module_command(self):
        result = self.shell('id() { echo 0; }; uname() { echo wrong; }; insmod() { echo UNSAFE; }; main dry')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('UNSAFE', result.stdout)

    def test_cleanup_unloads_only_owned_dry_overlay(self):
        result = self.shell('DRY_LOADED=1; rmmod() { echo "removed $*"; }; trap cleanup EXIT; exit 0')
        self.assertEqual(result.returncode, 0)
        self.assertIn('removed azahi_usb_overlay', result.stdout)
        result = self.shell('DRY_LOADED=0; rmmod() { echo UNSAFE; }; trap cleanup EXIT; exit 9')
        self.assertEqual(result.returncode, 9)
        self.assertNotIn('UNSAFE', result.stdout)

    def test_cleanup_failure_is_nonzero(self):
        result = self.shell('DRY_LOADED=1; rmmod() { return 1; }; trap cleanup EXIT; exit 0')
        self.assertNotEqual(result.returncode, 0)

    def dry_mocks(self):
        return f'''
id() {{ echo 0; }}
uname() {{ echo '7.0.13-400.asahi.fc44.aarch64+16k'; }}
findmnt() {{ echo PRIVATE-LINUX-FSUUID-NOT-CONFIGURED; }}
mktemp() {{ echo {shlex.quote(str(self.root / 'main.log'))}; }}
verify_bundle() {{ return 0; }}
insmod() {{ echo "LOAD $*"; }}
rmmod() {{ echo "UNLOAD $*"; }}
modprobe() {{ echo UNEXPECTED_MODPROBE; return 1; }}
dmesg() {{ echo mocked-kernel-log; }}
'''

    def test_default_main_is_dry_and_cleans_up(self):
        result = self.shell(self.dry_mocks() + 'main; exit $?')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('dry_run=1', result.stdout)
        self.assertEqual(result.stdout.count('UNLOAD azahi_usb_overlay'), 1)
        self.assertNotIn('UNEXPECTED_MODPROBE', result.stdout)
        self.assertNotIn('SUCCESS:', result.stdout)

    def test_failed_dry_load_is_not_unloaded(self):
        result = self.shell(self.dry_mocks() + 'insmod() { return 19; }; main dry; exit $?')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('UNLOAD', result.stdout)

    def test_failed_dry_dmesg_still_unloads(self):
        result = self.shell(self.dry_mocks() + 'dmesg() { return 1; }; main dry; exit $?')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('UNLOAD azahi_usb_overlay', result.stdout)

    def test_wrong_root_never_loads(self):
        result = self.shell(self.dry_mocks() + 'findmnt() { echo other-root; }; main dry; exit $?')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('LOAD', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
