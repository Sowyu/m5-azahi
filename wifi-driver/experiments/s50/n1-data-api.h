/* SPDX-License-Identifier: GPL-2.0 */
#ifndef N1_DATA_API_H
#define N1_DATA_API_H
#include <linux/types.h>
int n1_data_rx_read_v2(unsigned int,void *,void *,size_t *);
int n1_data_rx_status_v2(unsigned int *);
void n1_data_rx_quiesce_v2(void);
/* One host consumer. Callback runs under the transport lock and must not
 * sleep or call transport APIs. Bytes are a host copy valid until return.
 * Detach waits for any in-flight callback before its context can be freed. */
typedef void (*n1_rx_consumer_v2)(void *,const void *,size_t);
int n1_data_rx_attach_v2(n1_rx_consumer_v2,void *);
void n1_data_rx_detach_v2(void *);
#endif
