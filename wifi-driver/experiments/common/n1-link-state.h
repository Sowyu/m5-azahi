/* SPDX-License-Identifier: GPL-2.0 */
/* Persistent connection evidence, independent of diagnostic history.
 * Callers serialize updates. A command ACK never establishes carrier.
 */
#ifndef N1_LINK_STATE_H
#define N1_LINK_STATE_H
#include "n1-aci-events.h"

struct n1_link_state {
	n1_u32 generation, changes, losses;
	n1_u16 sequence, status, reason;
	n1_u8 requested, protected, complete, secure, failed, associated, roaming;
	n1_u8 bssid[6], channel[4], ssid[32], ssid_length;
};

static inline void n1_link_begin(struct n1_link_state *s, n1_u16 sequence,
	int protected)
{
	n1_u32 generation = s->generation + 1, changes = s->changes + 1;
	n1_u32 losses = s->losses;
	memset(s, 0, sizeof(*s));
	s->generation = generation; s->changes = changes; s->losses = losses;
	s->sequence = sequence; s->requested = 1; s->protected = !!protected;
}

static inline int n1_link_ready(const struct n1_link_state *s)
{
	return s->requested && s->complete && !s->failed &&
		(!s->protected || s->secure);
}

static inline void n1_link_event(struct n1_link_state *s,
	const struct n1_aci_event *e)
{
	if (e->kind == N1_EVENT_CONNECTION_LOST ||
	    e->kind == N1_EVENT_DISCONNECT_COMPLETE) {
		s->complete = s->secure = s->roaming = 0;
		s->failed = 1; s->losses++; s->changes++;
		s->reason = e->kind == N1_EVENT_CONNECTION_LOST ? e->data.lost.reason : 0;
		return;
	}
	if (!s->requested || s->failed) return;
	/* Live firmware emits four-way events with sequence zero, after a
	 * sequence-correlated associated event. Never let an uncorrelated
	 * handshake preceding association authorize a new join. */
	if (e->kind == N1_EVENT_FOUR_WAY) {
		if (!s->associated || (e->header.sequence && e->header.sequence != s->sequence)) return;
	} else if (e->header.sequence != s->sequence &&
		!(e->kind == N1_EVENT_ASSOCIATED && !e->header.sequence && s->complete)) return;
	switch (e->kind) {
	case N1_EVENT_ASSOCIATED:
		if (e->header.status) break;
		s->associated = 1;
		if (!e->header.sequence) { s->roaming = s->protected; s->secure = 0; }
		memcpy(s->bssid, e->data.associated.bssid, 6);
		memcpy(s->channel, e->data.associated.channel, 4);
		s->changes++;
		break;
	case N1_EVENT_FOUR_WAY:
		if (e->header.status || e->data.four_way.status) {
			s->failed = 1; s->secure = 0;
			s->status = e->header.status ? e->header.status : 1;
		} else if (e->data.four_way.stage == 7) { s->secure = 1; s->roaming = 0; }
		s->changes++;
		break;
	case N1_EVENT_CONNECT_COMPLETE:
		s->status = e->header.status;
		s->complete = !s->status; s->failed = !!s->status;
		memcpy(s->bssid, e->data.connect.bssid, 6);
		memcpy(s->ssid, e->data.connect.ssid, e->data.connect.ssid_length);
		s->ssid_length = e->data.connect.ssid_length;
		s->changes++;
		break;
	default:
		break;
	}
}
#endif
