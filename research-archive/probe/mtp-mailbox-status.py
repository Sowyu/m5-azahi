#!/usr/bin/env python3
"""Bounded post-guest MTP mailbox inspection; no shared-memory reads or writes.

Only known ASC offsets are accessed. Reading OUTBOX1 consumes queued messages.
Run only in proxy mode, with no other proxy client.
"""
import time
import signal
# Bound connection/bootstrap too: the live kit can otherwise block on USB writes.
signal.alarm(15)
from m1n1.setup import p, u

base, _ = u.adt["/arm-io/mtp"].get_reg(0)
assert base == 0x294600000
for offset in (0x44, 0x48, 0x8110, 0x8114):
    print(f"MTP {offset:#x}: {p.read32(base + offset):#x}", flush=True)
deadline = time.monotonic() + 3
count = 0
while time.monotonic() < deadline and count < 128:
    if p.read32(base + 0x8114) & (1 << 17):
        break
    msg = p.read64(base + 0x8830)
    tag = p.read64(base + 0x8838)
    print(f"MTP RX ep={tag & 0xff:#x} message={msg:#018x} tag={tag:#018x}", flush=True)
    count += 1
print(f"MTP_MAILBOX_SURVEY_DONE messages={count}", flush=True)
