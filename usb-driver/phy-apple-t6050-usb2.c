// SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause
/*
 * Apple T6050 ("M5 Pro", Mac17,9 / J714s) eUSB2 PHY -- experimental USB2 host-only provider.
 *
 * The register sequence is a transcription of the saved Mac17,9 kernelcache
 * (probe/firmware-analysis/kernelcache.mac17j.macho):
 *   AppleT6050TypeCPhy::eusb2phy_init(bool primary, bool secondary)  VA 0xfffffe0009a3b744
 *   AppleT6050TypeCPhy::eusb2phy_shutdown()                          VA 0xfffffe0009a3ce54
 *   AppleT6050TypeCPhy::initUSB2(unsigned)                           VA 0xfffffe0009a76e98
 * The XHCI host path calls initUSB2(0x40000) -> eusb2phy_init(false, false).
 * Bank 0 is the ADT atc-phy reg[0] block, bank 1 is reg[1] (see README.md).
 *
 * Differences from the M4 slice this is modelled on: the host/device signal
 * bits are not hard coded, they come from the ADT tunables
 * tunable_USB2PHY_DFLT and tunable_USB2PHY_HOST, exactly as the M5 driver
 * applies them through AppleT6050TypeCPhy::applyTunables(0, data).
 *
 * Private one-machine bring-up code. Not for upstream submission.
 */

#include <dt-bindings/phy/phy.h>
#include <linux/bitfield.h>
#include <linux/bitops.h>
#include <linux/cleanup.h>
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/phy/phy.h>
#include <linux/platform_device.h>

/* Bank 0: USB2 PHY control (ADT atc-phy reg[0], 0x382a90000 for instance 2) */
#define USB2PHY_USBCTL			0x00
#define USB2PHY_USBCTL_MODE		GENMASK(2, 0)
#define USB2PHY_USBCTL_MODE_RUN		2	/* eusb2phy_init: (primary && secondary) ? 0 : 2 */
#define USB2PHY_USBCTL_MODE_ISOLATION	4	/* eusb2phy_shutdown */

#define USB2PHY_CTL			0x04
#define USB2PHY_CTL_RESET		BIT(0)
#define USB2PHY_CTL_PORT_RESET		BIT(1)
#define USB2PHY_CTL_APB_RESET_N		BIT(2)
#define USB2PHY_CTL_SIDDQ		BIT(3)

#define USB2PHY_SIG			0x08	/* only touched through the tunables */
#define USB2PHY_UNK18			0x18	/* only touched through tunable_USB2PHY_DFLT */

#define USB2PHY_MISCTUNE		0x1c
#define USB2PHY_MISCTUNE_APBCLK_GATE_OFF	BIT(29)
#define USB2PHY_MISCTUNE_REFCLK_GATE_OFF	BIT(30)

/* Bank 1: USB2 event block (ADT atc-phy reg[1], 0x382800000 for instance 2) */
#define USB2PHY_EVT_CTL			0x00
#define USB2PHY_EVT_CTL_EN		BIT(0)
#define USB2PHY_EVT_CTL_LOAD_CNT	BIT(3)
#define USB2PHY_EVT_STATUS		0x20

/*
 * ADT tunable entry as consumed by AppleT6050TypeCPhy::applyTunables():
 * word0 bits 31:27 = access width code (4 == 32-bit), bits 26:0 = offset,
 * word1 = mask of bits to clear, word2 = bits to set.
 */
#define TUNABLE_OFFSET_MASK		GENMASK(26, 0)
#define TUNABLE_WIDTH_SHIFT		27
#define TUNABLE_WIDTH_32		4
#define TUNABLE_MAX_ENTRIES		16
#define BANK_SIZE			0x4000

struct t6050_tunable {
	u32 offset;
	u32 mask;
	u32 value;
};

struct t6050_usb2_phy {
	struct device *dev;
	void __iomem *usb2;
	void __iomem *evt;
	struct phy *phy;
	struct mutex lock;
	enum phy_mode mode;
	bool powered;
	u32 sig_clear;
	int n_dflt;
	int n_host;
	struct t6050_tunable dflt[TUNABLE_MAX_ENTRIES];
	struct t6050_tunable host[TUNABLE_MAX_ENTRIES];
};

static inline void t6050_mask32(void __iomem *reg, u32 clear, u32 set)
{
	u32 value = readl(reg);

	value &= ~clear;
	value |= set;
	writel(value, reg);
}

static inline void t6050_set32(void __iomem *reg, u32 set)
{
	t6050_mask32(reg, 0, set);
}

static inline void t6050_clear32(void __iomem *reg, u32 clear)
{
	t6050_mask32(reg, clear, 0);
}

static void t6050_usb2_dump(struct t6050_usb2_phy *tphy, const char *when)
{
	dev_info(tphy->dev,
		 "%s: usbctl %#x ctl %#x sig %#x unk18 %#x misctune %#x evt_ctl %#x evt_status %#x\n",
		 when, readl(tphy->usb2 + USB2PHY_USBCTL), readl(tphy->usb2 + USB2PHY_CTL),
		 readl(tphy->usb2 + USB2PHY_SIG), readl(tphy->usb2 + USB2PHY_UNK18),
		 readl(tphy->usb2 + USB2PHY_MISCTUNE), readl(tphy->evt + USB2PHY_EVT_CTL),
		 readl(tphy->evt + USB2PHY_EVT_STATUS));
}

/* AppleT6050TypeCPhy::applyTunables(0, data): bank 0, 32-bit read/modify/write, skip if unchanged */
static void t6050_apply_tunables(struct t6050_usb2_phy *tphy, const struct t6050_tunable *t, int n,
				 const char *name)
{
	int i;

	for (i = 0; i < n; i++) {
		u32 old = readl(tphy->usb2 + t[i].offset);
		u32 new = (old & ~t[i].mask) | t[i].value;

		dev_dbg(tphy->dev, "%s[%d]: +%#x %#x -> %#x\n", name, i, t[i].offset, old, new);
		if (new != old)
			writel(new, tphy->usb2 + t[i].offset);
	}
}

/* AppleT6050TypeCPhy::eusb2phy_shutdown(), in order */
static void t6050_usb2_shutdown_seq(struct t6050_usb2_phy *tphy)
{
	if (!(readl(tphy->usb2 + USB2PHY_CTL) & USB2PHY_CTL_PORT_RESET)) {
		t6050_set32(tphy->usb2 + USB2PHY_CTL, USB2PHY_CTL_PORT_RESET);
		msleep(5);
	}
	t6050_mask32(tphy->usb2 + USB2PHY_USBCTL, USB2PHY_USBCTL_MODE,
		     FIELD_PREP(USB2PHY_USBCTL_MODE, USB2PHY_USBCTL_MODE_ISOLATION));
	t6050_set32(tphy->usb2 + USB2PHY_CTL, USB2PHY_CTL_SIDDQ);
	t6050_set32(tphy->usb2 + USB2PHY_CTL, USB2PHY_CTL_RESET);
	t6050_set32(tphy->usb2 + USB2PHY_MISCTUNE, USB2PHY_MISCTUNE_APBCLK_GATE_OFF);
	t6050_set32(tphy->usb2 + USB2PHY_MISCTUNE, USB2PHY_MISCTUNE_REFCLK_GATE_OFF);
	udelay(1);	/* IOPause(500 ns) */
}

/* AppleT6050TypeCPhy::eusb2phy_init(false, false), in order */
static void t6050_usb2_init_seq(struct t6050_usb2_phy *tphy)
{
	u32 status;

	/*
	 * Local deviation, documented in README.md: the loader initialised this
	 * PHY for device mode with the M1-era value 0x01c1000f in USB2PHY_SIG.
	 * The M5 host path never sets bits 2,3,16,22,23,24, so drop them before
	 * applying the tunables (which only own mask 0x7003).
	 */
	if (tphy->sig_clear)
		t6050_clear32(tphy->usb2 + USB2PHY_SIG, tphy->sig_clear);

	t6050_apply_tunables(tphy, tphy->dflt, tphy->n_dflt, "tunable_USB2PHY_DFLT");
	t6050_apply_tunables(tphy, tphy->host, tphy->n_host, "tunable_USB2PHY_HOST");

	msleep(10);

	t6050_clear32(tphy->usb2 + USB2PHY_CTL, USB2PHY_CTL_SIDDQ);
	udelay(10);
	t6050_clear32(tphy->usb2 + USB2PHY_CTL, USB2PHY_CTL_RESET);
	t6050_clear32(tphy->usb2 + USB2PHY_CTL, USB2PHY_CTL_PORT_RESET);

	t6050_set32(tphy->evt + USB2PHY_EVT_CTL, USB2PHY_EVT_CTL_LOAD_CNT | USB2PHY_EVT_CTL_EN);

	t6050_set32(tphy->usb2 + USB2PHY_CTL, USB2PHY_CTL_APB_RESET_N);
	t6050_clear32(tphy->usb2 + USB2PHY_MISCTUNE, USB2PHY_MISCTUNE_APBCLK_GATE_OFF);
	t6050_clear32(tphy->usb2 + USB2PHY_MISCTUNE, USB2PHY_MISCTUNE_REFCLK_GATE_OFF);

	udelay(30);
	status = readl(tphy->evt + USB2PHY_EVT_STATUS);
	dev_info(tphy->dev, "USB2 event status %#x%s\n", status,
		 status ? "" : " (zero; the macOS driver logs this and continues)");

	msleep(5);
	t6050_mask32(tphy->usb2 + USB2PHY_USBCTL, USB2PHY_USBCTL_MODE,
		     FIELD_PREP(USB2PHY_USBCTL_MODE, USB2PHY_USBCTL_MODE_RUN));
}

static int t6050_usb2_set_mode(struct phy *phy, enum phy_mode mode, int submode)
{
	struct t6050_usb2_phy *tphy = phy_get_drvdata(phy);

	if (mode != PHY_MODE_USB_HOST)
		return -EOPNOTSUPP;

	guard(mutex)(&tphy->lock);
	if (tphy->powered && tphy->mode != mode)
		return -EBUSY;
	tphy->mode = mode;
	return 0;
}

static int t6050_usb2_power_on(struct phy *phy)
{
	struct t6050_usb2_phy *tphy = phy_get_drvdata(phy);
	u32 ctl, usbctl;

	guard(mutex)(&tphy->lock);

	if (tphy->mode != PHY_MODE_USB_HOST)
		return -EINVAL;
	if (tphy->powered)
		return 0;

	t6050_usb2_dump(tphy, "before power_on");

	/*
	 * The loader (m1n1 usb_phy_bringup) leaves the PHY running in its
	 * device-mode configuration. Bring it to the shut-down state the M5
	 * driver expects before running the host init sequence.
	 */
	ctl = readl(tphy->usb2 + USB2PHY_CTL);
	usbctl = readl(tphy->usb2 + USB2PHY_USBCTL);
	if (!(ctl & USB2PHY_CTL_RESET) ||
	    FIELD_GET(USB2PHY_USBCTL_MODE, usbctl) != USB2PHY_USBCTL_MODE_ISOLATION) {
		dev_info(tphy->dev, "PHY is active (ctl %#x usbctl %#x); running shutdown sequence first\n",
			 ctl, usbctl);
		t6050_usb2_shutdown_seq(tphy);
		t6050_usb2_dump(tphy, "after shutdown");
	}

	t6050_usb2_init_seq(tphy);
	tphy->powered = true;
	t6050_usb2_dump(tphy, "after host init");
	dev_info(tphy->dev, "USB2 host sequence complete\n");
	return 0;
}

static int t6050_usb2_power_off(struct phy *phy)
{
	struct t6050_usb2_phy *tphy = phy_get_drvdata(phy);

	guard(mutex)(&tphy->lock);
	if (!tphy->powered)
		return 0;
	t6050_usb2_shutdown_seq(tphy);
	tphy->powered = false;
	t6050_usb2_dump(tphy, "after power_off");
	return 0;
}

/* AppleT6050TypeCPhy::usb2PhyPortReset(iface, true) then (iface, false) */
static int t6050_usb2_reset(struct phy *phy)
{
	struct t6050_usb2_phy *tphy = phy_get_drvdata(phy);

	guard(mutex)(&tphy->lock);
	if (!tphy->powered)
		return -EINVAL;
	t6050_set32(tphy->usb2 + USB2PHY_CTL, USB2PHY_CTL_PORT_RESET);
	msleep(5);
	t6050_clear32(tphy->usb2 + USB2PHY_CTL, USB2PHY_CTL_PORT_RESET);
	dev_info(tphy->dev, "USB2 port reset pulsed\n");
	return 0;
}

static const struct phy_ops t6050_usb2_phy_ops = {
	.owner = THIS_MODULE,
	.set_mode = t6050_usb2_set_mode,
	.power_on = t6050_usb2_power_on,
	.power_off = t6050_usb2_power_off,
	.reset = t6050_usb2_reset,
};

static struct phy *t6050_usb2_xlate(struct device *dev, const struct of_phandle_args *args)
{
	struct t6050_usb2_phy *tphy = dev_get_drvdata(dev);

	if (args->args_count != 1 || args->args[0] != PHY_TYPE_USB2)
		return ERR_PTR(-ENODEV);
	return tphy->phy;
}

static int t6050_parse_tunable(struct device *dev, const char *name, struct t6050_tunable *out,
			       int max)
{
	struct device_node *np = dev->of_node;
	int count, i;

	count = of_property_count_u32_elems(np, name);
	if (count < 0)
		return dev_err_probe(dev, count, "missing %s\n", name);
	if (count % 3 || count / 3 > max)
		return dev_err_probe(dev, -EINVAL, "bad %s length %d\n", name, count);

	for (i = 0; i < count / 3; i++) {
		u32 word;

		if (of_property_read_u32_index(np, name, 3 * i, &word) ||
		    of_property_read_u32_index(np, name, 3 * i + 1, &out[i].mask) ||
		    of_property_read_u32_index(np, name, 3 * i + 2, &out[i].value))
			return -EINVAL;
		if ((word >> TUNABLE_WIDTH_SHIFT) && (word >> TUNABLE_WIDTH_SHIFT) != TUNABLE_WIDTH_32)
			return dev_err_probe(dev, -EINVAL, "%s[%d]: unsupported width code %u\n",
					     name, i, word >> TUNABLE_WIDTH_SHIFT);
		out[i].offset = word & TUNABLE_OFFSET_MASK;
		if (out[i].offset % 4 || out[i].offset > BANK_SIZE - 4)
			return dev_err_probe(dev, -EINVAL, "%s[%d]: bad offset %#x\n", name, i,
					     out[i].offset);
		if (out[i].value & ~out[i].mask)
			return dev_err_probe(dev, -EINVAL, "%s[%d]: value outside mask\n", name, i);
		dev_info(dev, "%s[%d]: +%#x mask %#x value %#x\n", name, i, out[i].offset,
			 out[i].mask, out[i].value);
	}
	return count / 3;
}

static int t6050_usb2_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct t6050_usb2_phy *tphy;
	struct phy_provider *provider;
	int ret;

	tphy = devm_kzalloc(dev, sizeof(*tphy), GFP_KERNEL);
	if (!tphy)
		return -ENOMEM;

	tphy->dev = dev;
	/*
	 * dwc3 powers its PHYs on from dwc3_core_init() before any consumer
	 * set_mode() can reach us (M4 ticket 108). This provider only knows
	 * host mode, so start there; set_mode() still rejects anything else.
	 */
	tphy->mode = PHY_MODE_USB_HOST;
	mutex_init(&tphy->lock);
	platform_set_drvdata(pdev, tphy);

	tphy->usb2 = devm_platform_ioremap_resource_byname(pdev, "usb2phy");
	if (IS_ERR(tphy->usb2))
		return dev_err_probe(dev, PTR_ERR(tphy->usb2), "failed to map usb2phy bank\n");
	tphy->evt = devm_platform_ioremap_resource_byname(pdev, "usb2evt");
	if (IS_ERR(tphy->evt))
		return dev_err_probe(dev, PTR_ERR(tphy->evt), "failed to map usb2evt bank\n");

	ret = t6050_parse_tunable(dev, "azahi,tunable-usb2phy-default", tphy->dflt,
				  TUNABLE_MAX_ENTRIES);
	if (ret < 0)
		return ret;
	tphy->n_dflt = ret;
	ret = t6050_parse_tunable(dev, "azahi,tunable-usb2phy-host", tphy->host,
				  TUNABLE_MAX_ENTRIES);
	if (ret < 0)
		return ret;
	tphy->n_host = ret;
	of_property_read_u32(dev->of_node, "azahi,sig-clear-mask", &tphy->sig_clear);

	/* No register writes at probe. Read-only snapshot for the log. */
	t6050_usb2_dump(tphy, "probe");

	tphy->phy = devm_phy_create(dev, NULL, &t6050_usb2_phy_ops);
	if (IS_ERR(tphy->phy))
		return PTR_ERR(tphy->phy);
	phy_set_drvdata(tphy->phy, tphy);

	provider = devm_of_phy_provider_register(dev, t6050_usb2_xlate);
	return PTR_ERR_OR_ZERO(provider);
}

static const struct of_device_id t6050_usb2_of_match[] = {
	{ .compatible = "azahi,t6050-usb2-phy" },
	{}
};
MODULE_DEVICE_TABLE(of, t6050_usb2_of_match);

static struct platform_driver t6050_usb2_driver = {
	.probe = t6050_usb2_probe,
	.driver = {
		.name = "phy-apple-t6050-usb2",
		.of_match_table = t6050_usb2_of_match,
	},
};
module_platform_driver(t6050_usb2_driver);

MODULE_DESCRIPTION("Experimental Apple T6050 eUSB2 host PHY (azahi private bring-up)");
MODULE_LICENSE("Dual BSD/GPL");
