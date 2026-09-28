#!/usr/bin/env python3
"""Compile actual loader fragments on the host; no target access.

Checks the bootargs return-value test, the T6050 usable-RAM clamp and that the
hand-typed addresses shared by azahi_standalone.c and kboot.c still agree.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

SRC = Path(__file__).parent / 'm1n1-20260911/src'
KBOOT = (SRC / 'kboot.c').read_text()
LOADER = (SRC / 'azahi_standalone.c').read_text()


def run_c(body):
    if not shutil.which('trash-put'):
        raise RuntimeError('Install trash-cli: sudo apt-get install -y trash-cli')
    temporary = tempfile.mkdtemp(prefix='azahi-loader-test-')
    try:
        exe = Path(temporary) / 'check'
        subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-x', 'c', '-',
                        '-o', str(exe)], input=body, text=True, check=True)
        subprocess.run([str(exe)], check=True)
    finally:
        subprocess.run(['trash-put', temporary], check=True)


class LoaderGuards(unittest.TestCase):
    def test_pcie_gate_cannot_select_hardware_from_partial_tokens(self):
        source = (SRC / 'azahi_pcie.c').read_text()
        entry = source[source.index('static int pcie_mode('):]
        gates = re.search(r'static const u32 gp_gate_index\[\].*?;', source).group()
        run_c(r'''#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
#define T6050 0x6050
#define APCIE_PATH "/arm-io/apcie0"
#define FDT_DART_PATH "/soc/iommu@410000000"
#define FDT_PCIE_PATH "/soc/pcie@1cb0000000"
static unsigned chip_id = T6050, board_id = 8;
static const char *target = "J714s";
static void *adt;
static unsigned reads, writes, enables;
static bool active = true, compatible = true, preflight_ok = true;
static int missing_node, gp_error, port_error;
static int fdt_path_offset(void *fdt, const char *path) {
    assert(fdt);
    int node = !strcmp(path, FDT_DART_PATH) ? 1 : 2;
    return missing_node == node ? -1 : node;
}
static const void *adt_getprop(void *a, int n, const char *p, u32 *s) {
    (void)a; (void)n; (void)s; assert(!strcmp(p, "target-type")); return target;
}
static int adt_path_offset_trace(void *a, const char *p, int *path) {
    (void)a; (void)path; assert(!strcmp(p, APCIE_PATH)); return 1;
}
static bool adt_is_compatible(void *a, int n, const char *s) {
    (void)a; (void)n; assert(!strcmp(s, "apcie,t6050")); return compatible;
}
static bool ssd_domains_active(void) { reads++; return active; }
static bool pcie_preflight(int *path, bool bringup) {
    (void)path; (void)bringup; assert(!reads && !writes); return preflight_ok;
}
static void dump_state(int *path) { (void)path; reads++; }
static int pmgr_adt_power_enable_index(const char *p, unsigned i) {
    assert(!strcmp(p, APCIE_PATH));
    assert(i == 1 || i == 2 || i == 9 || i == 10 || i == 11);
    writes++; return 0;
}
static int gp_controller_init(int *path) { (void)path; writes++; return gp_error; }
static int port0_bringup(int *path) { (void)path; writes++; return port_error; }
static int fdt_enable_node(void *fdt, const char *path) {
    (void)fdt; assert(!strcmp(path, FDT_DART_PATH) || !strcmp(path, FDT_PCIE_PATH));
    enables++; return 0;
}
''' + gates + '\n' + entry + r'''
int main(void) {
    const char *absent[] = {NULL, "", "maxcpus=1", "prefixazahi.pcie=bringup",
        "other=azahi.pcie=probe", "-- azahi.pcie=bringup", "\t--\tazahi.pcie=probe"};
    for (unsigned i = 0; i < sizeof(absent) / sizeof(*absent); i++) {
        assert(azahi_pcie_init(absent[i], NULL) == 0);
        assert(!reads && !writes && !enables);
    }
    const char *bad[] = {"azahi.pcie=", "azahi.pcie=probes", "azahi.pcie=bringup-extra",
        "azahi.pcie=probe azahi.pcie=bringup", "azahi.pcie=bringup azahi.pcie=probe",
        "azahi.pcie=probe azahi.pcie=probe", "azahi.pcie=other"};
    for (unsigned i = 0; i < sizeof(bad) / sizeof(*bad); i++) {
        assert(azahi_pcie_init(bad[i], NULL) < 0);
        assert(!reads && !writes && !enables);
    }
    chip_id = 0x6051;
    assert(azahi_pcie_init("azahi.pcie=bringup", NULL) < 0); chip_id = T6050;
    board_id = 9;
    assert(azahi_pcie_init("azahi.pcie=bringup", NULL) < 0); board_id = 8;
    target = "J999";
    assert(azahi_pcie_init("azahi.pcie=probe", NULL) < 0); target = NULL;
    assert(azahi_pcie_init("azahi.pcie=probe", NULL) < 0); target = "J714s";
    compatible = false;
    assert(azahi_pcie_init("azahi.pcie=bringup", NULL) == 0); compatible = true;
    assert(!reads && !writes && !enables);
    assert(azahi_pcie_init("azahi.pcie=bringup", NULL) < 0);
    for (missing_node = 1; missing_node <= 2; missing_node++)
        assert(azahi_pcie_init("azahi.pcie=bringup", &adt) < 0);
    missing_node = 0;
    assert(!reads && !writes && !enables);
    preflight_ok = false;
    assert(azahi_pcie_init("azahi.pcie=bringup", &adt) < 0);
    assert(azahi_pcie_init("azahi.pcie=probe", NULL) < 0);
    assert(!reads && !writes && !enables); preflight_ok = true;
    active = false;
    assert(azahi_pcie_init("azahi.pcie=bringup", &adt) < 0);
    assert(reads == 1 && !writes && !enables); reads = 0; active = true;
    assert(azahi_pcie_init("\tazahi.pcie=probe\t-- azahi.pcie=bringup", NULL) == 0);
    assert(reads == 2 && !writes && !enables); reads = 0;
    gp_error = -1;
    assert(azahi_pcie_init("azahi.pcie=bringup", &adt) < 0);
    assert(writes == 6 && !enables); reads = writes = 0; gp_error = 0;
    port_error = -1;
    assert(azahi_pcie_init("azahi.pcie=bringup", &adt) < 0);
    assert(writes == 7 && !enables); reads = writes = 0; port_error = 0;
    assert(azahi_pcie_init("maxcpus=1 azahi.pcie=bringup ", &adt) == 0);
    assert(reads == 4 && writes == 7 && enables == 2);
    return 0;
}
''')

    def test_pcie_ranges_and_all_tunables_are_checked_before_mmio(self):
        source = (SRC / 'azahi_pcie.c').read_text()
        defines = '\n'.join(line for line in source.splitlines() if line.startswith('#define '))
        helpers = source[source.index('static u64 apcie_reg('):source.index('static bool ssd_domains_active(')]
        run_c(r'''#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define BIT(n) (1UL << (n))
static void *adt;
static unsigned mmio_reads;
static u64 regs[20][2] = {
    [1] = {0x414000000UL, 0x4000}, [2] = {0x417000000UL, 0x800000},
    [3] = {0x417020000UL, 0x4000}, [16] = {0x410028000UL, 0x8000},
    [18] = {0x417010000UL, 0x4000}, [19] = {0x410024000UL, 0x4000},
};
static u64 pmgr[] = {0x280900000UL, 0x58000};
static u32 tunables[3][12] = {{0, 4}, {0, 4}, {0, 4}};
static u32 length = 24;
static bool missing_property, missing_node;
static int failed_index = -1;
static u32 read32(u64 addr) {
    assert(addr == 0x280900140UL); mmio_reads++; return 0x1f0;
}
static int adt_path_offset_trace(void *a, const char *p, int *path) {
    (void)a; assert(!strcmp(p, "/arm-io/pmgr")); path[0] = 1;
    return missing_node ? -1 : 1;
}
static int adt_get_reg(void *a, int *path, const char *p, int idx, u64 *base, u64 *size) {
    (void)a; assert(!strcmp(p, "reg"));
    if (path[0] == 1) { assert(idx == 1); *base = pmgr[0]; *size = pmgr[1]; }
    else { assert(idx >= 0 && idx < 20); *base = regs[idx][0]; *size = regs[idx][1]; }
    return idx == failed_index ? -1 : 0;
}
static int adt_path_offset(void *a, const char *p) {
    (void)a; assert(!strcmp(p, "/arm-io/apcie0") || !strcmp(p, "/arm-io/apcie0/pci-bridge0"));
    return missing_node ? -1 : 1;
}
static const void *adt_getprop(void *a, int node, const char *p, u32 *len) {
    (void)a; (void)node; *len = length;
    if (missing_property) return NULL;
    if (!strcmp(p, "apcie-common-tunables")) return tunables[0];
    if (!strcmp(p, "apcie-phy-tunables")) return tunables[1];
    assert(!strcmp(p, "apcie-config-tunables")); return tunables[2];
}
''' + defines + '\n' + helpers + r'''
int main(void) {
    int path[] = {2};
    assert(pcie_preflight(path, true) && !mmio_reads);
    const int indices[] = {1, 2, 3, 16, 18, 19};
    for (unsigned i = 0; i < sizeof(indices) / sizeof(*indices); i++) {
        unsigned idx = indices[i];
        regs[idx][0] ^= 0x4000; assert(!pcie_preflight(path, false)); regs[idx][0] ^= 0x4000;
        regs[idx][1]--; assert(!pcie_preflight(path, false)); regs[idx][1]++;
        failed_index = idx; assert(!pcie_preflight(path, false)); failed_index = -1;
    }
    pmgr[0]++; assert(!pcie_preflight(path, false)); assert(!pmgr_group1_ps(0x140)); pmgr[0]--;
    pmgr[1]--; assert(!pcie_preflight(path, false)); pmgr[1]++;
    missing_node = true; assert(!pcie_preflight(path, true)); missing_node = false;
    assert(!mmio_reads);
    assert(pmgr_group1_ps(0x140) == 0x1f0 && mmio_reads == 1); mmio_reads = 0;
    missing_property = true; assert(pcie_preflight(path, true)); missing_property = false;
    length = 0; assert(!pcie_preflight(path, true));
    length = 25; assert(!pcie_preflight(path, true)); length = 24;
    const u32 sizes[] = {0x4000, 0x800000, 0x8000};
    for (unsigned i = 0; i < 3; i++) {
        for (u32 width = 1; width <= 8; width *= 2) {
            tunables[i][0] = sizes[i] - width; tunables[i][1] = width;
            assert(pcie_preflight(path, true));
        }
        tunables[i][0] = sizes[i]; assert(!pcie_preflight(path, true));
        tunables[i][0] = UINT32_MAX; assert(!pcie_preflight(path, true));
        tunables[i][0] = 1; tunables[i][1] = 4; assert(!pcie_preflight(path, true));
        tunables[i][0] = 0;
        for (u32 width = 0; width <= 16; width += 3) {
            tunables[i][1] = width; assert(!pcie_preflight(path, true));
        }
        tunables[i][1] = 4;
        length = 48; tunables[i][6] = sizes[i]; tunables[i][7] = 4;
        assert(!pcie_preflight(path, true)); /* Second entry, before the first can write. */
        assert(pcie_preflight(path, false)); /* Probe never applies tunables. */
        length = 24;
    }
    assert(!mmio_reads);
    return 0;
}
''')

    def test_pcie_tunable_failures_stop_the_sequence(self):
        source = (SRC / 'azahi_pcie.c').read_text()
        defines = '\n'.join(line for line in source.splitlines() if line.startswith('#define '))
        begin = source.index('static int gp_controller_init(')
        functions = source[begin:source.index('/* Returns 0 if the node was enabled', begin)]
        run_c(r'''#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define BIT(n) (1U << (n))
''' + defines + r'''
static void *adt;
static const char *failed_tunable;
static unsigned writes, polls, tunables;
static u64 apcie_reg(int *path, int index) { (void)path; return (index + 1) * 0x10000; }
static int adt_path_offset(void *a, const char *p) { (void)a; (void)p; return 1; }
static const void *adt_getprop(void *a, int n, const char *p, u32 *len) {
    (void)a; (void)n; (void)p; (void)len; return "present";
}
static int tunables_apply_local(const char *path, const char *prop, unsigned index) {
    (void)path; (void)index; tunables++;
    return failed_tunable && !strcmp(prop, failed_tunable) ? -1 : 0;
}
static int tunables_apply_local_addr(const char *path, const char *prop, uintptr_t base) {
    (void)base; return tunables_apply_local(path, prop, 0);
}
static void write32(u64 address, u32 value) { (void)address; (void)value; writes++; }
static void set32(u64 a, u32 v) { write32(a, v); }
static void clear32(u64 a, u32 v) { write32(a, v); }
static void mask32(u64 a, u32 mask, u32 v) { (void)mask; write32(a, v); }
static u32 read32(u64 address) { (void)address; return PORT_RET_PIPE_EN; }
static int poll32(u64 a, u32 mask, u32 v, unsigned timeout) {
    (void)a; (void)mask; (void)v; (void)timeout; polls++; return 0;
}
static void udelay(unsigned usec) { (void)usec; }
''' + functions + r'''
int main(void) {
    failed_tunable = "apcie-common-tunables";
    assert(gp_controller_init(NULL) < 0 && writes == 0 && polls == 0 && tunables == 1);
    failed_tunable = "apcie-phy-tunables"; writes = polls = tunables = 0;
    assert(gp_controller_init(NULL) < 0 && writes == 1 && polls == 0 && tunables == 2);
    failed_tunable = "apcie-config-tunables"; writes = polls = tunables = 0;
    assert(port0_bringup(NULL) < 0 && writes > 0 && polls == 0 && tunables == 1);
    failed_tunable = NULL;
    assert(gp_controller_init(NULL) == 0);
    assert(port0_bringup(NULL) == 0);
    return 0;
}
''')

    def test_pcie_failure_refuses_kernel_handoff(self):
        begin = KBOOT.index('        const char *pcie_cmdline = NULL;')
        block = KBOOT[begin:KBOOT.index('    } else {', begin)]
        run_c(r'''#include <assert.h>
#include <string.h>
#define MAX_CHOSEN_PARAMS 3
#define bail(...) return -1
static const char *chosen_params[3][2] = {{"other", "x"}, {"bootargs", "azahi.pcie=bringup"}};
static void *dt;
static int init_result, handoffs;
static int azahi_pcie_init(const char *args, void *fdt) {
    assert(!strcmp(args, "azahi.pcie=bringup")); assert(fdt == dt); return init_result;
}
static int boot(void) {
''' + block + r'''
    handoffs++; return 0;
}
int main(void) {
    init_result = -1; assert(boot() < 0 && handoffs == 0);
    init_result = 0; assert(boot() == 0 && handoffs == 1);
    return 0;
}
''')

    def test_exact_unique_boot_arguments(self):
        helper = LOADER[LOADER.index('static bool bootarg_is('):LOADER.index('static bool reg_matches(')]
        start = LOADER.index('    if (args[h->args_len - 1]')
        guard = LOADER[start:LOADER.index('    unsigned source_len', start)]
        run_c('''#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
static int stop(const char *s) { (void)s; return -1; }
static int fdt_check_header(const void *p) { (void)p; return 0; }
static unsigned fdt_totalsize(const void *p) { (void)p; return 40; }
static int fdt_node_check_compatible(const void *p, int n, const char *s) {
    (void)p; (void)n; (void)s; return 0;
}
''' + helper + '''
static int check(const char *args) {
    struct { unsigned args_len, dt_len; } header = {strlen(args) + 1, 40}, *h = &header;
    const void *fdt = NULL;
''' + guard + '''
    return 0;
}
#define ROOT "root=PARTUUID=PRIVATE-LINUX-PARTUUID-NOT-CONFIGURED"
#define GOOD "azahi.ssd_root=1 maxcpus=1 " ROOT
int main(void) {
    assert(check(GOOD) == 0);
    assert(check("\\t" ROOT "\\tmaxcpus=1  azahi.ssd_root=1 ") == 0);
    const char *bad[] = {
        "azahi.ssd_root=1 maxcpus=18 " ROOT,
        "azahi.ssd_root=10 maxcpus=1 " ROOT,
        "azahi.ssd_root=1 maxcpus=1 " ROOT "-wrong",
        "azahi.ssd_root=1 other=maxcpus=1 " ROOT,
        "azahi.ssd_root=1 maxcpus=1 other=" ROOT,
        GOOD " maxcpus=18", "maxcpus=18 " GOOD,
        GOOD " maxcpus=1", GOOD " root=wrong", GOOD " azahi.ssd_root=0",
        "-- " GOOD, "azahi.ssd_root=1 " ROOT " -- maxcpus=1"
    };
    for (unsigned i = 0; i < sizeof(bad) / sizeof(*bad); i++)
        assert(check(bad[i]) < 0);
    assert(check(GOOD " -- init-option") == 0);
    return 0;
}
''')

    def test_bootargs_accepts_any_slot(self):
        function = KBOOT[KBOOT.index('int kboot_set_chosen('):KBOOT.index('int kboot_set_uboot(')]
        condition = re.search(r'if \((kboot_set_chosen\("bootargs", args\)[^\n]*?)\)\s*(/\*.*\*/)?\n',
                              LOADER).group(1)
        run_c('''#include <assert.h>
#include <stdlib.h>
#include <string.h>
#define MAX_CHOSEN_PARAMS 16
static char *chosen_params[MAX_CHOSEN_PARAMS][2];
''' + function + '''
int main(void) {
    const char *args = "maxcpus=1";
    assert(kboot_set_chosen("other", "1") == 0);
    int refused = (''' + condition + ''');
    assert(!refused);
    assert(!strcmp(chosen_params[1][1], args));
    return 0;
}
''')

    def test_usable_ram_is_intersection(self):
        start = KBOOT.index('        u64 safe_min = 0x1010a960000UL;')
        block = KBOOT[start:KBOOT.index('\n        }\n', start) + len('\n        }\n')]
        run_c('''#include <assert.h>
#include <stdint.h>
#include <stdio.h>
typedef uint64_t u64;
static void clamp(u64 *low, u64 *high) {
    u64 dram_min = *low, dram_max = *high;
''' + block + '''    *low = dram_min; *high = dram_max;
}
int main(void) {
    u64 low = 0x10003af8000UL, high = low + 0xfc7008000UL; /* recorded J714s 64 GB */
    clamp(&low, &high);
    assert(low == 0x1010a960000UL && high == 0x10F4AB00000UL);
    low = 0x10003af8000UL; high = low + (24UL << 30);      /* smaller RAM: never extend */
    clamp(&low, &high);
    assert(low == 0x1010a960000UL && high == 0x10003af8000UL + (24UL << 30));
    return 0;
}
''')

    def test_shared_addresses_agree(self):
        define = dict(re.findall(r'#define (\w+) (0x[0-9a-fA-F]+)UL', LOADER))
        relocation = KBOOT[KBOOT.index('void kboot_set_initrd('):]
        initrd = re.search(r'void \*safe = \(void \*\)(0x[0-9a-fA-F]+)UL', relocation).group(1)
        fdt = re.search(r'void \*safe_dt = \(void \*\)(0x[0-9a-fA-F]+)UL', KBOOT).group(1)
        # The loader cleans INITRD_ADDR because kboot_set_initrd copies there.
        self.assertEqual(int(define['INITRD_ADDR'], 16), int(initrd, 16))
        self.assertEqual(int(define['SAFE_LOW'], 16), 0x1010a960000)
        self.assertEqual(int(define['SAFE_HIGH'], 16), 0x10F4AB00000)
        kernel_bytes = int(re.search(r'#define KERNEL_BYTES (\d+)U', LOADER).group(1))
        initrd_bytes = int(re.search(r'#define INITRD_BYTES (\d+)U', LOADER).group(1))
        self.assertLess(int(define['KERNEL_ADDR'], 16) + kernel_bytes, int(fdt, 16))
        self.assertLessEqual(int(fdt, 16) + 65536 + 0x10000, int(initrd, 16))
        self.assertLessEqual(int(initrd, 16) + initrd_bytes, 0x10F4AB00000)


if __name__ == '__main__':
    unittest.main(verbosity=2)
