#!/usr/bin/env python3
"""Pinned LAN enrollment helper and single readback receiver per operation.

Never executes uploaded code or extracts an archive. Requires the fresh,
validated V5 backup before serving installation. Target performs kmutil only
after local confirmation. No automatic reboot, retry or rollback.
"""
import argparse
import hashlib
import http.server
import json
from pathlib import Path, PurePosixPath
import plistlib
import re
import runpy
import secrets
import socketserver
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
V = runpy.run_path(str(HERE / 'validate-backup.py'))
require = V['require']
CANDIDATE = '866aea9d523152f0a0767cb7529be297f52ad4e64d94a70d0fe5bddf222a5a2a'
FRESH_BACKUP = '494b5e91993411b34e94b42cfc059c1694fc65ed2a494a7bf7172b3ad44e2214'
EXPECTED = set(('linux.plist preboot.plist linux-container.plist policy-before.txt '
                'policy-rechecked.txt policy-after.txt installed.bin installed-cksum.txt '
                'installed-path.txt mode.txt').split())
COIH = 'CustomKC or fuOS Image4 Hash            (coih)'
LPNH = 'Local Policy Nonce Hash                 (lpnh)'
ALIGNED_CANDIDATE = '397a0e4125087c63b83c09b35cd44fe6bc35508d7d54613bd9a2bf4d9aff46fc'
CONTROL_SHA = '8e615848c75b941c109a23ab040d639b4dcd57fc7eef7a9f68162c82410e2014'
CONTROL_COIH = 'F32F08BEB837A75ED540A0098F7D1A70F2BCC106364E1EE3E041F9C7C521A2BED425C146F14CB375425B6805FB429401'


def policy_fields(blob):
    text = blob.decode()
    require(text.startswith('Operating on Volume Group UUID ' + V['VG'] + '\n'), 'Wrong policy target')
    fields = {}
    for line in text.splitlines():
        if ':' not in line:
            continue
        key, value = [s.strip() for s in line.split(':', 1)]
        require(key not in fields or fields[key] == value, 'Conflicting repeated policy field')
        fields[key] = value
    require(re.fullmatch('[0-9A-F]{96}', fields.get(COIH, '')), 'Invalid policy coih')
    return fields


def check_policy(blob, baseline):
    fields = policy_fields(blob)
    require(fields.keys() == baseline.keys(), 'Policy fields changed')
    for key, value in baseline.items():
        if key not in (COIH, LPNH):
            require(fields[key] == value, 'Policy/security/firmware changed: ' + key)
    return fields


def validate_after(path, mode, baseline, candidate=CANDIDATE, candidate_size=92651350,
                   rollback=None, rollback_size=1114112):
    require(mode in ('install', 'rollback', 'snapshot'), 'Unknown operation')
    require(0 < path.stat().st_size <= 110 * 1024 * 1024, 'Oversized readback archive')
    data, total = {}, 0
    with tarfile.open(path, 'r:gz') as archive:
        for m in archive:
            require(m.name in EXPECTED and m.name not in data and m.isfile(), 'Unexpected archive member')
            limit = 96 * 1024 * 1024 if m.name == 'installed.bin' else 1024 * 1024
            require(0 <= m.size <= limit, 'Oversized member')
            total += m.size
            require(total <= 106 * 1024 * 1024, 'Oversized expanded archive')
            data[m.name] = archive.extractfile(m).read()
    require(set(data) == EXPECTED, 'Missing readback metadata')
    require(data['mode.txt'] == (mode + '\n').encode(), 'Mode mismatch')
    linux = plistlib.loads(data['linux.plist'])
    preboot = plistlib.loads(data['preboot.plist'])
    containers = plistlib.loads(data['linux-container.plist'])['Containers']
    require(linux['VolumeUUID'] == V['SYSTEM'] and linux['APFSVolumeGroupID'] == V['VG']
            and linux['MountPoint'] == '/Volumes/Linux' and linux['VolumeName'] == 'Linux', 'Linux identity mismatch')
    require(preboot['VolumeUUID'] == V['PREBOOT'] and preboot['WritableVolume'] is False
            and preboot['DeviceIdentifier'] == linux['BooterDeviceIdentifier']
            and preboot['APFSContainerReference'] == linux['APFSContainerReference'], 'Preboot identity/state mismatch')
    require(len(containers) == 1 and containers[0]['APFSContainerUUID'] == V['CONTAINER']
            and containers[0]['ContainerReference'] == linux['APFSContainerReference']
            and containers[0]['CapacityCeiling'] == 96000000000, 'Container mismatch')
    before = check_policy(data['policy-before.txt'], baseline)
    rechecked = check_policy(data['policy-rechecked.txt'], baseline)
    after = check_policy(data['policy-after.txt'], baseline)
    require(before == rechecked, 'Policy changed before install')
    if mode == 'install':
        require(before[COIH] == baseline[COIH] and after[COIH] != before[COIH], 'Unexpected install policy transition')
    if mode == 'snapshot':
        require(before == after and before[COIH] == baseline[COIH], 'Snapshot policy changed')
    source = data['installed-path.txt'].decode().removesuffix('\n')
    nsih = baseline['Next Stage Image4 Hash                  (nsih)']
    expected_path = (preboot['MountPoint'] + '/' + V['VG'] + '/boot/' + nsih +
                     '/System/Library/Caches/com.apple.kernelcaches/kernelcache.custom.' + after[COIH])
    require(source == expected_path and '..' not in PurePosixPath(source).parts, 'Installed source path mismatch')
    wrapped = data['installed.bin']
    require(data['installed-cksum.txt'] == (V['fingerprint'](wrapped) + '\n').encode(), 'Readback checksum mismatch')
    raw, props = V['raw_loader'](wrapped)
    expected_sha = candidate if mode == 'install' else (rollback or V['V5'])
    require(hashlib.sha256(raw).hexdigest() == expected_sha, 'Installed raw SHA256 mismatch')
    require(len(raw) == (candidate_size if mode == 'install' else rollback_size), 'Raw size mismatch')
    return dict(status=('INSTALLED_READBACK_VERIFIED_COLD_BOOT_UNTESTED' if mode == 'install'
                        else 'CURRENT_BOOT_BACKUP_VERIFIED' if mode == 'snapshot'
                        else 'ROLLBACK_READBACK_VERIFIED' if rollback else 'V5_RESTORE_READBACK_VERIFIED'),
                mode=mode, raw_sha256=expected_sha, wrapped_sha256=hashlib.sha256(wrapped).hexdigest(),
                raw_properties=props, reported_coih=after[COIH], source=source,
                archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                signature_verified=False, coih_derived=False)


def aligned_profile(backup_path, control_path):
    """Revalidate both recovery backups before updating immutable helper pins."""
    backup = V['validate'](backup_path)
    require(backup['archive_sha256'] == FRESH_BACKUP, 'Wrong original backup')
    with tarfile.open(backup_path, 'r:gz') as archive:
        original_baseline = policy_fields(archive.extractfile('boot-policy.txt').read())
    require(hashlib.sha256(control_path.read_bytes()).hexdigest() == CONTROL_SHA,
            'Not the reviewed restored-V5 backup')
    report = validate_after(control_path, 'rollback', original_baseline)
    receipt = control_path.with_name('rollback-receipt.txt').read_text()
    require(receipt == f'CKSUM {V["fingerprint"](control_path.read_bytes())}\nSHA256 {CONTROL_SHA}\nVALIDATED rollback\n',
            'Control backup receipt mismatch')
    require(report['reported_coih'] == CONTROL_COIH and report['wrapped_sha256'] ==
            '136d0424339f80cfe3d2d8a2d557a7fb3a247bd00fe630aa9554d406d2ef9a0e',
            'Restored V5 selection changed')
    with tarfile.open(control_path, 'r:gz') as archive:
        baseline = policy_fields(archive.extractfile('policy-after.txt').read())
    script = (HERE / 'recovery-install.sh').read_text()
    substitutions = [
        ('819284573 92651350', '750659463 92651520', 2),
        ('F2BB0BDC7EB3154646420C1F976F9A7AD74B9F1F80C9A2E3243A785068C8BA457F495C2F2EB1F9EF488A45449A24894E', CONTROL_COIH, 1),
        ('2652175684 1117034', '2129482942 1117033', 1),
    ]
    for old, new, count in substitutions:
        require(script.count(old) == count, 'Helper template drift: ' + old)
        script = script.replace(old, new)
    return baseline, script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', required=True)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--aligned-control-backup', type=Path, required=True,
                        help='Verified Sep12 restored V5 archive; v2 unaligned installation disabled')
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    backup = V['validate'](args.backup)
    require(backup['archive_sha256'] == FRESH_BACKUP, 'Not the reviewed fresh backup')
    baseline, helper = aligned_profile(args.backup, args.aligned_control_backup)
    artifacts = {'/standalone.bin': (ROOT / 'standalone-ssdroot-v3-aligned-20260912.bin', ALIGNED_CANDIDATE),
                 '/v5.bin': (ROOT / 'probe/m1n1-smp-diag-v5-20260906.bin', V['V5'])}
    # Immutable in-memory copies ensure bytes served match validated SHA pins.
    payloads = {}
    for name, (path, expected) in artifacts.items():
        payloads[name] = path.read_bytes()
        require(hashlib.sha256(payloads[name]).hexdigest() == expected, 'Artifact pin mismatch: ' + name)
        require(len(payloads[name]) % 16384 == 0, 'Enrollment object not 16 KiB aligned')
    aligned = runpy.run_path(str(HERE / 'build-aligned.py'))
    aligned['inspect'](payloads['/standalone.bin'], json.loads(
        (ROOT / 'standalone-ssdroot-v3-aligned-20260912.json').read_text()))
    destination = args.destination.resolve(strict=True)
    token = secrets.token_hex(16)
    base = f'http://{args.bind}:{args.port}'
    upload_base = '/upload/' + token
    script = helper.replace('@BASE_URL@', base).replace('@UPLOAD_URL@', base + upload_base).encode()
    require(b'@BASE_URL@' not in script and b'@UPLOAD_URL@' not in script, 'Unexpanded helper')
    payloads['/ssdboot.sh'] = script

    class Handler(http.server.BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(60)

        def do_GET(self):
            if self.path not in payloads:
                self.send_error(404)
                return
            blob = payloads[self.path]
            self.send_response(200)
            self.send_header('Content-Length', str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)

        def do_PUT(self):
            allowed = {upload_base + '/' + m: m for m in ('install', 'rollback')}
            if self.path not in allowed:
                self.send_error(404)
                return
            mode = allowed[self.path]
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                length = 0
            if not 0 < length <= 110 * 1024 * 1024:
                self.send_error(413)
                return
            path = destination / (mode + '-after.tar.gz')
            partial = destination / (mode + '-after.tar.gz.partial')
            if path.exists() or partial.exists():
                self.send_error(409, 'Readback already received; review before retry')
                return
            try:
                with partial.open('xb') as output:
                    while length:
                        chunk = self.rfile.read(min(length, 1024 * 1024))
                        require(chunk, 'Incomplete upload')
                        output.write(chunk)
                        length -= len(chunk)
                partial.rename(path)
                report = validate_after(path, mode, baseline, ALIGNED_CANDIDATE, 92651520)
                with (destination / (mode + '-verified.json')).open('x') as output:
                    json.dump(report, output, indent=2)
                blob = path.read_bytes()
                receipt = f'CKSUM {V["fingerprint"](blob)}\nSHA256 {report["archive_sha256"]}\nVALIDATED {mode}\n'
                with (destination / (mode + '-receipt.txt')).open('x') as output:
                    output.write(receipt)
                print(json.dumps(report), flush=True)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(receipt.encode())
            except Exception as error:
                print(f'READBACK FAILED ({mode}): {error}; files preserved; do not reboot', flush=True)
                self.send_error(422, 'Host validation failed; do not reboot; report error')

        def log_message(self, fmt, *values):
            print(f'{self.client_address[0]} {self.command} {self.path.split("/")[1]}', flush=True)

    class Server(http.server.HTTPServer):
        def server_bind(self):
            socketserver.TCPServer.server_bind(self)
            self.server_name = args.bind
            self.server_port = self.server_address[1]

    server = Server((args.bind, args.port), Handler)
    print(f'Pinned enrollment helper: {base}/ssdboot.sh', flush=True)
    print(f'Readback destination: {destination}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
