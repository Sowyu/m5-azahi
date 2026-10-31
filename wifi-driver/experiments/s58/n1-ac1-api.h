/* SPDX-License-Identifier: GPL-2.0 */
#ifndef N1_AC1_API_H
#define N1_AC1_API_H
#include <linux/types.h>
int n1_data_tx_ac1(const void *,size_t);
int n1_data_tx_status_ac1(unsigned int *,unsigned int *);
void n1_data_tx_quiesce_ac1(void);
#endif
