#!/usr/bin/env python3
"""Bounded evdev capture of the built-in devices; releases grabs on exit."""
import argparse
from collections import Counter
import fcntl
import glob
import os
from pathlib import Path
import select
import struct
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--seconds", type=int, default=60)
a = p.parse_args()
if not 1 <= a.seconds <= 180:
    p.error("Use a capture duration from 1 to 180 seconds")
devices = {}
counts = Counter()
samples = Counter()
event = struct.Struct("llHHi")
try:
    for path in sorted(glob.glob("/dev/input/event*")):
        name = (Path("/sys/class/input") / Path(path).name / "device/name").read_text().strip()
        if name not in ("Apple MTP multi-touch", "Apple MTP keyboard"):
            continue
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        devices[fd] = name
        fcntl.ioctl(fd, 0x40044590, 1)
        print("CAPTURE_DEVICE", path, name, flush=True)
    if len(devices) != 2:
        raise RuntimeError("Expected both built-in input devices")
    print("INPUT_CAPTURE_READY", flush=True)
    end = time.monotonic() + a.seconds
    while time.monotonic() < end:
        for fd in select.select(list(devices), [], [], min(1, max(0, end-time.monotonic())))[0]:
            data = os.read(fd, event.size * 64)
            if not data or len(data) % event.size:
                raise RuntimeError("Incomplete evdev read")
            name = devices[fd]
            for _, _, typ, code, value in event.iter_unpack(data):
                counts[(name, typ, code)] += 1
                if typ == 1 or (typ == 3 and samples[name] < 30):
                    print("INPUT_EVENT", name, typ, code, value, flush=True)
                    samples[name] += 1
finally:
    for fd in devices:
        try:
            fcntl.ioctl(fd, 0x40044590, 0)
        finally:
            os.close(fd)
    for key, count in sorted(counts.items()):
        print("INPUT_COUNT", *key, count, flush=True)
    print("INPUT_CAPTURE_DONE", flush=True)
