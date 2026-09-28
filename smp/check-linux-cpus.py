#!/usr/bin/env python3
"""Check the pinned J714s Linux CPU state; --run performs bounded per-CPU work.

Default mode only reports readiness. Each worker checks its actual executing
CPU and computes a known SHA-256 result while pinned to that CPU. Passing this
short check does not establish endurance, thermal or sleep reliability.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

KERNEL = '7.0.13-400.asahi.fc44.aarch64+16k'
CPUS = set(range(18))
BLOCK = b'azahi-cpu-check\0' * 4096
ROUNDS = 256  # 16 MiB per worker, fixed work rather than an unbounded stress loop.
EXPECTED_SHA256 = '6b9b9afe6967854cb33d88f05a969778da078c1a29886edb98601bc7d0569e6c'


def preflight(root=Path('/'), kernel=None, affinity=None):
    kernel = os.uname().release if kernel is None else kernel
    if kernel != KERNEL:
        raise ValueError('requires J714s and the pinned kernel')
    compatible = (root / 'proc/device-tree/compatible').read_bytes().split(b'\0')
    if b'apple,j714s' not in compatible:
        raise ValueError('requires J714s and the pinned kernel')
    online = (root / 'sys/devices/system/cpu/online').read_text().strip()
    if online != '0-17':
        raise ValueError('all 18 CPUs must be online first; no workers started')
    affinity = os.sched_getaffinity(0) if affinity is None else affinity
    if not CPUS <= affinity:
        raise ValueError('process affinity excludes target CPUs; no workers started')


def worker(cpu):
    # Linux affinity 0 addresses the calling task. Workers are separate processes.
    os.sched_setaffinity(0, {cpu})
    if os.sched_getaffinity(0) != {cpu}:
        raise RuntimeError('affinity did not take effect')
    libc = ctypes.CDLL(None, use_errno=True)
    getcpu = libc.sched_getcpu
    getcpu.argtypes = []
    getcpu.restype = ctypes.c_int
    digest = hashlib.sha256()
    started = time.monotonic()
    for _ in range(ROUNDS):
        if getcpu() != cpu:
            raise RuntimeError('worker executed on the wrong CPU')
        digest.update(BLOCK)
    if getcpu() != cpu:
        raise RuntimeError('worker left its CPU')
    return {'cpu': cpu, 'rounds': ROUNDS, 'sha256': digest.hexdigest(),
            'elapsed_ms': round((time.monotonic() - started) * 1000, 3)}


def validate(results):
    if any(not isinstance(r, dict) or type(r.get('cpu')) is not int for r in results):
        raise ValueError('invalid CPU result')
    if len(results) != len(CPUS) or {r.get('cpu') for r in results} != CPUS:
        raise ValueError('missing or duplicate CPU results')
    for result in results:
        if result.get('rounds') != ROUNDS or result.get('sha256') != EXPECTED_SHA256:
            raise ValueError('CPU computation failed verification')


def execute():
    processes = []
    results = []
    deadline = time.monotonic() + 30
    try:
        for cpu in sorted(CPUS):
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                        '--worker', str(cpu)],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            processes.append((cpu, process))
        for cpu, process in processes:
            stdout, _ = process.communicate(timeout=max(0.001, deadline - time.monotonic()))
            if process.returncode:
                raise RuntimeError(f'CPU {cpu} worker failed')
            result = json.loads(stdout)
            if not isinstance(result, dict) or type(result.get('cpu')) is not int or result['cpu'] != cpu:
                raise ValueError('worker result has the wrong CPU identity')
            results.append(result)
        # An offline/online transition or changed affinity prevents a pass.
        preflight()
        validate(results)
        return {'status': 'ALL_18_CPUS_EXECUTED', 'workers': results,
                'kernel': KERNEL, 'bytes_per_cpu': len(BLOCK) * ROUNDS,
                'concurrency_tested': False, 'endurance_tested': False,
                'thermal_tested': False, 'sleep_tested': False}
    finally:
        for _, process in processes:
            if process.poll() is None:
                process.kill()
        for _, process in processes:
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                pass  # Kernel-stuck tasks cannot be repaired by this userspace check.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--run', action='store_true')
    mode.add_argument('--worker', type=int, choices=sorted(CPUS), help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        preflight()
        if args.worker is not None:
            print(json.dumps(worker(args.worker)))
        elif args.run:
            print(json.dumps(execute(), indent=2))
        else:
            print('CPU_READY_NOT_TESTED: 18 online and allowed; use --run for per-CPU work')
    except (OSError, ValueError, RuntimeError, AttributeError, subprocess.TimeoutExpired) as error:
        # Do not emit private paths or raw child output in a shareable result.
        print('CPU_CHECK_FAILED: ' + (str(error) if isinstance(error, (ValueError, RuntimeError))
                                     else type(error).__name__), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
