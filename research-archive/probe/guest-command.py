#!/usr/bin/env python3
"""Send one guest-console command with paced writes and a bounded USB timeout.

Does not read: boot-input.py owns console capture. Never opens the proxy port.
"""
import argparse
import glob
import os
import select
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("command")
args = parser.parse_args()
ports = sorted(glob.glob("/dev/cu.usbmodem*"))
if len(ports) != 2:
    parser.error(f"Expected two CDC ports, got {ports}")
payload = (args.command + "\n").encode()
fd = os.open(ports[1], os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK)
try:
    for value in payload:
        deadline = time.monotonic() + 3
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([], [fd], [], remaining)[1]:
                raise TimeoutError("Guest console is not accepting USB writes")
            try:
                if os.write(fd, bytes([value])) == 1:
                    break
            except BlockingIOError:
                continue
        time.sleep(0.01)
finally:
    os.close(fd)
print(f"Sent {len(payload)} bytes to {ports[1]}; inspect the runner's console.log")
