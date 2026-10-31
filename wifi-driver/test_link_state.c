/* SPDX-License-Identifier: GPL-2.0 */
#include <assert.h>
#include <stdio.h>
#include "n1-link-state.h"

static struct n1_aci_event event(enum n1_event_kind kind, unsigned int seq)
{
	struct n1_aci_event e = {0};
	e.kind = kind; e.header.sequence = seq;
	return e;
}
int main(void)
{
	struct n1_link_state s = {0};
	struct n1_aci_event e;
	unsigned int i, order;
	assert(!n1_link_ready(&s));
	for (order = 0; order < 2; order++) {
		n1_link_begin(&s, 41, 1);
		assert(!n1_link_ready(&s));
		/* Old successful events cannot complete the new join. */
		e = event(N1_EVENT_CONNECT_COMPLETE, 40); n1_link_event(&s, &e);
		e = event(N1_EVENT_FOUR_WAY, 40); e.data.four_way.stage = 7;
		n1_link_event(&s, &e); assert(!s.complete && !s.secure);
		e = event(N1_EVENT_FOUR_WAY, 0); e.data.four_way.stage = 7;
		n1_link_event(&s, &e); assert(!s.secure);
		e = event(N1_EVENT_ASSOCIATED, 41); n1_link_event(&s, &e);
		for (i = 0; i < 2; i++) {
			e = event((i ^ order) ? N1_EVENT_FOUR_WAY : N1_EVENT_CONNECT_COMPLETE, 41);
			if (e.kind == N1_EVENT_FOUR_WAY) { e.data.four_way.stage = 7; e.header.sequence = 0; }
			n1_link_event(&s, &e);
			assert(n1_link_ready(&s) == (i == 1));
		}
		/* Arbitrarily many scans do not evict the link evidence. */
		for (i = 0; i < 100000; i++) {
			e = event(N1_EVENT_SCAN_COMPLETE, i); n1_link_event(&s, &e);
		}
		assert(n1_link_ready(&s));
		/* Firmware-initiated roaming has sequence zero, no new connect
		 * completion, and must re-establish WPA2 before restoring carrier. */
		e = event(N1_EVENT_ASSOCIATED, 0); e.data.associated.bssid[0] = 2;
		n1_link_event(&s, &e); assert(s.roaming && !n1_link_ready(&s));
		e = event(N1_EVENT_FOUR_WAY, 0); e.data.four_way.stage = 7;
		n1_link_event(&s, &e); assert(!s.roaming && n1_link_ready(&s) && s.bssid[0] == 2);
		e = event(N1_EVENT_CONNECTION_LOST, 0); e.data.lost.reason = 4;
		n1_link_event(&s, &e); assert(!n1_link_ready(&s) && s.reason == 4);
		e = event(N1_EVENT_CONNECT_COMPLETE, 41); n1_link_event(&s, &e);
		assert(!n1_link_ready(&s));
	}
	n1_link_begin(&s, 65535, 0);
	e = event(N1_EVENT_CONNECT_COMPLETE, 65535); n1_link_event(&s, &e);
	assert(n1_link_ready(&s));
	n1_link_begin(&s, 1, 1); assert(!n1_link_ready(&s));
	e = event(N1_EVENT_ASSOCIATED, 1); n1_link_event(&s, &e);
	e = event(N1_EVENT_FOUR_WAY, 1); e.data.four_way.stage = 3;
	n1_link_event(&s, &e); assert(!s.secure);
	e.data.four_way.status = 362; n1_link_event(&s, &e);
	e = event(N1_EVENT_CONNECT_COMPLETE, 1); n1_link_event(&s, &e);
	assert(s.failed && !n1_link_ready(&s));
	n1_link_begin(&s, 2, 1);
	e = event(N1_EVENT_CONNECT_COMPLETE, 2); e.header.status = 1;
	n1_link_event(&s, &e); assert(s.failed && !n1_link_ready(&s));
	puts("PASS: link state survives scan history, rejects stale joins, gates WPA2 on handshake, and clears on loss");
}
