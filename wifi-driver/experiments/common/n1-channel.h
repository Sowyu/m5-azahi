/* SPDX-License-Identifier: GPL-2.0 */
#ifndef N1_CHANNEL_H
#define N1_CHANNEL_H
#include "n1-wire.h"

/* ACI band values, distinct from nl80211 enum values. Only conventional
 * 20 MHz 2.4/5 GHz candidates are exposed; regulatory limits remain cfg80211's. */
static inline int n1_channel20(n1_u8 out[4],unsigned int channel,unsigned int band)
{
	int valid = band == 0 ? channel >= 1 && channel <= 13 :
		band == 1 && ((channel >= 36 && channel <= 64 && channel % 4 == 0) ||
		(channel >= 100 && channel <= 144 && channel % 4 == 0) ||
		(channel >= 149 && channel <= 165 && channel % 4 == 1));
	if (!out || !valid) return -EINVAL;
	out[0] = channel; out[1] = band; out[2] = out[3] = 0;
	return 0;
}

/* Associated events can report 40/80/160 MHz center channels. The native
 * primary-position field counts from the upper edge of each channel block. */
static inline int n1_primary_channel(const n1_u8 data[4],unsigned int *band)
{
	unsigned int width=data[2], center=data[0], b=data[1]&7;
	int primary;
	n1_u8 check[4];
	if (width==0) primary=center;
	else if (width<=2) primary=(int)center+2-4*(width-1);
	else if (width<=6) primary=(int)center+6-4*(width-3);
	else if (width<=14) primary=(int)center+14-4*(width-7);
	else return -EINVAL;
	if (n1_channel20(check,primary,b)) return -EINVAL;
	*band=b;
	return primary;
}
#endif
