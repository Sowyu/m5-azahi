// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* Narrow livepatch for the exact installed J714s DockChannel module.
 * The transport cannot be unbound (its remove path BUGs). Use kernel
 * livepatch consistency at hid_hw_open; reuse its original startup. The
 * manually built transport lacks ftrace entries, so it cannot itself be
 * livepatched. All unrelated HID devices keep the original open path.
 */
#include <linux/atomic.h>
#include <linux/completion.h>
#include <linux/hid.h>
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/livepatch.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/workqueue.h>

/* ABI prefix from the installed baseline. No allocation or layout change. */
struct dchid_iface {
	void *dchid;
	struct hid_device *hid;
	struct workqueue_struct *wq;
	bool creating;
	struct work_struct create_work;
	int index;
	const char *name;
	const struct device_node *of_node;
	u8 tx_seq;
	bool deferred, starting, open;
	struct completion ready;
};
static int (*original_start)(struct dchid_iface *);
static int (*original_open)(struct hid_device *);
static struct device *transport;
static struct module *transport_owner;
static atomic_t retry_used = ATOMIC_INIT(0);
static bool afe_reset;
module_param(afe_reset, bool, 0444);
MODULE_PARM_DESC(afe_reset, "Pulse the DT-declared AFE reset for 50ms before the single failed-start retry");
static int prepare_retry(void)
{
	struct gpio_desc *gpio;
	int initial, asserted, released;
	if (!afe_reset) return 0;
	gpio = gpiod_get_index(transport, "apple,afe-reset", 0, GPIOD_ASIS);
	if (IS_ERR(gpio)) return PTR_ERR(gpio);
	initial = gpiod_get_value_cansleep(gpio);
	if (initial < 0) { gpiod_put(gpio); return initial; }
	asserted = gpiod_direction_output(gpio, 1);
	msleep(50);
	released = gpiod_set_value_cansleep(gpio, 0);
	gpiod_put(gpio);
	pr_info("azahi-input: AFE reset initial=%d assert=%d release=%d\n",
		initial, asserted, released);
	if (asserted || released) return asserted ? asserted : released;
	msleep(50);
	return 0;
}
#include "recovery-open.h"

/* Resolve one unchanged local helper in the pinned transport module. We do
 * not resolve arbitrary kernel symbols or modify module code/pointers.
 * The exact relative offsets reject other builds before the patch applies.
 */
static int validate_baseline(void)
{
	struct mod_kallsyms *ks;
	unsigned long start = 0, open = 0, close = 0, base_addr;
	unsigned int found = 0;
	transport = bus_find_device_by_name(&platform_bus_type, NULL, "294b28000.input");
	if (!transport) return -ENODEV;
	device_lock(transport);
	if (transport->driver && transport->driver->owner &&
	    !strcmp(transport->driver->owner->name, "dockchannel_hid") &&
	    try_module_get(transport->driver->owner))
		transport_owner = transport->driver->owner;
	device_unlock(transport);
	if (!transport_owner) return -ENODEV;
	base_addr = (unsigned long)transport_owner->mem[MOD_TEXT].base;
	rcu_read_lock();
	ks = rcu_dereference(transport_owner->kallsyms);
	if (ks) for (unsigned int i = 0; i < ks->num_symtab; i++) {
		const Elf_Sym *sym = &ks->symtab[i];
		const char *name = ks->strtab + sym->st_name;
		if (ELF_ST_TYPE(sym->st_info) != STT_FUNC) continue;
		if (!strcmp(name, "dchid_start_interface")) {
			start = sym->st_value; found++;
		}
		if (!strcmp(name, "dchid_open")) { open = sym->st_value; found++; }
		if (!strcmp(name, "dchid_close")) { close = sym->st_value; found++; }
	}
	rcu_read_unlock();
	if (found != 3 || start != base_addr + 0x19c4 ||
	    open != base_addr + 0x1008 || close != base_addr + 0x1080) return -EINVAL;
	original_start = (void *)start;
	original_open = (void *)open;
	pr_info("azahi-input: validated installed DockChannel baseline; bounded retry available\n");
	return 0;
}
/* Exact 7.0.13 HID-core open semantics with one guarded call substitution. */
static int recovery_hw_open(struct hid_device *hdev)
{
	int ret = mutex_lock_killable(&hdev->ll_open_lock);
	if (ret) return ret;
	if (!hdev->ll_open_count++) {
		if (hdev->dev.parent == transport && hdev->type == HID_TYPE_SPI_MOUSE &&
		    hdev->ll_driver->open == original_open)
			ret = recovery_open(hdev);
		else
			ret = hdev->ll_driver->open(hdev);
		if (ret) hdev->ll_open_count--;
		if (hdev->driver->on_hid_hw_open)
			hdev->driver->on_hid_hw_open(hdev);
	}
	mutex_unlock(&hdev->ll_open_lock);
	return ret;
}
static struct klp_func funcs[] = {
	{.old_name = "hid_hw_open", .new_func = recovery_hw_open},
	{}
};
static struct klp_object objects[] = {
	{.funcs = funcs},
	{}
};
static struct klp_patch patch = {.mod = THIS_MODULE, .objs = objects};
static void release_transport(void)
{
	if (transport_owner) module_put(transport_owner);
	if (transport) put_device(transport);
	transport_owner = NULL; transport = NULL;
}
static int __init recovery_init(void)
{
	int ret;
	if (!of_machine_is_compatible("apple,j714s") ||
	    !of_machine_is_compatible("apple,t6050")) return -ENODEV;
	ret = validate_baseline();
	if (!ret) ret = klp_enable_patch(&patch);
	if (ret) release_transport();
	return ret;
}
static void __exit recovery_exit(void) { release_transport(); }
module_init(recovery_init);
module_exit(recovery_exit);
MODULE_LICENSE("GPL");
MODULE_INFO(livepatch, "Y");
MODULE_DESCRIPTION("Exact-baseline J714s trackpad startup recovery");
