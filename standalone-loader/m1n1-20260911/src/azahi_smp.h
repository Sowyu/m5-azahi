/* SPDX-License-Identifier: MIT */
#ifndef AZAHI_SMP_H
#define AZAHI_SMP_H

/*
 * Default-off T6050 secondary-CPU diagnostic. No-op unless the kernel cmdline
 * contains an "azahi.smp=" token:
 *
 *   (absent)            -> do nothing (default; one-core boot behaviour).
 *   azahi.smp=probe     -> read-only dump of the discriminating registers:
 *                          per-secondary Apple reset vector (cpu-impl-reg[0]),
 *                          its lock bit vs the loader entry, and the PMGR
 *                          CPU_START bank (+0x0/+0x4/+0x8/+0xc/+0x10) on die 0,
 *                          the only populated die on J714s. No writes.
 *   azahi.smp=start     -> dump CPU_START, run the stock smp_start_secondaries()
 *                          (its own 100 ms/core bounded wait), dump CPU_START
 *                          again, then report smp_is_alive() per core. The
 *                          private smp.c returns early on T6050
 *                          (AZAHI_ONE_CORE): remove that first, or start is a
 *                          no-op.
 *
 * Always returns after a bounded time; it cannot hang the attended boot. It
 * writes no hardware in probe mode, and in start mode only the registers the
 * stock loader already writes. See azahi_smp.c for the full rationale and the
 * candidate fix this diagnostic gates.
 */
void azahi_smp_diag(const char *cmdline);

#endif
