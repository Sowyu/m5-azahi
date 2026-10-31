/* SPDX-License-Identifier: GPL-2.0 */
/* Experimental raw-MSDU payload conversion. This does not set the 802.11
 * destination: the current firmware-generated header still addresses the AP.
 * Consequently this helper alone does not provide general Ethernet bridging.
 */
#ifndef N1_TX_MSDU_H
#define N1_TX_MSDU_H
#include "n1-wire.h"
static inline int n1_ethernet_to_snap(n1_u8 *out, size_t capacity,
	const n1_u8 *frame, size_t length)
{
	n1_u8 type_hi, type_lo;
	if (!out || !frame) return -EINVAL;
	if (length < 14 || length > 1514 || capacity < length - 6)
		return -EMSGSIZE;
	type_hi = frame[12]; type_lo = frame[13];
	/* Reject length-coded 802.3 and protocols requiring bridge-tunnel OUI. */
	if (type_hi < 6 || (type_hi == 0x80 && type_lo == 0xf3) ||
	    (type_hi == 0x81 && type_lo == 0x37)) return -EPROTONOSUPPORT;
	memmove(out + 8, frame + 14, length - 14);
	memcpy(out, "\xaa\xaa\x03\x00\x00\x00", 6);
	out[6] = type_hi; out[7] = type_lo;
	return (int)length - 6;
}
#endif
