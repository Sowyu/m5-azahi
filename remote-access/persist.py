#!/usr/bin/env python3
"""Persist the already authenticated session, without restarting it.

Arguments: verified runtime directory, expected Linux root UUID, helper IPv4.
Only creates dedicated state/units and a new NetworkManager profile. All
existing sshd/authorized_keys, active connections and boot images preserved.
"""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    runtime, expected_uuid, host = sys.argv[1:]
    if os.geteuid() != 0 or os.uname().release != '7.0.13-400.asahi.fc44.aarch64+16k':
        raise RuntimeError('Wrong execution environment')
    if b'apple,j714s\0' not in Path('/proc/device-tree/compatible').read_bytes():
        raise RuntimeError('Wrong model')
    if subprocess.check_output(['findmnt', '-n', '-o', 'UUID', '/'], text=True).strip() != expected_uuid:
        raise RuntimeError('Wrong root filesystem')
    mounts = json.loads(subprocess.check_output(['findmnt', '-J', '-l', '-o', 'FSTYPE']))
    if any(m['fstype'] == 'apfs' for m in mounts['filesystems']):
        raise RuntimeError('APFS mounted; stop for scope review')
    ipaddress.IPv4Address(host)
    if not re.fullmatch('/run/azahi-remote-[a-zA-Z0-9_]+', runtime):
        raise RuntimeError('Unexpected runtime path')
    source = Path(runtime)
    if source.is_symlink() or source.stat().st_uid != 0 or source.stat().st_mode & 0o077:
        raise RuntimeError('Unsafe runtime directory')
    dest = Path('/var/lib/azahi-remote')
    units = Path('/etc/systemd/system')
    names = ['azahi-native-sshd.service', 'azahi-native-tunnel.service']
    if dest.exists() or any((units / n).exists() or (units / n).is_symlink() for n in names):
        raise RuntimeError('Dedicated persistent state already exists; no overwrite')
    if 'azahi-usb-tether' in subprocess.check_output(['nmcli', '-g', 'NAME', 'connection', 'show'], text=True).splitlines():
        raise RuntimeError('Named network profile already exists; no overwrite')
    files = ('controller.pub', 'tunnel_key', 'relay_known_hosts', 'host_key', 'host_key.pub', 'sshd_config')
    for name in files:
        path = source / name
        if path.is_symlink() or not path.is_file() or path.stat().st_uid != 0:
            raise RuntimeError('Unsafe runtime file')
    os.umask(0o077)
    backup = Path(tempfile.mkdtemp(prefix='azahi-access-before-', dir='/root'))
    for unit in names:
        # Record absence, since overwriting existing units is prohibited.
        (backup / (unit + '.absent')).touch(exist_ok=False)
    dest.mkdir(mode=0o700)
    for name in files:
        if name != 'sshd_config':
            shutil.copyfile(source / name, dest / name)
            os.chmod(dest / name, 0o600)
    (dest / 'sshd_config').write_text((source / 'sshd_config').read_text().replace(runtime, str(dest)))
    run('/usr/sbin/sshd', '-t', '-f', str(dest / 'sshd_config'))
    daemon = f'''[Unit]
Description=Azahi task-key-only native SSH (loopback)
ConditionPathExists={dest}/host_key
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=/usr/sbin/sshd -D -e -f {dest}/sshd_config
Restart=on-failure
RestartSec=5
UMask=0077

[Install]
WantedBy=multi-user.target
'''
    tunnel = f'''[Unit]
Description=Azahi pinned outbound SSH tunnel to helper
After=NetworkManager.service azahi-native-sshd.service
Wants=NetworkManager.service azahi-native-sshd.service
ConditionPathExists={dest}/tunnel_key
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=/usr/bin/ssh -F none -NT -i {dest}/tunnel_key -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=azahi-relay -o UserKnownHostsFile={dest}/relay_known_hosts -o GlobalKnownHostsFile=/dev/null -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -p 8022 -R 127.0.0.1:22022:127.0.0.1:2222 tunnel@{host}
Restart=on-failure
RestartSec=15
UMask=0077
# Outbound client that only reads its key and pin: no capabilities, read-only
# filesystem. No NoNewPrivileges/seccomp options: under SELinux they can block
# the exec domain transition and this unit is the only remote-access path.
CapabilityBoundingSet=
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
'''
    for name, contents in zip(names, (daemon, tunnel)):
        with (units / name).open('x') as stream:
            stream.write(contents)
        os.chmod(units / name, 0o644)
    run('systemd-analyze', 'verify', *(str(units / n) for n in names))
    run('nmcli', 'connection', 'add', 'type', 'ethernet', 'ifname', 'enu1',
        'con-name', 'azahi-usb-tether', 'connection.autoconnect', 'yes',
        'connection.autoconnect-priority', '100', 'ipv4.method', 'auto',
        'ipv6.method', 'disabled')
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', *names)
    # Do not start conflicting new listeners or replace the working tunnel.
    receipt = {'runtime_preserved': runtime, 'backup': str(backup),
               'enabled_units': names, 'services_started': False,
               'network_profile': 'azahi-usb-tether', 'boot_changed': False,
               'host_public_sha256': hashlib.sha256((dest / 'host_key.pub').read_bytes()).hexdigest()}
    with (dest / 'install-receipt.json').open('x') as output:
        json.dump(receipt, output, indent=2)
    run('sync')
    print('PERSISTENT_ACCESS_PREPARED: current session untouched; cold boot not yet tested')


if __name__ == '__main__': main()
