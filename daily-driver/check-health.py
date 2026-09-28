#!/usr/bin/env python3
"""Read cached Linux state. No network requests, MMIO, service or module changes.

Output omits serials, UUIDs, network addresses, SSIDs, credentials and raw logs.
A configured interface is not proof of internet access or reliable hardware.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

KERNEL = '7.0.13-400.asahi.fc44.aarch64+16k'
USB_MODULES = ('phy_apple_t6050_usb2', 'azahi_usb_overlay', 'dwc3_apple_t6050')
SLEEP_TARGETS = ('sleep', 'suspend', 'hibernate', 'hybrid-sleep', 'suspend-then-hibernate')


def read(path):
    try:
        return path.read_text().strip()
    except (OSError, UnicodeError):
        return None


def command(*args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5)
        # is-enabled returns nonzero for a correctly masked target.
        return result.stdout.strip() if result.returncode in (0, 1) else None
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return None


def cpu_count(value):
    if value is None:
        return None
    cpus = set()
    try:
        for item in value.split(','):
            bounds = item.split('-')
            first = int(bounds[0])
            last = int(bounds[1]) if len(bounds) == 2 else first
            if len(bounds) > 2 or not 0 <= first <= last < 4096:
                return None
            cpus.update(range(first, last + 1))
    except ValueError:
        return None
    return len(cpus)


def right_port(path):
    try:
        return '382280000.usb' in path.resolve(strict=True).parts
    except (OSError, RuntimeError):
        return False


def collect(root=Path('/'), run=command):
    compatible = read(root / 'proc/device-tree/compatible')
    kernel = run('uname', '-r')
    if not compatible or 'apple,j714s' not in compatible.split('\0') or kernel != KERNEL:
        raise ValueError('requires J714s and the pinned kernel; no target state inspected')

    masked = [name for name in SLEEP_TARGETS
              if run('systemctl', 'is-enabled', name + '.target') == 'masked']
    report = {
        'schema': 1, 'kernel': kernel, 'model': 'J714s',
        'cpu_online': cpu_count(read(root / 'sys/devices/system/cpu/online')),
        'cpu_possible': cpu_count(read(root / 'sys/devices/system/cpu/possible')),
        'root_btrfs': run('findmnt', '-n', '-o', 'FSTYPE', '/') == 'btrfs',
        'sleep_targets_masked': len(masked),
        'sleep_targets_required': len(SLEEP_TARGETS),
    }
    synchronized = run('timedatectl', 'show', '--property=NTPSynchronized', '--value')
    report['clock_ntp_synchronized'] = {'yes': True, 'no': False}.get(synchronized)
    modules = [name for name in USB_MODULES if (root / 'sys/module' / name).is_dir()]
    hubs, devices, functions, lpm = 0, 0, set(), []
    for node in sorted((root / 'sys/bus/usb/devices').glob('*')):
        if not right_port(node):
            continue
        if node.name.startswith('usb'):
            hubs += 1
        elif ':' not in node.name and (node / 'idVendor').is_file():
            devices += 1
            # This sysfs file exposes usb2_hw_lpm_allowed, not actual L1 state
            # or even successful hardware enablement. Keep that distinction.
            value = read(node / 'power/usb2_hardware_lpm')
            lpm.append(value if value in ('enabled', 'disabled') else 'unknown')
        elif ':' in node.name:
            values = [read(node / key) for key in
                      ('bInterfaceClass', 'bInterfaceSubClass', 'bInterfaceProtocol')]
            try:
                cls, sub, protocol = (int(v, 16) for v in values)
            except (ValueError, TypeError):
                functions.add('unknown')
                continue
            if (cls, sub, protocol) == (255, 66, 1):
                functions.add('adb')
            elif cls == 6:
                functions.add('imaging')
            elif (cls, sub) in ((2, 6), (2, 13)):
                functions.add('cdc-network')
            elif (cls, sub, protocol) in ((224, 1, 3), (239, 4, 1), (2, 2, 255)):
                functions.add('rndis')
            elif cls != 9:
                functions.add('other')

    interfaces = {node.name for node in (root / 'sys/class/net').glob('*')
                  if right_port(node / 'device')}
    addresses = run('ip', '-j', '-4', 'addr', 'show')
    configured = None
    try:
        entries = json.loads(addresses)
        if not isinstance(entries, list):
            raise ValueError('address report must be a list')
        configured = {entry['ifname'] for entry in entries
                      if entry.get('ifname') in interfaces
                      and any(a.get('scope') == 'global' and a.get('family') == 'inet'
                              for a in entry.get('addr_info', []))}
    except (ValueError, TypeError, AttributeError):
        pass
    route_text = read(root / 'proc/net/route')
    default_route = None if route_text is None or configured is None else False
    for line in (route_text or '').splitlines()[1:]:
        fields = line.split()
        if (len(fields) >= 8 and fields[0] in (configured or set())
                and fields[1] == '00000000' and fields[7] == '00000000'):
            try:
                flags = int(fields[3], 16)
                # UP must be set, REJECT must be clear.
                default_route = default_route or flags & 0x201 == 1
            except ValueError:
                pass

    if not hubs:
        status = 'HOST_NOT_READY' if not modules else 'HOST_MODULES_WITHOUT_HUB'
    elif not interfaces:
        if functions & {'cdc-network', 'rndis'}:
            status = 'NETWORK_FUNCTION_WITHOUT_INTERFACE'
        elif functions & {'adb', 'imaging'}:
            status = 'PHONE_NON_NETWORK_FUNCTION'
        else:
            status = 'NO_NETWORK_INTERFACE' if devices else 'NO_USB_DEVICE'
    elif configured is None or default_route is None:
        status = 'NETWORK_STATE_UNKNOWN'
    elif not configured:
        status = 'NETWORK_NO_IPV4'
    elif not default_route:
        status = 'NETWORK_NO_DEFAULT_ROUTE'
    else:
        status = 'NETWORK_CONFIGURED_NOT_TESTED'
    enabled = run('systemctl', 'is-enabled', 'azahi-usb.service')
    active = run('systemctl', 'show', 'azahi-usb.service', '--property=ActiveState', '--value')
    report['usb'] = dict(status=status, modules=len(modules), hubs=hubs, devices=devices,
                         functions=sorted(functions), usb2_lpm_policy=lpm,
                         service_enabled=enabled if enabled in
                         ('enabled', 'enabled-runtime', 'disabled', 'masked', 'masked-runtime',
                          'static', 'indirect', 'not-found') else None,
                         service_state=active if active in
                         ('active', 'inactive', 'failed', 'activating', 'deactivating',
                          'reloading', 'refreshing', 'maintenance') else None,
                         network_interfaces=len(interfaces),
                         ipv4_interfaces=None if configured is None else len(configured),
                         default_route=default_route)
    hpm = root / 'sys/module/azahi_hpm_once/parameters'
    report['hpm'] = {}
    for name in ('result', 'ready', 'poisoned'):
        value = read(hpm / name)
        if name in ('ready', 'poisoned'):
            report['hpm'][name] = value if value in ('Y', 'N') else None
        else:
            try:
                report['hpm'][name] = int(value)
            except (ValueError, TypeError):
                report['hpm'][name] = None
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        result = collect()
    except ValueError as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"CPU: {result['cpu_online']} online, {result['cpu_possible']} possible; no load test")
        print(f"ROOT: Btrfs={result['root_btrfs']}; SLEEP: {result['sleep_targets_masked']}/5 targets masked")
        print(f"CLOCK: NTP synchronized={result['clock_ntp_synchronized']}")
        print('USB: ' + result['usb']['status'])
        print('USB DETAILS: ' + json.dumps(result['usb'], sort_keys=True))
        print('HPM: ' + json.dumps(result['hpm'], sort_keys=True))
    return 0  # Successfully collected a report, not a declaration of health.


if __name__ == '__main__':
    sys.exit(main())
