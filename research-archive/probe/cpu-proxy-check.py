#!/usr/bin/env python3
"""Fresh-proxy T6050 CPU inventory and optional existing-API WFE start test.

Never run while a guest or another proxy client owns the connection. No
source/binary patching, register scans, disk access, or unbounded SMP calls.
The optional start uses the installed bootloader's own bounded startup path.
"""
import argparse
import hashlib
import os
from pathlib import Path
import signal
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--offline", action="store_true")
parser.add_argument("--start-existing", action="store_true")
parser.add_argument("--verify-v5", action="store_true",
                    help="Require pristine V5 reset/runtime vectors and unused diagnostic state")
parser.add_argument("--read-start-status", action="store_true",
                    help="Read only the exact start registers already used by the loader")
parser.add_argument("--read-core-power", action="store_true",
                    help="Read ADT-identified CPU/cluster power states; no power writes")
parser.add_argument("--read-reset-status", action="store_true",
                    help="Read only CPU0/1 impl+0x100 used by the existing stop path")
parser.add_argument("--read-apsc", action="store_true",
                    help="Read three source-resolved APSC controls; no control writes")
parser.add_argument("--read-ctrr", action="store_true",
                    help="Read the three exact EL2 registers identified by upstream PR657")
parser.add_argument("--verify-ctrr-wfi", action="store_true",
                    help="Verify original WFI filler in the exact 48KiB CTRR range after a physical cycle")
args = parser.parse_args()
sys.path[:0] = ["/PRIVATE-USER/azahi/lib", "/PRIVATE-USER/azahi/proxyclient"]
from m1n1.adt import load_adt

def inventory(adt):
    if adt["/chosen"].chip_id != 0x6050:
        raise RuntimeError("Only T6050 is in scope")
    nodes = list(adt["/cpus"])
    if len(nodes) != 18:
        raise RuntimeError("Unexpected CPU count")
    for index, node in enumerate(nodes):
        expected_reg = (index // 6) * 256 + index % 6
        if node.cpu_id != index or node.reg != expected_reg:
            raise RuntimeError("Unexpected six-core cluster topology")
        if node.getprop("function-enable_core").args[0] != 1 << index:
            raise RuntimeError("Unexpected CPU enable mask")
        impl = node.cpu_impl_reg[0]
        expected_impl = 0x210050000 + (index // 6) * 0x1000000 + (index % 6) * 0x100000
        if impl != expected_impl:
            raise RuntimeError("Unexpected CPU implementation register")
        print(f"CPU_MAP id={index} mpidr={node.reg:#x} impl={impl:#x} "
              f"enable={1<<index:#x} legacy_enable={1<<(4*(index//6)+index%6):#x}", flush=True)
    pmgr = adt["/arm-io/pmgr"].get_reg(0)
    if pmgr != (0x280600000, 0x1fc000):
        raise RuntimeError("Unexpected PMGR range")
    print(f"PMGR_ADT_RANGE base={pmgr[0]:#x} length={pmgr[1]:#x}; not a safe scan range", flush=True)
    return nodes

if args.offline:
    inventory(load_adt((Path(__file__).resolve().parent.parent / "adt-real-t6050.bin").read_bytes()))
    print("CPU_MAP_OFFLINE_PASS")
    raise SystemExit(0)

signal.alarm(35)
os.environ["M1N1DEVICE"] = "/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED"
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port
iface = UartInterface()
iface.dev.timeout = 3
iface.dev.write_timeout = 3
try:
    proxy = M1N1Proxy(iface)
    bootstrap_port(iface, proxy)
    util = ProxyUtils(proxy, heap_size=16 * 1024 * 1024)
    nodes = inventory(util.adt)
    print(f"BOOTLOADER_BASE {util.base:#x}", flush=True)
    print("CPU_FEATURES", util.cpu_features, flush=True)
    print(f"BOOT_CPU_MPIDR {util.mrs('MPIDR_EL1'):#x}", flush=True)
    if args.verify_v5:
        image = (Path(__file__).resolve().parent / "m1n1-smp-diag-v5-20260906.bin").read_bytes()
        if hashlib.sha256(image).hexdigest() != "7e90e916d09dd9ef7fd7decb971091bfa62984027735f542e200d2a8179b32ef":
            raise RuntimeError("V5 local artifact mismatch")
        if iface.readmem(util.base, 0x840) != image[:0x840]:
            raise RuntimeError("Resident V5 reset/entry mismatch")
        if iface.readmem(util.base + 0x2a800, 0x800) != image[0x2a800:0x2b000]:
            raise RuntimeError("Resident V5 runtime vectors mismatch")
        if util.mrs('MPIDR_EL1') != 0x80040000 or util.mrs('CurrentEL') != 8:
            raise RuntimeError("Unexpected boot CPU/exception level")
        if util.mrs('VBAR_EL1') != util.base + 0x2a800:
            raise RuntimeError("V5 runtime VBAR mismatch")
        if proxy.read8(util.base + 0xe1890) or proxy.read32(util.base + 0xe1888):
            raise RuntimeError("V5 diagnostic state already used")
        print("V5_RESIDENT_IDENTITY_AND_UNUSED_STATE_VERIFIED", flush=True)
    for index in (0, 1, 6, 12):
        value = proxy.read64(nodes[index].cpu_impl_reg[0])
        if value & 0xffffffff == 0xabad1dea:
            raise RuntimeError("RVBAR read fault; refusing startup")
        print(f"CPU_RVBAR id={index} value={value:#x} locked={bool(value&1)}", flush=True)
    before = [index for index in range(18) if proxy.smp_is_alive(index)]
    print("CPU_ALIVE_BEFORE", before, flush=True)
    if args.read_ctrr or args.verify_ctrr_wfi:
        if util.mrs('CurrentEL') != 8:
            raise RuntimeError('CTRR M4 registers require EL2')
        ctrr_values = {}
        for name, reg in (('LWR', (3, 0, 11, 1, 0)),
                          ('UPR', (3, 0, 11, 1, 1)),
                          ('CTL', (3, 0, 11, 1, 4))):
            value = util.mrs(reg)
            ctrr_values[name] = value
            print(f'CTRR_M4_{name}_EL2 {reg}={value:#x}', flush=True)
        if args.verify_ctrr_wfi:
            start, end = ctrr_values['LWR'], ctrr_values['UPR'] + 4096
            if (start & 4095 or end - start != 48 * 1024 or ctrr_values['CTL'] != 0
                    or not 0x10000000000 <= util.base < start < end <= util.heap_base):
                raise RuntimeError('Unexpected firmware WFI range; no RAM read')
            data = iface.readmem(start, end - start)
            if data != bytes.fromhex('7f2003d5') * (len(data) // 4) or len(data) != 49152:
                raise RuntimeError('Firmware WFI filler differs: not a clean diagnostic state')
            print(f'FIRMWARE_WFI_FILLER_VERIFIED {start:#x}..{end:#x} sha256={hashlib.sha256(data).hexdigest()}', flush=True)
    if args.read_apsc:
        for cluster, index in enumerate((0x10, 0x1a, 0x24)):
            base, length = util.adt['/arm-io/pmgr'].get_reg(index)
            if (base, length) != (0x210e20000 + cluster * 0x1000000, 0x12e8):
                raise RuntimeError('Unexpected APSC mapping')
            value = proxy.read64(base + 0x20)
            if value & 0xffffffff == 0xabad1dea:
                raise RuntimeError('APSC read fault')
            print(f'APSC_READ cluster={cluster} address={base+0x20:#x} value={value:#x}', flush=True)
    if args.read_start_status:
        for offset in (0x88004, 0x88008, 0x8800c, 0x88010):
            address = 0x280600000 + offset
            value = proxy.read32(address)
            print(f"CPU_START_READ {address:#x}={value:#x}", flush=True)
            if value == 0xabad1dea:
                raise RuntimeError("CPU start register read fault; stopping without writes")
    if args.read_core_power:
        pmgr = util.adt["/arm-io/pmgr"]
        group = pmgr.getprop("ps-groups")[0]
        if group.reg != 0 or group.offset != 0:
            raise RuntimeError("Unexpected CPU PMGR group")
        targets = {1: ("MCPU0_0", 0), 2: ("MCPU0_1", 8),
                   7: ("MCPU1_0", 0x30), 13: ("PCPU_0", 0x60),
                   19: ("MCPM0", 0x90), 20: ("MCPM1", 0x98),
                   21: ("PCPM", 0xa0)}
        selected = []
        for ident, (name, offset) in targets.items():
            match = [dev for dev in pmgr.devices if dev.id2 == ident]
            if len(match) != 1:
                raise RuntimeError("CPU power device missing/duplicated")
            dev = match[0]
            if (dev.name != name or dev.group != 0 or dev.offset != offset
                    or dev.flags.no_ps or list(dev.parents_un.u16id.parents) != [0, 0]):
                raise RuntimeError("Unexpected CPU power device identity")
            selected.append((name, 0x280600000 + offset))
        for name, address in selected:
            value = proxy.read32(address)
            print(f"CPU_POWER_READ {name} {address:#x}={value:#x} "
                  f"target={value & 15} actual={(value >> 4) & 15} "
                  f"auto={bool(value & (1 << 28))}", flush=True)
            if value == 0xabad1dea:
                raise RuntimeError("CPU power register read fault; no writes")
    if args.read_reset_status:
        for index in (0, 1):
            # Only read a powered CPU, not an off cluster or sparse bank.
            power = proxy.read32(0x280600000 + 8 * index)
            if power == 0xabad1dea or ((power >> 4) & 15) != 15:
                raise RuntimeError("CPU is not reported active; refusing status read")
            address = nodes[index].cpu_impl_reg[0] + 0x100
            value = proxy.read64(address)
            print(f"CPU_IMPL_STATUS id={index} {address:#x}={value:#x}", flush=True)
            if value & 0xffffffff == 0xabad1dea:
                raise RuntimeError("CPU status register read fault; no writes")
    if args.start_existing:
        if before:
            raise RuntimeError("Not a fresh unused SMP table; refusing restart")
        print("CPU_TEST_ENABLE_WFE_BEFORE_FIRST_START", flush=True)
        proxy.smp_set_wfe_mode(True)
        print("CPU_TEST_EXISTING_START_BEGIN", flush=True)
        proxy.smp_start_secondaries()
        after = [index for index in range(18) if proxy.smp_is_alive(index)]
        print("CPU_ALIVE_AFTER", after, flush=True)
        print("CPU_TEST_EXISTING_START_DONE; no execute-and-return claim", flush=True)
    proxy.nop()
    print("CPU_CHECK_PROXY_ALIVE", flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
