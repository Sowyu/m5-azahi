#!/usr/bin/env python3
"""Force overlapping GPIO acquisitions in the actual interface functions.

Pthreads model two sleepable callers and gpiolib's exclusive request. The
fixture does not run HID core, workqueues, a GPIO controller or firmware.
"""
import os
from pathlib import Path
import runpy
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent
helpers = runpy.run_path(str(ROOT / 'smp/test-smp-diag.py'))
source = Path(os.environ.get('AZAHI_INPUT_SOURCE', ROOT / 'input-driver/dockchannel-hid.c')).read_text()
functions = '\n'.join(helpers['extract'](source, name) for name in (
    'static struct dchid_iface *\ndchid_get_interface(', 'static int dchid_request_gpio('))

STUB = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
#include <time.h>
#define MAX_INTERFACES 16
#define MAX_GPIO_NAME 32
#define GFP_KERNEL 0
#define WQ_MEM_RECLAIM 0
#define GPIOD_OUT_LOW 1
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_warn(...) ((void)0)
#define IS_ERR_OR_NULL(p) (!(p) || (uintptr_t)(p)>=(uintptr_t)-4095)
#define PTR_ERR(p) ((long)(intptr_t)(p))
#define init_completion(p) (*(p)=0)
#define spin_lock_init(p) (*(p)=0)
struct mutex { pthread_mutex_t raw; bool initialized; };
struct device_node { int unused; };
struct device { struct device_node *of_node; };
struct gpio_desc { bool requested; };
struct dchid_iface {
 struct dockchannel_hid *dchid; const char *name; int index, out_report;
 int out_complete, ready, resp_lock; struct mutex out_mutex, gpio_lock;
 void *wq; const struct device_node *of_node;
 struct gpio_desc *gpio; unsigned gpio_id; char gpio_name[MAX_GPIO_NAME];
};
struct dockchannel_hid { struct device *dev; struct dchid_iface *ifaces[MAX_INTERFACES]; };
static struct device_node node;
static struct device dev={.of_node=&node};
static struct dockchannel_hid dchid={.dev=&dev};
static struct gpio_desc pin;
static struct dchid_iface *iface;
static unsigned lookups;
static int failure, first_failure;
static bool overlap, first_entered, second_entered, first_finished;
static _Thread_local int caller;
static pthread_mutex_t schedule=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed=PTHREAD_COND_INITIALIZER;
static struct timespec deadline(void) {
 struct timespec ts; assert(!clock_gettime(CLOCK_REALTIME,&ts)); ts.tv_sec+=3; return ts;
}
static void wait_flag(bool *flag) {
 struct timespec ts=deadline();
 while (!*flag) assert(!pthread_cond_timedwait(&changed,&schedule,&ts));
}
static void notify(bool *flag) { *flag=true; assert(!pthread_cond_broadcast(&changed)); }
static void mutex_init(struct mutex *m) {
 assert(!pthread_mutex_init(&m->raw,NULL)); m->initialized=true;
}
static void mutex_lock(struct mutex *m) {
 assert(m->initialized);
 if (overlap && caller==2 && m==&iface->gpio_lock) {
  assert(!pthread_mutex_lock(&schedule)); notify(&second_entered);
  assert(!pthread_mutex_unlock(&schedule));
 }
 struct timespec ts=deadline(); assert(!pthread_mutex_timedlock(&m->raw,&ts));
}
static void mutex_unlock(struct mutex *m) {
 assert(m->initialized && !pthread_mutex_unlock(&m->raw));
}
static void *devm_kzalloc(struct device *d, size_t n, unsigned flags) {
 assert(d==&dev && n==sizeof(*iface) && flags==GFP_KERNEL); return calloc(1,n);
}
static char *devm_kstrdup(struct device *d, const char *s, unsigned flags) {
 assert(d==&dev && flags==GFP_KERNEL); return strdup(s);
}
static void *alloc_ordered_workqueue(const char *fmt, unsigned flags, const char *name) {
 assert(!strcmp(fmt,"dchid-%s") && flags==WQ_MEM_RECLAIM && !strcmp(name,"multi-touch"));
 return &node;
}
static struct device_node *of_get_child_by_name(struct device_node *np, const char *name) {
 assert(np==&node && !strcmp(name,"multi-touch")); return &node;
}
static void destroy_workqueue(void *wq) { assert(wq==&node); }
static struct gpio_desc *devm_gpiod_get_index(struct device *d, const char *id,
 int index, int flags) {
 assert(d==&dev && !strcmp(id,"apple,afe-reset") && !index && flags==GPIOD_OUT_LOW);
 assert(!pthread_mutex_lock(&schedule)); lookups++;
 int err=overlap && caller==1 ? first_failure : failure;
 /* gpiolib claims the descriptor before returning it to the consumer. */
 if (!err && pin.requested) err=-EBUSY;
 if (!err) pin.requested=true;
 if (overlap && caller==1) {
  notify(&first_entered); wait_flag(&second_entered);
 } else if (overlap && caller==2) {
  notify(&second_entered);
  /* Let the first caller publish its pointer before returning -EBUSY. */
  wait_flag(&first_finished);
 }
 assert(!pthread_mutex_unlock(&schedule));
 return err==1 ? NULL : err ? (void *)(intptr_t)err : &pin;
}
'''

TESTS = r'''
static void setup(void) {
 lookups=0; failure=first_failure=0; pin.requested=false;
 overlap=first_entered=second_entered=first_finished=false; caller=0;
 iface=dchid_get_interface(&dchid,1,"multi-touch"); assert(iface);
 iface->gpio_id=7; strcpy(iface->gpio_name,"afe-reset");
}
static void cleanup(void) {
 if (iface->gpio_lock.initialized) assert(!pthread_mutex_destroy(&iface->gpio_lock.raw));
 assert(!pthread_mutex_destroy(&iface->out_mutex.raw));
 free((void *)iface->name); free(iface); dchid.ifaces[1]=NULL;
}
static void *request(void *arg) {
 caller=(int)(intptr_t)arg;
 int ret=dchid_request_gpio(iface);
 if (caller==1) {
  assert(!pthread_mutex_lock(&schedule)); notify(&first_finished);
  assert(!pthread_mutex_unlock(&schedule));
 }
 return (void *)(intptr_t)ret;
}
int main(void) {
 const int errors[]={-517,-EIO,-EBUSY,1};
 for (unsigned i=0;i<sizeof(errors)/sizeof(*errors);i++) {
  setup(); failure=errors[i];
  assert(dchid_request_gpio(iface)==-1 && !iface->gpio && !pin.requested);
  failure=0;
  assert(!dchid_request_gpio(iface) && iface->gpio==&pin && pin.requested && lookups==2);
  assert(!dchid_request_gpio(iface) && lookups==2 && iface->gpio==&pin);
  cleanup();
 }
 puts("PASS: acquisition errors release the lock; successful descriptors are cached");
 for (unsigned i=0;i<16;i++) {
  setup(); overlap=true; first_failure=(i&1) ? -EIO : 0;
  pthread_t first, second; void *a, *b;
  assert(!pthread_create(&first,NULL,request,(void *)1));
  assert(!pthread_mutex_lock(&schedule)); wait_flag(&first_entered);
  assert(!pthread_mutex_unlock(&schedule));
  assert(!pthread_create(&second,NULL,request,(void *)2));
  assert(!pthread_join(first,&a) && !pthread_join(second,&b));
  assert((intptr_t)a==(first_failure ? -1 : 0));
  assert(iface->gpio==&pin && pin.requested);
  assert(!b);
  assert(lookups==(first_failure ? 2U : 1U));
  cleanup();
 }
 puts("PASS: 16 forced overlaps retain one GPIO claim, including retry after the first lookup fails");
 return 0;
}
'''

root = helpers['temporary_build']()
try:
    host = root / 'test.c'
    host.write_text(STUB + functions + TESTS)
    exe = root / 'test'
    subprocess.run([*shlex.split(os.environ.get('CC', 'gcc')), '-std=gnu11', '-O1', '-g',
                    '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-UNDEBUG',
                    '-fno-pie', '-no-pie', '-pthread', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all',
                    str(host), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=20)
finally:
    subprocess.run(['trash-put', str(root)], check=True)
