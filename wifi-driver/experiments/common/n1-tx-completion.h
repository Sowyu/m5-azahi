/* SPDX-License-Identifier: GPL-2.0 */
/* Bounded decoding for the in-order, single-segment station TX ring.
 * CD status bit0 selects a batch; bits1..3 describe transfer completion.
 * A batch reports its LAST tag and count in bits8..23 of the word at +8.
 * The WLAN result is the low byte of the opaque word at +12, not the
 * timestamp footer. Validate the entire batch before returning ownership.
 */
#ifndef N1_TX_COMPLETION_H
#define N1_TX_COMPLETION_H
#include "n1-wire.h"
struct n1_tx_completion {
	n1_u16 first, last, count;
	n1_u32 length;
	n1_u8 firmware_status;
};
static inline int n1_decode_tx_completion(const n1_u8 *cd, size_t size,
	n1_u16 ring, unsigned int capacity, unsigned int next,
	const n1_u16 *pending_lengths, struct n1_tx_completion *out)
{
	struct n1_tx_completion c = {0};
	n1_u32 ext;
	unsigned int i;
	if (!cd || !pending_lengths || !out || capacity < 2 || capacity > 128 ||
	    next >= capacity) return -EINVAL;
	if (size != 32) return -EMSGSIZE;
	if ((cd[0] != 1 && cd[0] != 2 && cd[0] != 3) ||
	    (cd[1] != 4 && cd[1] != 5) || n1_get16(cd + 2) != ring)
		return -EPROTO;
	ext = n1_get32(cd + 8);
	if (ext & 0xff000000U) return -EPROTO;
	c.count = (ext >> 8) & 0xffff;
	if (cd[1] & 1) {
		if (!c.count || c.count >= capacity) return -EPROTO;
	} else {
		if (c.count) return -EPROTO;
		c.count = 1;
	}
	c.first = next;
	c.last = n1_get16(cd + 4);
	if (c.last >= capacity || c.last != (next + c.count - 1) % capacity)
		return -EPROTO;
	for (i = 0; i < c.count; i++)
		if (!pending_lengths[(next + i) % capacity]) return -EPROTO;
	c.length = n1_get16(cd + 6) | ((ext & 255) << 16);
	if (c.length > pending_lengths[c.last]) return -EPROTO;
	c.firmware_status = cd[12];
	*out = c;
	return 0;
}
static inline int n1_tx_firmware_success(n1_u8 status)
{
	return status == 0 || status == 1 || status == 0x83;
}
#endif
