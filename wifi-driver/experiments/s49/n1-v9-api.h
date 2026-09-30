/* SPDX-License-Identifier: GPL-2.0 */
#ifndef N1_V9_API_H
#define N1_V9_API_H
#include <linux/types.h>
int n1_alpha_exchange_v9(const void *,size_t,void *,size_t *,bool accept_ack);
int n1_alpha_record_v9(unsigned int,unsigned int *,void *,size_t *);
int n1_alpha_scan_status_v9(unsigned int *,unsigned int *,unsigned int *,bool *);
int n1_alpha_cursor_v9(u16 *,u8 *);
#endif
