#!/usr/bin/env python3
"""Host test for apply-safe-config.sh with a fake root and mocked commands."""
import os
import configparser
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('apply-safe-config.sh')
KERNEL = '7.0.13-400.asahi.fc44.aarch64+16k'
MOCKS = {
    'uname': 'echo "${MOCK_KERNEL}"',
    # State lives in $AZAHI_ROOT/units: "<unit> <state>" lines.
    'systemctl': r'''if [[ $1 = --root ]]; then
    [[ $2 = "$AZAHI_ROOT" ]] || exit 9
    shift 2
elif [[ $REQUIRE_ROOT_ARG = 1 ]]; then
    exit 9
fi
db=$AZAHI_ROOT/units; touch "$db"
case $1 in
  is-enabled) grep -q "^$2 " "$db" && sed -n "s/^$2 //p" "$db" || { echo disabled; exit 1; } ;;
  mask|enable) [ "$1" = mask ] && s=masked || s=enabled; cmd=$1; shift
    for u in "$@"; do grep -v "^$u " "$db" > "$db.n" || true; echo "$u $s" >> "$db.n"; mv "$db.n" "$db"; done ;;
  *) exit 1 ;;
esac''',
}


class ApplySafeConfig(unittest.TestCase):
    def setUp(self):
        if not shutil.which('trash-put'):
            raise RuntimeError('Install trash-cli: sudo apt-get install -y trash-cli')
        self.tmp = Path(tempfile.mkdtemp(prefix='azahi-settings-test-'))
        self.addCleanup(subprocess.run, ['trash-put', str(self.tmp)], check=True)
        self.root = self.tmp / 'root'
        (self.root / 'proc/device-tree').mkdir(parents=True)
        (self.root / 'proc/device-tree/compatible').write_bytes(b'apple,j714s\0apple,t6050\0apple,arm-platform\0')
        (self.root / 'etc/dnf').mkdir(parents=True)
        (self.root / 'etc/dnf/dnf.conf').write_text('[main]\ngpgcheck=True\n')
        bindir = self.tmp / 'bin'
        bindir.mkdir()
        for name, body in MOCKS.items():
            path = bindir / name
            path.write_text('#!/bin/bash\n' + body + '\n')
            path.chmod(0o755)
        self.env = dict(os.environ, AZAHI_ROOT=str(self.root), MOCK_KERNEL=KERNEL,
                        REQUIRE_ROOT_ARG='1',
                        PATH=f'{bindir}:{os.environ["PATH"]}')

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
                         '[main]\nexcludepkgs=m1n1*,uboot-images*,update-m1n1,firefox,kernel*\n')
        backups = list(conf.parent.glob('dnf.conf.azahi-bak-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), '[main]\nexcludepkgs=firefox,kernel*\n')

    def test_missing_dnf_conf(self):
        subprocess.run(['trash-put', str(self.root / 'etc/dnf/dnf.conf')], check=True)
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
        # The short offline command blocks sleep, but must not claim DNF setup.
        readme = SCRIPT.with_name('README.md').read_text()
        block = readme.split('### Without network: type these as root\n\n```sh\n', 1)[1]
        block = block.split('```', 1)[0].replace('/etc/', f'{self.root}/etc/')
        self.env['REQUIRE_ROOT_ARG'] = '0'  # Typed target commands have no test-root override.
        for _ in range(2):  # twice: typing it again must not duplicate anything
            subprocess.run(['bash', '-e', '-c', block], env=self.env, check=True,
                           capture_output=True)
        status = self.status(self.run_script().stdout)
        self.assertEqual(status.count('OK'), 5)
        self.assertEqual(status.count('WOULD-CHANGE'), 2)
        self.assertEqual((self.root / 'etc/dnf/dnf.conf').read_text(), '[main]\ngpgcheck=True\n')

    def test_global_excludes_with_empty_indented_and_repository_options(self):
        conf = self.root / 'etc/dnf/dnf.conf'
        for value in ('', '   excludepkgs = \n', 'excludepkgs=firefox kernel*\n',
                      'excludepkgs=firefox,\n    kernel*\n'):
            with self.subTest(value=value):
                repo = '[extras]\nexcludepkgs=kernel*,m1n1*,uboot-images*,update-m1n1\n'
                conf.write_text('[main]\n' + value + repo)
                self.run_script('--apply')
                parsed = configparser.ConfigParser(interpolation=None)
                parsed.read(conf)
                tokens = set(parsed['main']['excludepkgs'].replace(',', ' ').split())
                self.assertTrue({'kernel*', 'm1n1*', 'uboot-images*', 'update-m1n1'} <= tokens)
                if 'firefox' in value:
                    self.assertIn('firefox', tokens)
                self.assertTrue(conf.read_text().endswith(repo))
                self.assertEqual(set(self.status(self.run_script().stdout)), {'OK'})

    def test_refuses_ambiguous_or_disabled_excludes_before_writes(self):
        conf = self.root / 'etc/dnf/dnf.conf'
        for body in ('excludepkgs=a\nexcludepkgs=b\n', 'disable_excludes=main\n',
                     'disable_excludes=*\n', 'exclude=firefox\n'):
            with self.subTest(body=body):
                original = '[main]\n' + body
                conf.write_text(original)
                result = self.run_script('--apply', check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('REFUSED', result.stderr)
                self.assertEqual(conf.read_text(), original)
                self.assertFalse((self.root / 'etc/systemd').exists())
                self.assertFalse((self.root / 'units').exists())

    def test_repeated_changes_keep_every_backup(self):
        date = self.tmp / 'bin/date'
        date.write_text('#!/bin/sh\nprintf fixed-timestamp\n')
        date.chmod(0o755)
        conf = self.root / 'etc/dnf/dnf.conf'
        originals = ['[main]\nexcludepkgs=firefox\n', '[main]\nexcludepkgs=chromium\n']
        for original in originals:
            conf.write_text(original)
            self.run_script('--apply')
        backups = list(conf.parent.glob('dnf.conf.azahi-bak-*'))
        self.assertEqual(len(backups), 2)
        self.assertEqual({p.read_text() for p in backups}, set(originals))

    def test_dnf5_inherited_disable_excludes_refuses_before_changes(self):
        drop = self.root / 'usr/share/dnf5/libdnf.conf.d/50-vendor.conf'
        drop.parent.mkdir(parents=True)
        conf = self.root / 'etc/dnf/dnf.conf'
        original = conf.read_text()
        for value in ('main', '"main"', "'*'", '$exclude_policy'):
            with self.subTest(value=value):
                drop.write_text('[main]\ndisable_excludes=' + value + '\n')
                result = self.run_script('--apply', check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('REFUSED', result.stderr)
                self.assertEqual(conf.read_text(), original)
                self.assertFalse((self.root / 'etc/systemd').exists())
                self.assertFalse((self.root / 'units').exists())

    def test_dnf5_dropin_order_masks_and_main_override(self):
        vendor = self.root / 'usr/share/dnf5/libdnf.conf.d/50-policy.conf'
        user = self.root / 'etc/dnf/libdnf5.conf.d/50-policy.conf'
        vendor.parent.mkdir(parents=True)
        user.parent.mkdir(parents=True)
        vendor.write_text('[main]\ndisable_excludes=*\n')
        user.write_text('[main]\ndisable_excludes=extras\n')
        self.run_script()  # Same filename: user file masks the vendor file.
        later = vendor.with_name('90-policy.conf')
        later.write_text('[main]\ndisable_excludes=main\n')
        self.assertNotEqual(self.run_script('--apply', check=False).returncode, 0)
        self.assertFalse((self.root / 'etc/systemd').exists())
        conf = self.root / 'etc/dnf/dnf.conf'
        conf.write_text('[main]\ndisable_excludes=\n')
        self.run_script('--apply')  # Main file loads after every drop-in.
        self.assertIn('disable_excludes=\n', conf.read_text())
        self.assertEqual(set(self.status(self.run_script().stdout)), {'OK'})

    def test_quoted_values_keep_quotes_and_detect_disabled_policy(self):
        conf = self.root / 'etc/dnf/dnf.conf'
        for value in ('"main"', "'*'", '$exclude_policy'):
            conf.write_text('[main]\ndisable_excludes=' + value + '\n')
            self.assertNotEqual(self.run_script('--apply', check=False).returncode, 0)
            self.assertFalse((self.root / 'etc/systemd').exists())
        for quote in ('"', "'"):
            for existing in ('firefox', 'firefox,\n    kernel*'):
                conf.write_text('[main]\nexcludepkgs=' + quote + existing + quote + '\n')
                self.run_script('--apply')
                value = configparser.ConfigParser(interpolation=None)
                value.read(conf)
                text = value['main']['excludepkgs']
                self.assertEqual(text[0], quote)
                self.assertEqual(text[-1], quote)
                tokens = set(text[1:-1].replace(',', ' ').split())
                self.assertTrue({'firefox', 'kernel*', 'm1n1*', 'uboot-images*', 'update-m1n1'} <= tokens)
                self.assertEqual(set(self.status(self.run_script().stdout)), {'OK'})

    def test_unknown_argument(self):
        self.assertEqual(self.run_script('--force', check=False).returncode, 2)


if __name__ == '__main__':
    unittest.main()
