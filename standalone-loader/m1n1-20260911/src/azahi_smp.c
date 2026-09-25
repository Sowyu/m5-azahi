/* SPDX-License-Identifier: MIT */
/*
 * Private J714s (T6050 / M5 Pro) secondary-CPU startup diagnostic.
 *
 * Problem. On T6050 the stock m1n1 CPU-start path (src/smp.c) that brings up
 * every secondary on M1..M4 leaves the M5 secondaries powered but not running:
 * PMGR reports the core active (PS_ACTUAL goes 0x100 -> 0x1f0) but the core
 * never stores its reset-trace marker, so it never executes loader code. This
 * matches the upstream note on the initial T6050 support ("the cores turn on
 * as can be seen in pmgr, but never start executing our code", AsahiLinux/m1n1
 * PR #610, commit b2d3f5e) and the repo's own V1..V5 live checkpoints
 * (research-archive/probe/CPU-CHECKPOINT.md).
 *
 * The M4 result does NOT transfer. The damsleth/wallace M4 Pro (T6040) project
 * brings up all 14 secondaries with the same bare PMGR CPU_START write, so
 * SPTM being resident is not by itself the blocker. Something specific to the
 * T6050 reset-release path is. See docs/audit-2026-09-25/smp.md for the ranked
 * diagnosis; the two live-testable candidates are:
 *
 *   (A) The PMGR CPU_START "system enable" register (cpu_start_base + 0x4) is
 *       not a plain RW register on T6050. iBoot leaves it holding 0x3fffe
 *       (bits 1..17, i.e. every secondary pre-enabled). smp_start_cpu()
 *       OVERWRITES it with 1 << (4*cluster+core); the one recorded live read
 *       went 0x3fffe -> 0x3fffc, i.e. the target core's own enable bit came
 *       back CLEARED, not set. If +0x4 latches/auto-clears, the stock write
 *       disables the very core it then tries to start. Candidate fix: on
 *       T6050 do not clobber +0x4 (rely on iBoot's mask), or OR the bit in.
 *
 *   (B) The secondary reset entry is owned by the Apple guarded monitor
 *       (SPTM/firmware), not by the per-core Apple reset vector m1n1 writes.
 *       The 48 KiB WFI-filled block in the CTRR-locked, secondary-only range
 *       (CPU-CHECKPOINT.md) is where an unassigned core parks. If so, no
 *       loader-only register poke can release the core and secondaries need
 *       secure-monitor cooperation Linux cannot get outside SPTM.
 *
 * This file does not itself pick a winner; it captures, in one attended boot,
 * the registers that tell (A) from (B):
 *   - probe: the per-secondary Apple reset vector (cpu-impl-reg[0]) and its
 *     lock bit, compared to the loader entry _vectors_start, plus the whole
 *     CPU_START bank on die 0, all read-only.
 *   - start: CPU_START before, the stock smp_start_secondaries() (bounded),
 *     CPU_START after, and smp_is_alive() per core. The before/after of +0x4
 *     shows whether the stock write clears the enable bit (candidate A), and
 *     alive==false with a correct, locked reset vector points at (B).
 *
 * SAFETY. probe writes nothing. start calls only the stock loader path, which
 * writes just the PMGR CPU_START bank at pmgr_reg + 0x88000 (CPU cores only;
 * not the apcie/ANS storage domain at 0x2809xxxxx). Every wait is bounded and
 * the boot continues either way. Default-off: no "azahi.smp=" token, no-op.
 *
 * Not for upstream. Compile-checked against upstream m1n1 headers; runs in the
 * private standalone-loader m1n1 tree alongside azahi_standalone.c.
 */

#include "adt.h"
#include "smp.h"
#include "soc.h"
#include "string.h"
#include "utils.h"

#include "azahi_smp.h"

/* Matches src/smp.c for T6031/T6040/T6050/T6051. */
#define CPU_START_OFF_T6050 0x88000

#define CPU_REG_CORE    GENMASK(7, 0)
#define CPU_REG_CLUSTER GENMASK(10, 8)
#define CPU_REG_DIE     GENMASK(14, 11)

#define RVBAR_LOCK BIT(0)
#define RVBAR_ADDR GENMASK(47, 12)

/* _vectors_start is the loader reset entry (src/start.S); iBoot locks each
 * secondary's Apple reset vector to it on the SoCs where SMP works. */
extern u8 _vectors_start[0];

static const char *azahi_smp_mode(const char *cmdline)
{
    if (!cmdline)
        return NULL;
    const char *p = strstr(cmdline, "azahi.smp=");
    if (!p)
        return NULL;
    return p + sizeof("azahi.smp=") - 1;
}

static bool azahi_smp_mode_is(const char *val, const char *want)
{
    size_t n = strlen(want);
    if (strncmp(val, want, n) != 0)
        return false;
    char after = val[n];
    return after == 0 || after == ' ' || after == '\t';
}

/* Resolve /arm-io/pmgr reg[0] the same way src/smp.c does (absolute address,
 * parent ranges applied: 0x280600000 live). */
static int azahi_smp_pmgr_reg(u64 *pmgr_reg)
{
    int pmgr_path[8];

    if (adt_path_offset_trace(adt, "/arm-io/pmgr", pmgr_path) < 0) {
        printf("AZAHI_SMP: no /arm-io/pmgr node\n");
        return -1;
    }
    if (adt_get_reg(adt, pmgr_path, "reg", 0, pmgr_reg, NULL) < 0) {
        printf("AZAHI_SMP: no /arm-io/pmgr reg\n");
        return -1;
    }
    return 0;
}

/* Die 0 only. The J714s (M5 Pro) has all 18 CPUs on die 0; the restore-image
 * ADT template also lists die-2 CPUs, and no evidence places a die-1 PMGR at
 * +0x2000000000 on this SoC. Reading an unmapped address can SError. */
static void azahi_smp_dump_cpu_start(u64 pmgr_reg)
{
    u64 base = pmgr_reg + CPU_START_OFF_T6050;
    printf("AZAHI_SMP: die0 CPU_START @0x%lx: +0=0x%x +4=0x%x +8=0x%x +c=0x%x +10=0x%x\n",
           base, read32(base + 0x0), read32(base + 0x4), read32(base + 0x8),
           read32(base + 0xc), read32(base + 0x10));
}

/* Read-only per-secondary dump. Only touches the Apple reset vector register
 * (cpu-impl-reg[0]); src/smp.c reads exactly this offset before start, so it is
 * safe even while the core is powered down. It does NOT touch impl+0x100 (the
 * CPU status/stop register), which is only safe on a running core. */
static void azahi_smp_probe(void)
{
    int node = adt_path_offset(adt, "/cpus");
    if (node < 0) {
        printf("AZAHI_SMP: no /cpus node\n");
        return;
    }

    u64 entry = (u64)_vectors_start;
    printf("AZAHI_SMP: loader entry _vectors_start = 0x%lx, boot MPIDR = 0x%lx, boot_cpu_idx = %d\n",
           entry, mrs(MPIDR_EL1) & 0xFFFFFF, boot_cpu_idx);

    ADT_FOREACH_CHILD(adt, node)
    {
        u32 cpu_id, reg;
        u64 impl_reg[2];

        if (ADT_GETPROP(adt, node, "cpu-id", &cpu_id) < 0)
            continue;
        if (ADT_GETPROP(adt, node, "reg", &reg) < 0)
            continue;
        if (ADT_GETPROP_ARRAY(adt, node, "cpu-impl-reg", impl_reg) < 0)
            continue;

        u8 core = FIELD_GET(CPU_REG_CORE, reg);
        u8 cluster = FIELD_GET(CPU_REG_CLUSTER, reg);
        u8 die = FIELD_GET(CPU_REG_DIE, reg);
        const char *state = adt_getprop(adt, node, "state", NULL);

        if (die != 0) {
            printf("AZAHI_SMP: cpu%-2u die%u skipped (only die 0 is populated on J714s)\n",
                   cpu_id, die);
            continue;
        }

        u64 rv = read64(impl_reg[0]);
        u64 rvbar = rv & RVBAR_ADDR;
        bool locked = FIELD_GET(RVBAR_LOCK, rv);
        const char *verdict = (rvbar == entry) ? "==entry" : "!=entry";

        printf("AZAHI_SMP: cpu%-2u die%u cl%u co%u state=%s impl=0x%lx rvbar=0x%lx lock=%d %s\n",
               cpu_id, die, cluster, core, state ? state : "?", impl_reg[0], rvbar, locked,
               verdict);
    }
}

/* Start experiment: the stock loader path plus before/after evidence. */
static void azahi_smp_start(u64 pmgr_reg)
{
    printf("AZAHI_SMP: CPU_START before smp_start_secondaries():\n");
    azahi_smp_dump_cpu_start(pmgr_reg);

    smp_start_secondaries();

    printf("AZAHI_SMP: CPU_START after smp_start_secondaries():\n");
    azahi_smp_dump_cpu_start(pmgr_reg);

    int node = adt_path_offset(adt, "/cpus");
    if (node < 0)
        return;

    int alive = 0, total = 0;
    ADT_FOREACH_CHILD(adt, node)
    {
        u32 cpu_id;
        if (ADT_GETPROP(adt, node, "cpu-id", &cpu_id) < 0)
            continue;
        if ((int)cpu_id == boot_cpu_idx)
            continue;
        total++;
        bool a = smp_is_alive(cpu_id);
        if (a)
            alive++;
        printf("AZAHI_SMP: cpu%-2u alive=%d\n", cpu_id, a);
    }
    printf("AZAHI_SMP: %d/%d secondaries alive\n", alive, total);
}

void azahi_smp_diag(const char *cmdline)
{
    const char *mode = azahi_smp_mode(cmdline);
    if (!mode)
        return;

    if (chip_id != T6050 && chip_id != T6051) {
        printf("AZAHI_SMP: chip 0x%x is not T6050/T6051, ignoring azahi.smp\n", chip_id);
        return;
    }

    u64 pmgr_reg;
    if (azahi_smp_pmgr_reg(&pmgr_reg) < 0)
        return;

    printf("AZAHI_SMP: pmgr_reg = 0x%lx, cpu_start_base = 0x%lx\n", pmgr_reg,
           pmgr_reg + CPU_START_OFF_T6050);

    if (azahi_smp_mode_is(mode, "probe")) {
        azahi_smp_probe();
        azahi_smp_dump_cpu_start(pmgr_reg);
        printf("AZAHI_SMP: probe done (read-only)\n");
    } else if (azahi_smp_mode_is(mode, "start")) {
        azahi_smp_probe();
        azahi_smp_start(pmgr_reg);
        printf("AZAHI_SMP: start done\n");
    } else {
        printf("AZAHI_SMP: unknown azahi.smp mode, expected probe|start\n");
    }
}
