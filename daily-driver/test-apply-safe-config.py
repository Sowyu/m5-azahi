#!/usr/bin/env python3
"""Host test for apply-safe-config.sh with a fake root and mocked commands."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('apply-safe-config.sh')
KERNEL = '7.0.13-400.asahi.fc44.aarch64+16k'
MOCKS = {
    'uname': 'echo "${MOCK_KERNEL}"',
    # State lives in $AZAHI_ROOT/units: "<unit> <state>" lines.
    'systemctl': r'''db=$AZAHI_ROOT/units; touch "$db"
case $1 in
  is-enabled) grep -q "^$2 " "$db" && sed -n "s/^$2 //p" "$db" || { echo disabled; exit 1; } ;;
  mask|enable) [ "$1" = mask ] && s=masked || s=enabled; cmd=$1; shift
    for u in "$@"; do grep -v "^$u " "$db" > "$db.n" || true; echo "$u $s" >> "$db.n"; mv "$db.n" "$db"; done ;;
  *) exit 1 ;;
esac''',
}


class ApplySafeConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'root'
        (self.root / 'proc/device-tree').mkdir(parents=True)
        (self.root / 'proc/device-tree/compatible').write_bytes(b'apple,j714s\0apple,t6050\0apple,arm-platform\0')
        (self.root / 'etc/dnf').mkdir(parents=True)
        (self.root / 'etc/dnf/dnf.conf').write_text('[main]\ngpgcheck=True\n')
        bindir = Path(self.tmp.name) / 'bin'
        bindir.mkdir()
        for name, body in MOCKS.items():
            path = bindir / name
            path.write_text('#!/bin/bash\n' + body + '\n')
            path.chmod(0o755)
        self.env = dict(os.environ, AZAHI_ROOT=str(self.root), MOCK_KERNEL=KERNEL,
                        PATH=f'{bindir}:{os.environ["PATH"]}')

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args, check=True):
        r = subprocess.run(['bash', str(SCRIPT), *args], env=self.env, text=True,
                           capture_output=True)
        if check:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def status(self, out):
        return [line.split()[0] for line in out.splitlines()]

    def test_check_mode_changes_nothing(self):
        before = (self.root / 'etc/dnf/dnf.conf').read_text()
        out = self.run_script().stdout
        self.assertEqual(set(self.status(out)), {'WOULD-CHANGE'})
        self.assertEqual((self.root / 'etc/dnf/dnf.conf').read_text(), before)
        self.assertFalse((self.root / 'etc/systemd').exists())
        self.assertFalse((self.root / 'units').exists() and (self.root / 'units').read_text())

    def test_apply_then_idempotent(self):
        out = self.run_script('--apply').stdout
        self.assertEqual(set(self.status(out)), {'CHANGED'})
        logind = (self.root / 'etc/systemd/logind.conf.d/90-azahi-no-sleep.conf').read_text()
        self.assertIn('HandleLidSwitch=ignore\n', logind)
        dnf = (self.root / 'etc/dnf/dnf.conf').read_text()
        self.assertEqual(dnf, '[main]\nexcludepkgs=kernel*,m1n1*,uboot-images*,update-m1n1\ngpgcheck=True\n')
        units = (self.root / 'units').read_text()
        for target in ('sleep', 'suspend', 'hibernate', 'hybrid-sleep', 'suspend-then-hibernate'):
            self.assertIn(f'{target}.target masked', units)
        self.assertEqual(set(self.status(self.run_script('--apply').stdout)), {'OK'})
        self.assertEqual(set(self.status(self.run_script().stdout)), {'OK'})

    def test_existing_excludes_are_kept_and_backed_up(self):
        conf = self.root / 'etc/dnf/dnf.conf'
        conf.write_text('[main]\nexcludepkgs=firefox,kernel*\n')
        self.run_script('--apply')
        self.assertEqual(conf.read_text(),
                         '[main]\nexcludepkgs=firefox,kernel*,m1n1*,uboot-images*,update-m1n1\n')
        backups = list(conf.parent.glob('dnf.conf.azahi-bak-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), '[main]\nexcludepkgs=firefox,kernel*\n')

    def test_missing_dnf_conf(self):
        (self.root / 'etc/dnf/dnf.conf').unlink()
        self.run_script('--apply')
        self.assertEqual((self.root / 'etc/dnf/dnf.conf').read_text(),
                         '[main]\nexcludepkgs=kernel*,m1n1*,uboot-images*,update-m1n1\n')

    def test_usb_at_boot_is_opt_in(self):
        self.run_script('--apply')
        self.assertNotIn('azahi-usb', (self.root / 'units').read_text())
        out = self.run_script('--apply', '--usb-at-boot').stdout
        self.assertIn('MISSING', out)
        (self.root / 'etc/systemd/system').mkdir(parents=True)
        (self.root / 'etc/systemd/system/azahi-usb.service').write_text('[Unit]\n')
        self.run_script('--apply', '--usb-at-boot')
        self.assertIn('azahi-usb.service enabled', (self.root / 'units').read_text())

    def test_refuses_wrong_machine_or_kernel(self):
        self.env['MOCK_KERNEL'] = '7.1.0-400.asahi.fc44.aarch64+16k'
        r = self.run_script('--apply', check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('REFUSED', r.stdout)
        self.env['MOCK_KERNEL'] = KERNEL
        (self.root / 'proc/device-tree/compatible').write_bytes(b'apple,j614s\0')
        r = self.run_script('--apply', check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.root / 'etc/systemd').exists())

    def test_readme_typed_steps_match_script(self):
        # The no-network commands in README.md must leave nothing to change.
        readme = SCRIPT.with_name('README.md').read_text()
        block = readme.split('### Without network: type these as root\n\n```sh\n', 1)[1]
        block = block.split('```', 1)[0].replace('/etc/', f'{self.root}/etc/')
        for _ in range(2):  # twice: typing it again must not duplicate anything
            subprocess.run(['bash', '-e', '-c', block], env=self.env, check=True,
                           capture_output=True)
        self.assertEqual(set(self.status(self.run_script().stdout)), {'OK'})
        self.assertEqual((self.root / 'etc/dnf/dnf.conf').read_text().count('excludepkgs'), 1)

    def test_unknown_argument(self):
        self.assertEqual(self.run_script('--force', check=False).returncode, 2)


if __name__ == '__main__':
    unittest.main()
