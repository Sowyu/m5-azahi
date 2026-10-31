#!/usr/bin/env python3
"""Read-only capture of DebugUSB KIS channel 0. Never writes to the device.
Reopens across target resets. Stops after --seconds."""
import argparse, os, select, time
ap = argparse.ArgumentParser()
ap.add_argument('--dev', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--seconds', type=int, default=900)
a = ap.parse_args()
end = time.time() + a.seconds
fd = None
with open(a.out, 'ab', buffering=0) as log:
    def note(s):
        log.write(f'\n[[{time.strftime("%H:%M:%S")} {s}]]\n'.encode())
    note('capture start')
    while time.time() < end:
        if fd is None:
            try:
                fd = os.open(a.dev, os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY)
                note('opened')
            except OSError:
                time.sleep(0.2)
                continue
        try:
            r, _, _ = select.select([fd], [], [], 1)
            if r:
                d = os.read(fd, 65536)
                if d:
                    log.write(d)
                else:
                    raise OSError('eof')
        except OSError as e:
            note(f'closed {e}')
            os.close(fd)
            fd = None
    note('capture end')
