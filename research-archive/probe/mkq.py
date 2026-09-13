#!/usr/bin/env python3
"""boot-q series: AIC3 sysreg fixes (init + FIQ handler) baked into every image.

Fatal impdef sysregs on T6050 (proven by the p-series probes): UPMCR0
(S3_7_C15_C0_4) and the EL2 block regs (VM_TMR_FIQ_ENA S3_5_C15_C1_3 /
ICH_HCR_EL2). aic_init_cpu was already fixed (p-fixtick); but aic_handle_fiq
reads BOTH register classes on EVERY FIQ -> first timer tick after
local_irq_enable() kills the machine. Fix both sites here too.

Also packages: m1n1.bin + dtb(kvm-arm.mode=none) + gzip(Image).
kvm-arm.mode=none: kvm_arm_init would otherwise enable_percpu_irq() the guest
timers -> aic_fiq_clear_mask writes VM_TMR_FIQ_ENA -> same death, during
initcalls (before simpledrm in link order).
"""
import gzip, struct, subprocess, sys, os

AZ = "/PRIVATE-USER/PRIVATE-PROJECT/Azahi"

# (file_off, expect_orig, new, why)
FIXES = [
    (0xbbc0ac, 0x540002c0, 0xd503201f, "aic_init_cpu+0x3c: don't take EL2 block (VM_TMR/ICH_HCR)"),
    (0xbbc0c4, 0xd503201f, 0x14000004, "aic_init_cpu+0x54: skip UPMCR0 access"),
    (0x10530,  0x540001a0, 0xd503201f, "aic_handle_fiq+0x48: don't take EL2 guest-timer path (VM_TMR read)"),
    (0x10544,  0xd503201f, 0x14000005, "aic_handle_fiq+0x5c: skip UPMCR0 uncore check -> epilogue"),
]

# (name, symbol file_off or None, row)   offsets = System.map vaddr - 0xffff800080000000
PROBES = [
    ("fiqfix",    None,      0),     # fixes only - the recommended boot
    ("restinit",  0x16e6b70, 100),   # rest_init: end of start_kernel (past first FIQs)
    ("initcalls", 0x2aa1af8, 200),   # do_initcalls: scheduler/kthreads/smp_init survived
    ("simpledrm", 0x0fd14b0, 1750),  # simpledrm_probe: fb device bound
    ("regfb",     0x0cdc768, 1850),  # register_framebuffer: fbcon takeover is next
]

COLOR = 0x3fffffff  # white; identity is the ROW

def apply_fixes(path):
    img = bytearray(open(path, "rb").read())
    for off, exp, new, why in FIXES:
        cur = struct.unpack_from("<I", img, off)[0]
        assert cur == exp, f"{path} @{off:#x}: {cur:#x} != expected {exp:#x} ({why})"
        struct.pack_into("<I", img, off, new)
    open(path, "wb").write(bytes(img))

def main():
    dtb = f"{AZ}/t6050-j714s-serial-kvmoff.dtb"
    subprocess.run(["cp", f"{AZ}/t6050-j714s-serial.dtb", dtb], check=True)
    args = subprocess.run(["fdtget", dtb, "/chosen", "bootargs"],
                          capture_output=True, text=True, check=True).stdout.strip()
    if "kvm-arm.mode" not in args:
        subprocess.run(["fdtput", "-t", "s", dtb, "/chosen", "bootargs",
                        args + " kvm-arm.mode=none"], check=True)
    m1n1 = open(f"{AZ}/m1n1/build/m1n1.bin", "rb").read()
    dtb_b = open(dtb, "rb").read()

    for name, off, row in PROBES:
        img = f"{AZ}/Image-q-{name}.bin"
        if off is None:
            subprocess.run(["cp", f"{AZ}/Image-asahi", img], check=True)
        else:
            subprocess.run([sys.executable, f"{AZ}/probe/mkprobe2.py",
                            f"{off:#x}", str(row), f"{COLOR:#x}", img], check=True)
        apply_fixes(img)
        gz = gzip.compress(open(img, "rb").read(), 6)
        out = f"{AZ}/boot-q-{name}.bin"
        open(out, "wb").write(m1n1 + dtb_b + gz)
        print(f"{out}: row {row or '-'} ({len(m1n1)+len(dtb_b)+len(gz)} bytes)")

if __name__ == "__main__":
    main()
