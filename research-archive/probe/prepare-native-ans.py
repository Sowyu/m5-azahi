"""Bounded J714s ANS prerequisite check; no NVMe init or SSD data commands.

Only the exact APCIE_SYS_ST0 link activation already verified in the HV is
allowed. Unlike prepare-ans this requires no HV and installs no MMIO hooks.
"""
import time

DOMAINS = (("FAB6_SOC", 0x280900138), ("APCIE_ST0", 0x280900128),
           ("ANS", 0x280900140), ("APCIE_SYS_ST0", 0x280900150))


def prepare(proxy, util, activate=False):
    if util.adt["/chosen"].chip_id != 0x6050:
        raise RuntimeError("Not T6050")
    devices = {d.name.upper(): d for d in util.adt["/arm-io/pmgr"].devices}
    for name, address in DOMAINS:
        if util.adt.pmgr_dev_get_addr(devices[name]) != address:
            raise RuntimeError("ANS power identity mismatch")
    ans = util.adt["/arm-io/ans"]
    if [ans.get_reg(i)[0] for i in (0, 3, 9)] != [0x419600000, 0x41dcc0000, 0x45dcc0000]:
        raise RuntimeError("ANS BAR identity mismatch")
    if util.adt["/arm-io/sart-ans"].get_reg(0) != (0x41dc50000, 0xc000):
        raise RuntimeError("SART identity mismatch")
    # Validate every parent before considering any write.
    states = {address: proxy.read32(address) for _, address in DOMAINS}
    for name, address in DOMAINS:
        value = states[address]
        print(f"NATIVE_ANS_POWER {name} {address:#x}={value:#x}", flush=True)
        if value == 0xabad1dea:
            raise RuntimeError("PMGR read fault")
        if (value >> 4) & 15 != 15:
            if not (activate and name == "APCIE_SYS_ST0" and value == 0x1000030f):
                raise RuntimeError("Unverified ANS power state; no writes")
    address = DOMAINS[-1][1]
    if (states[address] >> 4) & 15 != 15:
        print("NATIVE_ANS_LINK_ACTIVATE exact verified link only", flush=True)
        proxy.mask32(address, (1 << 28) | (1 << 9) | (1 << 8) | 15, 15)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            value = proxy.read32(address)
            if value == 0xabad1dea:
                raise RuntimeError("ANS link read fault")
            if (value >> 4) & 15 == 15:
                break
            time.sleep(.01)
        else:
            raise RuntimeError("ANS link activation timeout")
    # Known ANS coprocessor run control only; no cold-reset fallback.
    value = proxy.read32(0x419600044)
    print(f"NATIVE_ANS_COPROC_RUN {value:#x}", flush=True)
    if value == 0xabad1dea or not value & 16:
        raise RuntimeError("ANS firmware not already running; refusing reset")
    proxy.nop()
    print("NATIVE_ANS_WARM_HANDOFF_READY", flush=True)
