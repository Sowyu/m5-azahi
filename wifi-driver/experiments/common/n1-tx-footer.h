/* SPDX-License-Identifier: GPL-2.0 */
/* Minimal 16-byte WLAN TX footer, before any optional expiration/PTM data.
 * Native AirshipDataPacket::prepare writes hardware interface bits15..17;
 * setTxPolicyId optionally writes bits48..55 and sets bit60.
 * AC/TID and peer binding belong to the ring-open client appendix.
 * This is metadata encoding only: packet transmission is not implemented.
 */
#ifndef N1_TX_FOOTER_H
#define N1_TX_FOOTER_H
#include "n1-wire.h"
static inline int n1_build_tx_footer(n1_u8 *out, size_t capacity,
	n1_u8 hardware_interface, n1_u8 policy)
{
	if (!out || hardware_interface > 7) return -EINVAL;
	if (capacity < 16) return -EMSGSIZE;
	memset(out, 0, 16);
	n1_put32(out, (n1_u32)hardware_interface << 15);
	if (policy) { out[6] = policy; out[7] = 0x10; }
	return 16;
}
#endif
