#!/usr/bin/env python3
"""Compile the real diagnostic and patched startup functions against host mocks.

No target access. Temporary build artifacts go to recoverable Trash.
"""
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'standalone-loader/m1n1-20260911/src'
SMP = (SRC / 'azahi_smp.c').read_text()


def extract(source, name):
    begin = source.rindex('\n', 0, source.index(name)) + 1
    depth = 0
    j = source.index('{', begin)
    while True:
        if source[j] == '{':
            depth += 1
        elif source[j] == '}':
            depth -= 1
            if depth == 0:
                return source[begin:j + 1]
        j += 1


def temporary_build():
    if not shutil.which('trash-put'):
        raise RuntimeError('Install trash-cli before running: sudo apt-get install -y trash-cli')
    return Path(tempfile.mkdtemp(prefix='azahi-smp-test-'))


def run_c(body):
    tmp = temporary_build()
    try:
        exe = tmp / 'check'
        subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        '-x', 'c', '-', '-o', str(exe)], input=body, text=True, check=True)
        subprocess.run([str(exe)], check=True)
    finally:
        subprocess.run(['trash-put', str(tmp)], check=True)


class Diagnostic(unittest.TestCase):
    def test_token_boundaries(self):
        helpers = extract(SMP, 'static const char *azahi_smp_mode(') + '\n' + \
            extract(SMP, 'static bool azahi_smp_mode_is(')
        run_c('''#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
''' + helpers + r'''
int main(void) {
    assert(azahi_smp_mode(NULL) == NULL);
    assert(azahi_smp_mode("maxcpus=1 idle=nop") == NULL);
    assert(azahi_smp_mode("fooazahi.smp=probe") == NULL);
    assert(azahi_smp_mode("other=azahi.smp=probe") == NULL);
    assert(azahi_smp_mode("-- azahi.smp=probe") == NULL);
    assert(!azahi_smp_mode_is(NULL, "probe"));
    assert(azahi_smp_mode_is(azahi_smp_mode("azahi.smp=probe"), "probe"));
    assert(azahi_smp_mode_is(azahi_smp_mode(" \tx azahi.smp=probe\ty"), "probe"));
    assert(!azahi_smp_mode_is(azahi_smp_mode("azahi.smp=probes"), "probe"));
    assert(!azahi_smp_mode_is(azahi_smp_mode("azahi.smp="), "probe"));
    assert(!azahi_smp_mode_is(azahi_smp_mode("azahi.smp=probe azahi.smp=start"), "probe"));
    assert(!azahi_smp_mode_is(azahi_smp_mode("azahi.smp=start azahi.smp=probe"), "probe"));
    assert(!azahi_smp_mode_is(azahi_smp_mode("azahi.smp=probe azahi.smp=probe"), "probe"));
    assert(azahi_smp_mode_is(azahi_smp_mode("badazahi.smp=start azahi.smp=probe"), "probe"));
    assert(azahi_smp_mode_is(azahi_smp_mode("azahi.smp=probe -- azahi.smp=start"), "probe"));
    return 0;
}
''')

    def test_actual_diagnostic_reads_and_refusals(self):
        # No write or startup mocks exist. Adding such a call fails compilation/linking.
        body = re.sub(r'^#include[^\n]*\n', '', SMP, flags=re.M)
        # The host's PIE address exceeds the target's 42-bit physical address field.
        body = body.replace('extern u8 _vectors_start[0];', '')
        run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
typedef uint64_t u64;
typedef uint32_t u32;
typedef uint8_t u8;
#define BIT(n) (1UL << (n))
#define GENMASK(h, l) ((~0UL >> (63 - (h))) & (~0UL << (l)))
#define FIELD_GET(mask, value) (((value) & (mask)) >> __builtin_ctzl(mask))
#define T6050 0x6050
static unsigned chip_id = T6050, board_id = 8;
static void *adt;
static int boot_cpu_idx;
#define _vectors_start ((u8 *)0x100043a4000UL)
static unsigned reads32, reads64, count = 18;
static bool bad_pmgr, short_pmgr, bad_impl, bad_id, short_prop, bad_board;
static bool missing_pmgr, missing_cpus;
static int quiet_printf(const char *fmt, ...) { (void)fmt; return 0; }
#define printf quiet_printf
#define mrs(reg) (0x40000UL)
static int adt_path_offset_trace(void *a, const char *p, int *t) {
    (void)a; (void)p; (void)t; return missing_pmgr ? -1 : 1;
}
static int adt_get_reg(void *a, int *t, const char *p, int n, u64 *b, u64 *s) {
    (void)a; (void)t; (void)p; (void)n;
    *b = bad_pmgr ? 0 : 0x280600000UL;
    *s = short_pmgr ? 4 : 0x100000;
    return 0;
}
static int adt_path_offset(void *a, const char *p) {
    (void)a; (void)p; return missing_cpus ? -1 : 100;
}
static const void *adt_getprop(void *a, int n, const char *p, u32 *s) {
    (void)a; (void)n; (void)s;
    if (!strcmp(p, "target-type")) return bad_board ? "J999" : "J714s";
    return "waiting";
}
static int adt_getprop_copy(void *a, int node, const char *p, void *out, size_t n) {
    (void)a;
    unsigned i = (node - 1) % 18, cluster = i / 6, core = i % 6;
    u32 val;
    if (short_prop) return 0;
    if (!strcmp(p, "cpu-id")) val = bad_id ? 255 : node - 1;
    else if (!strcmp(p, "reg")) val = (cluster << 8) | core | (node > 18 ? 2 << 11 : 0);
    else {
        assert(n == 16);
        u64 range[] = {bad_impl ? 0x210010ff0UL : 0x210050000UL + ((u64)cluster << 24) + ((u64)core << 20), 0x9018};
        memcpy(out, range, sizeof(range));
        return sizeof(range);
    }
    assert(n == 4); memcpy(out, &val, n); return n;
}
#define ADT_GETPROP(a, n, p, v) adt_getprop_copy(a, n, p, v, sizeof(*(v)))
#define ADT_GETPROP_ARRAY(a, n, p, v) adt_getprop_copy(a, n, p, v, sizeof(v))
#define ADT_FOREACH_CHILD(a, n) for (n = 1; n <= (int)count; n++)
static u32 read32(u64 addr) {
    assert(addr >= 0x280688000UL && addr <= 0x280688010UL && !(addr & 3));
    reads32++; return 0;
}
static u64 read64(u64 addr) {
    unsigned i = reads64++;
    assert(i < 18);
    assert(addr == 0x210050000UL + ((u64)(i / 6) << 24) + ((u64)(i % 6) << 20));
    return (u64)_vectors_start | 1;
}
''' + body + r'''
int main(void) {
    assert(azahi_smp_diag(NULL) == 0);
    assert(azahi_smp_diag("prefixazahi.smp=probe") == 0);
    assert(azahi_smp_diag("-- azahi.smp=probe") == 0);
    assert(azahi_smp_diag("azahi.smp=start") < 0);
    assert(azahi_smp_diag("azahi.smp=unknown") < 0);
    assert(azahi_smp_diag("azahi.smp=probe azahi.smp=start") < 0);
    chip_id = 0x6051; assert(azahi_smp_diag("azahi.smp=probe") < 0); chip_id = T6050;
    board_id = 9; assert(azahi_smp_diag("azahi.smp=probe") < 0); board_id = 8;
    bool *bad[] = {&bad_pmgr, &short_pmgr, &bad_impl, &bad_id, &short_prop, &bad_board,
                   &missing_pmgr, &missing_cpus};
    for (unsigned i = 0; i < sizeof(bad)/sizeof(*bad); i++) {
        *bad[i] = true; assert(azahi_smp_diag("azahi.smp=probe") < 0); *bad[i] = false;
        assert(reads32 == 0 && reads64 == 0);
    }
    assert(azahi_smp_diag("azahi.smp=probe") == 0);
    assert(reads32 == 5 && reads64 == 18);
    reads32 = reads64 = 0; count = 36;
    assert(azahi_smp_diag("azahi.smp=probe") == 0); /* Template die 2 is skipped. */
    assert(reads32 == 5 && reads64 == 18);
    reads32 = reads64 = 0; count = 17;
    assert(azahi_smp_diag("azahi.smp=probe") < 0);
    assert(reads32 == 0 && reads64 == 17);
    return 0;
}
''')

    def test_integrated_before_dt_and_stop_on_error(self):
        loader = (SRC / 'azahi_standalone.c').read_text()
        self.assertIn('#include "azahi_smp.h"', loader)
        self.assertIn('if (azahi_smp_diag(args) < 0)\n        return stop(', loader)
        self.assertLess(loader.index('azahi_smp_diag(args)'), loader.index('kboot_prepare_dt('))
        self.assertNotIn('smp_start_secondaries(', SMP)


class StartupPatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = temporary_build()
        cls.addClassCleanup(subprocess.run, ['trash-put', str(cls.tmp)], check=True)
        base = ROOT / 'research-archive/standalone-loader/m1n1-20260911'
        (cls.tmp / 'src').mkdir()
        for p in ('Makefile', 'src/smp.c'):
            shutil.copyfile(base / p, cls.tmp / p)
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(cls.tmp),
                        '-i', str(ROOT / 'smp/t6050-start-guards.patch')], check=True)
        cls.source = (cls.tmp / 'src/smp.c').read_text()

    def test_all_core_masks_and_legacy(self):
        run_c('''#include <assert.h>
#include <stdint.h>
typedef uint32_t u32;
#define T6050 0x6050
static int chip_id = T6050;
''' + extract(self.source, 'static u32 smp_core_mask(') + '''
int main(void) {
    u32 seen = 0;
    for (int i = 0; i < 18; i++) {
        u32 mask = smp_core_mask(i / 6, i % 6);
        assert(mask == (1U << i)); assert(!(seen & mask)); seen |= mask;
    }
    assert(seen == 0x3ffff);
    assert(!smp_core_mask(-1, 0) && !smp_core_mask(0, -1));
    assert(!smp_core_mask(3, 0) && !smp_core_mask(0, 6));
    chip_id = 0x6040;
    for (int cluster = 0; cluster < 8; cluster++)
        for (int core = 0; core < 4; core++)
            assert(smp_core_mask(cluster, core) == (1U << (4 * cluster + core)));
    assert(!smp_core_mask(8, 0) && !smp_core_mask(0, 32));
    return 0;
}
''')

    def test_start_stop_writes_refusals_and_timeout_quarantine(self):
        functions = '\n'.join(extract(self.source, name) for name in (
            'static u32 smp_core_mask(',
            'static __attribute__((noreturn)) void smp_start_quarantine(',
            'static void smp_start_cpu(', 'static void smp_stop_cpu('))
        run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <setjmp.h>
typedef uint64_t u64;
typedef uint32_t u32;
typedef uint8_t u8;
#define T6050 0x6050
#define MAX_CPUS 64
#define MAX_EL3_CPUS 8
#define SECONDARY_STACK_SIZE 0x4000
#define DUMMY_STACK_SIZE 0x1000
#define RVBAR_ADDR 0xfffffffff000UL
#define GENMASK(h, l) ((~0UL >> (63 - (h))) & (~0UL << (l)))
#define PMGR_DIE_OFFSET 0x2000000000UL
#define sysop(op) mock_sysop(op)
static int chip_id = T6050, target_cpu, writes, allocations, sleeps, delays, parked;
static u64 addresses[2], values[2];
static u64 wrong_vector;
static bool allocation_failure, timeout;
static jmp_buf halted;
static struct { bool apple_sysregs_unlocked; } features;
static const typeof(features) *cpu_features = &features;
static struct spin_table { u64 flag; } spin_table[MAX_CPUS];
static u8 *secondary_stacks[MAX_CPUS], *secondary_stacks_el3[MAX_CPUS];
static u8 stack[SECONDARY_STACK_SIZE], dummy_stack[DUMMY_STACK_SIZE], dummy_stack_el1[DUMMY_STACK_SIZE];
static void *_reset_stack, *_reset_stack_el1;
#define _vectors_start ((u8 *)0x100043a4000UL)
static void mock_sysop(const char *op) {
    if (strcmp(op, "wfe")) return;
    assert(timeout && delays == 100 && writes == 2);
    assert(target_cpu == 1 && _reset_stack == stack + SECONDARY_STACK_SIZE);
    /* A late arrival must not release the boot CPU from quarantine. */
    spin_table[1].flag = 1;
    if (++parked == 2) longjmp(halted, 1);
}
static bool has_el3(void) { return false; }
static u64 read64(u64 addr) {
    if (addr == 0x210150100UL) return 0;
    assert(addr == 0x210150000UL);
    return ((u64)_vectors_start + wrong_vector) | 1;
}
static void write64(u64 addr, u64 val) { (void)addr; (void)val; assert(0); }
static void write32(u64 addr, u32 val) {
    assert(writes < 2); addresses[writes] = addr; values[writes++] = val;
    if (writes == 2 && !timeout) spin_table[target_cpu].flag = 1;
}
static void *memalign(unsigned align, unsigned size) {
    assert(align == 0x4000 && size == SECONDARY_STACK_SIZE);
    allocations++; return allocation_failure ? NULL : stack;
}
static void dc_civac_range(void *p, unsigned n) { (void)p; (void)n; }
static void udelay(unsigned n) { assert(timeout && n == 1000); delays++; }
static void cpu_sleep(void) {}
static void smp_call1(int i, void (*f)(void), u64 arg) {
    assert(i == 17 && f == cpu_sleep && arg == 0); sleeps++;
}
static int quiet_printf(const char *fmt, ...) { (void)fmt; return 0; }
#define printf quiet_printf
''' + functions + r'''
int main(void) {
    wrong_vector = 0x1000;
    smp_start_cpu(1, 0, 0, 1, 0x210150000UL, 0x280688000UL);
    assert(writes == 0 && allocations == 0);
    wrong_vector = 0x800; /* An entry in the other half-page is also wrong. */
    smp_start_cpu(1, 0, 0, 1, 0x210150000UL, 0x280688000UL);
    assert(writes == 0 && allocations == 0);
    wrong_vector = 0;
    smp_start_cpu(-1, 0, 0, 1, 0x210150000UL, 0x280688000UL);
    smp_start_cpu(1, 0, 3, 0, 0x210150000UL, 0x280688000UL);
    smp_start_cpu(1, 2, 0, 1, 0x210150000UL, 0x280688000UL);
    smp_start_cpu(1, 0, 2, 5, 0x210150000UL, 0x280688000UL);
    assert(writes == 0 && allocations == 0);
    allocation_failure = true;
    smp_start_cpu(1, 0, 0, 1, 0x210150000UL, 0x280688000UL);
    assert(writes == 0 && target_cpu == 0 && _reset_stack == NULL);
    allocation_failure = false;
    for (int cpu = 1; cpu < 18; cpu++) {
        writes = 0; spin_table[cpu].flag = 0;
        smp_start_cpu(cpu, 0, cpu / 6, cpu % 6, 0x210150000UL, 0x280688000UL);
        assert(writes == 2 && spin_table[cpu].flag);
        assert(addresses[0] == 0x280688004UL && values[0] == (1U << cpu));
        assert(addresses[1] == 0x280688008UL + 4 * (cpu / 6) && values[1] == (1U << (cpu % 6)));
    }
    writes = 0;
    smp_stop_cpu(1, 0, 2, 5, 0x210150000UL, 0x280688000UL, false);
    smp_stop_cpu(17, 2, 2, 5, 0x210150000UL, 0x280688000UL, false);
    assert(writes == 0 && sleeps == 0);
    smp_stop_cpu(17, 0, 2, 5, 0x210150000UL, 0x280688000UL, false);
    assert(writes == 1 && addresses[0] == 0x280688000UL && values[0] == (1U << 17));
    assert(sleeps == 1 && !spin_table[17].flag);
    writes = 0; timeout = true; spin_table[1].flag = 0;
    if (!setjmp(halted)) {
        smp_start_cpu(1, 0, 0, 1, 0x210150000UL, 0x280688000UL);
        assert(!"timed-out start returned to its caller");
    }
    assert(parked == 2 && spin_table[1].flag == 1);
    assert(target_cpu == 1 && secondary_stacks[1] == stack);
    assert(_reset_stack == stack + SECONDARY_STACK_SIZE);
    return 0;
}
''')

    def test_default_one_core_guard_preserved(self):
        startup = extract(self.source, 'void smp_start_secondaries(')
        self.assertIn('if (chip_id == T6050)', startup)
        self.assertLess(startup.index('AZAHI_ONE_CORE'), startup.index('smp_start_cpu('))
        self.assertIn('azahi_smp.o', (self.tmp / 'Makefile').read_text())


class OfflineBuild(unittest.TestCase):
    def test_full_link_refuses_overwrite_and_missing_compiler(self):
        check = runpy.run_path(str(ROOT / 'standalone-loader/check-full-link.py'))['check_link']
        tmp = temporary_build()
        self.addCleanup(subprocess.run, ['trash-put', str(tmp)], check=True)
        (tmp / 'sentinel').write_text('keep this build\n')
        with self.assertRaisesRegex(ValueError, 'Output already exists'):
            check(tmp, tmp, 'compiler-must-not-run')
        self.assertEqual((tmp / 'sentinel').read_text(), 'keep this build\n')
        with self.assertRaisesRegex(ValueError, 'AArch64 GCC executable'):
            check(tmp, tmp / 'new', 'compiler-must-not-run')
        self.assertFalse((tmp / 'new').exists())

    def test_refuses_overwrite_and_host_compiler_before_writing(self):
        build = runpy.run_path(str(ROOT / 'smp/build-offline.py'))['build']
        tmp = temporary_build()
        self.addCleanup(subprocess.run, ['trash-put', str(tmp)], check=True)
        for name in ('src/smp.h', 'src/utils.h', 'sysinc/limits.h'):
            p = tmp / name
            p.parent.mkdir(exist_ok=True)
            p.write_text('header sentinel\n')
        with self.assertRaisesRegex(ValueError, 'Output already exists'):
            build(tmp, tmp, 'compiler-must-not-run')
        self.assertEqual((tmp / 'src/smp.h').read_text(), 'header sentinel\n')
        with mock.patch('subprocess.check_output', return_value='x86_64-linux-gnu\n'):
            with self.assertRaisesRegex(ValueError, 'AArch64 cross compiler'):
                build(tmp, tmp / 'new', 'cc')
        self.assertFalse((tmp / 'new').exists())
        (tmp / 'src/pmgr.c').write_text('unreviewed source\n')
        with mock.patch('subprocess.check_output', return_value='aarch64-linux-gnu\n'):
            with self.assertRaisesRegex(ValueError, 'PMGR source differs'):
                build(tmp, tmp / 'new', 'cc')
        self.assertFalse((tmp / 'new').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
