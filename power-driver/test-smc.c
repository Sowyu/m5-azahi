/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define SMC_KEY(x) (((u32)(#x)[0]<<24)|((u32)(#x)[1]<<16)|((u32)(#x)[2]<<8)|(#x)[3])
#define IS_ALIGNED(x,a) (!((x)&((a)-1)))
#define APPLE_SMC_INITIALIZED 1
struct apple_smc {
 int lock, boot_stage;
 bool atomic_mode, atomic_pending;
 unsigned int msg_id;
 struct {void *iomem;} shmem;
 void *rtk;
};
static unsigned int writes, sends;
static u32 word;
static u64 message;
static int send_error;
#define spin_lock_irqsave(l,f) do { assert(!*(l)); *(l)=1; (f)=0; } while(0)
#define spin_unlock_irqrestore(l,f) do { assert(*(l)); *(l)=0; (void)(f); } while(0)
static void writel(u32 v, void *p) { assert(p == &word); word=v; writes++; }
static int apple_rtkit_send_message(void *r, unsigned int ep, u64 msg, void *c, bool atomic)
{
 assert(r && ep==0x20 && !c && atomic); sends++; message=msg; return send_error;
}
#include "smc-final.h"
static struct apple_smc make(void)
{
 writes=sends=word=message=send_error=0;
 return (struct apple_smc){.boot_stage=1,.atomic_mode=true,.shmem.iomem=&word,.rtk=&word};
}
int main(void)
{
 for (unsigned int id=0;id<16;id++) for (int off=0;off<2;off++) {
  struct apple_smc s=make(); s.msg_id=id;
  u32 action=off ? SMC_KEY(off1):SMC_KEY(phra);
  assert(!smc_final_send(&s,action));
  assert(writes==1 && sends==1 && word==action && s.atomic_pending && !s.lock);
  assert(s.msg_id==((id+1)&15));
  assert(message==((u64)SMC_KEY(MBSE)<<32 | 4u<<16 | s.msg_id<<12 | 0x11));
  assert(smc_final_send(&s,action)==-EBUSY && writes==1 && sends==1);
 }
 for (int fault=0;fault<6;fault++) {
  struct apple_smc s=make();
  if(fault==0) s.boot_stage=0;
  if(fault==1) s.atomic_mode=false;
  if(fault==2) s.shmem.iomem=NULL;
  if(fault==3) s.shmem.iomem=(char *)&word+1;
  if(fault==4) s.atomic_pending=true;
  u32 action=fault==5 ? SMC_KEY(rest):SMC_KEY(off1);
  assert(smc_final_send(&s,action)<0 && !writes && !sends && !s.lock);
 }
 struct apple_smc s=make(); send_error=-ETIMEDOUT;
 assert(smc_final_send(&s,SMC_KEY(phra))==-ETIMEDOUT && s.atomic_pending);
 assert(smc_final_send(&s,SMC_KEY(phra))==-EBUSY && writes==1 && sends==1);
 puts("PASS: SMC final actions, 16 message IDs, one 32-bit write, state/alignment guards, pending/timeout quarantine, no RX polling");
}
