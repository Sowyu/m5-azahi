/* SPDX-License-Identifier: GPL-2.0 */
/* Independent encoder for the locally decoded ACI connect command.
 * Only one 2.4 GHz candidate, open or WPA2-PSK/CCMP, no MLO/roaming/PMF.
 * Caller owns sequence allocation and must erase buffers containing PMKs.
 */
#ifndef N1_ACI_CONNECT_H
#define N1_ACI_CONNECT_H
#include "n1-wire.h"

/* Native connectAp first clears previously installed vendor IEs. */
static inline int n1_build_clear_vendor_ie(n1_u8 *out, size_t capacity,
	n1_u16 sequence)
{
	if (!out || !sequence) return -EINVAL;
	if (capacity < 25) return -EMSGSIZE;
	memset(out, 0, 25);
	n1_put16(out + 16, 25); n1_put16(out + 18, sequence);
	n1_put32(out + 20, 0x1c); out[24] = 0x3f;
	return 25;
}

/* No optional vendor IEs. The caller supplies the native disconnect mode;
 * its meaning is not yet established, so this helper supplies no default. */
static inline int n1_build_disconnect(n1_u8 *out, size_t capacity,
	n1_u16 sequence, n1_u16 reason, n1_u32 mode)
{
	if (!out || !sequence) return -EINVAL;
	if (capacity < 40) return -EMSGSIZE;
	memset(out, 0, 40);
	n1_put16(out + 16, 40); n1_put16(out + 18, sequence);
	n1_put32(out + 20, 0x20001); n1_put16(out + 24, reason);
	n1_put16(out + 32, 0x148); n1_put16(out + 34, 4);
	n1_put32(out + 36, mode);
	return 40;
}

static inline int n1_build_connect(n1_u8 *out, size_t capacity,
	n1_u16 sequence, const n1_u8 bssid[6], n1_u8 channel,
	const n1_u8 *ssid, size_t ssid_len, const n1_u8 *pmk, size_t pmk_len)
{
	static const n1_u8 rsn_ccmp_psk[] = {
		1, 0, 0, 15, 172, 4, 1, 0, 0, 15, 172, 4,
		1, 0, 0, 15, 172, 2, 12, 0
	};
	static const n1_u8 global[] = {
		1, 0, 1, 255, 255, 255, 255, 255, 255, 255, 255, 3
	};
	size_t pos, length = 206 + ssid_len + (pmk_len ? 29 : 0);
	unsigned int i, nonzero = 0;
	if (!out || !bssid || !ssid || !sequence || !ssid_len || ssid_len > 32 ||
	    channel < 1 || channel > 11 || (bssid[0] & 1) ||
	    (pmk_len && (pmk_len != 32 || !pmk)) || (!pmk_len && pmk))
		return -EINVAL;
	for (i = 0; i < 6; i++) nonzero |= bssid[i];
	if (!nonzero) return -EINVAL;
	if (capacity < length) return -EMSGSIZE;
	memset(out, 0, length);
	n1_put16(out + 16, length);
	n1_put16(out + 18, sequence);
	out[22] = 2; /* CID 0x00020000 */
	out[24] = 1;
	memcpy(out + 25, bssid, 6);
	out[31] = channel; /* 20 MHz, 2 GHz */
	if (pmk_len) {
		out[95] = 4; /* WPA2-PSK */
		n1_put16(out + 96, 4); /* CCMP */
		n1_put16(out + 98, 32);
		memcpy(out + 100, pmk, 32);
	}
	pos = 154;
	n1_put16(out + pos, 0x130); n1_put16(out + pos + 2, 1); pos += 5;
	n1_put16(out + pos, 0xf913); n1_put16(out + pos + 2, 20); pos += 24;
	n1_put16(out + pos, 0x156); n1_put16(out + pos + 2, ssid_len + 3);
	out[pos + 4] = 1; out[pos + 6] = ssid_len;
	memcpy(out + pos + 7, ssid, ssid_len); pos += 7 + ssid_len;
	if (pmk_len) {
		n1_put16(out + pos, 0x30); n1_put16(out + pos + 2, sizeof(rsn_ccmp_psk));
		memcpy(out + pos + 4, rsn_ccmp_psk, sizeof(rsn_ccmp_psk)); pos += 24;
		n1_put16(out + pos, 0x13c); n1_put16(out + pos + 2, 1); pos += 5;
	}
	n1_put16(out + pos, 0x178); n1_put16(out + pos + 2, sizeof(global));
	memcpy(out + pos + 4, global, sizeof(global));
	return length;
}

/* Firmware 91.104.6 extends GlobalConfig TLV 0x178. Its parser at
 * image aciw offset 0x173d20 rejects lengths <13, copies 14 bytes, and
 * inspects optional flags at byte13. The 25G83 host builder emits only12.
 * Supply the full14 bytes with both extension bytes zero/disabled.
 * Keep the old builder separate so its native oracle stays meaningful. */
static inline int n1_build_connect_91_104_6(n1_u8 *out, size_t capacity,
	n1_u16 sequence, const n1_u8 bssid[6], n1_u8 channel,
	const n1_u8 *ssid, size_t ssid_len, const n1_u8 *pmk, size_t pmk_len)
{
	int length;
	if (capacity < 2) return -EMSGSIZE;
	length = n1_build_connect(out, capacity - 2, sequence, bssid, channel,
		ssid, ssid_len, pmk, pmk_len);
	if (length < 0) return length;
	/* f913 payload is five connection timers, copied to state+0x6d5.
	 * Firmware defaults at aciw offset0x11330c..0x113336. Zero values
	 * cause an immediate four-way timeout (live status362, stage3). */
	n1_put32(out + 163, 260);
	n1_put32(out + 167, 6000);
	n1_put32(out + 171, 2000);
	n1_put32(out + 175, 15000);
	n1_put32(out + 179, 300);
	/* GlobalConfig is the final TLV in this bounded encoder. */
	n1_put16(out + length - 14, 14);
	out[length] = out[length + 1] = 0;
	n1_put16(out + 16, length + 2);
	return length + 2;
}
#endif
