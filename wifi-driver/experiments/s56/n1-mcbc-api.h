/* SPDX-License-Identifier: GPL-2.0 */
#ifndef N1_MCBC_API_H
#define N1_MCBC_API_H
#include <linux/types.h>
int n1_data_tx_mcbc(const void *,size_t);
int n1_data_tx_status_mcbc(unsigned int *,unsigned int *);
void n1_data_tx_quiesce_mcbc(void);
#endif
