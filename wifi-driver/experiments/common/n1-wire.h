/* SPDX-License-Identifier: GPL-2.0 */
#ifndef N1_WIRE_H
#define N1_WIRE_H
#ifdef __KERNEL__
#include <linux/types.h>
#include <linux/string.h>
#include <linux/errno.h>
typedef u8 n1_u8;
typedef u16 n1_u16;
typedef u32 n1_u32;
#else
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <errno.h>
typedef uint8_t n1_u8;
typedef uint16_t n1_u16;
typedef uint32_t n1_u32;
#endif
static inline n1_u16 n1_get16(const n1_u8 *p)
{
	return (n1_u16)p[0] | (n1_u16)p[1] << 8;
}
static inline n1_u32 n1_get32(const n1_u8 *p)
{
	return (n1_u32)p[0] | (n1_u32)p[1] << 8 |
	       (n1_u32)p[2] << 16 | (n1_u32)p[3] << 24;
}
static inline void n1_put16(n1_u8 *p, n1_u16 v)
{
	p[0] = v; p[1] = v >> 8;
}
static inline void n1_put32(n1_u8 *p, n1_u32 v)
{
	p[0] = v; p[1] = v >> 8; p[2] = v >> 16; p[3] = v >> 24;
}
#endif
