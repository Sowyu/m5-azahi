// SPDX-License-Identifier: GPL-2.0
/* T6050 right-port SPMI4 polling prototype. NOT a complete PD controller.
 * Compile-only at this checkpoint. Both bind and transactions default OFF.
 * No IRQ domain, DT overlay, recovery reset, queue flush or IRQ-mask writes.
 */
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/spmi.h>
#include "spmi4-transport.h"

static bool allow_probe;
module_param(allow_probe, bool, 0444);
MODULE_PARM_DESC(allow_probe, "Unverified hardware experiment: permit guarded probe (default off)");
static bool allow_transactions;
module_param(allow_transactions, bool, 0444);
MODULE_PARM_DESC(allow_transactions, "Permit HPM transactions (default off; not approved for live use)");

struct azahi_spmi4 {
	void __iomem *base;
	struct mutex lock;
	struct spmi4_io io;
};

static u32 azahi_spmi4_read(void *context, u32 offset)
{
	struct azahi_spmi4 *s = context;
	return readl(s->base + offset);
}

static void azahi_spmi4_write(void *context, u32 offset, u32 value)
{
	struct azahi_spmi4 *s = context;
	writel(value, s->base + offset);
}

static void azahi_spmi4_delay(void *context, unsigned int usec)
{
	(void)context;
	usleep_range(usec, usec + 25);
}

static int azahi_spmi4_transfer(struct spmi_controller *ctrl, u8 op, u8 sid,
			      u16 addr, const u8 *out, size_t out_len,
			      u8 *in, size_t in_len)
{
	struct azahi_spmi4 *s = spmi_controller_get_drvdata(ctrl);
	int ret;
	if (!allow_transactions)
		return -EPERM;
	mutex_lock(&s->lock);
	ret = spmi4_transfer(&s->io, sid, op, addr, out, out_len, in, in_len);
	mutex_unlock(&s->lock);
	return ret;
}

static int azahi_spmi4_read_cmd(struct spmi_controller *c, u8 op, u8 sid,
			       u16 addr, u8 *buf, size_t len)
{
	if (op != SPMI_CMD_READ && op != SPMI_CMD_EXT_READ)
		return -EOPNOTSUPP;
	return azahi_spmi4_transfer(c, op, sid, addr, NULL, 0, buf, len);
}

static int azahi_spmi4_write_cmd(struct spmi_controller *c, u8 op, u8 sid,
				u16 addr, const u8 *buf, size_t len)
{
	if (op != SPMI_CMD_WRITE && op != SPMI_CMD_ZERO_WRITE &&
	    op != SPMI_CMD_EXT_WRITE)
		return -EOPNOTSUPP;
	return azahi_spmi4_transfer(c, op, sid, addr, buf, len, NULL, 0);
}

static int azahi_spmi4_cmd(struct spmi_controller *c, u8 op, u8 sid)
{
	if (op != SPMI_CMD_WAKEUP && op != SPMI_CMD_SLEEP)
		return -EOPNOTSUPP;
	return azahi_spmi4_transfer(c, op, sid, 0, NULL, 0, NULL, 0);
}

static int azahi_spmi4_probe(struct platform_device *pdev)
{
	struct spmi_controller *ctrl;
	struct azahi_spmi4 *s;
	struct resource *r;
	u32 gen;
	int ret;
	/* No MMIO or controller registration before explicit future test gates. */
	if (!allow_probe)
		return -EPERM;
	if (!of_machine_is_compatible("apple,j714s"))
		return -ENODEV;
	if (of_property_read_u32(pdev->dev.of_node, "azahi,spmi-generation", &gen) || gen != 4)
		return -EINVAL;
	r = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!r || r->start != 0x28a1a8000ULL || resource_size(r) != 0x4000)
		return -EINVAL;
	ctrl = devm_spmi_controller_alloc(&pdev->dev, sizeof(*s));
	if (IS_ERR(ctrl))
		return PTR_ERR(ctrl);
	s = spmi_controller_get_drvdata(ctrl);
	s->base = devm_ioremap_resource(&pdev->dev, r);
	if (IS_ERR(s->base))
		return PTR_ERR(s->base);
	mutex_init(&s->lock);
	s->io = (struct spmi4_io) {
		.context = s, .read = azahi_spmi4_read,
		.write = azahi_spmi4_write, .delay = azahi_spmi4_delay,
	};
	if (!spmi4_idle(readl(s->base + SPMI4_STATUS)))
		return -EBUSY;
	ctrl->dev.of_node = pdev->dev.of_node;
	ctrl->read_cmd = azahi_spmi4_read_cmd;
	ctrl->write_cmd = azahi_spmi4_write_cmd;
	ctrl->cmd = azahi_spmi4_cmd;
	ret = devm_spmi_controller_add(&pdev->dev, ctrl);
	if (ret)
		return ret;
	dev_warn(&pdev->dev, "EXPERIMENTAL SPMI4 polling; no IRQ domain, not a complete PD driver\n");
	return 0;
}

static const struct of_device_id azahi_spmi4_match[] = {
	{ .compatible = "azahi,t6050-spmi4-experimental" },
	{}
};
MODULE_DEVICE_TABLE(of, azahi_spmi4_match);
static struct platform_driver azahi_spmi4_driver = {
	.probe = azahi_spmi4_probe,
	.driver = { .name = "azahi-spmi4-experimental", .of_match_table = azahi_spmi4_match },
};
module_platform_driver(azahi_spmi4_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Unverified, default-disabled T6050 SPMI4 polling prototype");
