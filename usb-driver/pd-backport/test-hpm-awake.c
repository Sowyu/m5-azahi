/* SPDX-License-Identifier: GPL-2.0 */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "hpm-awake.h"
struct fake {
	spmi4_u32 reg[128];
	unsigned int selected, writes, delays, calls;
	int fail, busy, reject, pending, wrong_state;
};
static int xfer(void *ctx, unsigned int op, unsigned int addr,
		const spmi4_u8 *out, size_t outlen, spmi4_u8 *in, size_t inlen)
{
	struct fake *f = ctx;
	unsigned int i;
	f->calls++;
	if (f->fail) return -EIO;
	if (op == 0x80) { assert(outlen == 1); f->selected = out[0]; return 0; }
	if (op == 0x60) {
		assert(inlen == 1);
		if (addr == 0) *in = f->selected | (f->busy ? 0x80 : 0);
		else { assert(addr == 0x1f); *in = hpm_length(f->selected); }
		return 0;
	}
	if (op == 0x20) {
		assert(addr == 0x20 && inlen == hpm_length(f->selected));
		for (i = 0; i < inlen; i++) in[i] = f->reg[f->selected] >> (i * 8);
		return 0;
	}
	assert(op == 0 && addr == 0xa0);
	f->writes++;
	if (f->selected == 9) { assert(outlen == 1 && !*out); f->reg[9] = 0; }
	else {
		assert(f->selected == 8 && outlen == 4 && !memcmp(out, "SSPS", 4));
		f->reg[8] = f->pending ? 0x53505353 : 0;
		f->reg[9] = f->reject ? 3 : 0;
		if (!f->pending && !f->reject && !f->wrong_state) f->reg[0x20] = 0;
	}
	return 0;
}
static void delay(void *ctx, unsigned int ms) { assert(ms == 10); ((struct fake *)ctx)->delays++; }
static struct fake initial(void)
{
	struct fake f = {0};
	f.reg[3] = 0x20505041; f.reg[0] = 0x28;
	f.reg[0x1a] = 0x10000000; f.reg[0x20] = 7;
	return f;
}
static struct hpm_io io(struct fake *f) { return (struct hpm_io){.context=f, .xfer=xfer, .delay_ms=delay}; }
int main(void)
{
	struct fake f; struct hpm_io h; struct hpm_snapshot s;
	unsigned int i, calls;
	f = initial(); h = io(&f);
	assert(!hpm_awake_once(&h, &s, 1)); assert(!s.state && f.writes == 2);
	assert(!hpm_awake_once(&h, &s, 1)); assert(f.writes == 2);
	puts("PASS: exact SSPS sequence, readback and already-awake no-op");
	for (i = 0; i < 32; i++) {
		f = initial(); h = io(&f); f.reg[0x1a] ^= 1u << i;
		assert(hpm_awake_once(&h, &s, 1) == -EAGAIN); assert(!f.writes);
	}
	f = initial(); h = io(&f); assert(hpm_awake_once(&h, &s, 0) == -EAGAIN); assert(!f.writes);
	f = initial(); h = io(&f); f.reg[0] = 1; assert(hpm_awake_once(&h, &s, 1) == -ENODEV); assert(!f.writes);
	f = initial(); h = io(&f); f.reg[0x3f] = 1; assert(hpm_awake_once(&h, &s, 1) == -EAGAIN); assert(!f.writes);
	f = initial(); h = io(&f); f.reg[0x5f] = 1; assert(hpm_awake_once(&h, &s, 1) == -EAGAIN); assert(!f.writes);
	f = initial(); h = io(&f); f.reg[8] = 1; assert(hpm_awake_once(&h, &s, 1) == -EBUSY); assert(!f.writes);
	puts("PASS: all status-bit deviations, read-only mode, identity, partner and task guards");
	for (i = 0; i < 5; i++) {
		f = initial(); h = io(&f);
		if (i == 0) f.fail = 1;
		if (i == 1) f.busy = 1;
		if (i == 2) f.reject = 1;
		if (i == 3) f.pending = 1;
		if (i == 4) f.wrong_state = 1;
		assert(hpm_awake_once(&h, &s, 1) < 0); assert(h.failed);
		assert(f.delays <= 100); calls = f.calls;
		assert(hpm_awake_once(&h, &s, 1) < 0); assert(calls == f.calls);
	}
	puts("PASS: transport, selector, rejected task, timeout and readback faults latch");
	return 0;
}
