#!/usr/bin/env python3
"""Install verified USB startup artifacts only on the pinned Linux root.

Usage: python3 script.py STAGING_DIRECTORY EXPECTED_ROOT_UUID
Refuses existing destinations. Never changes bootloader, partitions or mounts.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PINS = {
    'phy-apple-t6050-usb2.ko': 'c54ffb8d82f966c5a907898e09e0d53fec42904493e42a45999791586f3e0b12',
    'dwc3-apple-t6050.ko': '24b80b4e23f9a0065547df170ca7e6016e93ac7f17a3b47a2b8757636be045ce',
    'azahi-usb-overlay.ko': 'bf9a5c1804f7c37db022d5db46a6f2dd75d4d6490b294e7388271fcd693903b1',
    'azahi_hpm_once.ko': '7b6d2d80595e2596e63cc64fb11c9525ae10895900169fa2cd05ecc9ee0fb21d',
}


def main():
    stage, expected = Path(sys.argv[1]), sys.argv[2]
    check = subprocess.check_output
    if os.geteuid() != 0 or os.uname().release != '7.0.13-400.asahi.fc44.aarch64+16k':
        raise RuntimeError('Wrong target environment')
    if check(['findmnt', '-n', '-o', 'UUID', '/'], text=True).strip() != expected:
        raise RuntimeError('Wrong Linux root')
    if b'apple,j714s\0' not in Path('/proc/device-tree/compatible').read_bytes():
        raise RuntimeError('Wrong model')
    if 'apfs' in check(['findmnt', '-rn', '-o', 'FSTYPE'], text=True).splitlines():
        raise RuntimeError('APFS mounted; stop for scope review')
    target = Path('/opt/azahi-usb')
    unit = Path('/etc/systemd/system/azahi-usb.service')
    config = Path('/etc/azahi-usb-root')
    if any(p.exists() or p.is_symlink() for p in (target, unit, config)):
        raise RuntimeError('Installation already exists; no overwrite')
    for name, pin in PINS.items():
        path = stage / name if name == 'azahi_hpm_once.ko' else Path('/root/usb-candidate') / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise RuntimeError('Module checksum failed: ' + name)
    for name in ('start-native-usb.sh', 'azahi-usb.service'):
        path = stage / name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('Missing staged source')
    subprocess.run(['bash', '-n', str(stage / 'start-native-usb.sh')], check=True)
    os.umask(0o077)
    backup = Path(tempfile.mkdtemp(prefix='azahi-usb-before-', dir='/root'))
    (backup / 'destinations-were-absent').write_text('/opt/azahi-usb\n/etc/azahi-usb-root\n/etc/systemd/system/azahi-usb.service\n')
    target.mkdir(mode=0o700)
    for name in PINS:
        source = stage / name if name == 'azahi_hpm_once.ko' else Path('/root/usb-candidate') / name
        shutil.copyfile(source, target / name)
    shutil.copyfile(stage / 'start-native-usb.sh', target / 'start-native-usb.sh')
    os.chmod(target / 'start-native-usb.sh', 0o700)
    all_files = list(PINS) + ['start-native-usb.sh']
    (target / 'SHA256SUMS').write_text(''.join(hashlib.sha256((target / n).read_bytes()).hexdigest() + '  ' + n + '\n' for n in all_files))
    shutil.copyfile(stage / 'azahi-usb.service', unit)
    os.chmod(unit, 0o644)
    with config.open('x') as out:
        out.write(expected + '\n')
    subprocess.run(['systemd-analyze', 'verify', str(unit)], check=True)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', 'azahi-usb.service'], check=True)
    (target / 'install-receipt.json').write_text(json.dumps({'backup': str(backup),
        'cold_boot_tested': False, 'boot_changed': False, 'pins': PINS}, indent=2))
    subprocess.run(['sync'], check=True)
    print('USB_STARTUP_INSTALLED: enabled, not yet started or cold-boot tested')


if __name__ == '__main__': main()
