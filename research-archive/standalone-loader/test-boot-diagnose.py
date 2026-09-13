#!/usr/bin/env python3
"""Exercise read-only Recovery collector using shell mocks, never hardware."""
import os
from pathlib import Path
import plistlib
import subprocess
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BACKUP = ROOT / 'logs/standalone-preinstall-backup-20260911.T0uKOR/backup.tar.gz'
MOCKS = r'''
sysctl() { echo Mac17,9; }
diskutil() {
    echo "diskutil $*" >> "$TEST_DIR/events"
    case "$1 $2" in
        'info -plist')
            case "$3" in
                PRIVATE-UUID-REMOVED) /bin/cat "$TEST_DIR/linux.plist";;
                disk3s4) /bin/cat "$TEST_DIR/preboot.plist";;
                *) return 91;;
            esac;;
        'apfs list') /bin/cat "$TEST_DIR/linux-container.plist";;
        *) return 92;;
    esac
}
bputil() {
    echo "bputil $*" >> "$TEST_DIR/events"
    [[ $* == '-d -v PRIVATE-UUID-REMOVED' ]] || return 93
    /bin/cat "$TEST_DIR/boot-policy.txt"
}
ioreg() { echo 'MOCK chosen associated-volume-group'; }
nvram() {
    echo "nvram $*" >> "$TEST_DIR/events"
    if [[ $# == 1 && $1 == -p ]]; then
        echo 'TEST-GUID:iboot-failure-reason MOCK_REASON'
        echo 'TEST-GUID:unrelated-private-value MUST_NOT_BE_COLLECTED'
        return 0
    fi
    [[ $# == 1 && $1 != *=* && $1 != -* ]] || return 94
    if [[ $TEST_CASE == absent ]]; then echo 'variable not found'; return 1; fi
    echo "$1 MOCK_READ_ONLY"
}
sw_vers() { echo 'ProductVersion: MOCK'; }
tail() { echo 'Recovery log not available'; return 1; }
curl() {
    local previous='' archive='' arg
    for arg in "$@"; do
        [[ $previous != --upload-file ]] || archive=$arg
        previous=$arg
    done
    [[ -n $archive && -f $archive ]] || return 95
    /bin/cp "$archive" "$TEST_DIR/result.tar.gz"
    echo "CKSUM $(/usr/bin/cksum < "$archive")"
    echo 'SHA256 MOCK_RECEIPT'
}
'''


class DiagnoseTests(unittest.TestCase):
    def test_shell_paths(self):
        with tarfile.open(BACKUP) as archive:
            fixture = {n: archive.extractfile(n).read() for n in
                       ('linux.plist', 'preboot.plist', 'linux-container.plist', 'boot-policy.txt')}
        for case in ['unmounted', 'absent', 'wrong_uuid']:
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix='azahi-bootdiag-test-') as temp:
                directory = Path(temp)
                for name, blob in fixture.items():
                    if name == 'preboot.plist':
                        value = plistlib.loads(blob)
                        value.pop('MountPoint', None)
                        if case == 'wrong_uuid':
                            value['VolumeUUID'] = 'wrong'
                        blob = plistlib.dumps(value)
                    (directory / name).write_bytes(blob)
                (directory / 'mocks.sh').write_text(MOCKS)
                script = (HERE / 'recovery-boot-diagnose.sh').read_text().replace(
                    '/tmp/azahi-boot-diagnose.XXXXXX', temp + '/work.XXXXXX')
                (directory / 'helper.sh').write_text(script)
                result = subprocess.run(['/bin/bash', str(directory / 'helper.sh')],
                                        env=dict(os.environ, BASH_ENV=str(directory / 'mocks.sh'),
                                                 TEST_DIR=temp, TEST_CASE=case),
                                        text=True, capture_output=True, timeout=15)
                events = (directory / 'events').read_text()
                self.assertNotIn('diskutil mount', events)
                if case == 'wrong_uuid':
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse((directory / 'result.tar.gz').exists())
                else:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('BOOT_DIAGNOSTICS_SENT', result.stdout)
                    with tarfile.open(directory / 'result.tar.gz') as archive:
                        self.assertIn(b'PREBOOT_UNMOUNTED disk3s4', archive.extractfile('selected-object.txt').read())
                        self.assertEqual(archive.extractfile('nvram-iboot-failure-reason.txt.status').read(),
                                         b'1\n' if case == 'absent' else b'0\n')
                        self.assertEqual(archive.extractfile('recovery-log-tail.txt.status').read(), b'1\n')
                        self.assertEqual(archive.extractfile('nvram-boot-fields-qualified.txt').read(),
                                         b'TEST-GUID:iboot-failure-reason MOCK_REASON\n')

    def test_syntax(self):
        subprocess.run(['/bin/bash', '-n', str(HERE / 'recovery-boot-diagnose.sh')], check=True)


if __name__ == '__main__':
    unittest.main()
