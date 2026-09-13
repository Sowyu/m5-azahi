#!/usr/bin/env python3
"""Host-only candidate inspection and mocked first-boot configuration tests."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CANDIDATE = ROOT / os.environ.get('SSDROOT_TEST_IMAGE', 'native-ssdroot-v1-20260906.bin')
FSUUID = 'PRIVATE-UUID-REMOVED'
spec = importlib.util.spec_from_file_location('builder', HERE / 'build-native-ssdroot.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ConfigureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='azahi-ssd-config-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.sysroot = self.base / 'sysroot'
        self.overlay = self.base / 'overlay'
        self.commands = self.base / 'bin'
        for directory in (self.sysroot / 'etc', self.overlay / 'etc', self.commands):
            directory.mkdir(parents=True)
        (self.sysroot / 'etc/fstab').write_text('original fstab\n')
        (self.overlay / 'etc/fstab').write_text('new fstab\n')
        (self.base / 'files').write_text('etc/fstab\n')
        (self.base / 'initrd-release').touch()
        (self.base / 'armed').write_text('Y\n')
        self.command('findmnt', 'case "$*" in *UUID*) echo "$TEST_UUID";; *FSROOT*) echo /root;; *OPTIONS*) echo "$TEST_OPTIONS";; esac')
        self.command('blkid', 'echo "$TEST_UUID"')
        self.command('busybox', 'test "$1" = sync')
        script = (HERE / 'ssdroot-configure.sh').read_text()
        for old, new in (
            ('export PATH=/usr/bin:/usr/sbin:/bin:/sbin', f'export PATH="{self.commands}:/usr/bin:/bin:/usr/sbin:/sbin"'),
            ('/usr/local/libexec/busybox.static', str(self.commands / 'busybox')),
            ('/etc/initrd-release', str(self.base / 'initrd-release')),
            ('/sys/module/nvme_apple/parameters/root_write_armed', str(self.base / 'armed')),
            ('/ssdroot-overlay-files', str(self.base / 'files')),
            ('/ramroot/sysroot-overlay', str(self.overlay)),
            ('/sysroot', str(self.sysroot)),
        ):
            script = script.replace(old, new)
        self.script = self.base / 'configure.sh'
        self.script.write_text(script)

    def command(self, name, body):
        path = self.commands / name
        path.write_text('#!/bin/bash\n' + body + '\n')
        path.chmod(0o755)

    def run_config(self, uuid=FSUUID, options='rw,subvol=/root,nodiscard'):
        return subprocess.run(['bash', str(self.script)], capture_output=True, text=True,
                              env={**os.environ, 'TEST_UUID': uuid, 'TEST_OPTIONS': options})

    def test_first_boot_backs_up_and_marks(self):
        result = self.run_config()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.sysroot / 'etc/fstab').read_text(), 'new fstab\n')
        self.assertEqual((self.sysroot / 'var/lib/azahi-ssdboot/original/etc/fstab').read_text(), 'original fstab\n')
        self.assertEqual((self.sysroot / 'var/lib/azahi-ssdboot/initialized-v1').read_text().strip(), FSUUID)

    def test_second_boot_preserves_user_edit(self):
        self.assertEqual(self.run_config().returncode, 0)
        (self.sysroot / 'etc/fstab').write_text('user edit\n')
        result = self.run_config()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.sysroot / 'etc/fstab').read_text(), 'user edit\n')

    def test_wrong_uuid_refuses_writes(self):
        self.assertNotEqual(self.run_config(uuid='wrong').returncode, 0)
        self.assertEqual((self.sysroot / 'etc/fstab').read_text(), 'original fstab\n')

    def test_readonly_refuses_configuration(self):
        self.assertNotEqual(self.run_config(options='ro').returncode, 0)
        self.assertFalse((self.sysroot / 'var').exists())

    def test_disarmed_refuses_configuration(self):
        (self.base / 'armed').write_text('N\n')
        self.assertNotEqual(self.run_config().returncode, 0)
        self.assertFalse((self.sysroot / 'var').exists())

    def test_symlink_target_refused(self):
        outside = self.base / 'outside'
        outside.write_text('do not touch')
        (self.sysroot / 'etc/fstab').unlink()
        (self.sysroot / 'etc/fstab').symlink_to(outside)
        self.assertNotEqual(self.run_config().returncode, 0)
        self.assertEqual(outside.read_text(), 'do not touch')

    def test_traversal_refused(self):
        (self.base / 'files').write_text('../outside\n')
        self.assertNotEqual(self.run_config().returncode, 0)


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = CANDIDATE
        cls.receipt = json.loads(cls.path.with_suffix('.json').read_text())
        with cls.path.open('rb') as image:
            head = image.read(64 << 20)
            args = head.index(b'chosen.bootargs=')
            dt = head.index(b'\n', args) + 1
            kernel = dt + struct.unpack_from('>I', head, dt + 4)[0]
            marker = head.index(b'm1n1_initramfs', kernel) + len(b'm1n1_initramfs')
            image.seek(marker + 4)
            initrd = image.read()
        cls.assets = {name: (mode, data) for name, mode, data in builder.entries(builder.unpack(initrd))}

    def test_candidate_pin(self):
        self.assertEqual(builder.digest(self.path), self.receipt['image_sha256'])

    def test_actual_assets(self):
        for name, expected in self.receipt['assets'].items():
            self.assertEqual(hashlib.sha256(self.assets[name][1]).hexdigest(), expected, name)
        for name, target in self.receipt['links'].items():
            mode, data = self.assets[name]
            self.assertTrue(stat.S_ISLNK(mode), name)
            self.assertEqual(data.decode(), target)

    def test_no_ram_image_or_ram_service(self):
        self.assertFalse(any(name.startswith('ramroot/root.img') or name.endswith('/ramroot.service') for name in self.assets))
        self.assertLess(self.receipt['initrd_bytes'], 100 << 20)

    def test_configuration_list_complete(self):
        prefix = 'ramroot/sysroot-overlay/'
        actual = {name[len(prefix):] for name, (mode, data) in self.assets.items()
                  if name.startswith(prefix) and not stat.S_ISDIR(mode)}
        listed = set(self.assets['ssdroot-overlay-files'][1].decode().splitlines())
        self.assertEqual(actual, listed)

    def test_mount_order_and_no_replay(self):
        mount = self.assets['etc/systemd/system/sysroot.mount'][1].decode()
        self.assertIn('After=ssdroot-prepare.service', mount)
        self.assertIn('Options=rw,subvol=root,nodiscard', mount)
        prepare = self.assets['ssdroot-prepare.sh'][1].decode()
        self.assertIn('ro,rescue=nologreplay,subvol=root', prepare)
        self.assertLess(prepare.index('hash_region "/dev/$disk"'), prepare.index('echo Y > "$PARAM"'))

    def test_busybox_static_16k_compatible(self):
        mode, elf = self.assets['usr/local/libexec/busybox.static']
        self.assertTrue(mode & 0o111)
        phoff = struct.unpack_from('<Q', elf, 32)[0]
        entsize, count = struct.unpack_from('<HH', elf, 54)
        for i in range(count):
            ptype, flags, offset, vaddr, paddr, fsize, msize, align = struct.unpack_from('<IIQQQQQQ', elf, phoff + i * entsize)
            self.assertNotEqual(ptype, 3, 'Unexpected dynamic interpreter')
            if ptype == 1:
                self.assertGreaterEqual(align, 16384)
                self.assertEqual(offset % 16384, vaddr % 16384)

    def test_udev_cleanup_does_not_stop_root_dependency_chain(self):
        if not self.receipt.get('udev_lifetime_fix'):
            self.skipTest('Original candidate retains the udev lifetime bug')
        def values(name, key):
            data = self.assets[name][1].decode()
            return {value for line in data.splitlines()
                    if line.startswith(key + '=')
                    for value in line.split('=', 1)[1].split()}
        prepare = 'etc/systemd/system/ssdroot-prepare.service'
        mount = 'etc/systemd/system/sysroot.mount'
        configure = 'etc/systemd/system/ssdroot-configure.service'
        cleanup = 'usr/lib/systemd/system/initrd-udevadm-cleanup-db.service'
        self.assertIn('systemd-udevd.service', values(cleanup, 'Conflicts'))
        self.assertIn('systemd-udevd.service', values(prepare, 'Wants'))
        self.assertIn('systemd-udevd.service', values(prepare, 'After'))
        for key in ('Requires', 'Requisite', 'BindsTo', 'PartOf'):
            self.assertNotIn('systemd-udevd.service', values(prepare, key))
        self.assertIn('ssdroot-prepare.service', values(mount, 'Requires'))
        self.assertIn('sysroot.mount', values(configure, 'Requires'))
        # Only the dependency unit changes versus v2. Guard scripts, root
        # configuration, driver, diagnostic console and mount remain pinned.
        old = json.loads((ROOT / 'native-ssdroot-v2-20260906.json').read_text())
        changed = {name for name in self.receipt['assets']
                   if self.receipt['assets'][name] != old['assets'].get(name)}
        self.assertEqual(changed, {prepare})
        self.assertEqual(self.receipt['links'], old['links'])
        self.assertEqual(self.receipt['modules'], old['modules'])
        script = self.assets['ssdroot-prepare.sh'][1].decode()
        self.assertIn('set -Eeuo pipefail', script)
        self.assertLess(script.index('udevadm control --stop-exec-queue'),
                        script.index('modprobe nvme_apple'))

    def test_diagnostic_v2_keeps_guards(self):
        if self.receipt.get('diagnostic_console') != 2:
            self.skipTest('Original candidate has no diagnostic console')
        old = json.loads((ROOT / 'native-ssdroot-v1-20260906.json').read_text())
        self.assertEqual(self.receipt['modules'], old['modules'])
        for name in ('ssdroot-prepare.sh', 'ssdroot-configure.sh',
                     'etc/systemd/system/sysroot.mount'):
            self.assertEqual(self.receipt['assets'][name], old['assets'][name])
        for name in self.receipt['root_files']:
            key = 'ramroot/sysroot-overlay/' + name
            if key in old['assets']:
                self.assertEqual(self.receipt['assets'][key], old['assets'][key])
        unit = self.assets['etc/systemd/system/emergency.service'][1].decode()
        self.assertIn('ConditionPathExists=/etc/initrd-release', unit)
        self.assertIn('StandardInput=tty-force', unit)
        shell = self.assets['ssdroot-emergency.sh'][1].decode()
        self.assertIn('exec /bin/bash --noprofile --norc -i', shell)
        self.assertNotIn('echo Y', shell)
        self.assertNotIn('echo N', shell)


class DiagnosticTests(unittest.TestCase):
    def stage(self, result):
        with tempfile.TemporaryDirectory(prefix='azahi-stage-test-') as temporary:
            base = Path(temporary)
            (base / 'initrd-release').touch()
            fixture = base / 'prepare.sh'
            fixture.write_text(f'echo diagnostic-stage-output\nexit {result}\n')
            wrapper = (HERE / 'ssdroot-run-stage.sh').read_text()
            wrapper = wrapper.replace('/etc/initrd-release', str(base / 'initrd-release'))
            wrapper = wrapper.replace('/ssdroot-prepare.sh', str(fixture))
            wrapper = wrapper.replace('/run/ssdroot-', str(base / 'ssdroot-'))
            path = base / 'wrapper.sh'
            path.write_text(wrapper)
            completed = subprocess.run(['bash', str(path), 'prepare'], capture_output=True, text=True)
            self.assertEqual(completed.returncode, result)
            self.assertIn('diagnostic-stage-output', (base / 'ssdroot-prepare.log').read_text())
            return completed.stdout

    def test_stage_success(self):
        self.assertIn('prepare PASS', self.stage(0))

    def test_stage_failure_preserves_status(self):
        self.assertIn('FAILED: exit 37', self.stage(37))

    def test_diagnostic_syntax(self):
        for name in ('ssdroot-run-stage.sh', 'ssdroot-handoff-report.sh', 'ssdroot-emergency.sh'):
            self.assertEqual(subprocess.run(['bash', '-n', str(HERE / name)]).returncode, 0)


class PreflightTests(unittest.TestCase):
    def hash_check(self, content, expected, blocks=1):
        with tempfile.TemporaryDirectory(prefix='azahi-ssd-hash-test-') as temporary:
            path = Path(temporary) / 'region'
            path.write_bytes(content)
            script = '''
source "$1"
bb() {
    case "$1" in
        dd) shift; /bin/dd "$@";;
        sha256sum) /usr/bin/shasum -a 256;;
        *) return 1;;
    esac
}
fail_cleanup() { echo MOCK_DISARMED >&2; }
hash_region "$2" 0 "$3" "$4"
'''
            return subprocess.run(['bash', '-c', script, 'hash-test', str(HERE / 'ssdroot-prepare.sh'),
                                   str(path), str(blocks), expected], capture_output=True, text=True)

    def test_matching_region(self):
        data = bytes(4096)
        result = self.hash_check(data, hashlib.sha256(data).hexdigest())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_region_disarms(self):
        result = self.hash_check(bytes(4096), '0' * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('MOCK_DISARMED', result.stderr)

    def test_short_region_refused(self):
        result = self.hash_check(bytes(4095), hashlib.sha256(bytes(4096)).hexdigest())
        self.assertNotEqual(result.returncode, 0)

    def test_bash_syntax(self):
        for name in ('ssdroot-prepare.sh', 'ssdroot-configure.sh', 'native-ssd-profile.sh',
                     'native-ssd-kde-start.sh', 'native-ssd-input-check.sh'):
            result = subprocess.run(['bash', '-n', str(HERE / name)], capture_output=True)
            self.assertEqual(result.returncode, 0, name)

    def test_guards_not_dropped_from_boot_runner(self):
        path = CANDIDATE
        for mode in ([], ['--ssd-readonly'], ['--rootguard-test']):
            result = subprocess.run(['python3', str(HERE / 'boot-native.py'), str(path), '--offline', *mode],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('NATIVE_LAYOUT_PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
