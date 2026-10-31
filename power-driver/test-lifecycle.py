#!/usr/bin/env python3
"""Exercise the real power callbacks with injected PMU/SMC failures."""
from pathlib import Path
import subprocess
import tempfile

source = Path(__file__).with_name('power.c').read_text()
notify = source[source.index('static int power_notify('):source.index('static struct notifier_block power_nb')]
final = source[source.index('static int power_prepare('):source.index('static void unregister_handlers(')]
stub = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
#define SYS_RESTART 1
#define SYS_POWER_OFF 3
#define NOTIFY_DONE 0
#define NOTIFY_OK 1
#define PMU_FLAGS 0xf80f
#define PMU_STAGE 0xf801
#define PMU_OFF_BIT 8
#define SMC_KEY(x) (((u32)(#x)[0]<<24)|((u32)(#x)[1]<<16)|((u32)(#x)[2]<<8)|(#x)[3])
#define pr_info(...) ((void)0)
#define pr_err(...) ((void)0)
#define pr_emerg(...) ((void)0)
struct notifier_block {int unused;};
struct sys_off_data {void *cb_data;};
static bool ready,notified,prepared,final_sent;
static unsigned long requested_action;
static int result, bus, lifecycle_lock, smc_store, *smc=&smc_store;
static int warnings, updates, enters, sends, delays, warning_error, pmu_error_at, atomic_error;
static u32 warning, action;
static unsigned int addresses[2], values[2];
static void mutex_lock(int *l) {assert(!*l);*l=1;}
static void mutex_unlock(int *l) {assert(*l);*l=0;}
static int apple_smc_write_u32(int *s,u32 key,u32 val) {
 assert(s==smc && key==SMC_KEY(MBSE));warnings++;warning=val;return warning_error;
}
static int pmu_update(int *b,unsigned int addr,unsigned int mask,unsigned int val) {
 assert(b==&bus && updates<2);
 assert((addr==PMU_FLAGS && mask==PMU_OFF_BIT)||(addr==PMU_STAGE && mask==255));
 addresses[updates]=addr;values[updates]=val;updates++;
 return pmu_error_at==updates ? -EIO:0;
}
static int apple_smc_enter_atomic(int *s) {assert(s==smc);enters++;return atomic_error;}
static int smc_final_send(int *s,u32 val) {assert(s==smc);sends++;action=val;return 0;}
static void mdelay(unsigned int ms) {assert(ms==1000);delays++;}
'''
tests = r'''
static void reset(void) {
 ready=true;notified=prepared=final_sent=false;requested_action=result=0;
 warnings=updates=enters=sends=delays=warning_error=pmu_error_at=atomic_error=0;
 lifecycle_lock=0;
}
int main(void) {
 for(int mode=1;mode<=3;mode+=2) {
  reset();struct sys_off_data d={.cb_data=(void *)(unsigned long)mode};
  power_prepare(&d);power_final(&d);assert(!enters && !sends);
  assert(power_notify(NULL,99,NULL)==NOTIFY_DONE && !warnings);
  power_notify(NULL,mode,NULL);
  assert(warnings==1 && updates==2 && ready && notified && requested_action==mode);
  assert(addresses[0]==PMU_FLAGS && values[0]==(mode==3 ? 8:0));
  assert(addresses[1]==PMU_STAGE && values[1]==0);
  assert(warning==(mode==3 ? SMC_KEY(offw):SMC_KEY(rest)));
  power_prepare(&d);power_prepare(&d);assert(enters==1 && prepared);
  struct sys_off_data wrong={.cb_data=(void *)(unsigned long)(mode==3?1:3)};
  power_final(&wrong);assert(!sends);
  power_final(&d);power_final(&d);power_notify(NULL,mode,NULL);
  assert(sends==1 && delays==1 && warnings==1 && updates==2);
  assert(action==(mode==3 ? SMC_KEY(off1):SMC_KEY(phra)));
 }
 for(int fault=0;fault<4;fault++) {
  reset();struct sys_off_data d={.cb_data=(void *)3};
  if(fault==0) warning_error=-ETIMEDOUT;
  if(fault==1) pmu_error_at=1;
  if(fault==2) pmu_error_at=2;
  if(fault==3) atomic_error=-EIO;
  power_notify(NULL,3,NULL);power_prepare(&d);power_final(&d);
  assert(!sends && !delays);
  if(fault==1) assert(updates==1);
  if(fault!=3) assert(!ready && !enters);
 }
 puts("PASS: actual lifecycle callbacks, off/restart selection, verified PMU-before-final order, failures suppress final command, single-use callbacks");
}
'''
with tempfile.TemporaryDirectory(prefix='azahi-power-test-') as directory:
    c = Path(directory) / 'callbacks.c'
    binary = Path(directory) / 'callbacks'
    c.write_text(stub + notify + final + tests)
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-parameter', '-Wno-sign-compare',
                    '-fsanitize=address,undefined', str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
