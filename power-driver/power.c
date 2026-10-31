// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* J714s board power lifecycle for the early standalone DT. SMC actions and
 * legacy PMU semantics follow the Asahi macsmc-reboot driver. The M5 board
 * needs its generation-4 SPMI controller and has no SMC reboot OF child.
 * This driver owns only the documented boot-state bytes and SPMI0 clock.
 */
#include <linux/device.h>
#include <linux/mfd/macsmc.h>
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/reboot.h>
#include "pmu-platform.h"
#include "smc-final.h"
static bool enable;
module_param(enable, bool, 0444);
MODULE_PARM_DESC(enable, "Enable J714s shutdown/restart handlers after PMU/SMC validation");
static int result = -EINPROGRESS;
module_param(result, int, 0444);
static bool ready;
module_param(ready, bool, 0444);
static int saved_stage = -1, saved_errors = -1, saved_flags = -1;
module_param(saved_stage, int, 0444);
module_param(saved_errors, int, 0444);
module_param(saved_flags, int, 0444);
static struct device *smc_dev;
static struct module *smc_owner;
static struct apple_smc *smc;
static struct sys_off_handler *handlers[4];
static bool notified, prepared, final_sent, notifier_registered;
static unsigned long requested_action;
static DEFINE_MUTEX(lifecycle_lock);

static int power_notify(struct notifier_block *nb, unsigned long action, void *unused)
{
	int ret, warning_ret;
	u32 warning;
	if (action != SYS_RESTART && action != SYS_POWER_OFF) return NOTIFY_DONE;
	mutex_lock(&lifecycle_lock);
	if (!ready || notified) goto out;
	notified = true; requested_action = action;
	pr_info("azahi-power: preparing %s\n", action == SYS_POWER_OFF ? "poweroff" : "restart");
	warning = action == SYS_POWER_OFF ? SMC_KEY(offw) : SMC_KEY(rest);
	warning_ret = apple_smc_write_u32(smc, SMC_KEY(MBSE), warning);
	/* Select the destination before marking this a clean shutdown. Every
	 * write is read back, and the shutdown byte's other bits are preserved.
	 */
	ret = pmu_update(&bus, PMU_FLAGS, PMU_OFF_BIT,
			 action == SYS_POWER_OFF ? PMU_OFF_BIT : 0);
	if (!ret) ret = pmu_update(&bus, PMU_STAGE, 255, 0);
	if (ret || warning_ret < 0) {
		ready = false;
		pr_err("azahi-power: preparation failed PMU=%d SMC=%d; final SMC action disabled\n",
			ret, warning_ret);
	} else {
		pr_info("azahi-power: clean shutdown recorded; destination=%s\n",
			action == SYS_POWER_OFF ? "off" : "restart");
	}
out:
	mutex_unlock(&lifecycle_lock);
	return NOTIFY_OK;
}
static struct notifier_block power_nb = {.notifier_call = power_notify};

static int power_prepare(struct sys_off_data *data)
{
	if (!ready || !notified || prepared) return NOTIFY_DONE;
	result = apple_smc_enter_atomic(smc);
	prepared = result >= 0;
	pr_info("azahi-power: atomic prepare result=%d\n", result);
	return NOTIFY_OK;
}
static int power_final(struct sys_off_data *data)
{
	unsigned long expected = (unsigned long)data->cb_data;
	int ret;
	if (!ready || !prepared || final_sent || expected != requested_action)
		return NOTIFY_DONE;
	final_sent = true;
	pr_emerg("azahi-power: issuing %s\n", expected == SYS_POWER_OFF ? "off1" : "phra");
	ret = smc_final_send(smc, expected == SYS_POWER_OFF ? SMC_KEY(off1) : SMC_KEY(phra));
	if (ret >= 0) mdelay(1000);
	pr_emerg("azahi-power: SMC action returned (%d), lower-priority handlers may run\n", ret);
	return NOTIFY_DONE;
}
static void unregister_handlers(void)
{
	if (notifier_registered) unregister_reboot_notifier(&power_nb);
	notifier_registered = false;
	for (int i = 3; i >= 0; i--) {
		if (handlers[i]) unregister_sys_off_handler(handlers[i]);
		handlers[i] = NULL;
	}
}
static int add_handler(unsigned int index, enum sys_off_mode mode,
		       int (*callback)(struct sys_off_data *), unsigned long action)
{
	struct sys_off_handler *h = register_sys_off_handler(mode, SYS_OFF_PRIO_HIGH,
						 callback, (void *)action);
	if (IS_ERR(h)) return PTR_ERR(h);
	handlers[index] = h;
	return 0;
}
static void release_smc(void)
{
	if (smc_owner) module_put(smc_owner);
	if (smc_dev) put_device(smc_dev);
	smc_owner = NULL; smc_dev = NULL; smc = NULL;
}
static int __init power_init(void)
{
	u8 v;
	int ret;
	if (kernel_can_power_off()) return -EBUSY;
	ret = pmu_open(true);
	if (ret) return ret;
	ret = pmu_byte(&bus, PMU_STAGE, 0, &v);
	if (!ret) { saved_stage = v; ret = pmu_byte(&bus, PMU_ERRORS, 0, &v); }
	if (!ret) { saved_errors = v; ret = pmu_byte(&bus, PMU_FLAGS, 0, &v); }
	if (!ret) saved_flags = v;
	if (ret) goto fail;
	smc_dev = bus_find_device_by_name(&platform_bus_type, NULL, "28c600000.smc");
	if (!smc_dev) { ret = -ENODEV; goto fail; }
	device_lock(smc_dev);
	if (smc_dev->driver && try_module_get(smc_dev->driver->owner)) {
		smc_owner = smc_dev->driver->owner;
		smc = dev_get_drvdata(smc_dev);
	}
	device_unlock(smc_dev);
	if (!smc || !smc_owner || smc->boot_stage != APPLE_SMC_INITIALIZED || smc->atomic_mode) {
		ret = -ENODEV; goto fail;
	}
	/* Key existence queries do not copy the metadata from SMC SRAM. */
	ret = apple_smc_get_key_info(smc, SMC_KEY(MBSE), NULL);
	if (ret < 0) goto fail;
	pr_info("azahi-power: PMU stage=%#x errors=%#x flags=%#x; MBSE exists; enable=%d\n",
		saved_stage, saved_errors, saved_flags, enable);
	if (!enable) { result = 0; return 0; }
	ret = add_handler(0, SYS_OFF_MODE_POWER_OFF_PREPARE, power_prepare, SYS_POWER_OFF);
	if (!ret) ret = add_handler(1, SYS_OFF_MODE_POWER_OFF, power_final, SYS_POWER_OFF);
	if (!ret) ret = add_handler(2, SYS_OFF_MODE_RESTART_PREPARE, power_prepare, SYS_RESTART);
	if (!ret) ret = add_handler(3, SYS_OFF_MODE_RESTART, power_final, SYS_RESTART);
	if (ret) goto fail;
	ret = register_reboot_notifier(&power_nb);
	if (ret) goto fail;
	notifier_registered = true;
	ret = pmu_update(&bus, PMU_STAGE, 255, 0x30);
	if (!ret) ret = pmu_update(&bus, PMU_ERRORS, 255, 0);
	if (ret) goto fail;
	ready = true; result = 0;
	pr_info("azahi-power: shutdown and restart handlers ready; watchdog restart remains fallback\n");
	return 0;
fail:
	result = ret;
	unregister_handlers(); release_smc();
	if (bus.poisoned) {
		/* Retain the ambiguous FIFO ownership until the next boot. */
		__module_get(THIS_MODULE);
		pr_err("azahi-power: PMU failure %d; disabled and pinned until reboot\n", ret);
		return 0;
	}
	release_maps();
	return ret;
}
static void __exit power_exit(void)
{
	unregister_handlers(); release_smc(); release_maps();
}
module_init(power_init);
module_exit(power_exit);
MODULE_LICENSE("Dual MIT/GPL");
MODULE_DESCRIPTION("J714s SMC and Abbey PMU shutdown/restart support");
