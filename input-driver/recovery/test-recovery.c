/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
struct hid_device {void *driver_data;};
struct dchid_iface {struct hid_device *hid;const char *name;int index;bool starting,open;int ready;};
static int retry_used, starts, waits, success_wait, start_error, prepare_error;
static int prepare_retry(void) {return prepare_error;}
static int completion_done(int *v) {return *v;}
static unsigned long msecs_to_jiffies(unsigned int ms) {assert(ms==2000);return ms;}
static int wait_for_completion_timeout(int *v,unsigned long t) {
 assert(t==2000);waits++;if(waits==success_wait)*v=1;return *v;
}
static int atomic_cmpxchg(int *v,int expected,int next) {int old=*v;if(old==expected)*v=next;return old;}
static int original_start(struct dchid_iface *i) {
 starts++;if(i->starting)return -EINPROGRESS;
 if(start_error)return start_error;
 i->starting=true;return 0;
}
#define pr_warn(...) ((void)0)
#define pr_err(...) ((void)0)
#define pr_info(...) ((void)0)
#include "recovery-open.h"
int main(void)
{
 for(int stale=0;stale<2;stale++)for(int success=0;success<=2;success++) {
  retry_used=starts=waits=start_error=0;success_wait=success;
  struct hid_device h;
  struct dchid_iface i={.hid=&h,.name="multi-touch",.index=1,.starting=stale};h.driver_data=&i;
  int ret=recovery_open(&h);
  assert(ret==(success?0:-ETIMEDOUT));
  assert(i.open==!!success && waits==(success==1?1:2));
  assert(starts==(!stale)+(success==1?0:1));
  int old_starts=starts;
  ret=recovery_open(&h);
  assert(starts==old_starts); /* success no-op or exhausted retry */
  assert(ret==(success?0:-ETIMEDOUT));
 }
 retry_used=starts=waits=success_wait=0;start_error=-EIO;
 struct hid_device h;
 struct dchid_iface i={.hid=&h,.name="multi-touch",.index=1};h.driver_data=&i;
 assert(recovery_open(&h)==-EIO && starts==1 && !retry_used && !waits);
 i.ready=1;assert(!recovery_open(&h) && starts==1 && i.open);
 i.ready=i.open=0;i.name="keyboard";i.index=2;i.starting=1;start_error=0;
 assert(recovery_open(&h)==-EINPROGRESS && !retry_used);
 retry_used=starts=waits=0;prepare_error=-EIO;success_wait=0;
 i.name="multi-touch";i.index=1;i.starting=1;
 assert(recovery_open(&h)==-EIO && !starts && retry_used==1 && !i.open);
 puts("PASS: actual open path, normal/late READY, one stale-start retry, exhausted retry, command errors, ready/no-op, keyboard behavior");
}
