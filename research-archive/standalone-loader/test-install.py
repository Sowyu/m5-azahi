#!/usr/bin/env python3
"""Offline enrollment/readback tests. Synthetic IMG4 signatures are not valid."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import runpy
import subprocess
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
S = runpy.run_path(str(HERE / 'install-server.py'))
V = S['V']
BACKUP = ROOT / 'logs/standalone-preinstall-backup-20260911.T0uKOR/backup.tar.gz'


def encode(tag, value):
    length = len(value)
    if length < 128:
        size = bytes([length])
    else:
        count = (length.bit_length() + 7) // 8
        size = bytes([128 + count]) + length.to_bytes(count, 'big')
    return tag + size + value


def tag_bytes(encoded):
    end = 1
    if encoded[0] & 31 == 31:
        while encoded[end] & 128:
            end += 1
        end += 1
    return encoded[:end]


def wrap_candidate(original, raw):
    outer = V['items'](V['only'](original, 0x30))
    im4p = V['items'](outer[1][1])

    def resize(data):
        result = []
        for tag, value, encoded in V['items'](data):
            if tag & 0x20:
                value = resize(value)
            elif tag == 2 and int.from_bytes(value, 'big') == 1114112:
                value = len(raw).to_bytes(4, 'big')
            result.append(encode(tag_bytes(encoded), value))
        return b''.join(result)

    payload = b''.join(x[2] for x in im4p[:3]) + encode(b'\x04', raw) + encode(b'\xa0', resize(im4p[4][1]))
    return encode(b'\x30', outer[0][2] + encode(b'\x30', payload) + b''.join(x[2] for x in outer[2:]))


class InstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        V['validate'](BACKUP)
        with tarfile.open(BACKUP) as archive:
            cls.backup = {m.name: archive.extractfile(m).read() for m in archive}
        cls.baseline = S['policy_fields'](cls.backup['boot-policy.txt'])
        cls.script = (HERE / 'recovery-install.sh').read_text()
        cls.candidate_path = ROOT / 'standalone-ssdroot-v2-20260911.bin'
        cls.fixture = {n: cls.backup[n] for n in ('linux.plist', 'preboot.plist', 'linux-container.plist')}
        policy = cls.backup['boot-policy.txt']
        source = cls.backup['manifest.tsv'].decode().splitlines()[1].split('\t')[1]
        wrapped = cls.backup['custom-02.bin']
        cls.fixture.update({'policy-before.txt': policy, 'policy-rechecked.txt': policy,
                            'policy-after.txt': policy, 'installed.bin': wrapped,
                            'installed-cksum.txt': (V['fingerprint'](wrapped) + '\n').encode(),
                            'installed-path.txt': (source + '\n').encode(), 'mode.txt': b'rollback\n'})

    def check(self, data=None, mode='rollback', extra=None):
        data = self.fixture if data is None else data
        with tempfile.TemporaryDirectory(prefix='azahi-readback-test-') as temp:
            path = Path(temp) / 'after.tar.gz'
            with tarfile.open(path, 'w:gz', compresslevel=1) as archive:
                for name, blob in data.items():
                    m = tarfile.TarInfo(name)
                    m.size = len(blob)
                    archive.addfile(m, io.BytesIO(blob))
                if extra:
                    archive.addfile(extra)
            return S['validate_after'](path, mode, self.baseline)

    def test_real_v5_rollback_readback(self):
        result = self.check()
        self.assertEqual(result['raw_sha256'], V['V5'])
        self.assertFalse(result['signature_verified'])

    def test_rewrapped_v5_readback(self):
        # Signature bytes may change on re-enrollment. Raw payload must not.
        data = copy.copy(self.fixture)
        wrapped = bytearray(data['installed.bin'])
        wrapped[-1] ^= 1
        data['installed.bin'] = bytes(wrapped)
        data['installed-cksum.txt'] = (V['fingerprint'](wrapped) + '\n').encode()
        result = self.check(data)
        self.assertEqual(result['raw_sha256'], V['V5'])
        self.assertFalse(result['signature_verified'])

    def test_full_candidate_synthetic_wrapper(self):
        raw = self.candidate_path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), S['CANDIDATE'])
        data = copy.copy(self.fixture)
        data['installed.bin'] = wrap_candidate(data['installed.bin'], raw)
        data['installed-cksum.txt'] = (V['fingerprint'](data['installed.bin']) + '\n').encode()
        old = self.baseline[S['COIH']].encode()
        data['policy-after.txt'] = data['policy-after.txt'].replace(old, b'A' * 96)
        data['installed-path.txt'] = data['installed-path.txt'].replace(old, b'A' * 96)
        data['mode.txt'] = b'install\n'
        result = self.check(data, 'install')
        self.assertEqual(result['raw_sha256'], S['CANDIDATE'])
        self.assertEqual(result['raw_properties']['kcwz'], len(raw))

    def test_policy_changes_rejected(self):
        for before, after in [(b'(sip0): absent', b'(sip0): 1'),
                              (b': Paired', b': Unpaired'),
                              (b'(CHIP): 0x6050', b'(CHIP): 0x6040')]:
            with self.subTest(change=after), self.assertRaises(ValueError):
                data = copy.copy(self.fixture)
                data['policy-after.txt'] = data['policy-after.txt'].replace(before, after)
                self.check(data)

    def test_wrong_volume_and_rw_preboot(self):
        for field, value in [('VolumeUUID', V['SYSTEM']), ('WritableVolume', True)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                data = copy.copy(self.fixture)
                info = plistlib.loads(data['preboot.plist'])
                info[field] = value
                data['preboot.plist'] = plistlib.dumps(info)
                self.check(data)

    def test_wrong_payload_and_checksum(self):
        for recalc in [False, True]:
            with self.subTest(recalc=recalc), self.assertRaises(ValueError):
                data = copy.copy(self.fixture)
                data['installed.bin'] = self.backup['custom-01.bin']
                if recalc:
                    data['installed-cksum.txt'] = (V['fingerprint'](data['installed.bin']) + '\n').encode()
                self.check(data)

    def test_wrong_path_and_mode(self):
        for name, value in [('installed-path.txt', b'/Volumes/macOS/custom\n'), ('mode.txt', b'install\n')]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                data = copy.copy(self.fixture)
                data[name] = value
                self.check(data)

    def test_no_policy_transition_rejected(self):
        data = copy.copy(self.fixture)
        data['mode.txt'] = b'install\n'
        with self.assertRaisesRegex(ValueError, 'policy transition'):
            self.check(data, 'install')

    def test_duplicate_symlink_path_rejected(self):
        for name in ['../escape', 'installed.bin', 'unexpected']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.check(extra=tarfile.TarInfo(name))

    def test_shell_syntax(self):
        subprocess.run(['/bin/bash', '-n', str(HERE / 'recovery-install.sh')], check=True)

    def test_recovery_shell_mock_paths(self):
        # Actual helper control flow, but EVERY hardware/network command is a
        # shell function. Only its scratch/bootdir paths are relocated. No real
        # diskutil, bputil, kmutil, sysctl or curl can run in this test.
        mocks = r'''
sysctl() { echo Mac17,9; }
diskutil() {
    echo "diskutil $*" >> "$TEST_DIR/events"
    case "$1 $2" in
        'info -plist')
            case "$3" in
                PRIVATE-UUID-REMOVED) /bin/cat "$TEST_DIR/linux.plist";;
                disk3s4) /bin/cat "$TEST_DIR/preboot-${MOUNT_RW:-false}.plist";;
                *) return 91;;
            esac;;
        'apfs list') /bin/cat "$TEST_DIR/linux-container.plist";;
        'unmount disk3s4') return 0;;
        'mount disk3s4') MOUNT_RW=true;;
        'mount readOnly') [[ $3 == disk3s4 ]] || return 92; MOUNT_RW=false;;
        *) return 93;;
    esac
}
bputil() {
    [[ $* == '-d -v PRIVATE-UUID-REMOVED' ]] || return 94
    /bin/cat "$TEST_DIR/policy-${CONFIGURED:-before}.txt"
}
curl() {
    echo "curl" >> "$TEST_DIR/events"
    local previous='' output='' artifact='' archive='' arg
    for arg in "$@"; do
        [[ $previous != -o ]] || output=$arg
        [[ $previous != --upload-file ]] || archive=$arg
        case "$arg" in
            */standalone.bin) artifact=standalone.bin;;
            */v5.bin) artifact=v5.bin;;
        esac
        previous=$arg
    done
    if [[ -n $archive ]]; then
        echo upload >> "$TEST_DIR/events"
        [[ $TEST_CASE != upload_fail ]] || return 22
        echo "CKSUM $(/usr/bin/cksum < "$archive")"
        echo 'SHA256 MOCK_ONLY_NOT_A_REAL_SERVER_VALIDATION'
        echo "VALIDATED $TEST_MODE"
    else
        /bin/cp "$TEST_DIR/$artifact" "$output"
        if [[ $TEST_CASE == corrupt && $artifact == standalone.bin ]]; then
            echo CORRUPT >> "$output"
        fi
    fi
}
kmutil() {
    echo "kmutil $*" >> "$TEST_DIR/events"
    [[ $TEST_CASE != kmutil_fail ]] || return 1
    [[ $1 == configure-boot && $2 == -c && $4 == --raw && $5 == --entry-point && $6 == 2048 && $7 == --lowest-virtual-address && $8 == 0 && $9 == -v && ${10} == /Volumes/Linux ]] || return 95
    CONFIGURED=after
    # Mock disk writer: object need only exercise the shell's size/CRC checks.
    # Real candidate raw SHA and DER validation are tested independently above.
    /bin/cp "$TEST_DIR/current-v5.bin" "$TEST_DIR/objects/kernelcache.custom.$TEST_NEW_COIH"
}
'''
        for case in ['pass', 'rollback_rewrap', 'wrong_uuid', 'wrong_policy', 'cancel', 'corrupt', 'kmutil_fail', 'upload_fail']:
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix='azahi-recovery-mock-') as temp:
                directory = Path(temp)
                (directory / 'objects').mkdir()
                for name in ('linux.plist', 'linux-container.plist'):
                    (directory / name).write_bytes(self.backup[name])
                if case == 'wrong_uuid':
                    info = plistlib.loads(self.backup['linux.plist'])
                    info['VolumeUUID'] = V['PREBOOT']
                    (directory / 'linux.plist').write_bytes(plistlib.dumps(info))
                for writable in [False, True]:
                    info = plistlib.loads(self.backup['preboot.plist'])
                    info['WritableVolume'] = writable
                    (directory / f'preboot-{str(writable).lower()}.plist').write_bytes(plistlib.dumps(info))
                policy = self.backup['boot-policy.txt']
                if case == 'wrong_policy':
                    policy = policy.replace(b': Paired', b': Unpaired')
                (directory / 'policy-before.txt').write_bytes(policy)
                mode = 'rollback' if case == 'rollback_rewrap' else 'install'
                new_coih = self.baseline[S['COIH']] if mode == 'rollback' else 'A' * 96
                (directory / 'policy-after.txt').write_bytes(policy.replace(self.baseline[S['COIH']].encode(), new_coih.encode()))
                for line in self.backup['manifest.tsv'].decode().splitlines():
                    member, source = line.split('\t')
                    (directory / 'objects' / Path(source).name).write_bytes(self.backup[member])
                wrapper = bytearray(self.backup['custom-02.bin'])
                if case == 'rollback_rewrap':
                    wrapper[-1] ^= 1
                (directory / 'current-v5.bin').write_bytes(wrapper)
                (directory / 'standalone.bin').symlink_to(self.candidate_path)
                (directory / 'v5.bin').symlink_to(ROOT / 'probe/m1n1-smp-diag-v5-20260906.bin')
                (directory / 'mock-functions.sh').write_text(mocks)
                script = self.script
                old = 'bootdir="$mountpoint/$vg/boot/$nsih/System/Library/Caches/com.apple.kernelcaches"'
                self.assertEqual(script.count(old), 1)
                script = script.replace(old, 'bootdir="$TEST_DIR/objects"')
                script = script.replace('/tmp/azahi-enroll.XXXXXX', temp + '/work.XXXXXX')
                (directory / 'helper.sh').write_text(script)
                env = dict(os.environ, BASH_ENV=str(directory / 'mock-functions.sh'),
                           TEST_DIR=temp, TEST_CASE=case, TEST_NEW_COIH=new_coih, TEST_MODE=mode)
                answer = 'RESTORE\n' if mode == 'rollback' else 'INSTALL\n'
                result = subprocess.run(['/bin/bash', str(directory / 'helper.sh'), mode],
                                        input='CANCEL\n' if case == 'cancel' else answer,
                                        text=True, capture_output=True, env=env, timeout=60)
                events = (directory / 'events').read_text()
                if case in ('pass', 'rollback_rewrap'):
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(events.count('kmutil configure-boot'), 1)
                    self.assertIn('INSTALLED AND HOST-VERIFIED', result.stdout)
                    self.assertIn('diskutil mount readOnly disk3s4', events)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    if case in ['wrong_uuid', 'wrong_policy', 'cancel', 'corrupt']:
                        self.assertNotIn('kmutil', events)
                        self.assertNotIn('diskutil unmount', events)
                    if case == 'kmutil_fail':
                        self.assertNotIn('upload', events)
                    self.assertNotIn('INSTALLED AND HOST-VERIFIED', result.stdout)


if __name__ == '__main__':
    unittest.main()
