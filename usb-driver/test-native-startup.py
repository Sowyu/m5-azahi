#!/usr/bin/env python3
"""Run the real startup shell in a disposable, command-mocked filesystem.

All absolute task paths are redirected before execution; hardware commands
are shell functions. No native device, module or system service is accessed.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).with_name('start-native-usb.sh').read_text()
MODULES = ('phy_apple_t6050_usb2', 'azahi_usb_overlay', 'dwc3_apple_t6050')


class Startup(unittest.TestCase):
    def case(self, modules=(), hpm=None, hub=False, refusal=False, fault=False,
             hash_bad=False, wrong_root=False, fail_module='', no_hub=False):
        with tempfile.TemporaryDirectory(prefix='azahi-startup-test-') as tmp:
            root = Path(tmp)
            for path in ('etc', 'opt/azahi-usb', 'sys/module', 'sys/bus/usb/devices',
                         'proc/device-tree'):
                (root / path).mkdir(parents=True, exist_ok=True)
            (root / 'etc/azahi-usb-root').write_text('synthetic-root\n')
            for name in modules:
                (root / 'sys/module' / name).mkdir()
            params = root / 'sys/module/azahi_hpm_once/parameters'
            if hpm is not None:
                params.mkdir(parents=True)
                for name, value in zip(('result', 'ready', 'poisoned'), hpm):
                    (params / name).write_text(str(value))
            if hub:
                (root / 'sys/bus/usb/devices/usb1').touch()
            # Longest explicit paths first. Production source has no test hooks.
            transformed = SOURCE
            for prefix in ('/proc/device-tree', '/sys/bus/usb/devices', '/sys/module',
                           '/etc/azahi-usb-root', '/opt/azahi-usb'):
                transformed = transformed.replace(prefix, tmp + prefix)
            commands = r'''
id() { echo 0; }
uname() { echo '7.0.13-400.asahi.fc44.aarch64+16k'; }
findmnt() { echo "$ROOT_RESULT"; }
grep() { return 0; }
sha256sum() { echo checksum >> "$T/calls"; return "$HASH_BAD"; }
readlink() { [[ -e "$2" ]] && echo /fake/382280000.usb/xhci/usb1; }
sleep() { :; }
modprobe() { echo "modprobe $*" >> "$T/calls"; [[ "$1" != "$FAIL_MODULE" ]]; }
rmmod() { echo "rmmod $*" >> "$T/calls"; rm -r "$T/sys/module/azahi_hpm_once"; }
insmod() {
    echo "insmod $*" >> "$T/calls"
    if [[ $1 = ./azahi_hpm_once.ko ]]; then
        p="$T/sys/module/azahi_hpm_once/parameters"
        mkdir -p "$p"
        printf '%s' "$NEW_RESULT" > "$p/result"
        printf '%s' "$NEW_READY" > "$p/ready"
        printf '%s' "$NEW_POISON" > "$p/poisoned"
    elif [[ $1 = ./dwc3-apple-t6050.ko && $NO_HUB = 0 ]]; then
        touch "$T/sys/bus/usb/devices/usb1"
    fi
}
'''
            env = dict(os.environ, T=tmp, HASH_BAD=str(int(hash_bad)),
                       ROOT_RESULT='wrong' if wrong_root else 'synthetic-root',
                       FAIL_MODULE=fail_module, NO_HUB=str(int(no_hub)),
                       NEW_RESULT='-5' if fault else '-11' if refusal else '0',
                       NEW_READY='N' if refusal or fault else 'Y',
                       NEW_POISON='Y' if fault else 'N')
            result = subprocess.run(['bash', '-c', commands + transformed], env=env,
                                    capture_output=True, text=True, timeout=5)
            calls = (root / 'calls').read_text().splitlines() if (root / 'calls').exists() else []
            return result.returncode, calls, result.stdout + result.stderr

    def test_preserve_live(self):
        code, calls, out = self.case(modules=MODULES, hub=True)
        self.assertEqual(code, 0)
        self.assertEqual(calls, ['checksum'])
        self.assertIn('USB_ALREADY_READY', out)

    def test_partial_or_missing_hub_never_reload(self):
        for modules in (MODULES[:1], MODULES[:2], MODULES):
            code, calls, _ = self.case(modules=modules)
            self.assertNotEqual(code, 0)
            self.assertEqual(calls, ['checksum'])

    def test_fresh_success_order(self):
        code, calls, out = self.case()
        self.assertEqual(code, 0, out)
        self.assertEqual(calls[1], 'insmod ./azahi_hpm_once.ko mode=awake')
        self.assertEqual(calls[-3:], ['insmod ./phy-apple-t6050-usb2.ko',
            'insmod ./azahi-usb-overlay.ko variant=minimal', 'insmod ./dwc3-apple-t6050.ko'])
        self.assertIn('USB_HOST_READY', out)

    def test_clean_refusal_rechecked_only(self):
        code, calls, out = self.case(hpm=(-11, 'N', 'N'))
        self.assertEqual(code, 0, out)
        self.assertEqual(calls[1:3], ['rmmod azahi_hpm_once',
                                    'insmod ./azahi_hpm_once.ko mode=awake'])

    def test_poison_or_not_ready_no_io(self):
        for state in ((-11, 'N', 'Y'), (-5, 'N', 'Y'), (0, 'N', 'N')):
            code, calls, _ = self.case(hpm=state)
            self.assertNotEqual(code, 0)
            self.assertEqual(calls, ['checksum'])

    def test_fresh_failure_no_usb_or_retry(self):
        for kwargs in ({'refusal': True}, {'fault': True}):
            code, calls, _ = self.case(**kwargs)
            self.assertNotEqual(code, 0)
            self.assertEqual(calls, ['checksum', 'insmod ./azahi_hpm_once.ko mode=awake'])

    def test_identity_hash_guards(self):
        for kwargs in ({'wrong_root': True}, {'hash_bad': True}):
            code, calls, _ = self.case(**kwargs)
            self.assertNotEqual(code, 0)
            self.assertTrue(all(c == 'checksum' for c in calls))

    def test_driver_failure_no_teardown(self):
        code, calls, _ = self.case(fail_module='dwc3')
        self.assertNotEqual(code, 0)
        self.assertEqual(calls[-1], 'modprobe dwc3')
        self.assertFalse(any('rmmod' in c for c in calls))
        code, calls, _ = self.case(no_hub=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(sum('insmod' in c for c in calls), 4)
        self.assertFalse(any('rmmod' in c for c in calls))


if __name__ == '__main__': unittest.main()
