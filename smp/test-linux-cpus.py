#!/usr/bin/env python3
"""Synthetic readiness/aggregation checks and one real host CPU worker."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).with_name('check-linux-cpus.py')
spec = importlib.util.spec_from_file_location('check', SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class CpuCheck(unittest.TestCase):
    def setUp(self):
        if not shutil.which('trash-put'):
            raise RuntimeError('Install trash-cli: sudo apt-get install -y trash-cli')
        self.root = Path(tempfile.mkdtemp(prefix='azahi-cpu-check-'))
        self.addCleanup(subprocess.run, ['trash-put', str(self.root)], check=True)
        device = self.root / 'proc/device-tree/compatible'
        device.parent.mkdir(parents=True)
        device.write_bytes(b'apple,j714s\0apple,t6050\0')
        self.online = self.root / 'sys/devices/system/cpu/online'
        self.online.parent.mkdir(parents=True)
        self.online.write_text('0-17\n')

    def test_readiness_refuses_partial_cpus_wrong_target_and_affinity(self):
        check.preflight(self.root, check.KERNEL, check.CPUS)
        for online in ('0', '0-16', '0-18', 'invalid'):
            self.online.write_text(online)
            with self.assertRaisesRegex(ValueError, '18 CPUs'):
                check.preflight(self.root, check.KERNEL, check.CPUS)
        self.online.write_text('0-17')
        with self.assertRaisesRegex(ValueError, 'pinned kernel'):
            check.preflight(self.root, 'other', check.CPUS)
        with self.assertRaisesRegex(ValueError, 'affinity'):
            check.preflight(self.root, check.KERNEL, {0})
        (self.root / 'proc/device-tree/compatible').write_bytes(b'apple,j714c\0')
        with self.assertRaisesRegex(ValueError, 'J714s'):
            check.preflight(self.root, check.KERNEL, check.CPUS)

    def test_pass_requires_each_distinct_cpu_and_correct_computation(self):
        results = [dict(cpu=cpu, rounds=check.ROUNDS, sha256=check.EXPECTED_SHA256)
                   for cpu in range(18)]
        check.validate(results)
        for bad in (results[:-1], results[:-1] + [results[0]],
                    results[:-1] + [None], results[:-1] + [dict(results[-1], cpu=[])],
                    [dict(results[0], cpu=False)] + results[1:],
                    results[:-1] + [dict(results[-1], sha256='wrong')],
                    results[:-1] + [dict(results[-1], rounds=1)]):
            with self.assertRaises(ValueError):
                check.validate(bad)

    def test_actual_worker_on_one_allowed_host_cpu(self):
        cpu = min(os.sched_getaffinity(0))
        # Separate child: the test runner's affinity must remain unchanged.
        program = '''import importlib.util, json, sys
sys.dont_write_bytecode = True
s = importlib.util.spec_from_file_location('worker', sys.argv[1])
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
print(json.dumps(m.worker(int(sys.argv[2]))))
'''
        original = os.sched_getaffinity(0)
        result = subprocess.run([sys.executable, '-c', program, str(SCRIPT), str(cpu)],
                                capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(os.sched_getaffinity(0), original)
        value = json.loads(result.stdout)
        self.assertEqual(value['cpu'], cpu)
        self.assertEqual(value['rounds'], check.ROUNDS)
        self.assertEqual(value['sha256'], check.EXPECTED_SHA256)

    def processes(self, fail_cpu=None):
        processes = []

        def launch(command, **kwargs):
            cpu = len(processes)
            self.assertEqual(command[-2:], ['--worker', str(cpu)])
            result = dict(cpu=cpu, rounds=check.ROUNDS, sha256=check.EXPECTED_SHA256)
            process = mock.Mock(returncode=None)

            def communicate(timeout):
                process.returncode = 1 if cpu == fail_cpu else 0
                return json.dumps(result), ''

            process.communicate.side_effect = communicate
            process.poll.side_effect = lambda: process.returncode
            processes.append(process)
            return process

        return processes, launch

    def test_failed_worker_cannot_pass_and_stops_pending_workers(self):
        processes, launch = self.processes(fail_cpu=5)
        with mock.patch.object(check.subprocess, 'Popen', side_effect=launch), \
                mock.patch.object(check, 'preflight'), \
                self.assertRaisesRegex(RuntimeError, 'CPU 5 worker failed'):
            check.execute()
        self.assertEqual(len(processes), 18)
        for process in processes[6:]:
            process.kill.assert_called_once()

    def test_changed_cpu_state_cannot_pass_after_successful_workers(self):
        _, launch = self.processes()
        with mock.patch.object(check.subprocess, 'Popen', side_effect=launch), \
                mock.patch.object(check, 'preflight', side_effect=ValueError('CPU state changed')), \
                self.assertRaisesRegex(ValueError, 'CPU state changed'):
            check.execute()


if __name__ == '__main__':
    unittest.main()
