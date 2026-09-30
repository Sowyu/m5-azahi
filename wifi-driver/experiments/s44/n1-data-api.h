/* SPDX-License-Identifier: GPL-2.0 */
#ifndef N1_DATA_API_H
#define N1_DATA_API_H
#include <linux/types.h>
int n1_data_rx_read_v1(unsigned int,void *,void *,size_t *);
int n1_data_rx_status_v1(unsigned int *);
void n1_data_rx_quiesce_v1(void);
#endif
