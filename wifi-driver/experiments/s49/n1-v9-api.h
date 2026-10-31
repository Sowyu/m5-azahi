/* SPDX-License-Identifier: GPL-2.0 */
#ifndef N1_V9_API_H
#define N1_V9_API_H
#include <linux/types.h>
#include "../common/n1-link-state.h"
int n1_alpha_exchange_v9(const void *,size_t,void *,size_t *,bool accept_ack);
int n1_alpha_record_v9(unsigned int,unsigned int *,void *,size_t *);
int n1_alpha_scan_status_v9(unsigned int *,unsigned int *,unsigned int *,bool *);
int n1_alpha_cursor_v9(u16 *,u8 *);
/* Snapshot and record cursor are captured under the same transport lock. */
int n1_alpha_state_v9(struct n1_link_state *,unsigned int *);
#endif
