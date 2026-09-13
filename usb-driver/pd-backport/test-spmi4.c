/* SPDX-License-Identifier: GPL-2.0 */
/* HOST ONLY: exercise the actual transport with deterministic fake IO.
 * No hardware, firmware, target identifiers, root access or device nodes.
 */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "spmi4-transport.h"

struct fake {
	spmi4_u32 replies[8], writes[8], initial, final;
	size_t count, consumed, written, reads;
	unsigned int delays, stall_at, release_after;
	int tx_full;
};

static spmi4_u32 read_fake(void *context, spmi4_u32 reg)
{
	struct fake *f = context;
	f->reads++;
	if (reg == SPMI4_REPLY) {
		assert(f->written && f->consumed < f->count);
		return f->replies[f->consumed++];
	}
	assert(reg == SPMI4_STATUS);
	if (!f->written)
		return f->initial;
	if (f->tx_full)
		return SPMI4_TX_FULL | SPMI4_RX_EMPTY;
	if (f->consumed == f->stall_at && f->delays < f->release_after)
		return SPMI4_TX_EMPTY | SPMI4_RX_EMPTY;
	if (f->consumed < f->count)
		return SPMI4_TX_EMPTY;
	return f->final;
}

static void write_fake(void *context, spmi4_u32 reg, spmi4_u32 value)
{
	struct fake *f = context;
	assert(reg == SPMI4_CMD && f->written < 8);
	f->writes[f->written++] = value;
}

static void delay_fake(void *context, unsigned int usec)
{
	struct fake *f = context;
	assert(usec == 50 && ++f->delays <= 1000);
}

static struct spmi4_io setup(struct fake *f, const spmi4_u32 *replies, size_t n)
{
	memset(f, 0, sizeof(*f));
	assert(n <= 8);
	if (n)
		memcpy(f->replies, replies, n * sizeof(*replies));
	f->count = n;
	f->initial = f->final = 0x40004000;
	return (struct spmi4_io) { f, read_fake, write_fake, delay_fake, 0 };
}

static void latched(struct spmi4_io *io, struct fake *f)
{
	size_t reads = f->reads, writes = f->written;
	unsigned int delays = f->delays;
	assert(io->poisoned);
	assert(spmi4_transfer(io, 12, 0x13, 0, NULL, 0, NULL, 0) == -EIO);
	assert(f->reads == reads && f->written == writes && f->delays == delays);
}

static void encodings(void)
{
	struct fake f;
	spmi4_u8 value = 0x1a, data[16], expected[16];
	const spmi4_u32 select[] = { 0x00008c9a };
	struct spmi4_io io = setup(&f, select, 1);
	assert(!spmi4_transfer(&io, 12, 0x80, 0, &value, 1, NULL, 0));
	assert(f.written == 1 && f.writes[0] == 0x1a000c9a);
	const spmi4_u32 regread[] = { 0x00010c60, 0x5a };
	io = setup(&f, regread, 2);
	assert(!spmi4_transfer(&io, 12, 0x60, 0, NULL, 0, data, 1));
	assert(f.writes[0] == 0x00000c60 && data[0] == 0x5a);
	const spmi4_u32 reg31[] = { 0x00010c7f, 0x7f };
	io = setup(&f, reg31, 2);
	assert(!spmi4_transfer(&io, 12, 0x60, 31, NULL, 0, data, 1));
	assert(f.writes[0] == 0x001f0c7f && data[0] == 0x7f);
	const spmi4_u32 extread[] = { 0xffff0c2f, 0x03020100, 0x07060504,
		0x0b0a0908, 0x0f0e0d0c };
	io = setup(&f, extread, 5);
	for (size_t i = 0; i < 16; i++) expected[i] = (spmi4_u8)i;
	assert(!spmi4_transfer(&io, 12, 0x20, 0x20, NULL, 0, data, 16));
	assert(f.writes[0] == 0x00200c2f && !memcmp(data, expected, 16));
	const spmi4_u32 wake[] = { 0x00008c13 };
	io = setup(&f, wake, 1);
	assert(!spmi4_transfer(&io, 12, 0x13, 0, NULL, 0, NULL, 0));
	assert(f.writes[0] == 0x00000c13);
	const spmi4_u32 sleep[] = { 0x00008c11 };
	io = setup(&f, sleep, 1);
	assert(!spmi4_transfer(&io, 12, 0x11, 0, NULL, 0, NULL, 0));
	assert(f.writes[0] == 0x00000c11);
	const spmi4_u32 regwrite[] = { 0x00008c5a };
	io = setup(&f, regwrite, 1); value = 0xf5;
	assert(!spmi4_transfer(&io, 12, 0x40, 0x1a, &value, 1, NULL, 0));
	assert(f.written == 1 && f.writes[0] == 0xf51a0c5a);
	const spmi4_u32 extwrite[] = { 0x00008c02 };
	const spmi4_u8 three[] = { 1, 2, 3 };
	io = setup(&f, extwrite, 1);
	assert(!spmi4_transfer(&io, 12, 0, 0xa0, three, 3, NULL, 0));
	assert(f.written == 2 && f.writes[0] == 0x00a00c02 && f.writes[1] == 0x00030201);
}

static void lengths(void)
{
	/* Exercise every legal extended length and both address boundaries. */
	for (size_t n = 1; n <= 16; n++) {
		for (unsigned int edge = 0; edge < 2; edge++) {
			struct fake f;
			spmi4_u8 data[16], expect[16];
			spmi4_u32 replies[5] = { (((1u << n) - 1) << 16) | 0xc20 | (n - 1) };
			for (size_t i = 0; i < n; i++) {
				expect[i] = (spmi4_u8)(i + 1);
				replies[1 + i / 4] |= (spmi4_u32)expect[i] << (8 * (i % 4));
			}
			unsigned int addr = edge ? (unsigned int)(256 - n) : 0;
			struct spmi4_io io = setup(&f, replies, 1 + (n + 3) / 4);
			assert(!spmi4_transfer(&io, 12, 0x20, addr, NULL, 0, data, n));
			assert(!memcmp(data, expect, n));
			assert(f.writes[0] == (addr << 16 | 0xc20 | (n - 1)));
			spmi4_u32 ack = 0x8c00 | (n - 1);
			io = setup(&f, &ack, 1);
			assert(!spmi4_transfer(&io, 12, 0, addr, expect, n, NULL, 0));
			assert(f.written == 1 + (n + 3) / 4);
			assert(f.writes[0] == (addr << 16 | 0xc00 | (n - 1)));
			for (size_t i = 1; i < f.written; i++) assert(f.writes[i] == replies[i]);
		}
	}
}

static void invalid(void)
{
	struct fake f;
	struct spmi4_io io = setup(&f, NULL, 0);
	spmi4_u8 data[32] = { 0 };
	assert(spmi4_transfer(NULL, 12, 0x13, 0, NULL, 0, NULL, 0) == -EINVAL);
	for (unsigned int sid = 0; sid < 256; sid++) {
		if (sid != 12)
			assert(spmi4_transfer(&io, sid, 0x13, 0, NULL, 0, NULL, 0) == -EPERM);
	}
	const unsigned int ops[] = { 0x10, 0x12, 0x30, 0x38, 0xff };
	for (size_t i = 0; i < sizeof(ops) / sizeof(ops[0]); i++)
		assert(spmi4_transfer(&io, 12, ops[i], 0, NULL, 0, NULL, 0) == -EOPNOTSUPP);
	assert(spmi4_transfer(&io, 12, 0x60, 32, NULL, 0, data, 1) == -EINVAL);
	assert(spmi4_transfer(&io, 12, 0x60, 0, NULL, 0, NULL, 1) == -EINVAL);
	assert(spmi4_transfer(&io, 12, 0x60, 0, data, 1, data, 1) == -EINVAL);
	assert(spmi4_transfer(&io, 12, 0x40, 0, NULL, 1, NULL, 0) == -EINVAL);
	assert(spmi4_transfer(&io, 12, 0x40, 0, data, 2, NULL, 0) == -EINVAL);
	assert(spmi4_transfer(&io, 12, 0x80, 1, data, 1, NULL, 0) == -EINVAL);
	data[0] = 128;
	assert(spmi4_transfer(&io, 12, 0x80, 0, data, 1, NULL, 0) == -EINVAL);
	for (unsigned int op = 0; op <= 0x20; op += 0x20) {
		for (size_t n = 0; n <= 17; n++) {
			if (n && n <= 16) continue;
			assert(spmi4_transfer(&io, 12, op, 0, op ? NULL : data, op ? 0 : n,
				op ? data : NULL, op ? n : 0) == -EINVAL);
		}
		for (unsigned int addr = 255; addr <= 256; addr++)
			assert(spmi4_transfer(&io, 12, op, addr, op ? NULL : data, op ? 0 : 2,
				op ? data : NULL, op ? 2 : 0) == -EINVAL);
	}
	assert(spmi4_transfer(&io, 12, 0x13, 1, NULL, 0, NULL, 0) == -EINVAL);
	assert(!f.reads && !f.written && !f.delays && !io.poisoned);
}

static void faults(void)
{
	struct fake f;
	spmi4_u8 data[16], before[16];
	memset(before, 0xa5, sizeof(before));
	/* SID, opcode, missing parity, excess parity, unexpected ACK, bad padding. */
	const spmi4_u32 bad[][2] = { {0x00010d60, 0}, {0x00010c61, 0},
		{0x00000c60, 0}, {0x00030c60, 0}, {0x00018c60, 0}, {0x00010c60, 0x100} };
	for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); i++) {
		struct spmi4_io io = setup(&f, bad[i], 2);
		memcpy(data, before, sizeof(data));
		assert(spmi4_transfer(&io, 12, 0x60, 0, NULL, 0, data, 1) < 0);
		assert(!memcmp(data, before, sizeof(data)));
		latched(&io, &f);
	}
	const spmi4_u32 missing_ack[] = { 0xc13 };
	struct spmi4_io io = setup(&f, missing_ack, 1);
	assert(spmi4_transfer(&io, 12, 0x13, 0, NULL, 0, NULL, 0) == -EIO);
	latched(&io, &f);
	/* Unexpected initial status must never cause a write or a FIFO drain. */
	const spmi4_u32 busy[] = { 0, 0x40004001, 0x40014000, 0xc0004000, 0x4000c000 };
	for (size_t i = 0; i < sizeof(busy) / sizeof(busy[0]); i++) {
		io = setup(&f, NULL, 0); f.initial = busy[i];
		assert(spmi4_transfer(&io, 12, 0x13, 0, NULL, 0, NULL, 0) == -EBUSY);
		assert(!f.written && !f.consumed && !f.delays);
		latched(&io, &f);
	}
	io = setup(&f, NULL, 0);
	assert(spmi4_transfer(&io, 12, 0x13, 0, NULL, 0, NULL, 0) == -ETIMEDOUT);
	assert(f.delays == 1000 && f.written == 1 && !f.consumed);
	latched(&io, &f);
	io = setup(&f, NULL, 0); f.tx_full = 1;
	assert(spmi4_transfer(&io, 12, 0, 0x20, before, 16, NULL, 0) == -ETIMEDOUT);
	assert(f.delays == 1000 && f.written == 1);
	latched(&io, &f);
	/* A partly received read must neither leak data nor reset its poll budget. */
	const spmi4_u32 partial[] = { 0xffff0c2f, 0x03020100 };
	io = setup(&f, partial, 2); f.release_after = 600;
	memcpy(data, before, sizeof(data));
	assert(spmi4_transfer(&io, 12, 0x20, 0x20, NULL, 0, data, 16) == -ETIMEDOUT);
	assert(f.delays == 1000 && f.consumed == 2 && !memcmp(data, before, sizeof(data)));
	latched(&io, &f);
	const spmi4_u32 extra[] = { 0x00010c60, 0x5a, 0xdeadbeef };
	io = setup(&f, extra, 3); memcpy(data, before, sizeof(data));
	assert(spmi4_transfer(&io, 12, 0x60, 0, NULL, 0, data, 1) == -EPROTO);
	assert(f.consumed == 2 && !memcmp(data, before, sizeof(data)));
	latched(&io, &f);
	const spmi4_u32 wake[] = { 0x8c13 };
	io = setup(&f, wake, 1); f.final = 0x40000000;
	assert(spmi4_transfer(&io, 12, 0x13, 0, NULL, 0, NULL, 0) == -EPROTO);
	latched(&io, &f);
	io = setup(&f, wake, 1); f.release_after = 999;
	assert(!spmi4_transfer(&io, 12, 0x13, 0, NULL, 0, NULL, 0));
	assert(f.delays == 999 && !io.poisoned);
}

int main(void)
{
	encodings(); puts("PASS: fixed independent command encodings");
	lengths(); puts("PASS: all extended lengths at both address boundaries");
	invalid(); puts("PASS: invalid requests perform no IO");
	faults(); puts("PASS: faults latch, bounded polling, no partial output");
	puts("HOST TESTS ONLY: no controller or phone tested.");
	return 0;
}
