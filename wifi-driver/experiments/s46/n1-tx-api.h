/* SPDX-License-Identifier: GPL-2.0 */
#ifndef N1_TX_API_H
#define N1_TX_API_H
#include <linux/types.h>
int n1_data_tx_v1(const void *,size_t);
int n1_data_tx_status_v1(unsigned int *,unsigned int *);
void n1_data_tx_quiesce_v1(void);
#endif
