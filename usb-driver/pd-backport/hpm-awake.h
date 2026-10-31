/* SPDX-License-Identifier: GPL-2.0 */
/* Bounded, one-shot logical HPM protocol shared by host tests and Linux.
 * SSPS(S0) wakes the observed state 7 with or without an attached partner.
 * No reset, power-role swap, IRQ acknowledgement/mask or generic task API.
 */
#ifndef AZAHI_HPM_AWAKE_H
#define AZAHI_HPM_AWAKE_H
#include "spmi4-transport.h"

struct hpm_io {
	void *context;
	int (*xfer)(void *, unsigned int, unsigned int,
		    const spmi4_u8 *, size_t, spmi4_u8 *, size_t);
	void (*delay_ms)(void *, unsigned int);
	int failed;
};
struct hpm_snapshot {
	spmi4_u32 mode, vid, status, data;
	unsigned int power, state;
};

static int hpm_xfer(struct hpm_io *h, unsigned int op, unsigned int addr,
		    const spmi4_u8 *out, size_t outlen, spmi4_u8 *in, size_t inlen)
{
	int ret;
	if (h->failed)
		return -EIO;
	ret = h->xfer(h->context, op, addr, out, outlen, in, inlen);
	if (ret)
		h->failed = 1;
	return ret;
}
static unsigned int hpm_length(unsigned int reg)
{
	switch (reg) {
	case 0: case 3: case 8: case 0x1a: case 0x5f: return 4;
	case 9: case 0x20: return 1;
	case 0x3f: return 2;
	default: return 0;
	}
}
static int hpm_select(struct hpm_io *h, unsigned int reg)
{
	spmi4_u8 value = reg, size;
	unsigned int i, len = hpm_length(reg);
	int ret;
	if (!len) return -EINVAL;
	ret = hpm_xfer(h, 0x80, 0, &value, 1, NULL, 0);
	if (ret) return ret;
	for (i = 0; i < 100; i++) {
		ret = hpm_xfer(h, 0x60, 0, NULL, 0, &value, 1);
		if (ret) return ret;
		if (value == reg) {
			ret = hpm_xfer(h, 0x60, 0x1f, NULL, 0, &size, 1);
			if (ret) return ret;
			if (size >= len && size <= 64) return 0;
			break;
		}
		if (value != (reg | 0x80)) break;
		h->delay_ms(h->context, 10);
	}
	h->failed = 1;
	return i == 100 ? -ETIMEDOUT : -EPROTO;
}
static int hpm_read(struct hpm_io *h, unsigned int reg, spmi4_u32 *value)
{
	spmi4_u8 data[4] = {0};
	unsigned int i, len = hpm_length(reg);
	int ret = hpm_select(h, reg);
	if (ret) return ret;
	ret = hpm_xfer(h, 0x20, 0x20, NULL, 0, data, len);
	if (ret) return ret;
	*value = 0;
	for (i = 0; i < len; i++) *value |= (spmi4_u32)data[i] << (8 * i);
	return 0;
}
static int hpm_snapshot_read(struct hpm_io *h, struct hpm_snapshot *s)
{
	spmi4_u32 p, state;
	int ret;
#define HPM_READ(r, v) do { ret = hpm_read(h, r, v); if (ret) return ret; } while (0)
	HPM_READ(3, &s->mode); HPM_READ(0, &s->vid);
	HPM_READ(0x1a, &s->status); HPM_READ(0x20, &state);
	HPM_READ(0x3f, &p); HPM_READ(0x5f, &s->data);
	s->power = p; s->state = state;
#undef HPM_READ
	return 0;
}
static int hpm_awake_once(struct hpm_io *h, struct hpm_snapshot *s, int allow_task)
{
	spmi4_u32 command, state;
	spmi4_u8 zero = 0;
	const spmi4_u8 task[4] = {'S', 'S', 'P', 'S'};
	unsigned int i;
	int ret = hpm_snapshot_read(h, s);
	if (ret) return ret;
	if (s->mode != 0x20505041 || s->vid != 0x28) return -ENODEV;
	if (s->state == 0) return 0; /* Already awake: no logical write. */
	if (!allow_task) return -EAGAIN;
	/* The pinned tipd SN201202x variant calls cd321x_switch_power_state(S0)
	 * before handling an existing partner. Attachment/power/data status are
	 * observations, not prerequisites for SSPS. Requiring an empty port here
	 * prevented boot with the tether cable attached. Leave role negotiation
	 * to the controller; this is only the system-power-state task. */
	if (s->state != 7) return -EAGAIN;
	ret = hpm_read(h, 8, &command);
	if (ret) return ret;
	if (command && command != 0x444d4321) return -EBUSY;
	ret = hpm_read(h, 0x20, &state);
	if (ret) return ret;
	if (!state) { s->state = 0; return 0; }
	if (state != 7) return -EAGAIN;
	ret = hpm_select(h, 9);
	if (ret) return ret;
	ret = hpm_xfer(h, 0, 0xa0, &zero, 1, NULL, 0);
	if (ret) return ret;
	ret = hpm_select(h, 8);
	if (ret) return ret;
	ret = hpm_xfer(h, 0, 0xa0, task, 4, NULL, 0);
	if (ret) return ret;
	for (i = 0; i < 100; i++) {
		ret = hpm_read(h, 8, &command);
		if (ret) return ret;
		if (!command) break;
		if (command != 0x53505353) { h->failed = 1; return -EIO; }
		h->delay_ms(h->context, 10);
	}
	if (i == 100) { h->failed = 1; return -ETIMEDOUT; }
	ret = hpm_read(h, 9, &command);
	if (ret) return ret;
	if (command) { h->failed = 1; return -EIO; }
	ret = hpm_snapshot_read(h, s);
	if (ret) return ret;
	if (s->mode != 0x20505041 || s->vid != 0x28 || s->state) {
		h->failed = 1; return -EIO;
	}
	return 0;
}
#endif
