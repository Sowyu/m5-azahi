/* SPDX-License-Identifier: MIT */
#ifndef AZAHI_PCIE_H
#define AZAHI_PCIE_H

/*
 * Opt-in apcie0 Wi-Fi PCIe bring-up for T6050 / J714s. No-op unless the kernel
 * cmdline contains "azahi.pcie=probe" (read-only dump) or "azahi.pcie=bringup"
 * (the guarded register sequence). Returns 0 on success or opt-out, negative on
 * a bounded failure (boot always continues). The overlay's PCIe and DART nodes
 * in @fdt ship disabled; only a completed bring-up sets them to "okay", so
 * Linux never probes hardware this loader did not power and initialise.
 * See azahi_pcie.c.
 */
int azahi_pcie_init(const char *cmdline, void *fdt);

#endif
