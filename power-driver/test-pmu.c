/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "pmu-transport.h"
struct mock {
	unsigned int addr, op, phase, writes, reads, delay, commands;
	int fault, busy, waiting_data;
	unsigned char regs[65536];
};
static pmu_u32 rd(void *ctx, pmu_u32 reg)
{
	struct mock *m = ctx;
	m->reads++;
	if (reg == PMU_STATUS) {
		if (m->busy) return PMU_TX_EMPTY;
		if (m->fault == 1 && m->commands) return PMU_TX_EMPTY | PMU_RX_EMPTY;
		if (m->fault == 2 && m->waiting_data) return PMU_TX_FULL | PMU_RX_EMPTY;
		if (m->fault == 3 && m->phase == 2) return PMU_TX_EMPTY | PMU_RX_EMPTY;
		if (m->fault == 8 && m->commands && !m->phase) return PMU_TX_EMPTY;
		return PMU_TX_EMPTY | (m->phase ? 0 : PMU_RX_EMPTY);
	}
	assert(reg == PMU_REPLY && m->phase);
	if (m->phase == 1) {
		unsigned int r = (PMU_SID << 8) | m->op |
			(m->op == 0x30 ? 0x8000 : 0x10000);
		m->phase = m->op == 0x30 ? 0 : 2;
		if (m->fault == 4) r ^= 0x100;
		if (m->fault == 5) r ^= 1;
		if (m->fault == 6) r ^= 0x8000;
		if (m->fault == 7) r ^= 0x10000;
		return r;
	}
	m->phase = 0;
	return m->regs[m->addr] | (m->fault == 9 ? 0x100 : 0);
}
static void wr(void *ctx, pmu_u32 reg, pmu_u32 value)
{
	struct mock *m = ctx;
	assert(reg == PMU_CMD);
	m->writes++;
	if (m->waiting_data) {
		assert(value <= 255);
		if (m->fault != 10) m->regs[m->addr] = value;
		m->waiting_data = 0; m->phase = 1;
		return;
	}
	assert(!m->phase);
	assert(((value >> 8) & 255) == PMU_SID);
	m->commands++;
	m->addr = value >> 16; m->op = value & 255;
	assert(m->op == 0x30 || m->op == 0x38);
	if (m->op == 0x30) m->waiting_data = 1;
	else m->phase = 1;
}
static void delay(void *ctx, unsigned int us)
{
	struct mock *m = ctx;
	assert(us == 25); m->delay++;
}
static struct pmu_io make(struct mock *m)
{
	memset(m, 0, sizeof(*m));
	return (struct pmu_io){.ctx=m, .read=rd, .write=wr, .delay=delay};
}
int main(void)
{
	struct mock m;
	struct pmu_io io = make(&m);
	pmu_u8 val = 0xee;
	assert(pmu_byte(&io, 0, 0, &val) == -EPERM && !m.reads);
	assert(pmu_byte(&io, PMU_STAGE, 2, &val) == -EINVAL && !m.reads);
	assert(pmu_update(&io, PMU_FLAGS, 255, 0) == -EPERM && !m.reads);
	assert(pmu_update(&io, PMU_ERRORS, 255, 1) == -EPERM && !m.reads);
	assert(pmu_update(&io, PMU_STAGE, 255, 0x2f) == -EPERM && !m.reads);
	for (int i = 0; i < 256; i++) {
		io = make(&m); m.regs[PMU_FLAGS] = i;
		assert(!pmu_update(&io, PMU_FLAGS, PMU_OFF_BIT, PMU_OFF_BIT));
		assert(m.regs[PMU_FLAGS] == (i | PMU_OFF_BIT));
		assert(!pmu_update(&io, PMU_FLAGS, PMU_OFF_BIT, 0));
		assert(m.regs[PMU_FLAGS] == (i & ~PMU_OFF_BIT));
	}
	io = make(&m); m.regs[PMU_STAGE] = 0x2f; m.regs[PMU_ERRORS] = 0x32;
	assert(!pmu_byte(&io, PMU_STAGE, 0, &val) && val == 0x2f);
	assert(!pmu_update(&io, PMU_STAGE, 255, 0x30) && m.regs[PMU_STAGE] == 0x30);
	assert(!pmu_update(&io, PMU_ERRORS, 255, 0) && !m.regs[PMU_ERRORS]);
	assert(!pmu_update(&io, PMU_STAGE, 255, 0) && !m.regs[PMU_STAGE]);
	io = make(&m); m.busy = 1;
	assert(pmu_byte(&io, PMU_STAGE, 0, &val) == -EBUSY && !m.writes);
	for (int fault = 1; fault <= 10; fault++) {
		io = make(&m); m.fault = fault; val = 0xee;
		int ret = fault == 2 ? pmu_byte(&io, PMU_STAGE, 1, &val) :
			fault == 10 ? pmu_update(&io, PMU_STAGE, 255, 0x30) :
			pmu_byte(&io, PMU_STAGE, 0, &val);
		assert(ret < 0 && io.poisoned && val == 0xee);
		assert(m.delay <= PMU_BUDGET);
		unsigned int reads = m.reads, writes = m.writes;
		assert(pmu_byte(&io, PMU_STAGE, 0, &val) == -EIO);
		assert(m.reads == reads && m.writes == writes);
	}
	puts("PASS: PMU byte framing, all flag values preserved, strict register/value allowlist, bounded waits, reply validation, verified writes, failure quarantine");
	return 0;
}
