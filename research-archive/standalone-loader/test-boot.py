#!/usr/bin/env python3
"""Pinned RAM-only chainload test; does NOT install a custom boot object.

Defaults to offline inspection. --run requires a verified fresh V5 session.
Uses the existing chainload implementation, with bounded input/target guards
and a one-way handoff instead of waiting for the new Linux to expose a proxy.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', action='store_true')
args = parser.parse_args()
spec = importlib.util.spec_from_file_location('bundle', HERE / 'build-bundle.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)
receipt = json.loads(bundle.OUTPUT.with_suffix('.json').read_text())
assert receipt['image_sha256'] == '866aea9d523152f0a0767cb7529be297f52ad4e64d94a70d0fe5bddf222a5a2a'
bundle.inspect(bundle.OUTPUT.read_bytes(), receipt)
original = Path('/PRIVATE-USER/azahi/proxyclient/tools/chainload.py')
source = original.read_bytes()
assert hashlib.sha256(source).hexdigest() == 'aebe6c30dc631b0fed366a65e40361b2e082af5812f1e3bde090e37de0fd2410'
code = source.decode()


def replace_once(old, new):
    global code
    assert code.count(old) == 1, old
    code = code.replace(old, new)


replace_once('new_base = u.base', '''
assert u.adt["/chosen"].chip_id == 0x6050
assert (u.mrs("MPIDR_EL1") & 0xffffff) == 0x40000
assert u.mrs("CurrentEL") == 8
assert not any(p.smp_is_alive(i) for i in range(18))
assert u.base & 0xfff == 0
assert iface.readmem(u.base, 0x840) == pathlib.Path("/PRIVATE-USER/azahi-port/probe/m1n1-smp-diag-v5-20260906.bin").read_bytes()[:0x840]
assert p.read8(u.base + 0xe1890) == 0 and p.read32(u.base + 0xe1888) == 0
new_base = 0x10400000000
''')
replace_once('image_addr = u.malloc(image_size)', '''
assert image_size <= 112 << 20
assert new_base == 0x10400000000 and new_base + image_size < 0x10408000000
assert entry == new_base + 0x800
assert u.ba.phys_base <= 0x1010a960000
assert u.ba.phys_base + u.ba.mem_size >= 0x10f4ab00000
image_addr = 0x10300000000
assert image_addr + image_size + 4096 < new_base
''')
replace_once('u.compressed_writemem(image_addr, image, True)', '''
for offset in range(0, len(image), 8 << 20):
    chunk = image[offset:offset + (8 << 20)]
    iface.writemem(image_addr + offset, chunk)
    assert iface.readmem(image_addr + offset + len(chunk) - 32, 32) == chunk[-32:]
    print(f"STANDALONE_RAM_TRANSFER {offset + len(chunk)}/{len(image)}", flush=True)
''')
# The dedicated one-core path must not change any locked secondary RVBAR.
rvbar_start = code.index('rvbar = entry & ~0xfff')
rvbar_end = code.index('u.push_adt()', rvbar_start)
code = code[:rvbar_start] + 'print("No secondary RVBAR writes; one-core high-RAM test")\n\n' + code[rvbar_end:]
replace_once('p.reload(stub.addr, new_base + bootargs_off, image_addr, new_base, image_size)',
             'p.request(p.P_VECTOR, stub.addr, new_base + bootargs_off, image_addr, new_base, image_size)')
replace_once('iface.nop()\nprint("Proxy is alive again")',
             'iface.dev.close()\nprint("STANDALONE_RAM_HANDOFF_SENT; inspect panel, not a persistent installation")')
compile(code, str(original), 'exec')
print('STANDALONE_TEST_BOOT_OFFLINE_PASS', receipt['image_sha256'], flush=True)
assert 'p.write64(addr, rvbar)' not in code
assert 'u.malloc(image_size)' not in code
if not args.run:
    raise SystemExit(0)
signal.alarm(180)
os.environ['M1N1DEVICE'] = '/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED'
sys.path[:0] = ['/PRIVATE-USER/azahi/lib', '/PRIVATE-USER/azahi/proxyclient']
sys.argv = [str(original), '-r', str(bundle.OUTPUT)]
exec(compile(code, str(original), 'exec'), {'__name__': '__main__', '__file__': str(original)})
signal.alarm(0)
