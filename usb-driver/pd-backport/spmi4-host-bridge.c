/* SPDX-License-Identifier: GPL-2.0 */
/* Host FFI only. No target instructions or MMIO; reuse the tested transport. */
#include "spmi4-transport.h"
size_t azahi_spmi4_io_size(void) { return sizeof(struct spmi4_io); }
int azahi_spmi4_transfer(struct spmi4_io *io, unsigned int sid,
	unsigned int op, unsigned int address, const spmi4_u8 *out,
	size_t out_len, spmi4_u8 *in, size_t in_len)
{
	return spmi4_transfer(io, sid, op, address, out, out_len, in, in_len);
}
