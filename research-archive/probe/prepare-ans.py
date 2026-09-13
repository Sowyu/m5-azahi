"""Board-checked ANS power preparation and four guest-only PMGR shadows.

Imported by the one-shot runner. Never starts m1n1 NVMe or touches disk data.
Default is read-only. Explicit activation can force only the observed gated
APCIE_SYS_ST0 link on, after all its parents have been verified ACTIVE.
"""
import time

DOMAINS = (
    ("FAB6_SOC", 0x280900138),
    ("APCIE_ST0", 0x280900128),
    ("ANS", 0x280900140),
    ("APCIE_SYS_ST0", 0x280900150),
)


def zero_based_limit(value):
    if value != 0x00400040:
        raise RuntimeError(f"Unexpected pending-command value {value:#x}")
    return 0x003f003f


def prepare(proxy, util, hv, activate_link=False, zero_based=False):
    from m1n1.trace import TraceMode
    from m1n1.utils import irange

    if util.adt["/chosen"].chip_id != 0x6050:
        raise RuntimeError("ANS preparation is only verified for T6050")
    by_name = {d.name.upper(): d for d in util.adt["/arm-io/pmgr"].devices}
    for name, expected in DOMAINS:
        actual = util.adt.pmgr_dev_get_addr(by_name[name])
        if actual != expected:
            raise RuntimeError(f"{name}: unexpected ADT address {actual:#x}")
    ans = util.adt["/arm-io/ans"]
    if [ans.get_reg(i)[0] for i in (0, 3, 9)] != [0x419600000, 0x41dcc0000, 0x45dcc0000]:
        raise RuntimeError("Unexpected ANS register map")
    shadow = {}
    for name, address in DOMAINS:
        value = proxy.read32(address)
        if value == 0xabad1dea:
            raise RuntimeError("PMGR read fault")
        print(f"ANS_POWER before {name} {address:#x}={value:#x}", flush=True)
        if value >> 4 & 15 != 15:
            if not activate_link or name != "APCIE_SYS_ST0" or value != 0x1000030f:
                raise RuntimeError(f"{name} is not ACTIVE; no PMGR writes performed")
            # Exact observed cold state: target ACTIVE, actual OFF, auto mode.
            # Parents APCIE_ST0 and ANS were checked in the preceding loop.
            print("ANS_LINK_FORCE_ACTIVE: clearing auto-gate, target ACTIVE", flush=True)
            proxy.mask32(address, (1 << 28) | (1 << 9) | (1 << 8) | 15, 15)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                value = proxy.read32(address)
                if value == 0xabad1dea:
                    raise RuntimeError("ANS link readback fault")
                if value >> 4 & 15 == 15:
                    break
                time.sleep(.01)
            else:
                raise RuntimeError("ANS link activation timed out; stopping")
        shadow[address] = value
        print(f"ANS_POWER active {name}={value:#x}", flush=True)

    original = hv.map_essential

    def install():
        original()

        def read(base, off, width):
            if width != 32 or base + off not in shadow:
                raise RuntimeError("Unexpected ANS PMGR read")
            return shadow[base + off]

        def write(base, off, data, width):
            if isinstance(data, list):
                if len(data) != 1:
                    raise RuntimeError("Unexpected wide PMGR write")
                data = data[0]
            if width != 32 or base + off not in shadow:
                raise RuntimeError("Unexpected ANS PMGR write")
            shadow[base + off] = (data & 0xfffffc0f) | ((data & 15) << 4)
            print(f"ANS_PMGR_SHADOW {base+off:#x} <- {data:#x}", flush=True)

        for _, address in DOMAINS:
            hv.map_hook(address, 4, read=read, write=write)
            hv.add_tracer(irange(address, 4), "ANS PMGR SHADOW", TraceMode.RESERVED)
        print("ANS_PMGR_SHADOWS_INSTALLED", flush=True)
        if zero_based:
            address = 0x45dcc1210

            def limit_read(base, off, width):
                if base + off != address or width != 32:
                    raise RuntimeError("Unexpected ANS limit read")
                return proxy.read32(address)

            def limit_write(base, off, data, width):
                if isinstance(data, list):
                    if len(data) != 1:
                        raise RuntimeError("Unexpected wide ANS limit write")
                    data = data[0]
                if base + off != address or width != 32:
                    raise RuntimeError("Unexpected ANS limit write")
                adjusted = zero_based_limit(data)
                proxy.write32(address, adjusted)
                actual = proxy.read32(address)
                if actual != adjusted:
                    raise RuntimeError(f"ANS limit readback mismatch {actual:#x}")
                print(f"ANS_ZERO_BASED_LIMIT {data:#x} -> {actual:#x}", flush=True)

            # One-word diagnostic only. No queue-memory or disk-data changes.
            hv.map_hook(address, 4, read=limit_read, write=limit_write)
            hv.add_tracer(irange(address, 4), "ANS ZERO-BASED LIMIT", TraceMode.RESERVED)

    hv.map_essential = install
