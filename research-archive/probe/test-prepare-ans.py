#!/usr/bin/env python3
"""Offline board-map and no-hardware-write test using the saved real ADT."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path[:0] = ["/PRIVATE-USER/azahi/lib", "/PRIVATE-USER/azahi/proxyclient"]
from m1n1.adt import load_adt

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("prepare_ans", root / "probe/prepare-ans.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
adt = load_adt((root / "adt-real-t6050.bin").read_bytes())

class Proxy:
    def __init__(self, off=None):
        self.off = off
    def read32(self, address):
        assert address in {a for _, a in m.DOMAINS}
        return 0 if address == self.off else 0xff
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected proxy operation: {name}")

class HV:
    def __init__(self):
        self.hooks = {}
    def map_essential(self):
        pass
    def map_hook(self, address, size, **callbacks):
        assert size == 4
        self.hooks[address] = callbacks
    def add_tracer(self, *args):
        pass

h = HV()
m.prepare(Proxy(), SimpleNamespace(adt=adt), h)
h.map_essential()
assert len(h.hooks) == 4
for address, callbacks in h.hooks.items():
    assert callbacks["read"](address, 0, 32) == 0xff
    callbacks["write"](address, 0, 0x100000ff, 32)
    assert callbacks["read"](address, 0, 32) == 0x100000ff
    callbacks["write"](address, 0, 0, 32)
    assert callbacks["read"](address, 0, 32) == 0
for _, address in m.DOMAINS:
    try:
        m.prepare(Proxy(address), SimpleNamespace(adt=adt), HV())
    except RuntimeError as error:
        assert "not ACTIVE" in str(error)
    else:
        raise AssertionError("Inactive power domain was not rejected")
print("PASS: real ADT addresses, four guest-only shadows, inactive-domain refusal, zero hardware writes")

class GatedLink(Proxy):
    def __init__(self):
        self.writes = []
    def read32(self, address):
        if address == 0x280900150 and not self.writes:
            return 0x1000030f
        return 0xff
    def mask32(self, address, clear, set_bits):
        assert (address, clear, set_bits) == (0x280900150, 0x1000030f, 15)
        self.writes.append((address, clear, set_bits))

g = GatedLink()
m.prepare(g, SimpleNamespace(adt=adt), HV(), activate_link=True)
assert len(g.writes) == 1
print("PASS: explicit gated-link activation performs exactly one expected write")

assert m.zero_based_limit(0x00400040) == 0x003f003f
for wrong in (0, 0x0040003f, 0xffffffff):
    try:
        m.zero_based_limit(wrong)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Unexpected limit was accepted")
print("PASS: exact zero-based limit transformation and unexpected-value rejection")

class LimitProxy(Proxy):
    def __init__(self):
        super().__init__()
        self.value = 0
        self.writes = []
    def read32(self, address):
        if address == 0x45dcc1210:
            return self.value
        return super().read32(address)
    def write32(self, address, value):
        assert address == 0x45dcc1210
        self.writes.append((address, value))
        self.value = value

p, h = LimitProxy(), HV()
m.prepare(p, SimpleNamespace(adt=adt), h, zero_based=True)
h.map_essential()
assert len(h.hooks) == 5
limit = h.hooks[0x45dcc1210]
limit["write"](0x45dcc1210, 0, [0x00400040], 32)
assert limit["read"](0x45dcc1210, 0, 32) == 0x003f003f
assert p.writes == [(0x45dcc1210, 0x003f003f)]
for args in ((0x45dcc1210, 0, 0, 32), (0x45dcc1210, 0, 0x00400040, 64),
             (0x45dcc1210, 4, 0x00400040, 32)):
    try:
        limit["write"](*args)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Invalid callback write accepted")
assert len(p.writes) == 1
for _, address in m.DOMAINS:
    h.hooks[address]["write"](address, 0, 15, 32)
    assert h.hooks[address]["read"](address, 0, 32) == 255
assert len(p.writes) == 1
print("PASS: limit callbacks, width/address rejection, and independent PMGR shadows")
