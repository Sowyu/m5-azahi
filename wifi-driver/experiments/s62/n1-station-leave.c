// SPDX-License-Identifier: GPL-2.0
/* Host-only transition helper for the fresh, single-TX-ring boot bundle.
 * The caller first removes all packet frontends. No DMA ownership or reset.
 * Older multi-ring experiments must continue using their own drain guards.
 */
#include <linux/delay.h>
#include <linux/module.h>
#include <linux/slab.h>
#include "../s49/n1-v9-api.h"
#include "../s51/n1-tx-api.h"
#include "../common/n1-aci-connect.h"
static bool launch;
static unsigned int expected_sequence;
static int result=-EINPROGRESS;
module_param(launch,bool,0400);
module_param(expected_sequence,uint,0400);
module_param(result,int,0444);

static int __init leave_init(void)
{
	struct n1_link_state before,after;
	u8 request[40],handle,*reply;
	u16 seq;
	unsigned int pending,cursor,i;
	size_t length=4096;
	int ret;
	if (!expected_sequence || expected_sequence>65535) return -EINVAL;
	ret=n1_data_tx_pending_v2(&pending);
	if (ret || pending) return ret?ret:-EBUSY;
	ret=n1_alpha_state_v9(&before,&cursor);
	if (ret) return ret;
	ret=n1_alpha_cursor_v9(&seq,&handle);
	if (ret || seq!=expected_sequence) return ret?ret:-ESTALE;
	if (!launch) { result=0; return 0; }
	seq=seq==65535?1:seq+1;
	ret=n1_build_disconnect(request,sizeof(request),seq,8,10);
	if (ret!=sizeof(request)) return ret<0?ret:-EPROTO;
	reply=kzalloc(length,GFP_KERNEL);
	if (!reply) return -ENOMEM;
	result=n1_alpha_exchange_v9(request,sizeof(request),reply,&length,true);
	kfree(reply);
	if (!result) {
		result=-ETIMEDOUT;
		for (i=0;i<300;i++) {
			ret=n1_alpha_state_v9(&after,&cursor);
			if (ret) { result=ret; break; }
			if (after.losses!=before.losses) { result=0; break; }
			msleep(10);
		}
	}
	pr_info("N1_STATION_LEAVE sequence=%u result=%d\n",seq,result);
	return 0;
}
static void __exit leave_exit(void) {}
module_init(leave_init);
module_exit(leave_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Host-only N1 single-ring station transition");
