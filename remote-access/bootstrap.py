#!/usr/bin/env python3
"""Target installer body; CONFIG is injected by the authenticated SSH relay.

Creates only task-specific /run state and transient systemd units. No boot
image, partition, global sshd configuration, user key or firewall changes.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def setup(config):
    if os.geteuid() != 0:
        raise RuntimeError('Run on the target Linux root terminal')
    if os.uname().release != '7.0.13-400.asahi.fc44.aarch64+16k':
        raise RuntimeError('Wrong target kernel')
    if b'apple,j714s\0' not in Path('/proc/device-tree/compatible').read_bytes():
        raise RuntimeError('Wrong target model')
    root_uuid = subprocess.check_output(['findmnt', '-n', '-o', 'UUID', '/'], text=True).strip()
    if root_uuid != config['root_uuid']:
        raise RuntimeError('Wrong Linux filesystem; no changes made')
    tag = config['tag']
    if not re.fullmatch('[a-z0-9]{8}', tag):
        raise RuntimeError('Invalid task identity')
    for command in ('ssh', 'ssh-keygen', 'systemd-run', 'systemctl'):
        run('/usr/bin/which', command, stdout=subprocess.DEVNULL)
    if not Path('/usr/sbin/sshd').is_file():
        raise RuntimeError('OpenSSH server missing; install openssh-server then retry')
    # No global service is stopped or altered. Refuse a competing listener.
    import socket
    check = socket.socket()
    try:
        check.bind(('127.0.0.1', 2222))
    finally:
        check.close()
    os.umask(0o077)
    folder = Path(tempfile.mkdtemp(prefix='azahi-remote-', dir='/run'))
    def write(name, data):
        with (folder / name).open('x') as out:
            out.write(data)
    write('controller.pub', config['controller_public'])
    write('tunnel_key', config['tunnel_private'])
    write('relay_known_hosts', 'azahi-relay ' + config['relay_public'])
    run('ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'azahi-native-task',
        '-f', str(folder / 'host_key'))
    write('sshd_config', f'''Port 2222
ListenAddress 127.0.0.1
HostKey {folder}/host_key
PidFile {folder}/sshd.pid
AuthorizedKeysFile {folder}/controller.pub
PasswordAuthentication no
KbdInteractiveAuthentication no
AuthenticationMethods publickey
PermitRootLogin prohibit-password
AllowUsers root
UsePAM no
AllowAgentForwarding no
AllowTcpForwarding no
AllowStreamLocalForwarding no
X11Forwarding no
PermitTunnel no
PermitUserEnvironment no
PermitUserRC no
StrictModes yes
Subsystem sftp internal-sftp
LogLevel VERBOSE
''')
    run('/usr/sbin/sshd', '-t', '-f', str(folder / 'sshd_config'))
    ssh = ['ssh', '-F', 'none', '-i', str(folder / 'tunnel_key'),
           '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
           '-o', 'StrictHostKeyChecking=yes', '-o', 'HostKeyAlias=azahi-relay',
           '-o', f'UserKnownHostsFile={folder}/relay_known_hosts',
           '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'ConnectTimeout=10',
           '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
           '-o', 'ExitOnForwardFailure=yes', '-p', str(config['port'])]
    host_public = (folder / 'host_key.pub').read_text().split()
    registration = json.dumps({'key': ' '.join(host_public[:2]),
                               'runtime': str(folder), 'tag': tag})
    run(*ssh, 'tunnel@' + config['host'], 'register',
        input=registration, text=True, timeout=20)
    daemon = f'azahi-remote-sshd-{tag}'
    tunnel = f'azahi-remote-tunnel-{tag}'
    run('systemd-run', '--unit=' + daemon, '--property=Restart=on-failure',
        '--property=RestartSec=3', '/usr/sbin/sshd', '-D', '-e', '-f',
        str(folder / 'sshd_config'))
    run('systemctl', 'is-active', daemon)
    try:
        run('systemd-run', '--unit=' + tunnel, '--property=Restart=on-failure',
            '--property=RestartSec=5', '--property=CapabilityBoundingSet=',
            '--property=ProtectSystem=strict', '--property=ProtectHome=yes',
            '--property=PrivateTmp=yes', *ssh, '-NT',
            '-R', '127.0.0.1:22022:127.0.0.1:2222', 'tunnel@' + config['host'])
        run('systemctl', 'is-active', tunnel)
    except BaseException:
        run('systemctl', 'stop', daemon)
        raise
    print('AZAHI_REMOTE_STARTED: task-only authenticated tunnel; no boot changes')
    print('To revoke this session: systemctl stop', tunnel, daemon)


if __name__ == '__main__':
    setup(CONFIG)
