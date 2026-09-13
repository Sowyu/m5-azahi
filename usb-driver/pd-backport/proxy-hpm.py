#!/usr/bin/env python3
"""Attended proxy-only right-HPM diagnostic; NOT a Linux installer.

Default invocation has no target access. --status reads only identity, power,
and FIFO status. --probe additionally wakes SID12 and selects a small fixed
set of logical registers. Selection sends commands: it is NOT read-only.
--s0 additionally permits precisely one SSPS-to-S0 command after APP/VID/status
checks. No other PD task, reset, IRQ mask, disk or boot policy writes exist.
Failure latches the process. Never automatically reconnect or flush FIFOs.
Requires the existing private fixture/proxy dependencies; source is publishable.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = 0x28a1a8000
POWER = 0x288300068
SOURCE_SHA = '0ca32c0df14ce714d32029ede06a428722616da0711fc5d0b85a98f1a77d77d0'
READ = C.CFUNCTYPE(C.c_uint32, C.c_void_p, C.c_uint32)
WRITE = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint32)
DELAY = C.CFUNCTYPE(None, C.c_void_p, C.c_uint)


class IO(C.Structure):
    _fields_ = [('context', C.c_void_p), ('read', READ), ('write', WRITE),
               ('delay', DELAY), ('poisoned', C.c_int)]


def build_bridge():
    (HERE / 'build').mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='host-bridge.', dir=HERE / 'build'))
    library = output / 'bridge.dylib'
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-O2', '-dynamiclib', str(HERE / 'spmi4-host-bridge.c'),
                    '-o', str(library)], check=True)
    lib = C.CDLL(str(library))
    lib.azahi_spmi4_io_size.restype = C.c_size_t
    if lib.azahi_spmi4_io_size() != C.sizeof(IO):
        raise RuntimeError('Host FFI layout mismatch')
    fn = lib.azahi_spmi4_transfer
    fn.argtypes = [C.POINTER(IO), C.c_uint, C.c_uint, C.c_uint,
                   C.POINTER(C.c_uint8), C.c_size_t, C.POINTER(C.c_uint8), C.c_size_t]
    fn.restype = C.c_int
    return lib


class Transport:
    def __init__(self, lib, proxy, clock=time.monotonic, sleep=time.sleep):
        self.lib, self.proxy, self.clock, self.sleep = lib, proxy, clock, sleep
        self.fatal = None
        self.deadline = 0
        self.callbacks = READ(self.read), WRITE(self.write), DELAY(self.delay)
        self.io = IO(None, *self.callbacks, 0)

    def guard(self):
        if self.fatal is not None:
            raise RuntimeError('Earlier transport fault')
        if self.clock() > self.deadline:
            raise TimeoutError('Proxy transaction deadline exceeded')

    def read(self, _context, reg):
        try:
            self.guard()
            if reg not in (0x200, 0x220):
                raise RuntimeError('Read outside FIFO allowlist')
            value = self.proxy.read32(BASE + reg)
            if value == 0xabad1dea:
                raise RuntimeError('Proxy MMIO read fault')
            return value
        except BaseException as error:
            self.fatal = error
            return 0xffffffff

    def write(self, _context, reg, value):
        try:
            self.guard()
            if reg != 0x210:
                raise RuntimeError('Write outside FIFO allowlist')
            self.proxy.write32(BASE + reg, value)
        except BaseException as error:
            self.fatal = error

    def delay(self, _context, usec):
        try:
            self.guard()
            if usec != 50:
                raise RuntimeError('Unexpected transport delay')
            self.sleep(usec / 1000000)
        except BaseException as error:
            self.fatal = error

    def transfer(self, op, address=0, out=b'', count=0):
        if self.fatal is not None or self.io.poisoned:
            raise RuntimeError('Transport latched; no retry or automatic recovery')
        self.deadline = self.clock() + 2
        data = (C.c_uint8 * len(out))(*out) if out else None
        result = (C.c_uint8 * count)() if count else None
        ret = self.lib.azahi_spmi4_transfer(C.byref(self.io), 12, op, address,
                                          data, len(out), result, count)
        if self.fatal is not None:
            self.io.poisoned = 1
            raise RuntimeError('Proxy transport failed; no further IO') from self.fatal
        if ret:
            raise RuntimeError(f'SPMI transaction failed: {ret}')
        return bytes(result) if count else b''


class HPM:
    ALLOWED = {0x00: 4, 0x03: 4, 0x08: 4, 0x09: 1,
               0x1a: 4, 0x20: 1, 0x3f: 2, 0x5f: 4}

    def __init__(self, transport, clock=time.monotonic, sleep=time.sleep):
        self.t, self.clock, self.sleep = transport, clock, sleep
        self.failed = False
        self.s0_attempted = False

    def select(self, reg):
        if self.failed or reg not in self.ALLOWED:
            raise RuntimeError('HPM request refused')
        try:
            self.t.transfer(0x80, out=bytes([reg]))
            deadline = self.clock() + 1
            for _ in range(100):
                value = self.t.transfer(0x60, count=1)[0]
                if value == reg:
                    size = self.t.transfer(0x60, address=0x1f, count=1)[0]
                    if not self.ALLOWED[reg] <= size <= 64:
                        raise RuntimeError('Unexpected logical register length')
                    return size
                if value != (reg | 0x80):
                    raise RuntimeError('Unexpected HPM selector; ownership/wake not proven')
                if self.clock() >= deadline:
                    break
                self.sleep(0.01)
            raise TimeoutError('HPM selector did not complete')
        except BaseException:
            self.failed = True
            raise

    def read(self, reg):
        self.select(reg)
        try:
            return self.t.transfer(0x20, address=0x20, count=self.ALLOWED[reg])
        except BaseException:
            self.failed = True
            raise

    def snapshot(self):
        # Nonzero selector first: a sleeping device returning reg0=0 cannot
        # masquerade as completed selection of the VID logical register.
        return {f'{r:02x}': self.read(r).hex() for r in (3, 0, 0x1a, 0x20, 0x3f, 0x5f)}

    def enter_s0(self):
        if self.failed or self.s0_attempted:
            raise RuntimeError('S0 attempt refused')
        self.s0_attempted = True
        try:
            if self.read(3) != b'APP ':
                raise RuntimeError('Controller not in application mode')
            # Reject zero/all-ones identity without guessing an Apple/TI VID.
            vid = int.from_bytes(self.read(0), 'little')
            if vid in (0, 0xffffffff):
                raise RuntimeError('Invalid controller vendor identity')
            status = int.from_bytes(self.read(0x1a), 'little')
            if status & ((1 << 16) | (1 << 28) | (1 << 29)):
                raise RuntimeError('PD controller reports power fault/warning')
            state = self.read(0x20)[0]
            if state == 0:
                return 'already-S0; no task written'
            if state not in (3, 4, 5):
                raise RuntimeError('Unknown system power state')
            if self.read(8) not in (bytes(4), b'!CMD'):
                raise RuntimeError('PD task slot busy; no override')
            # Two fixed <=4-byte writes only, following pinned tipd SSPS path.
            self.select(9)
            self.t.transfer(0, address=0xa0, out=b'\0')
            self.select(8)
            self.t.transfer(0, address=0xa0, out=b'SSPS')
            deadline = self.clock() + 2
            for _ in range(100):
                command = self.read(8)
                if command == b'!CMD':
                    raise RuntimeError('SSPS task rejected')
                if command == bytes(4):
                    break
                if command != b'SSPS':
                    raise RuntimeError('PD task changed unexpectedly')
                if self.clock() >= deadline:
                    raise TimeoutError('SSPS did not complete')
                self.sleep(0.01)
            else:
                raise TimeoutError('SSPS attempt limit')
            if self.read(9)[0] != 0:
                raise RuntimeError('SSPS result is not success')
            if self.read(0x20) != b'\0':
                raise RuntimeError('S0 state not confirmed')
            return 'S0 readback confirmed; USB not yet tested'
        except BaseException:
            self.failed = True
            raise


def verify_tree(tree):
    if tree.model != 'Mac17,9' or tree.target_type != 'J714s':
        raise RuntimeError('Wrong target model')
    n = tree['/arm-io/nub-spmi-a1']
    if n._properties['gen'] != 4 or n.get_reg(0) != (BASE, 0x4000):
        raise RuntimeError('Wrong controller generation/resource')
    h = tree['/arm-io/nub-spmi-a1/hpm2']
    if (h._properties['port-location'] != 'right' or
            h._properties['port-number'] != 3 or
            struct.unpack_from('<I', h._properties['reg'])[0] != 12 or
            'usbc,sn201202x,spmi' not in h.compatible):
        raise RuntimeError('Wrong HPM port/slave')
    p = tree['/arm-io/pmgr']
    group = p.getprop('ps-groups')[2]
    matches = [d for d in p.devices if d.id2 == 232]
    if (group.reg != 9 or group.offset != 0 or p.get_reg(9)[0] != 0x288300000 or
            len(matches) != 1 or matches[0].name != 'NUB_SPMI_A1' or
            matches[0].group != 2 or matches[0].offset != 0x68 or matches[0].flags.no_ps):
        raise RuntimeError('Wrong controller power mapping')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--status', action='store_true')
    mode.add_argument('--probe', action='store_true')
    mode.add_argument('--s0', action='store_true')
    parser.add_argument('--device')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if not (args.status or args.probe or args.s0):
        print('OFFLINE ONLY. Explicit mode, serial device and new receipt required for target access.')
        return
    if not args.device or not args.device.startswith('/dev/cu.usbmodem') or not args.receipt:
        parser.error('Explicit proxy serial device and fresh private receipt required')
    if args.receipt.exists():
        parser.error('Receipt already exists; refuse overwrite')
    image = (ROOT / 'standalone-ssdroot-usb-files-v4-20260913.bin').read_bytes()
    if hashlib.sha256(image).hexdigest() != SOURCE_SHA:
        raise RuntimeError('Known loader image hash mismatch')
    sys.path[:0] = [str(ROOT / 'pylib'), str(ROOT / 'proxy-kit/proxyclient')]
    from m1n1.proxy import UartInterface, M1N1Proxy
    from m1n1.tgtypes import BootArgs_r3
    from m1n1.adt import load_adt
    # Build on host before opening a serial device.
    lib = build_bridge() if not args.status else None
    report = {'mode': 's0' if args.s0 else 'probe' if args.probe else 'status',
              'disk_writes': False, 'boot_changed': False, 'network_verified': False}
    iface = None
    def expired(_signum, _frame):
        raise TimeoutError('Whole proxy diagnostic exceeded 90 seconds')
    old_alarm_handler = signal.signal(signal.SIGALRM, expired)
    signal.alarm(90)
    try:
        iface = UartInterface(args.device)
        iface.dev.timeout = iface.dev.write_timeout = 3
        iface.tty_enable = False
        iface.nop()
        proxy = M1N1Proxy(iface)
        base = proxy.get_base()
        if proxy.get_chipid() != 0x6050 or not 0x10000000000 <= base < 0x11000000000:
            raise RuntimeError('Unexpected proxy chip/base')
        if iface.readmem(base, 0x840) != image[:0x840]:
            raise RuntimeError('Unexpected loader code')
        ba_addr, rev = proxy.get_bootargs_rev()
        if rev != 3 or not base < ba_addr < 0x11000000000:
            raise RuntimeError('Unexpected bootargs')
        ba = iface.readstruct(ba_addr, BootArgs_r3)
        address = ba.devtree - ba.virt_base + ba.phys_base
        if not (0 < ba.devtree_size < 1 << 20 and
                ba.phys_base <= address < address + ba.devtree_size <= ba.top_of_kernel_data):
            raise RuntimeError('Unexpected ADT bounds')
        tree = load_adt(iface.readmem(address, ba.devtree_size))
        verify_tree(tree)
        report['identity_verified'] = True
        power = proxy.read32(POWER)
        report['power'] = hex(power)
        print('POWER', hex(power), flush=True)
        if power == 0xabad1dea or power & 0xff != 0xff or power & ((1 << 31) | (1 << 10) | (1 << 11)):
            raise RuntimeError('Controller power not active/healthy; no FIFO access')
        status = proxy.read32(BASE + 0x200)
        report['fifo'] = hex(status)
        print('FIFO', hex(status), flush=True)
        if status & 0xc0ffc0ff != 0x40004000:
            raise RuntimeError('FIFO not idle; do not flush or retry')
        if not args.status:
            t = Transport(lib, proxy)
            t.transfer(0x13)
            time.sleep(0.1)
            hpm = HPM(t)
            report['before'] = hpm.snapshot()
            print('HPM_BEFORE', json.dumps(report['before']), flush=True)
            if args.s0:
                report['s0_result'] = hpm.enter_s0()
                time.sleep(0.1)
                report['after'] = hpm.snapshot()
                print('HPM_AFTER', json.dumps(report['after']), flush=True)
        report['success'] = True
    except BaseException as error:
        report['success'] = False
        report['error_type'] = type(error).__name__
        report['error'] = str(error)
        raise
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_alarm_handler)
        if iface:
            iface.dev.close()
        with args.receipt.open('x') as output:
            json.dump(report, output, indent=2)
    print('Proxy remains parked. No boot, disk write, IRQ mask or reset was issued.')


if __name__ == '__main__':
    main()
