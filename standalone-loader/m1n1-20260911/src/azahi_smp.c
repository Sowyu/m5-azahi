/* SPDX-License-Identifier: MIT */
/* Read-only J714s CPU reset-vector diagnostic. Opt in with azahi.smp=probe.
 * A matching RVBAR does not prove that firmware releases the core to it.
 * CPU_START +4 is a trigger, not a persistent enable mask. Keep its write
 * sequence intact. See smp/README.md and docs/audit-2026-09-25/smp.md.
 *
 * Startup is deliberately refused here. The patched SMP loop quarantines a
 * timed-out start, but reset release remains unproven.
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
/* T6050 iBoot's reset-vector writer preserves bit 11. */
#define RVBAR_ADDR GENMASK(41, 11)

/* _vectors_start is the loader reset entry (src/start.S); iBoot locks each
 * secondary's Apple reset vector to it on the SoCs where SMP works. */
extern u8 _vectors_start[0];

static const char *azahi_smp_mode(const char *cmdline)
{
    const char *mode = NULL;
    if (!cmdline)
        return NULL;
    while (*cmdline) {
        while (*cmdline == ' ' || *cmdline == '\t')
            cmdline++;
        if (!strncmp(cmdline, "--", 2) &&
            (!cmdline[2] || cmdline[2] == ' ' || cmdline[2] == '\t'))
            break; /* The remaining tokens are init arguments. */
        if (!strncmp(cmdline, "azahi.smp=", sizeof("azahi.smp=") - 1)) {
            if (mode)
                return ""; /* Ambiguous requests must not select a mode. */
            mode = cmdline + sizeof("azahi.smp=") - 1;
        }
        while (*cmdline && *cmdline != ' ' && *cmdline != '\t')
            cmdline++;
    }
    return mode;
}

static bool azahi_smp_mode_is(const char *val, const char *want)
{
    if (!val)
        return false;
    size_t n = strlen(want);
    if (strncmp(val, want, n) != 0)
        return false;
    return val[n] == 0 || val[n] == ' ' || val[n] == '\t';
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
    u64 size;
    if (adt_get_reg(adt, pmgr_path, "reg", 0, pmgr_reg, &size) < 0 ||
        *pmgr_reg != 0x280600000UL || size < CPU_START_OFF_T6050 + 0x14) {
        printf("AZAHI_SMP: unexpected J714s PMGR register range\n");
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
 * (cpu-impl-reg[0]); src/smp.c reads this offset before start, and previous
 * J714s probes read it with the secondary powered down. It does not touch
 * impl+0x100, the CPU status/stop register. MMIO faults remain possible. */
static int azahi_smp_probe(void)
{
    int node = adt_path_offset(adt, "/cpus");
    if (node < 0) {
        printf("AZAHI_SMP: no /cpus node\n");
        return -1;
    }

    u64 entry = (u64)_vectors_start;
    printf("AZAHI_SMP: loader entry _vectors_start = 0x%lx, boot MPIDR = 0x%lx, boot_cpu_idx = %d\n",
           entry, mrs(MPIDR_EL1) & 0xFFFFFF, boot_cpu_idx);

    unsigned seen = 0;
    ADT_FOREACH_CHILD(adt, node)
    {
        u32 cpu_id, reg;
        u64 impl_reg[2];

        if (ADT_GETPROP(adt, node, "cpu-id", &cpu_id) != sizeof(cpu_id) ||
            ADT_GETPROP(adt, node, "reg", &reg) != sizeof(reg) ||
            ADT_GETPROP_ARRAY(adt, node, "cpu-impl-reg", impl_reg) != sizeof(impl_reg)) {
            printf("AZAHI_SMP: incomplete CPU properties\n");
            return -1;
        }

        u8 core = FIELD_GET(CPU_REG_CORE, reg);
        u8 cluster = FIELD_GET(CPU_REG_CLUSTER, reg);
        u8 die = FIELD_GET(CPU_REG_DIE, reg);
        const char *state = adt_getprop(adt, node, "state", NULL);

        if (die != 0) {
            printf("AZAHI_SMP: cpu%-2u die%u skipped (only die 0 is populated on J714s)\n",
                   cpu_id, die);
            continue;
        }

        if (cpu_id >= 18 || cluster >= 3 || core >= 6 ||
            cpu_id != 6U * cluster + core || (seen & (1U << cpu_id)) ||
            impl_reg[0] != 0x210050000UL + ((u64)cluster << 24) + ((u64)core << 20) ||
            impl_reg[1] < sizeof(u64)) {
            printf("AZAHI_SMP: unexpected J714s CPU layout; refusing register read\n");
            return -1;
        }
        seen |= 1U << cpu_id;

        u64 rv = read64(impl_reg[0]);
        u64 rvbar = rv & RVBAR_ADDR;
        bool locked = FIELD_GET(RVBAR_LOCK, rv);
        const char *verdict = (rvbar == entry) ? "==entry" : "!=entry";

        printf("AZAHI_SMP: cpu%-2u die%u cl%u co%u state=%s impl=0x%lx rvbar=0x%lx lock=%d %s\n",
               cpu_id, die, cluster, core, state ? state : "?", impl_reg[0], rvbar, locked,
               verdict);
    }
    if (seen != 0x3ffff) {
        printf("AZAHI_SMP: expected all 18 die-0 CPU records\n");
        return -1;
    }
    return 0;
}

int azahi_smp_diag(const char *cmdline)
{
    const char *mode = azahi_smp_mode(cmdline);
    if (!mode)
        return 0;
    if (!azahi_smp_mode_is(mode, "probe")) {
        printf("AZAHI_SMP: refused mode; only azahi.smp=probe is supported\n");
        return -1;
    }
    const char *target = adt_getprop(adt, 0, "target-type", NULL);
    if (chip_id != T6050 || board_id != 8 || !target || strcmp(target, "J714s")) {
        printf("AZAHI_SMP: probe is only validated for J714s T6050\n");
        return -1;
    }
    u64 pmgr_reg;
    if (azahi_smp_pmgr_reg(&pmgr_reg) < 0 || azahi_smp_probe() < 0)
        return -1;
    azahi_smp_dump_cpu_start(pmgr_reg);
    printf("AZAHI_SMP: probe done (read-only); reset ownership remains unproven\n");
    return 0;
}
