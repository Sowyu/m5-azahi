/* SPDX-License-Identifier: MIT */
#ifndef AZAHI_SMP_H
#define AZAHI_SMP_H

/* Default-off J714s diagnostic. azahi.smp=probe reads only the validated
 * CPU reset registers and PMGR CPU_START bank. Other modes are refused before
 * hardware access. Return 0 for success/no request, -1 for a refused request
 * or unexpected ADT layout. The caller must stop handoff on a negative result.
 * Read-only MMIO can still fault; this is not a hardware-safety guarantee.
 */
int azahi_smp_diag(const char *cmdline);

#endif
