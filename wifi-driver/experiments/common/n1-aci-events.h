/* SPDX-License-Identifier: GPL-2.0 */
/* Bounds-checked ACI decoding; no device access or connection policy.
 * Connection layouts come from the local native STA event adapter.
 * Scan, association, four-way and connection-complete events are live-observed.
 */
#ifndef N1_ACI_EVENTS_H
#define N1_ACI_EVENTS_H
#include "n1-wire.h"

enum n1_event_kind {
	N1_EVENT_OTHER, N1_EVENT_CONNECT_COMPLETE, N1_EVENT_ASSOCIATED,
	N1_EVENT_CONNECTION_LOST, N1_EVENT_CONNECTION_FAILED,
	N1_EVENT_SCAN_COMPLETE, N1_EVENT_FOUR_WAY
};
struct n1_aci_header {
	n1_u32 cid;
	n1_u16 sequence, status, length;
	n1_u8 opcode, interface_id;
};
struct n1_aci_event {
	struct n1_aci_header header;
	enum n1_event_kind kind;
	union {
		/* First candidate only, not an MLO/roaming decoder. */
		struct { n1_u8 ssid[32], ssid_length, bssid[6]; n1_u32 info; } connect;
		struct { n1_u8 bssid[6], channel[4], flags, mlo, mld[6]; } associated;
		struct { n1_u8 reason, bssid[6]; } lost;
		struct { n1_u16 status, results; n1_u32 dwell_ms; n1_u8 handle; } scan;
		/* Preserve raw supplicant stage; do not equate status0 with success. */
		struct { n1_u32 status, disabled_flags; n1_u8 stage; } four_way;
	} data;
};

static inline int n1_aci_parse_header(const n1_u8 *data, size_t length,
	struct n1_aci_header *out)
{
	struct n1_aci_header h = {0};
	if (!data || !out) return -EINVAL;
	if (length < 24 || length > 4096) return -EMSGSIZE;
	if (data[1] != 24 || n1_get16(data + 16) != length ||
	    (data[0] != 0x41 && data[0] != 0x43)) return -EPROTO;
	h.opcode = data[0]; h.interface_id = data[13];
	h.status = n1_get16(data + 14); h.length = length;
	h.sequence = n1_get16(data + 18); h.cid = n1_get32(data + 20);
	*out = h;
	return 0;
}

static inline int n1_aci_parse_event(const n1_u8 *data, size_t length,
	struct n1_aci_event *out)
{
	struct n1_aci_event e = {0};
	n1_u32 ssid_length;
	int ret;
	if (!out) return -EINVAL;
	ret = n1_aci_parse_header(data, length, &e.header);
	if (ret) return ret;
	if (e.header.opcode != 0x43 || !(e.header.cid & 0x80000000U)) return -EPROTO;
	/* Other interfaces use different event namespaces. Preserve their header. */
	if (e.header.interface_id) { *out = e; return 0; }
	switch (e.header.cid & 0x00ffffffU) {
	case 0:
		if (length < 114) return -EMSGSIZE;
		ssid_length = n1_get32(data + 56);
		if (ssid_length > 32) return -EPROTO;
		e.kind = N1_EVENT_CONNECT_COMPLETE;
		e.data.connect.ssid_length = ssid_length;
		memcpy(e.data.connect.ssid, data + 24, ssid_length);
		memcpy(e.data.connect.bssid, data + 60, 6);
		e.data.connect.info = n1_get32(data + 66);
		break;
	case 1:
		if (length < 44) return -EMSGSIZE;
		e.kind = N1_EVENT_ASSOCIATED;
		memcpy(e.data.associated.bssid, data + 26, 6);
		e.data.associated.flags = data[32];
		memcpy(e.data.associated.channel, data + 33, 4);
		e.data.associated.mlo = data[37];
		memcpy(e.data.associated.mld, data + 38, 6);
		break;
	case 3:
		if (length < 31) return -EMSGSIZE;
		e.kind = N1_EVENT_CONNECTION_LOST;
		e.data.lost.reason = data[24];
		memcpy(e.data.lost.bssid, data + 25, 6);
		break;
	case 4:
		e.kind = N1_EVENT_CONNECTION_FAILED;
		break;
	case 5:
		if (length < 33) return -EMSGSIZE;
		e.kind = N1_EVENT_SCAN_COMPLETE;
		e.data.scan.status = n1_get16(data + 24);
		e.data.scan.results = n1_get16(data + 26);
		e.data.scan.dwell_ms = n1_get32(data + 28);
		e.data.scan.handle = data[32];
		break;
	case 0x50:
		if (length < 64) return -EMSGSIZE;
		e.kind = N1_EVENT_FOUR_WAY;
		e.data.four_way.status = n1_get32(data + 24);
		e.data.four_way.stage = data[28];
		e.data.four_way.disabled_flags = n1_get32(data + 32);
		break;
	default:
		break;
	}
	*out = e;
	return 0;
}

enum n1_reply_action { N1_REPLY_UNRELATED, N1_REPLY_INTERMEDIATE, N1_REPLY_COMPLETE };
/* Caller explicitly chooses ACK-as-acceptance for asynchronous operations.
 * A COMPLETE reply is command completion, never proof of association.
 * Mismatched sequence/CID/interface must not satisfy a pending request. */
static inline int n1_aci_classify_reply(const n1_u8 *data, size_t length,
	n1_u32 cid, n1_u16 sequence, n1_u8 interface_id, int accept_ack)
{
	struct n1_aci_header h;
	int ret = n1_aci_parse_header(data, length, &h);
	if (ret) return ret;
	if (h.opcode != 0x41 || (h.cid & ~0x40000000U) != cid ||
	    h.sequence != sequence || h.interface_id != interface_id)
		return N1_REPLY_UNRELATED;
	return h.status || accept_ack || !(h.cid & 0x40000000U) ?
		N1_REPLY_COMPLETE : N1_REPLY_INTERMEDIATE;
}
#endif
