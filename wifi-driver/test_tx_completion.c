/* SPDX-License-Identifier: GPL-2.0 */
/* Synthetic in-order TX completions. No firmware or captured packet data. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "n1-tx-completion.h"

static void descriptor(n1_u8 *cd, unsigned int first, unsigned int count)
{
	memset(cd,0,32);
	cd[0]=2; cd[1]=5;
	n1_put16(cd+2,25);
	n1_put16(cd+4,(first+count-1)%128);
	n1_put32(cd+8,count<<8);
	/* Footer contains timestamps, not the WLAN result. */
	memset(cd+16,0xa5,16);
}
static void reject(n1_u8 *cd, unsigned int next, n1_u16 *pending)
{
	struct n1_tx_completion c,before;
	n1_u16 saved[128];
	memset(&before,0xa5,sizeof(before)); c=before;
	memcpy(saved,pending,sizeof(saved));
	assert(n1_decode_tx_completion(cd,32,25,128,next,pending,&c)<0);
	assert(!memcmp(&c,&before,sizeof(c)));
	assert(!memcmp(pending,saved,sizeof(saved)));
}
int main(void)
{
	n1_u8 cd[32],*short_cd;
	n1_u16 pending[128]={0};
	struct n1_tx_completion c;
	unsigned int first,count,i;
	/* Reproduces the old decoder's type-2/status-5 rejection. */
	descriptor(cd,0,1); pending[0]=60;
	assert(!n1_decode_tx_completion(cd,32,25,128,0,pending,&c));
	assert(c.first==0 && c.last==0 && c.count==1 && c.length==0);
	assert(c.firmware_status==0 && n1_tx_firmware_success(c.firmware_status));
	for (i=0;i<32;i++) {
		short_cd=malloc(i?i:1); assert(short_cd);
		memcpy(short_cd,cd,i);
		assert(n1_decode_tx_completion(short_cd,i,25,128,0,pending,&c)==-EMSGSIZE);
		free(short_cd);
	}
	assert(n1_decode_tx_completion(cd,33,25,128,0,pending,&c)==-EMSGSIZE);
	/* Every legal batch placement, including wrapping the tag array. */
	for (first=0;first<128;first++) for (count=1;count<128;count++) {
		memset(pending,0,sizeof(pending)); descriptor(cd,first,count);
		for (i=0;i<count;i++) pending[(first+i)%128]=60+i;
		assert(!n1_decode_tx_completion(cd,32,25,128,first,pending,&c));
		assert(c.first==first && c.last==(first+count-1)%128 && c.count==count);
		pending[(first+count/2)%128]=0;
		reject(cd,first,pending); /* gap: no partial ownership return */
	}
	memset(pending,0,sizeof(pending)); pending[0]=60;
	descriptor(cd,0,1); cd[0]=4; reject(cd,0,pending);
	descriptor(cd,0,1); cd[1]=7; reject(cd,0,pending);
	descriptor(cd,0,1); cd[2]=26; reject(cd,0,pending);
	descriptor(cd,0,1); n1_put16(cd+4,128); reject(cd,0,pending);
	descriptor(cd,0,1); reject(cd,1,pending); /* duplicate/stale last tag */
	descriptor(cd,0,1); n1_put16(cd+6,61); reject(cd,0,pending);
	descriptor(cd,0,1); cd[8]=1; reject(cd,0,pending); /* length high bits */
	descriptor(cd,0,1); cd[11]=1; reject(cd,0,pending);
	descriptor(cd,0,1); n1_put32(cd+8,0); reject(cd,0,pending);
	descriptor(cd,0,1); n1_put32(cd+8,128<<8); reject(cd,0,pending);
	descriptor(cd,0,1); cd[1]=4; reject(cd,0,pending); /* count requires batch bit */
	for (i=1;i<=3;i++) {
		descriptor(cd,0,1); cd[0]=i; cd[1]=4; n1_put32(cd+8,0);
		n1_put16(cd+6,60);
		assert(!n1_decode_tx_completion(cd,32,25,128,0,pending,&c));
		assert(c.count==1 && c.length==60);
	}
	for (i=0;i<256;i++) {
		descriptor(cd,0,1); cd[12]=i;
		assert(!n1_decode_tx_completion(cd,32,25,128,0,pending,&c));
		assert(c.firmware_status==i);
		assert(n1_tx_firmware_success(c.firmware_status)==(i==0 || i==1 || i==0x83));
	}
	assert(n1_decode_tx_completion(NULL,32,25,128,0,pending,&c)==-EINVAL);
	assert(n1_decode_tx_completion(cd,32,25,128,0,NULL,&c)==-EINVAL);
	assert(n1_decode_tx_completion(cd,32,25,128,0,pending,NULL)==-EINVAL);
	assert(n1_decode_tx_completion(cd,32,25,129,0,pending,&c)==-EINVAL);
	assert(n1_decode_tx_completion(cd,32,25,128,128,pending,&c)==-EINVAL);
	puts("PASS: TX batch regression, 16256 wrap/gap cases, bounds and all firmware statuses");
	return 0;
}
