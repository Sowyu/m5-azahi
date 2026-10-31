/* SPDX-License-Identifier: GPL-2.0-only */
/* J714s primary Abbey PMU: bounded SPMI4 legacy scratchpad byte access.
 * Wire format follows Asahi Linux/m1n1. No reset, flush, IRQ-mask writes,
 * retries, regulator access, or arbitrary register access.
 */
#ifndef AZAHI_PMU_TRANSPORT_H
#define AZAHI_PMU_TRANSPORT_H
#ifdef __KERNEL__
#include <linux/types.h>
#include <linux/errno.h>
typedef u32 pmu_u32;
typedef u8 pmu_u8;
#else
#include <stdint.h>
#include <errno.h>
typedef uint32_t pmu_u32;
typedef uint8_t pmu_u8;
#endif
#define PMU_STATUS 0x200u
#define PMU_CMD 0x210u
#define PMU_REPLY 0x220u
#define PMU_RX_EMPTY (1u << 30)
#define PMU_TX_EMPTY (1u << 14)
#define PMU_TX_FULL (1u << 15)
#define PMU_SID 14u
#define PMU_STAGE 0xf801u
#define PMU_ERRORS 0xf802u
#define PMU_FLAGS 0xf80fu
#define PMU_OFF_BIT 8u
#define PMU_BUDGET 2000u
struct pmu_io {
	void *ctx;
	pmu_u32 (*read)(void *, pmu_u32);
	void (*write)(void *, pmu_u32, pmu_u32);
	void (*delay)(void *, unsigned int);
	int poisoned;
};
static int pmu_fault(struct pmu_io *io, int error)
{
	io->poisoned = 1;
	return error;
}
static int pmu_idle(pmu_u32 s)
{
	return (s & 0xc0ffc0ffu) == (PMU_RX_EMPTY | PMU_TX_EMPTY);
}
static int pmu_wait(struct pmu_io *io, pmu_u32 mask, pmu_u32 value,
		    unsigned int *budget)
{
	for (;;) {
		if ((io->read(io->ctx, PMU_STATUS) & mask) == value)
			return 0;
		if (!*budget)
			return pmu_fault(io, -ETIMEDOUT);
		--*budget;
		io->delay(io->ctx, 25);
	}
}
/* Only the three documented legacy boot-state registers are accessible.
 * Caller serializes the entire operation, including update/readback.
 */
static int pmu_byte(struct pmu_io *io, unsigned int address, int write,
		    pmu_u8 *value)
{
	unsigned int budget = PMU_BUDGET;
	pmu_u32 op = write ? 0x30u : 0x38u, reply, data;
	int ret;
	if (!io || !io->read || !io->write || !io->delay || !value)
		return -EINVAL;
	if (address != PMU_STAGE && address != PMU_ERRORS && address != PMU_FLAGS)
		return -EPERM;
	if (write != 0 && write != 1)
		return -EINVAL;
	if (io->poisoned)
		return -EIO;
	if (!pmu_idle(io->read(io->ctx, PMU_STATUS)))
		return pmu_fault(io, -EBUSY);
	io->write(io->ctx, PMU_CMD, (address << 16) | (PMU_SID << 8) | op);
	if (write) {
		ret = pmu_wait(io, PMU_TX_FULL, 0, &budget);
		if (ret) return ret;
		io->write(io->ctx, PMU_CMD, *value);
	}
	ret = pmu_wait(io, PMU_RX_EMPTY, 0, &budget);
	if (ret) return ret;
	reply = io->read(io->ctx, PMU_REPLY);
	if ((reply & 0x7fffu) != ((PMU_SID << 8) | op))
		return pmu_fault(io, -EPROTO);
	if ((reply >> 16) != (write ? 0u : 1u) ||
	    !!(reply & 0x8000u) != write)
		return pmu_fault(io, -EIO);
	data = 0;
	if (!write) {
		ret = pmu_wait(io, PMU_RX_EMPTY, 0, &budget);
		if (ret) return ret;
		data = io->read(io->ctx, PMU_REPLY);
		if (data > 255)
			return pmu_fault(io, -EPROTO);
	}
	if (!pmu_idle(io->read(io->ctx, PMU_STATUS)))
		return pmu_fault(io, -EPROTO);
	if (!write) *value = data;
	return 0;
}
static inline int pmu_update(struct pmu_io *io, unsigned int address,
		      pmu_u8 mask, pmu_u8 value)
{
	pmu_u8 old, next, got;
	int ret;
	/* Never change unrelated persistent flags or introduce error counts. */
	if (!((address == PMU_FLAGS && mask == PMU_OFF_BIT && !(value & ~mask)) ||
	      (address == PMU_STAGE && mask == 255 && (value == 0 || value == 0x30)) ||
	      (address == PMU_ERRORS && mask == 255 && value == 0)))
		return -EPERM;
	ret = pmu_byte(io, address, 0, &old);
	if (ret) return ret;
	next = (old & ~mask) | value;
	if (next == old) return 0;
	ret = pmu_byte(io, address, 1, &next);
	if (ret) return ret;
	ret = pmu_byte(io, address, 0, &got);
	if (ret) return ret;
	if (got != next) return pmu_fault(io, -EIO);
	return 0;
}
#endif
