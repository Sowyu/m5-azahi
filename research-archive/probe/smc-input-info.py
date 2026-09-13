#!/usr/bin/env python3
"""Bounded SMC handshake and read-only input-key discovery from proxy mode."""
import time
from m1n1.setup import p, u
from m1n1.fw.smc import SMCClient, SMCError


class TimedSMC(SMCClient):
    def __init__(self, *args):
        super().__init__(*args)
        self.deadline = time.monotonic() + 10

    def work(self):
        if time.monotonic() > self.deadline:
            raise TimeoutError("SMC did not respond within the diagnostic deadline")
        return super().work()

    def send(self, msg0, msg1):
        while self.asc.INBOX_CTRL.reg.FULL:
            if time.monotonic() > self.deadline:
                raise TimeoutError("SMC inbox stayed full")
        self.asc.INBOX0.val = msg0
        self.asc.INBOX1.val = msg1


base, _ = u.adt["arm-io/smc"].get_reg(0)
print(f"SMC base {base:#x}", flush=True)
smc = TimedSMC(u, base)
smc.start()
smc.start_ep(0x20)
print(f"SMC_READY shmem={smc.smcep.shmem:#x}", flush=True)
for key in ("gP1c", "gP1d", "gp1c", "gp1d", "pcIO"):
    try:
        print(f"KEY {key} {smc.smcep.get_key_info(key)}", flush=True)
    except SMCError as error:
        print(f"KEY {key} absent: {error}", flush=True)
print("SMC_INPUT_SURVEY_DONE", flush=True)
