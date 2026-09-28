#!/usr/bin/env python3
"""Synthetic sysfs snapshots; no hardware or external commands under test."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('health', Path(__file__).with_name('check-health.py'))
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)
ROUTE_HEADER = 'Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n'


class Health(unittest.TestCase):
    def setUp(self):
        if not shutil.which('trash-put'):
            raise RuntimeError('Install trash-cli: sudo apt-get install -y trash-cli')
        self.root = Path(tempfile.mkdtemp(prefix='azahi-health-test-'))
        self.addCleanup(subprocess.run, ['trash-put', str(self.root)], check=True)
        self.put('proc/device-tree/compatible', 'apple,j714s\0apple,t6050\0')
        self.put('sys/devices/system/cpu/online', '0')
        self.put('sys/devices/system/cpu/possible', '0-17')
        self.put('proc/net/route', ROUTE_HEADER)
        self.addresses = []
        self.ntp = 'no'
        self.usb_enabled, self.usb_active = 'disabled', 'inactive'
        self.calls = []

    def put(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)

    def run_command(self, *args):
        self.calls.append(args)
        if args == ('uname', '-r'):
            return health.KERNEL
        if args == ('findmnt', '-n', '-o', 'FSTYPE', '/'):
            return 'btrfs'
        if args == ('systemctl', 'is-enabled', 'azahi-usb.service'):
            return self.usb_enabled
        if args == ('systemctl', 'show', 'azahi-usb.service', '--property=ActiveState', '--value'):
            return self.usb_active
        if args[:2] == ('systemctl', 'is-enabled'):
            return 'masked'
        if args == ('timedatectl', 'show', '--property=NTPSynchronized', '--value'):
            return self.ntp
        if args == ('ip', '-j', '-4', 'addr', 'show'):
            return json.dumps(self.addresses)
        raise AssertionError('unexpected command: ' + repr(args))

    def snapshot(self):
        return health.collect(self.root, self.run_command)

    def usb(self, function=(6, 1, 1), network=False, controller='382280000.usb'):
        base = self.root / 'sys/devices/platform' / controller / 'xhci/usb1'
        interface = base / '1-1/1-1:1.0'
        interface.mkdir(parents=True)
        self.put(str((base / '1-1/idVendor').relative_to(self.root)), '18d1')
        self.put(str((base / '1-1/serial').relative_to(self.root)), 'DO-NOT-EXPOSE-SERIAL')
        for name, value in zip(('bInterfaceClass', 'bInterfaceSubClass', 'bInterfaceProtocol'), function):
            (interface / name).write_text(f'{value:02x}')
        bus = self.root / 'sys/bus/usb/devices'
        bus.mkdir(parents=True, exist_ok=True)
        for name, target in [('usb1', base), ('1-1', base / '1-1'), ('1-1:1.0', interface)]:
            (bus / name).symlink_to(target)
        if network:
            net = self.root / 'sys/class/net/test-usb'
            net.mkdir(parents=True)
            (net / 'device').symlink_to(interface)

    def test_refuses_wrong_machine_before_inspecting_state(self):
        self.put('proc/device-tree/compatible', 'apple,j614s\0')
        with self.assertRaises(ValueError):
            self.snapshot()
        self.assertEqual(self.calls, [('uname', '-r')])

    def test_cpu_ranges_and_no_controller(self):
        self.assertEqual(health.cpu_count('0-5,8,12-17'), 13)
        for value in ('-1', '4-2', '0-4096', '1-2-3', 'oops', None):
            self.assertIsNone(health.cpu_count(value))
        report = self.snapshot()
        self.assertEqual((report['cpu_online'], report['cpu_possible']), (1, 18))
        self.assertEqual(report['usb']['status'], 'HOST_NOT_READY')
        self.assertEqual(report['sleep_targets_masked'], 5)
        self.assertEqual(report['usb']['service_enabled'], 'disabled')
        self.assertEqual(report['usb']['service_state'], 'inactive')
        self.assertIs(report['clock_ntp_synchronized'], False)

    def test_cached_policy_and_service_states_do_not_certify_hardware(self):
        self.usb((2, 13, 0), network=True)
        self.put('sys/bus/usb/devices/1-1/power/usb2_hardware_lpm', 'enabled')
        self.ntp, self.usb_enabled, self.usb_active = 'yes', 'enabled', 'active'
        report = self.snapshot()
        self.assertEqual(report['usb']['usb2_lpm_policy'], ['enabled'])
        self.assertEqual(report['usb']['status'], 'NETWORK_NO_IPV4')
        self.assertIs(report['clock_ntp_synchronized'], True)
        for unknown in (None, 'DO-NOT-EXPOSE-unexpected-output'):
            self.ntp = self.usb_enabled = self.usb_active = unknown
            self.put('sys/bus/usb/devices/1-1/power/usb2_hardware_lpm', unknown or '')
            report = self.snapshot()
            self.assertIsNone(report['clock_ntp_synchronized'])
            self.assertIsNone(report['usb']['service_enabled'])
            self.assertIsNone(report['usb']['service_state'])
            self.assertEqual(report['usb']['usb2_lpm_policy'], ['unknown'])
            self.assertNotIn('DO-NOT-EXPOSE', json.dumps(report))

    def test_phone_functions_and_missing_network_driver(self):
        self.usb()
        self.assertEqual(self.snapshot()['usb']['status'], 'PHONE_NON_NETWORK_FUNCTION')
        interface = self.root / 'sys/bus/usb/devices/1-1:1.0'
        (interface / 'bInterfaceClass').write_text('02')
        (interface / 'bInterfaceSubClass').write_text('0d')
        self.assertEqual(self.snapshot()['usb']['status'], 'NETWORK_FUNCTION_WITHOUT_INTERFACE')

    def test_network_stages_never_claim_internet_or_expose_identifiers(self):
        self.usb((2, 13, 0), network=True)
        self.assertEqual(self.snapshot()['usb']['status'], 'NETWORK_NO_IPV4')
        self.addresses = [dict(ifname='test-usb', address='DO-NOT-EXPOSE-MAC',
                              addr_info=[dict(scope='global', family='inet', local='DO-NOT-EXPOSE-IP')])]
        self.assertEqual(self.snapshot()['usb']['status'], 'NETWORK_NO_DEFAULT_ROUTE')
        self.put('proc/net/route', ROUTE_HEADER + 'test-usb 00000000 12345678 0003 0 0 100 00000000 0 0 0\n')
        report = self.snapshot()
        self.assertEqual(report['usb']['status'], 'NETWORK_CONFIGURED_NOT_TESTED')
        text = json.dumps(report)
        for private in ('DO-NOT-EXPOSE', 'test-usb', str(self.root), '12345678'):
            self.assertNotIn(private, text)

    def test_other_controller_does_not_count(self):
        self.usb((2, 13, 0), network=True, controller='other.usb')
        report = self.snapshot()
        self.assertEqual(report['usb']['hubs'], 0)
        self.assertEqual(report['usb']['network_interfaces'], 0)

    def test_address_and_route_must_belong_to_same_interface(self):
        self.usb((2, 13, 0), network=True)
        net = self.root / 'sys/class/net/second-usb'
        net.mkdir()
        (net / 'device').symlink_to(self.root / 'sys/bus/usb/devices/1-1:1.0')
        self.addresses = [dict(ifname='test-usb',
                              addr_info=[dict(scope='global', family='inet')])]
        self.put('proc/net/route', ROUTE_HEADER + 'second-usb 00000000 12345678 0003 0 0 100 00000000 0 0 0\n')
        report = self.snapshot()['usb']
        self.assertEqual(report['network_interfaces'], 2)
        self.assertEqual(report['ipv4_interfaces'], 1)
        self.assertEqual(report['status'], 'NETWORK_NO_DEFAULT_ROUTE')

    def test_nondefault_and_reject_routes_do_not_count(self):
        self.usb((2, 13, 0), network=True)
        self.addresses = [dict(ifname='test-usb', addr_info=[dict(scope='global', family='inet')])]
        for flags, mask in [('0003', '000000FF'), ('0000', '00000000'), ('0201', '00000000')]:
            self.put('proc/net/route', ROUTE_HEADER +
                     f'test-usb 00000000 12345678 {flags} 0 0 100 {mask} 0 0 0\n')
            self.assertEqual(self.snapshot()['usb']['status'], 'NETWORK_NO_DEFAULT_ROUTE')

    def test_missing_or_malformed_address_report_is_unknown(self):
        self.usb((2, 13, 0), network=True)
        for addresses in (None, {}, [None], [{'ifname': 'test-usb', 'addr_info': None}]):
            self.addresses = addresses
            report = self.snapshot()['usb']
            self.assertEqual(report['status'], 'NETWORK_STATE_UNKNOWN')


if __name__ == '__main__':
    unittest.main()
