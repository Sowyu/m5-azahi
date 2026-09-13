// SPDX-License-Identifier: GPL-2.0
/* One-shot native HPM startup candidate. Default: power/FIFO reads only.
 * Does not register SPMI children or modify USB/DWC3/PHY devices.
 * Inspect result/ready in sysfs; a loaded module alone is NOT success.
 */
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/string.h>
#include "hpm-awake.h"

#define BASE 0x28a1a8000ULL
#define SIZE 0x4000
static char *mode = "status";
module_param(mode, charp, 0444);
static int result = -EINPROGRESS;
module_param(result, int, 0444);
static bool ready;
module_param(ready, bool, 0444);
static bool poisoned;
module_param(poisoned, bool, 0444);
static void __iomem *base;
static struct resource *resource;
static struct spmi4_io bus;

static spmi4_u32 bus_read(void *ctx, spmi4_u32 reg) { return readl(base + reg); }
static void bus_write(void *ctx, spmi4_u32 reg, spmi4_u32 value) { writel(value, base + reg); }
static void bus_delay(void *ctx, unsigned int us) { usleep_range(us, us + 25); }
static void hpm_delay(void *ctx, unsigned int ms) { msleep(ms); }
static int transfer(void *ctx, unsigned int op, unsigned int addr,
		    const spmi4_u8 *out, size_t outlen, spmi4_u8 *in, size_t inlen)
{
	return spmi4_transfer(&bus, 12, op, addr, out, outlen, in, inlen);
}
static void release_maps(void)
{
	if (base) iounmap(base);
	if (resource) release_mem_region(BASE, SIZE);
	base = NULL; resource = NULL;
}
static int __init init_once(void)
{
	void __iomem *pmgr;
	u32 power, fifo;
	struct hpm_snapshot snapshot = {0};
	struct hpm_io h = {.xfer = transfer, .delay_ms = hpm_delay};
	if (strcmp(mode, "status") && strcmp(mode, "probe") && strcmp(mode, "awake")) return -EINVAL;
	if (!of_machine_is_compatible("apple,j714s")) return -ENODEV;
	/* Always-on power status only; never write PMGR or read a gated FIFO. */
	pmgr = ioremap_np(0x288300000ULL, SIZE);
	if (!pmgr) return -ENOMEM;
	power = readl(pmgr + 0x68);
	iounmap(pmgr);
	pr_info("azahi-hpm-once: controller power=%#x mode=%s\n", power, mode);
	if ((power & 0xff) != 0xff || (power & ((1u << 31) | (1u << 10) | (1u << 11)))) return -EHOSTDOWN;
	resource = request_mem_region(BASE, SIZE, "azahi-hpm-once");
	if (!resource) return -EBUSY;
	base = ioremap_np(BASE, SIZE);
	if (!base) { release_maps(); return -ENOMEM; }
	fifo = readl(base + SPMI4_STATUS);
	pr_info("azahi-hpm-once: fifo=%#x\n", fifo);
	if (!spmi4_idle(fifo)) { release_maps(); return -EBUSY; }
	bus = (struct spmi4_io){.read = bus_read, .write = bus_write, .delay = bus_delay};
	if (!strcmp(mode, "status")) { result = 0; return 0; }
	result = transfer(NULL, 0x13, 0, NULL, 0, NULL, 0);
	if (!result) {
		msleep(100);
		result = hpm_awake_once(&h, &snapshot, !strcmp(mode, "awake"));
	}
	ready = !result && snapshot.state == 0;
	poisoned = !!bus.poisoned || !!h.failed;
	pr_info("azahi-hpm-once: result=%d ready=%d poisoned=%d state=%u status=%#x power=%#x data=%#x\n",
		result, ready, poisoned, snapshot.state, snapshot.status, snapshot.power, snapshot.data);
	/* Keep ambiguous bus state pinned until reboot. No automatic retry. */
	if (poisoned) __module_get(THIS_MODULE);
	return 0;
}
static void __exit exit_once(void) { release_maps(); }
module_init(init_once);
module_exit(exit_once);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Guarded one-shot J714s HPM wake candidate, default read-only status");
