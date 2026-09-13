#!/usr/bin/env python3
"""Stop an orphaned guest after its host runner has died, without retrying boot.

Run only with no other proxy client. Discard trace traffic, validate a real
hypervisor callback packet, then request EXIT_GUEST. Never access target MMIO.
"""
import glob
import signal
import struct
import time
from serial import Serial
from m1n1.proxy import UartInterface, M1N1Proxy, EXC_RET

signal.alarm(15)
ports = sorted(glob.glob("/dev/cu.usbmodem*"))
assert len(ports) == 2, ports
with Serial(ports[0], 115200, timeout=0.2, write_timeout=1) as serial:
    iface = UartInterface(serial)
    serial.timeout = 0.2
    print("Requesting guest interrupt", flush=True)
    serial.write(b"!")
    pending = bytearray()
    deadline = time.monotonic() + 8
    found = False
    while time.monotonic() < deadline:
        pending.extend(serial.read(65536))
        while True:
            index = pending.find(b"\xff\x55\xaa\x04")
            if index < 0:
                pending = pending[-3:]
                break
            if len(pending) < index + 36:
                pending = pending[index:]
                break
            packet = pending[index:index + 36]
            pending = pending[index + 1:]
            if iface.checksum(packet[:-4]) != struct.unpack_from("<I", packet, 32)[0]:
                continue
            status, reason, code = struct.unpack_from("<iII", packet, 4)
            if status != 0 or reason not in (1, 2, 3):
                continue
            print(f"Validated hypervisor callback: reason={reason} code={code}", flush=True)
            found = True
            break
        if found:
            break
    if not found:
        raise TimeoutError("No validated hypervisor callback; no exit command sent")
    serial.timeout = 2
    proxy = M1N1Proxy(iface)
    proxy.exit(EXC_RET.EXIT_GUEST)
    print("EXIT_GUEST acknowledged", flush=True)
    # The abandoned hv_start RPC returns separately after P_EXIT's own ACK.
    iface.reply(iface.REQ_PROXY)
    print("Original hv_start response drained", flush=True)
    iface.nop()
    print("WIRE_NOP_AFTER_EXIT", flush=True)
