#!/usr/bin/env python3
"""Test real initrd tools in a QEMU VM: no disks, networking or USB passthrough.

Uses the pinned v5 initrd and kernel plus a test-only appended init script.
Host temporary artifacts are retained for inspection; no target access.
"""
import gzip
import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
V = runpy.run_path(str(HERE / 'build-transfer-v6.py'))
B = V['B']
F = V['F']


def main():
    image = F['OUTPUT'].read_bytes()
    assert V['sha'](image) == V['V5_SHA']
    receipt = json.loads(F['OUTPUT'].with_suffix('.json').read_text())
    parts = F['inspect'](image, receipt)
    work = Path(tempfile.mkdtemp(prefix='azahi-courier-vm-'))
    kernel = gzip.decompress(parts['gzip'])
    assert hashlib.sha256(kernel).hexdigest() == 'd2ec67ab79aea96292869f66e83c50d0fdb354d237d9787a9d6c238f0b7bffe7'
    (work / 'Image').write_bytes(kernel)
    archive = io.BytesIO()
    writer = B['W']['Writer'](archive)
    writer.file('courier-vm-init.sh', HERE / 'courier-vm-init.sh', 0o755)
    writer.file('courier-v2.sh', HERE / 'boot-stage-v2.sh', 0o755)
    writer.trailer()
    # Drop only the known zero padding, preserving both real v5 zstd frames.
    length = receipt['recompressed_original_bytes'] + receipt['extra_bytes']
    test_frame = subprocess.run(['zstd', '-q', '-c'], input=archive.getvalue(),
                                capture_output=True, check=True).stdout
    (work / 'initrd').write_bytes(parts['initrd'][:length] + test_frame)
    command = ['qemu-system-aarch64', '-machine', 'virt', '-cpu', 'max', '-accel', 'tcg',
               '-m', '2048', '-smp', '1', '-nodefaults', '-nic', 'none',
               '-display', 'none', '-serial', 'stdio', '-monitor', 'none', '-no-reboot',
               '-kernel', str(work / 'Image'), '-initrd', str(work / 'initrd'),
               '-append', 'console=ttyAMA0 rdinit=/courier-vm-init.sh panic=-1 quiet']
    print('NO_DISK_NO_NETWORK_VM', work, flush=True)
    with (work / 'console.log').open('wb') as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        except subprocess.TimeoutExpired:
            print((work / 'console.log').read_text(errors='replace')[-6000:])
            raise
    output = (work / 'console.log').read_text(errors='replace')
    print(output[-10000:])
    assert result.returncode == 0
    assert 'COURIER_VM_ALL_PASS' in output and 'COURIER_VM_FAIL' not in output
    for marker in ('OLD_FAILURE_REPRODUCED', 'SUCCESS_EMPTY_PATH', 'EXISTING_PRESERVED',
                   'CORRUPTION_REJECTED', 'SYMLINK_REJECTED', 'NON_TMPFS_REJECTED'):
        assert 'COURIER_VM_' + marker in output
    print('VERIFIED_REAL_ARM64_COURIER_TOOLS', work / 'console.log')


if __name__ == '__main__':
    main()
