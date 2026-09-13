/* SPDX-License-Identifier: GPL-2.0 */
/* Experimental, bounded T6050 SPMI4 polling transport.
 * Shared by the kernel adapter and host tests; no direct MMIO in this file.
 * See README: wire protocol follows published Asahi SPMI sources, while
 * generation-4 offsets are independently checked against saved fixtures.
 * No reset, queue flushing, interrupt masking, or automatic retry recovery.
 */
#ifndef AZAHI_SPMI4_TRANSPORT_H
#define AZAHI_SPMI4_TRANSPORT_H
#ifdef __KERNEL__
#include <linux/types.h>
#include <linux/errno.h>
typedef u32 spmi4_u32;
typedef u8 spmi4_u8;
#else
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
typedef uint32_t spmi4_u32;
typedef uint8_t spmi4_u8;
#endif

#define SPMI4_STATUS 0x200u
#define SPMI4_CMD 0x210u
#define SPMI4_REPLY 0x220u
#define SPMI4_RX_EMPTY (1u << 30)
#define SPMI4_RX_FULL (1u << 31)
#define SPMI4_TX_EMPTY (1u << 14)
#define SPMI4_TX_FULL (1u << 15)
#define SPMI4_COUNTS 0x00ff00ffu
#define SPMI4_HPM_SID 12u
#define SPMI4_POLL_BUDGET 1000u
#define SPMI4_POLL_DELAY_US 50u

struct spmi4_io {
	void *context;
	spmi4_u32 (*read)(void *context, spmi4_u32 reg);
	void (*write)(void *context, spmi4_u32 reg, spmi4_u32 value);
	void (*delay)(void *context, unsigned int usec);
	int poisoned;
};

/* A single controller lock must cover the whole call. The Linux adapter owns
 * that lock. An ambiguous FIFO state latches failure until a fresh, audited
 * controller lifecycle; this code never drains someone else's response.
 */
static int spmi4_fault(struct spmi4_io *io, int error)
{
	io->poisoned = 1;
	return error;
}

static int spmi4_wait(struct spmi4_io *io, spmi4_u32 mask,
		     spmi4_u32 value, unsigned int *budget)
{
	for (;;) {
		spmi4_u32 status = io->read(io->context, SPMI4_STATUS);
		if ((status & mask) == value)
			return 0;
		if (!*budget)
			return spmi4_fault(io, -ETIMEDOUT);
		--*budget;
		io->delay(io->context, SPMI4_POLL_DELAY_US);
	}
}

static int spmi4_idle(spmi4_u32 status)
{
	const spmi4_u32 mask = SPMI4_RX_EMPTY | SPMI4_TX_EMPTY |
		SPMI4_RX_FULL | SPMI4_TX_FULL | SPMI4_COUNTS;
	return (status & mask) == (SPMI4_RX_EMPTY | SPMI4_TX_EMPTY);
}

/* op is the base Linux SPMI opcode, not a length/address-encoded wire byte.
 * Only short register operations required by the HPM transport are supported.
 * out/in are mutually exclusive. Output is committed only on full success.
 */
static int spmi4_transfer(struct spmi4_io *io, unsigned int sid,
			 unsigned int op, unsigned int address,
			 const spmi4_u8 *out, size_t out_len,
			 spmi4_u8 *in, size_t in_len)
{
	spmi4_u32 extra = address, wire_op = op, reply, word, mask;
	spmi4_u8 temporary[16];
	unsigned int budget = SPMI4_POLL_BUDGET;
	size_t i, j;
	int ret;

	if (!io || !io->read || !io->write || !io->delay)
		return -EINVAL;
	if (sid != SPMI4_HPM_SID)
		return -EPERM;
	if ((out_len && !out) || (in_len && !in) || (out_len && in_len))
		return -EINVAL;
	switch (op) {
	case 0x60: /* Register read */
		if (address > 31 || in_len != 1 || out_len)
			return -EINVAL;
		wire_op |= address;
		break;
	case 0x40: /* Register write: data is carried in the command */
		if (address > 31 || out_len != 1 || in_len)
			return -EINVAL;
		wire_op |= address;
		extra |= (spmi4_u32)out[0] << 8;
		out_len = 0;
		break;
	case 0x80: /* Register-zero write / logical selector */
		if (address || out_len != 1 || in_len || out[0] > 0x7f)
			return -EINVAL;
		wire_op |= out[0];
		extra = (spmi4_u32)out[0] << 8;
		out_len = 0;
		break;
	case 0x20: /* Extended read, at most sixteen bytes */
		if (!in_len || in_len > 16 || out_len || address > 255 ||
		    in_len > 256 - address)
			return -EINVAL;
		wire_op |= in_len - 1;
		break;
	case 0x00: /* Extended write */
		if (!out_len || out_len > 16 || in_len || address > 255 ||
		    out_len > 256 - address)
			return -EINVAL;
		wire_op |= out_len - 1;
		break;
	case 0x11: /* Sleep */
	case 0x13: /* Wakeup */
		if (address || out_len || in_len)
			return -EINVAL;
		break;
	default: /* Includes RESET, SHUTDOWN, and unsupported long operations. */
		return -EOPNOTSUPP;
	}
	if (io->poisoned)
		return -EIO;
	if (!spmi4_idle(io->read(io->context, SPMI4_STATUS)))
		return spmi4_fault(io, -EBUSY);

	/* Polling mode: ALERT is deliberately clear. Hardware acceptance remains
	 * to be tested; no unhandled completion IRQ is intentionally requested.
	 */
	io->write(io->context, SPMI4_CMD, (extra << 16) | (sid << 8) | wire_op);
	for (i = 0; i < out_len; i += 4) {
		ret = spmi4_wait(io, SPMI4_TX_FULL, 0, &budget);
		if (ret)
			return ret;
		word = 0;
		for (j = 0; j < 4 && i + j < out_len; j++)
			word |= (spmi4_u32)out[i + j] << (8 * j);
		io->write(io->context, SPMI4_CMD, word);
	}
	ret = spmi4_wait(io, SPMI4_RX_EMPTY, 0, &budget);
	if (ret)
		return ret;
	reply = io->read(io->context, SPMI4_REPLY);
	if (((reply >> 8) & 0x7f) != sid || (reply & 0xff) != wire_op)
		return spmi4_fault(io, -EPROTO);
	if (!!(reply & (1u << 15)) != !in_len)
		return spmi4_fault(io, -EIO);
	mask = (1u << in_len) - 1u;
	if ((reply >> 16) != mask)
		return spmi4_fault(io, -EIO);
	for (i = 0; i < in_len; i += 4) {
		ret = spmi4_wait(io, SPMI4_RX_EMPTY, 0, &budget);
		if (ret)
			return ret;
		word = io->read(io->context, SPMI4_REPLY);
		/* The reference transport requires unused response bytes to be zero. */
		if (in_len - i < 4 && (word >> (8 * (in_len - i))))
			return spmi4_fault(io, -EPROTO);
		for (j = 0; j < 4 && i + j < in_len; j++)
			temporary[i + j] = (word >> (8 * j)) & 0xff;
	}
	if (!spmi4_idle(io->read(io->context, SPMI4_STATUS)))
		return spmi4_fault(io, -EPROTO);
	for (i = 0; i < in_len; i++)
		in[i] = temporary[i];
	return 0;
}
#endif
