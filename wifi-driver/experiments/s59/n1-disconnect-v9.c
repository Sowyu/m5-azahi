// SPDX-License-Identifier: GPL-2.0
/* Bounded native disconnect caller; host memory only, no DMA or reset.
 * Native abortJoin calls disconnect(reason=8), which passes mode=10 to
 * disconnectCommon. The encoder is independently checked against native
 * instruction emulation. Do not interpret the mode as a generic bitmask.
 */
#include <linux/module.h>
#include <linux/slab.h>
#include "../s49/n1-v9-api.h"
#include "../s51/n1-tx-api.h"
#include "../s58/n1-ac1-api.h"
#include "../common/n1-aci-connect.h"
static bool launch;
static unsigned int expected_sequence, expected_tx_done, expected_ac1_done, sequence;
static int result = -EINPROGRESS;
module_param(launch, bool, 0400);
module_param(expected_sequence, uint, 0400);
module_param(expected_tx_done, uint, 0400);
module_param(expected_ac1_done, uint, 0400);
module_param(sequence, uint, 0444);
module_param(result, int, 0444);
static int __init disconnect_init(void)
{
 u8 request[40], handle, *reply;
 u16 last;
 unsigned int done, errors;
 size_t length = 4096;
 int ret;
 if (!expected_sequence || expected_sequence > 65535) return -EINVAL;
 ret = n1_alpha_cursor_v9(&last, &handle);
 if (ret) return ret;
 if (last != expected_sequence) return -ESTALE;
 /* Caller has stopped frame producers and compared submitted to completed.
  * These APIs report completed/failed, not submitted/completed. */
 ret = n1_data_tx_status_v2(&done, &errors);
 if (ret || errors || done != expected_tx_done) return ret ? ret : -EBUSY;
 ret = n1_data_tx_status_ac1(&done, &errors);
 if (ret || errors || done != expected_ac1_done) return ret ? ret : -EBUSY;
 sequence = last == 65535 ? 1 : last + 1;
 ret = n1_build_disconnect(request, sizeof(request), sequence, 8, 10);
 if (ret != sizeof(request)) return ret < 0 ? ret : -EPROTO;
 if (!launch) return 0;
 reply = kzalloc(length, GFP_KERNEL);
 if (!reply) return -ENOMEM;
 result = n1_alpha_exchange_v9(request, sizeof(request), reply, &length, true);
 kfree(reply);
 pr_info("N1_DISCONNECT_V9 sequence=%u result=%d; completion is asynchronous\n",
         sequence, result);
 return 0;
}
static void __exit disconnect_exit(void) {}
module_init(disconnect_init);
module_exit(disconnect_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Bounded native N1 disconnect caller without DMA ownership");
