#!/usr/bin/env python3
"""Check the optional backport's assembled source. No target access.

Pass --source OUTPUT/source from check-full-link.py --smp-refactor.
Compiles the actual SMP C file with host MMIO/ADT mocks and ASan/UBSan.
Temporary test artifacts go to recoverable Trash.
"""
import argparse
from pathlib import Path
import re
import runpy
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent.parent
helpers = runpy.run_path(str(ROOT / 'smp/test-smp-diag.py'))
extract = helpers['extract']
SOURCE = None


def run_c(body):
    tmp = helpers['temporary_build']()
    try:
        exe = tmp / 'check'
        subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-no-pie',
                        '-x', 'c', '-', '-o', str(exe)], input=body, text=True, check=True)
        subprocess.run([str(exe)], check=True)
    finally:
        subprocess.run(['trash-put', str(tmp)], check=True)


class SharedState(unittest.TestCase):
    def test_start_stop_reentry_and_cached_adt(self):
        source = (SOURCE / 'src/smp.c').read_text()
        source = re.sub(r'^#include[^\n]*\n', '', source, flags=re.M)
        source = source.replace('extern u8 _vectors_start[0];', '')
        source = source.replace('extern u8 _stack_bot[0];', '')
        chips = re.findall(r'case (\w+):', source)
        definitions = '\n'.join(f'#define {name} {0x6050 if name == "T6050" else i + 1}'
                                for i, name in enumerate(chips))
        asm_header = (SOURCE / 'src/smp_asm.h').read_text()
        run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
typedef uint64_t u64;
typedef uint32_t u32;
typedef uint8_t u8;
#define ALIGNED(n) __attribute__((aligned(n)))
#define BIT(n) (1UL << (n))
#define GENMASK(h,l) ((~0UL >> (63-(h))) & (~0UL << (l)))
#define FIELD_GET(mask, value) (((value) & (mask)) >> __builtin_ctzl(mask))
#define PMGR_DIE_OFFSET 0x2000000000UL
#define _vectors_start ((u8 *)0x100043a4000UL)
#define _stack_bot ((u8 *)0x10005000000UL)
#define AIC_IPI_MASK_SET 0
#define AIC_IPI_SELF 1
#define AIC_IPI_ACK 2
#define AIC_IPI_OTHER 3
#define AIC_IPI_MASK_CLR 4
#define AIC_IPI_SEND 5
#define AIC_IPI_SEND_CPU(n) (n)
#define mrs(reg) mock_mpidr
#define msr(reg, value) ((void)(value))
#define sysop(op) mock_sysop(op)
static u64 mock_mpidr = 0x80040000UL, wrong_vector;
static int chip_id, writes, reads, sleeps, delays, parked, adt_reads;
static bool timeout, el3, mmio_allowed, missing_pmgr, short_reg, fallback;
static u32 fallback_bytes;
static jmp_buf halted;
static u64 addresses[40], values[40];
static struct { bool apple_sysregs_unlocked, fast_ipi; } features = {false, true};
static const typeof(features) *cpu_features = &features;
static void *adt;
static void mock_sysop(const char *op);
static void write32(u64 addr, u32 value);
static bool has_el3(void) { return el3; }
static bool in_el2(void) { return true; }
static void deep_wfi(void) { assert(0); }
static void aic_write(u32 reg, u32 value) { (void)reg; (void)value; assert(0); }
static void aic_ack(void) { assert(0); }
static u64 read64(u64 addr) {
    assert(mmio_allowed); reads++;
    assert(addr == 0x210150000UL || addr == 0x210150100UL);
    return (addr & 0x100) ? 0 : ((u64)_vectors_start + wrong_vector) | 1;
}
static void write64(u64 addr, u64 value) { (void)addr; (void)value; assert(0); }
static void udelay(unsigned n) { assert(timeout && n == 1000); delays++; }
static void cpu_sleep(void) {}
static void smp_call1(int i, void (*f)(void), u64 arg) {
    assert(i >= 1 && i < 18 && f == cpu_sleep && !arg); sleeps++;
}
void smp_set_wfe_mode(bool value);
void smp_send_ipi(int cpu);
bool smp_is_alive(int cpu);
static int quiet_printf(const char *fmt, ...) { (void)fmt; return 0; }
#define printf quiet_printf
static int adt_path_offset_trace(void *a, const char *p, int *t) {
    (void)a; (void)p; (void)t; adt_reads++; return missing_pmgr ? -1 : 1;
}
static int adt_get_reg(void *a, int *t, const char *p, int n, u64 *b, u64 *s) {
    (void)a; (void)t; (void)p; (void)n; (void)s; adt_reads++; *b = 0x280600000UL; return 0;
}
static int adt_path_offset(void *a, const char *p) {
    (void)a; (void)p; adt_reads++; return 1;
}
static const void *adt_getprop(void *a, int n, const char *p, u32 *size) {
    (void)a; adt_reads++;
    if (!strcmp(p, "state")) return n == 1 ? "running" : "waiting";
    assert(fallback && !strcmp(p, "reg") && size);
    /* Only a single CPU's fallback pair is needed by these boundary tests. */
    static const u64 regs[] = {0, 0, 0x210150000UL, 0x9018};
    *size = fallback_bytes;
    return regs;
}
static int adt_getprop_copy(void *a, int n, const char *p, void *out, size_t size) {
    (void)a; adt_reads++;
    if (!strcmp(p, "cpu-impl-reg")) {
        if (fallback) return -1;
        u64 regs[] = {0x210150000UL, 0x9018};
        assert(size == sizeof(regs)); memcpy(out, regs, size); return size;
    }
    u32 id = n - 1;
    u32 value = !strcmp(p, "cpu-id") ? id : ((id / 6) << 8) | (id % 6);
    assert(size == sizeof(value));
    if (short_reg && !strcmp(p, "reg")) return 0;
    memcpy(out, &value, size); return size;
}
#define ADT_GETPROP(a,n,p,v) adt_getprop_copy(a,n,p,v,sizeof(*(v)))
#define ADT_GETPROP_ARRAY(a,n,p,v) adt_getprop_copy(a,n,p,v,sizeof(v))
#define ADT_FOREACH_CHILD(a,n) for (n=1; n <= (fallback ? 1 : 18); n++)
''' + definitions + '\n' + asm_header + '\n' + source + r'''
static void write32(u64 addr, u32 value) {
    assert(mmio_allowed && writes < 40);
    addresses[writes] = addr; values[writes++] = value;
    if (addr >= 0x280688008UL && addr <= 0x280688010UL) {
        assert(_reset_stack == (el3 ? secondary_stacks_el3[target_cpu] :
                                      secondary_stacks[target_cpu]) + SECONDARY_STACK_SIZE);
        if (el3) assert(_reset_stack_el1 == secondary_stacks[target_cpu] + SECONDARY_STACK_SIZE);
        if (!timeout) spin_table[target_cpu].flag = 1;
    }
}
static void mock_sysop(const char *op) {
    if (strcmp(op, "wfe")) return;
    if (timeout) {
        assert(delays == 100 && writes == 2 && target_cpu == 1);
        assert(_reset_stack == secondary_stacks[1] + SECONDARY_STACK_SIZE);
        spin_table[1].flag = 1; /* A delayed arrival cannot release quarantine. */
        if (++parked < 2) return;
    }
    longjmp(halted, 1);
}
int main(void) {
    chip_id = T6050;
    assert(smp_reset_stacks[0].mpidr == ~0ULL && !smp_reset_stacks[0].stack);
    assert(!smp_initialized);
    smp_start_secondaries(); smp_stop_secondaries(false);
    missing_pmgr = true; assert(smp_init() < 0 && !smp_initialized);
    missing_pmgr = false; assert(smp_init() == 0 && smp_initialized);
    assert(boot_cpu_idx == 0 && boot_cpu_mpidr == mock_mpidr);
    assert(smp_reset_stacks[0].mpidr == 0x40000 && smp_reset_stacks[0].stack == (u64)_stack_bot);
    for (int i = 0; i < 18; i++) {
        assert(cpu_info[i].valid && !cpu_info[i].die);
        assert(cpu_info[i].cluster == i / 6 && cpu_info[i].core == i % 6);
    }
    int cached = adt_reads;
    assert(smp_init() == 0 && adt_reads == cached);
    smp_start_secondaries(); smp_stop_secondaries(false);
    assert(!reads && !writes && adt_reads == cached); /* Guard precedes RVBAR access too. */
    smp_initialized = false; short_reg = true;
    assert(smp_init() == 0);
    for (int i = 0; i < 18; i++) assert(!cpu_info[i].valid);
    short_reg = false; fallback = true;
    for (fallback_bytes = 0; fallback_bytes <= 32; fallback_bytes++) {
        smp_initialized = false; assert(smp_init() == 0);
        assert(cpu_info[0].valid == (fallback_bytes == 32));
    }
    fallback = false; smp_initialized = false; assert(smp_init() == 0);
    mmio_allowed = true;
    struct cpu_info cpu = {.valid=true, .core=1, .impl_reg=0x210150000UL};
    wrong_vector = 0x1000; smp_start_cpu(1, &cpu); assert(!writes);
    wrong_vector = 0x800; smp_start_cpu(1, &cpu); assert(!writes);
    wrong_vector = 0;
    smp_start_cpu(-1, &cpu); smp_start_cpu(MAX_CPUS, &cpu);
    cpu.die = 2; smp_start_cpu(1, &cpu); cpu.die = 0;
    cpu.cluster = 3; smp_start_cpu(1, &cpu); cpu.cluster = 0;
    cpu.core = 6; smp_start_cpu(1, &cpu); cpu.core = 1;
    smp_start_cpu(17, &cpu); assert(!writes);
    el3 = true; cpu.core = MAX_EL3_CPUS;
    smp_start_cpu(MAX_EL3_CPUS, &cpu); assert(!writes);
    cpu.core = 1; smp_start_cpu(1, &cpu); assert(writes == 2 && spin_table[1].flag);
    spin_table[1].flag = 0; el3 = false;
    for (int i = 1; i < 18; i++) {
        cpu.cluster = i / 6; cpu.core = i % 6; writes = 0;
        smp_start_cpu(i, &cpu);
        assert(writes == 2 && spin_table[i].flag);
        assert(addresses[0] == 0x280688004UL && values[0] == (1U << i));
        assert(addresses[1] == 0x280688008UL + 4*(i/6) && values[1] == (1U << (i%6)));
        smp_stop_cpu(i, &cpu, false);
        assert(writes == 3 && addresses[2] == 0x280688000UL && values[2] == (1U << i));
        assert(!spin_table[i].flag);
    }
    assert(sleeps == 17);
    writes = 0; cpu.cluster = 0; cpu.core = 1; timeout = true;
    if (!setjmp(halted)) { smp_start_cpu(1, &cpu); assert(0); }
    assert(parked == 2 && target_cpu == 1);
    assert(_reset_stack == secondary_stacks[1] + SECONDARY_STACK_SIZE);
    timeout = false; wfe_mode = true; target_cpu = 2; mock_mpidr = 0x80040100;
    /* First entry uses the serialized target. Re-entry must ignore a stale target. */
    if (!setjmp(halted)) smp_secondary_entry();
    assert(smp_reset_stacks[2].mpidr == 0x40100 && spin_table[2].flag == 1);
    assert(smp_reset_stacks[2].stack == (u64)secondary_stacks[2] + SECONDARY_STACK_SIZE);
    target_cpu = 17;
    if (!setjmp(halted)) smp_secondary_entry();
    assert(spin_table[2].flag == 2 && !spin_table[17].flag);
    assert(smp_reset_stacks[17].mpidr == ~0ULL && !smp_reset_stacks[17].stack);
    return 0;
}
''')

    def test_shared_alias_attributes(self):
        function = extract((SOURCE / 'src/memory.c').read_text(), 'static void mmu_remap_smp_shared(')
        # These linker addresses are one synthetic 64 KiB interval on the host.
        function = function.replace('    extern u8 _smp_shared_start[], _smp_shared_end[];\n', '')
        run_c(r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef uint64_t u64;
#define _smp_shared_start ((unsigned char *)0x100000)
#define _smp_shared_end ((unsigned char *)0x110000)
#define REGION_RWX_EL0 0x8000000000UL
#define REGION_RW_EL0 0x9000000000UL
#define REGION_RX_EL1 0xa000000000UL
#define MAIR_IDX_DEVICE_nGnRnE 2
#define PERM_RW 1
#define PERM_RW_EL0 3
static unsigned calls;
static void mmu_add_mapping(u64 from, u64 to, size_t size, unsigned type, u64 perm) {
    const u64 aliases[] = {0, REGION_RWX_EL0, REGION_RW_EL0, REGION_RX_EL1};
    assert(calls < 4 && from == (0x100000UL | aliases[calls]));
    assert(to == 0x100000 && size == 0x10000 && type == MAIR_IDX_DEVICE_nGnRnE);
    assert(perm == (calls ? PERM_RW_EL0 : PERM_RW)); calls++;
}
''' + function + '\nint main(void) { mmu_remap_smp_shared(); assert(calls == 4); }\n')

    def test_initialization_and_reserved_stack_integration(self):
        main = (SOURCE / 'src/main.c').read_text()
        self.assertLess(main.index('mmu_init();'), main.index('smp_init();'))
        self.assertLess(main.index('smp_init();'), main.index('run_actions();'))
        kboot = (SOURCE / 'src/kboot.c').read_text()
        self.assertNotIn('fdt_add_mem_rsv(dt, (uint64_t)secondary_stacks', kboot)
        self.assertIn('((u64)_end) - ((u64)_base)', kboot)
        self.assertIn('fdt_add_mem_rsv(dt, (u64)_base, loader_reserved)', kboot)
        memory = extract((SOURCE / 'src/memory.c').read_text(), 'static void mmu_add_default_mappings(')
        self.assertLess(memory.index('mmu_remap_ranges();'), memory.index('mmu_remap_smp_shared();'))

    def test_builder_rejects_changed_inputs_and_bad_layout(self):
        builder = runpy.run_path(str(ROOT / 'standalone-loader/check-full-link.py'))
        # Already patched inputs must not be patched again or run a subprocess.
        with self.assertRaisesRegex(ValueError, 'input differs'):
            builder['apply_smp_refactor'](SOURCE, lambda *args: self.fail('patch ran before pin checks'))
        for name in ('m1n1.elf', 'm1n1-raw.elf'):
            symbols = {f[2]: int(f[0], 16)
                       for line in (SOURCE.parent / (name + '.symbols')).read_text().splitlines()
                       if len(f := line.split()) == 3 and f[1] != 'U'}
            sizes = {f[3]: int(f[1], 16)
                     for line in (SOURCE.parent / (name + '.sizes')).read_text().splitlines()
                     if len(f := line.split()) == 4}
            check = builder['check_smp_layout']
            check(symbols, sizes)
            for key, value in (('_smp_shared_start', symbols['_smp_shared_start'] + 1),
                               ('spin_table', symbols['_smp_shared_end']),
                               ('secondary_stacks', symbols['_end']),
                               ('_end', symbols['_bss_end'] - 1)):
                with self.assertRaises(ValueError):
                    check(dict(symbols, **{key: value}), sizes)
            with self.assertRaises(ValueError):
                check(symbols, dict(sizes, secondary_stacks=0x10000))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    args, remaining = parser.parse_known_args()
    SOURCE = args.source.resolve()
    unittest.main(argv=[__file__, *remaining], verbosity=2)
