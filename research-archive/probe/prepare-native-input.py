#!/usr/bin/env python3
"""Apply only the already-verified J714s MTP access filter in fresh proxy mode.

Run before chainloading the native input image, with no guest/client active.
This does not touch SSD, GPU, CPU startup, or loader code.
"""
import os
import signal
import sys

signal.alarm(20)
sys.path[:0] = ["/PRIVATE-USER/azahi/lib", "/PRIVATE-USER/azahi/proxyclient"]
os.environ["M1N1DEVICE"] = "/dev/cu.usbmodemPRIVATE-SERIAL-REMOVED"
from m1n1.proxy import UartInterface, M1N1Proxy
from m1n1.proxyutils import ProxyUtils, bootstrap_port

iface = UartInterface()
iface.dev.timeout = 3
iface.dev.write_timeout = 3
try:
    proxy = M1N1Proxy(iface)
    bootstrap_port(iface, proxy)
    util = ProxyUtils(proxy, heap_size=16 << 20)
    assert util.adt["/chosen"].chip_id == 0x6050
    assert util.adt["/arm-io/dart-mtp"].get_reg(0) == (0x294800000, 0xc000)
    for address in (0x288300080, 0x288300088):
        value = proxy.read32(address)
        print(f"MTP_POWER {address:#x}={value:#x}", flush=True)
        assert value != 0xabad1dea and (value >> 4) & 15 == 15
    result = proxy.dapf_init("/arm-io/dart-mtp")
    assert result == 0, result
    proxy.nop()
    print("NATIVE_MTP_FILTER_READY", flush=True)
finally:
    iface.dev.close()
    signal.alarm(0)
