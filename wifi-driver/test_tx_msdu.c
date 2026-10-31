/* SPDX-License-Identifier: GPL-2.0 */
/* Synthetic payload conservation and rejection tests; no captured frames. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "n1-tx-msdu.h"
int main(void)
{
	n1_u8 frame[1515], original[1515], separate[1516], inplace[1515];
	const unsigned int types[] = {0x0600,0x0800,0x0806,0x86dd,0x8100};
	const unsigned int rejected[] = {0,1500,1535,0x80f3,0x8137};
	size_t length,i,j;
	int n;
	for (i=0;i<sizeof(frame);i++) frame[i]=(n1_u8)(i*37+11);
	for (j=0;j<sizeof(types)/sizeof(types[0]);j++) {
		frame[12]=types[j]>>8; frame[13]=types[j];
		for (length=14;length<=1514;length++) {
			memcpy(original,frame,sizeof(frame));
			memset(separate,0xa5,sizeof(separate));
			n=n1_ethernet_to_snap(separate+1,length-6,frame,length);
			assert(n==(int)length-6 && separate[0]==0xa5 && separate[n+1]==0xa5);
			assert(!memcmp(separate+1,"\xaa\xaa\x03\x00\x00\x00",6));
			assert(separate[7]==frame[12] && separate[8]==frame[13]);
			assert(!memcmp(separate+9,frame+14,length-14));
			assert(!memcmp(frame,original,sizeof(frame)));
			memcpy(inplace,frame,sizeof(frame));
			assert(n1_ethernet_to_snap(inplace,length, inplace,length)==n);
			assert(!memcmp(inplace,separate+1,n));
			memcpy(inplace,frame,sizeof(frame));
			assert(n1_ethernet_to_snap(inplace,length-7,inplace,length)==-EMSGSIZE);
			assert(!memcmp(inplace,frame,sizeof(frame)));
		}
	}
	for (length=0;length<14;length++) {
		n1_u8 *small=malloc(length?length:1); assert(small);
		assert(n1_ethernet_to_snap(separate,sizeof(separate),small,length)==-EMSGSIZE);
		free(small);
	}
	assert(n1_ethernet_to_snap(separate,sizeof(separate),frame,1515)==-EMSGSIZE);
	for (j=0;j<sizeof(rejected)/sizeof(rejected[0]);j++) {
		frame[12]=rejected[j]>>8; frame[13]=rejected[j];
		memcpy(original,frame,sizeof(frame));
		assert(n1_ethernet_to_snap(frame,sizeof(frame),frame,60)==-EPROTONOSUPPORT);
		assert(!memcmp(frame,original,sizeof(frame)));
	}
	assert(n1_ethernet_to_snap(NULL,100,frame,60)==-EINVAL);
	assert(n1_ethernet_to_snap(separate,100,NULL,60)==-EINVAL);
	puts("PASS: 7505 payload sizes/types, in-place conversion, bounds and unsupported formats");
	return 0;
}
