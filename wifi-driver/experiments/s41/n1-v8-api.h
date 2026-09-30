/* SPDX-License-Identifier: GPL-2.0 */
#ifndef N1_V8_API_H
#define N1_V8_API_H
#include <linux/types.h>
int n1_alpha_exchange_v8(const void *,size_t,void *,size_t *,bool accept_ack);
int n1_alpha_record_v8(unsigned int,unsigned int *,void *,size_t *);
int n1_alpha_scan_status_v8(unsigned int *,unsigned int *,unsigned int *,bool *);
int n1_alpha_cursor_v8(u16 *,u8 *);
#endif
