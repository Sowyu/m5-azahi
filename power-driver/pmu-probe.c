// SPDX-License-Identifier: GPL-2.0-only
/* Read-only PMU diagnostic; optional reversible controller clock hold. */
#include <linux/module.h>
#include "pmu-platform.h"
static bool read_scratch, hold_clock;
module_param(read_scratch, bool, 0444);
module_param(hold_clock, bool, 0444);
static int result = -EINPROGRESS, boot_stage = -1, error_counts = -1, flags = -1;
module_param(result, int, 0444);
module_param(boot_stage, int, 0444);
module_param(error_counts, int, 0444);
module_param(flags, int, 0444);
static int __init init_probe(void)
{
 u8 v;
 int ret = pmu_open(hold_clock);
 if (ret) return ret;
 result = 0;
 if (read_scratch) {
  result = pmu_byte(&bus, PMU_STAGE, 0, &v);
  if (!result) { boot_stage = v; result = pmu_byte(&bus, PMU_ERRORS, 0, &v); }
  if (!result) { error_counts = v; result = pmu_byte(&bus, PMU_FLAGS, 0, &v); }
  if (!result) flags = v;
 }
 pr_info("azahi-pmu-probe: result=%d stage=%#x errors=%#x flags=%#x poisoned=%d\n",
  result, boot_stage, error_counts, flags, bus.poisoned);
 if (bus.poisoned) __module_get(THIS_MODULE);
 return 0;
}
static void __exit exit_probe(void) { release_maps(); }
module_init(init_probe);
module_exit(exit_probe);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("J714s primary PMU read-only boot-state diagnostic");
