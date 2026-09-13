#!/usr/bin/env python3
"""Run one input bring-up guest with persistent stop handling and separate logs.

Uses the existing live kit; does not patch its sources. Chainload the known-good
host image first. SIGINT/SIGUSR2 request EXIT_GUEST at a hypervisor callback.
There are no automatic retries. Unexpected guest faults also exit the guest.
"""
import argparse
import glob
import importlib.util
import os
from pathlib import Path
import signal
import struct
import sys
import threading

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("guest", type=Path)
parser.add_argument("logdir", type=Path, help="New directory, one per boot")
parser.add_argument("--kit", type=Path, default=Path("/PRIVATE-USER/azahi"))
parser.add_argument("--share", type=Path, help="Optional directory exported as inputfiles over 9p")
parser.add_argument("--prepare-mtp", action="store_true", help="Initialize only the MTP DAPF before boot")
parser.add_argument("--trace-input", action="store_true", help="Trace known MTP mailbox and DART windows")
parser.add_argument("--prepare-mtp-tunables", action="store_true", help="Apply this board's MTP DART tunables")
parser.add_argument("--prepare-ans", action="store_true", help="Board-checked ANS power setup and guest PMGR shadows")
parser.add_argument("--activate-ans-link", action="store_true", help="Force only the observed auto-gated ANS link ACTIVE")
parser.add_argument("--ans-zero-based-limit", action="store_true", help="Test 63 rather than 64 in ANS pending-command limit fields")
args = parser.parse_args()
if args.activate_ans_link and not args.prepare_ans:
    parser.error("--activate-ans-link requires --prepare-ans")
if args.ans_zero_based_limit and not args.prepare_ans:
    parser.error("--ans-zero-based-limit requires --prepare-ans")
if args.logdir.exists():
    parser.error("logdir already exists; choose a new run directory")
ports = sorted(glob.glob("/dev/cu.usbmodem*"))
if len(ports) != 2:
    parser.error(f"Expected exactly two M5 CDC ports, found {ports}")
if not args.guest.is_file():
    parser.error("Guest image not found")
sys.path[:0] = [str(args.kit / "lib"), str(args.kit / "proxyclient")]
os.environ["M1N1DEVICE"] = ports[0]
os.environ["PATH"] = "/PRIVATE-USER/.local/bin:" + os.environ.get("PATH", "")

from m1n1.proxy import UartInterface, M1N1Proxy, EXC_RET
from m1n1.proxyutils import ProxyUtils, bootstrap_port
from m1n1.hv import HV
from m1n1.hv.virtio import Virtio9PTransport
from m1n1.utils import irange
from serial import Serial

args.logdir.mkdir(parents=True)
(args.logdir / "host.pid").write_text(f"{os.getpid()}\n")
console = Serial(ports[1], 115200, timeout=0.2)
finished = threading.Event()


def capture_console():
    with (args.logdir / "console.log").open("xb", buffering=0) as output:
        while not finished.is_set():
            data = console.read(65536)
            if data:
                output.write(data)


reader = threading.Thread(target=capture_console, daemon=True)
reader.start()
iface = None
try:
    iface = UartInterface()
    iface.dev.write_timeout = 3
    proxy = M1N1Proxy(iface)
    bootstrap_port(iface, proxy)
    util = ProxyUtils(proxy, heap_size=128 * 1024 * 1024)
    hv = HV(iface, proxy, util)
    requests = {"snapshot": False}

    def stop_guest(signum, frame):
        if not hv.started:
            raise SystemExit("Stopped before guest execution; no retry")
        hv._handle_sigint()

    def snapshot_guest(signum, frame):
        if hv.started:
            requests["snapshot"] = True
            hv._handle_sigint()

    def exit_at_callback(*unused, **kwargs):
        if requests["snapshot"] and not hv.is_fault:
            requests["snapshot"] = False
            print("INPUT_SNAPSHOT_BEGIN", flush=True)
            for base, offsets in (
                (0x294600000, (0x44, 0x48, 0x8110, 0x8114)),
                (0x294800000, (0, 4, 8, 12, 0x100, 0x104, 0x170, 0x174,
                               0x20c, 0x220, 0x224, 0x300, 0x308, 0x310,
                               0xc00, 0x1000, 0x1004, 0x1400, 0x1404)),
            ):
                for offset in offsets:
                    value = proxy.read32(base + offset)
                    print(f"INPUT_REG {base + offset:#x}={value:#010x}", flush=True)
                    if value == 0xabad1dea:
                        raise RuntimeError("Register read fault; stopping snapshot")
            print("INPUT_SNAPSHOT_END; resuming guest", flush=True)
            return EXC_RET.HANDLED
        print("Returning EXIT_GUEST from hypervisor callback", flush=True)
        return EXC_RET.EXIT_GUEST

    # run_shell's upstream SIGUSR2 handler exists only while IN its shell.
    # Install ours for the entire guest lifetime, before hv.start().
    hv.run_shell = exit_at_callback
    signal.signal(signal.SIGUSR2, stop_guest)
    signal.signal(signal.SIGTERM, stop_guest)
    signal.signal(signal.SIGUSR1, snapshot_guest)
    if args.prepare_ans:
        spec = importlib.util.spec_from_file_location("prepare_ans", Path(__file__).with_name("prepare-ans.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.prepare(proxy, util, hv, activate_link=args.activate_ans_link,
                       zero_based=args.ans_zero_based_limit)
    hv.init()
    for cpu in list(hv.adt["/cpus"]):
        if cpu.name != "cpu0":
            del hv.adt[f"/cpus/{cpu.name}"]
    if args.share:
        hv.attach_virtio(Virtio9PTransport(root=str(args.share.resolve()), tag="inputfiles"))
    with (args.logdir / "hv.log").open("x") as logfile:
        hv.set_logfile(logfile)
        hv.load_raw(args.guest.read_bytes(), 0x800)
        if args.trace_input:
            # Trace only accesses made by the guest; never scan unknown offsets.
            hv.trace_range(irange(0x294600040, 0x10), name="MTP-CPU")
            hv.trace_range(irange(0x294608800, 0x40), name="MTP-MAILBOX")
            # Error-IRQ reads can flood the trace transport. Writes capture
            # page-table/stream setup without logging the interrupt storm.
            hv.trace_range(irange(0x294800000, 0x1800), read=False, name="MTP-DART")
        if args.prepare_mtp:
            result = proxy.dapf_init("/arm-io/dart-mtp")
            if result != 0:
                raise RuntimeError(f"MTP access-filter initialization failed: {result}")
        if args.prepare_mtp_tunables:
            node = util.adt["/arm-io/dart-mtp"]
            base, size = node.get_reg(0)
            entries = list(struct.iter_unpack("<IIQQ", node.dart_tunables_instance_0))
            # This option is board-specific. Refuse changed or unexpected data.
            assert base == 0x294800000 and size == 0xc000
            assert [entry[0] for entry in entries] == [0x20c, 0x220, 0x224, 0x300, 0x308, 0x310]
            assert all(width == 4 and value & ~mask == 0 for _, width, mask, value in entries)
            for offset, _, mask, value in entries:
                old = proxy.read32(base + offset)
                print(f"MTP_TUNABLE before {offset:#x}={old:#x} mask={mask:#x} value={value:#x}", flush=True)
            result = proxy.tunables_apply_local("/arm-io/dart-mtp", "dart-tunables-instance-0", 0)
            if result != 0:
                raise RuntimeError(f"MTP DART tunable initialization failed: {result}")
            for offset, _, mask, value in entries:
                actual = proxy.read32(base + offset)
                print(f"MTP_TUNABLE after {offset:#x}={actual:#x}", flush=True)
                if actual & mask != value:
                    raise RuntimeError(f"MTP DART tunable readback mismatch at {offset:#x}")
        print(f"Host PID {os.getpid()}; request clean exit with SIGINT or SIGUSR2", flush=True)
        hv.start()
        print("Guest returned; checking proxy", flush=True)
        iface.dev.timeout = 3
        proxy.nop()
        print("PROXY_RESPONDED_AFTER_GUEST; reconnect still requires separate verification", flush=True)
finally:
    finished.set()
    reader.join(timeout=2)
    console.close()
    if iface is not None:
        iface.dev.close()
