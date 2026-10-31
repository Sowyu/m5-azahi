/* SPDX-License-Identifier: GPL-2.0-only */
/* Fixed J714s PMU controller ownership and clock lifetime. */
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/iopoll.h>
#include <linux/of.h>
#include "pmu-transport.h"
#define BASE 0x28a014000ULL
#define SIZE 0x4000
static void __iomem *base;
static struct resource *resource;
static struct resource *clock_resource;
static void __iomem *clock_base;
static u32 clock_original;
static bool clock_held;
static struct pmu_io bus;
static pmu_u32 bus_read(void *ctx, pmu_u32 reg) { return readl(base + reg); }
static void bus_write(void *ctx, pmu_u32 reg, pmu_u32 val) { writel(val, base + reg); }
static void bus_delay(void *ctx, unsigned int us) { usleep_range(us, us + 25); }
static void release_maps(void)
{
	if (base) iounmap(base);
	if (resource) release_mem_region(BASE, SIZE);
	base = NULL; resource = NULL;
	if (clock_held) {
		u32 v = readl(clock_base);
		/* Restore only the automatic clock-gating bit; never reset/gate it. */
		v = (v & ~((1u << 28) | 0x300u)) | (clock_original & (1u << 28));
		writel(v, clock_base);
	}
	if (clock_base) iounmap(clock_base);
	if (clock_resource) release_mem_region(0x288300120ULL, 4);
	clock_base = NULL; clock_resource = NULL; clock_held = false;
}
static int pmu_open(bool hold_clock)
{
	void __iomem *pmgr;
	u32 ahb, spmi, fifo;
	int result;
	if (!of_machine_is_compatible("apple,j714s") ||
	    !of_machine_is_compatible("apple,t6050")) return -ENODEV;
	pmgr = ioremap_np(0x288300000ULL, SIZE);
	if (!pmgr) return -ENOMEM;
	ahb = readl(pmgr + 0x118); spmi = readl(pmgr + 0x120);
	iounmap(pmgr);
	pr_info("azahi-pmu: AHB=%#x SPMI0=%#x\n", ahb, spmi);
	if ((ahb & 0xff) != 0xff || (spmi & 0xf) != 0xf ||
	    ((ahb | spmi) & ((1u << 31) | (1u << 10) | (1u << 11) | (1u << 12)))) return -EHOSTDOWN;
	if (hold_clock) {
		clock_resource = request_mem_region(0x288300120ULL, 4, "azahi-pmu-clock");
		if (!clock_resource) return -EBUSY;
		clock_base = ioremap_np(0x288300120ULL, 4);
		if (!clock_base) { release_maps(); return -ENOMEM; }
		clock_original = readl(clock_base);
		if (clock_original != spmi) {
			/* Actual clock state and sticky flags may change autonomously. */
			if ((clock_original ^ spmi) & ~0x3f0u) { release_maps(); return -EBUSY; }
		}
		writel(clock_original & ~((1u << 28) | 0x300u), clock_base);
		clock_held = true;
		result = readl_poll_timeout(clock_base, spmi, (spmi & 0xff) == 0xff, 1, 1000);
		pr_info("azahi-pmu: held SPMI0=%#x result=%d\n", spmi, result);
		if (result) { release_maps(); return result; }
	}
	if ((spmi & 0xff) != 0xff) { release_maps(); return -EHOSTDOWN; }
	resource = request_mem_region(BASE, SIZE, "azahi-pmu");
	if (!resource) { release_maps(); return -EBUSY; }
	base = ioremap_np(BASE, SIZE);
	if (!base) { release_maps(); return -ENOMEM; }
	fifo = readl(base + PMU_STATUS);
	pr_info("azahi-pmu: fifo=%#x\n", fifo);
	if (!pmu_idle(fifo)) { release_maps(); return -EBUSY; }
	bus = (struct pmu_io){.read = bus_read, .write = bus_write, .delay = bus_delay};
	return 0;
}
