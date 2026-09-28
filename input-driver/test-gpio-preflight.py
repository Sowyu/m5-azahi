#!/usr/bin/env python3
"""Check the real probe and later GPIO lookup with synthetic firmware nodes.

The GPIO backend models the target kernel's consumer-name suffix lookup.
Probe stops at a missing MTP helper after the preflight, before transport I/O.
No GPIO controller, fw_devlink graph or pin voltage is emulated.
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
    'static int dchid_request_gpio(', 'static int dockchannel_hid_probe('))

STUB = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define EPROBE_DEFER 517
#define GFP_KERNEL 0
#define GPIOD_ASIS 0
#define GPIOD_OUT_LOW 1
#define WQ_MEM_RECLAIM 0
#define IFACE_COMM 0
#define MAX_GPIO_NAME 32
#define DL_FLAG_AUTOREMOVE_CONSUMER 1
#define DL_DEV_DRIVER_BOUND 1
#define DMA_BIT_MASK(n) UINT64_MAX
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define IS_ERR_OR_NULL(p) (!(p) || (uintptr_t)(p)>=(uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
struct gpio_desc { unsigned held; };
struct property { const char *name; int result; struct gpio_desc gpio; struct property *next; };
struct fwnode_handle { struct device_node *node; };
struct device_node { struct fwnode_handle fwnode; struct property *properties; struct device_node *child, *next; };
struct device { struct device_node *of_node; struct { int status; } links; };
struct platform_device { struct device dev; };
struct device_link { struct device *supplier; };
struct dockchannel_hid { struct device *dev; int tx_lock; struct device_link *helper_link;
                        void *dc, *new_iface_wq, *comm; };
struct dchid_iface { struct dockchannel_hid *dchid; const char *name; unsigned gpio_id;
                    char gpio_name[MAX_GPIO_NAME]; struct gpio_desc *gpio; };
struct dchid_hdr { unsigned char bytes[8]; };
#define for_each_property_of_node(np,p) for ((p)=(np)->properties;(p);(p)=(p)->next)
#define for_each_child_of_node(np,c) for ((c)=(np) ? (np)->child : NULL;(c);(c)=(c)->next)
#define dev_fwnode(d) (&(d)->of_node->fwnode)
static struct device_node parent, child;
static struct property props[12], child_prop;
static struct platform_device pdev;
static struct dockchannel_hid allocated;
static unsigned lookups, gpio_releases, helper_lookups, strings, allocations, fail_string, writes;
static int dma_error;
static bool fail_state;
static void *devm_kzalloc(struct device *d, size_t n, unsigned flags) {
 assert(d==&pdev.dev && n==sizeof(allocated) && flags==GFP_KERNEL);
 memset(&allocated,0,sizeof(allocated)); return fail_state ? NULL : &allocated;
}
static int dma_set_mask_and_coherent(struct device *d, uint64_t mask) {
 assert(d==&pdev.dev && mask==UINT64_MAX); return dma_error;
}
static void mutex_init(int *lock) { *lock=0; }
static char *kstrndup(const char *s, size_t n, unsigned flags) {
 assert(flags==GFP_KERNEL); allocations++;
 if (allocations==fail_string) return NULL;
 char *p=strndup(s,n); assert(p); strings++; return p;
}
static void kfree(void *p) { assert(p && strings); strings--; free(p); }
static struct gpio_desc *fwnode_gpiod_get_index(struct fwnode_handle *fwnode,
 const char *con_id, int index, int flags, const char *label) {
 assert(!index && label && (flags==GPIOD_ASIS || flags==GPIOD_OUT_LOW)); lookups++;
 const char *suffixes[]={"gpios","gpio"};
 for (unsigned s=0;s<2;s++) {
  char key[32]; snprintf(key,sizeof(key),"%s-%s",con_id,suffixes[s]);
  for (struct property *p=fwnode->node->properties;p;p=p->next) {
   if (strcmp(p->name,key)) continue;
   if (p->result==1) return NULL;
   if (p->result) return (void *)(intptr_t)p->result;
   assert(!p->gpio.held); p->gpio.held++;
   if (flags==GPIOD_OUT_LOW) writes++;
   return &p->gpio;
  }
 }
 return (void *)(intptr_t)-ENOENT;
}
static void gpiod_put(struct gpio_desc *gpio) {
 assert(gpio && gpio->held==1); gpio->held--; gpio_releases++;
}
static struct gpio_desc *devm_gpiod_get_index(struct device *dev, const char *id,
 int index, int flags) {
 assert(dev==&pdev.dev); return fwnode_gpiod_get_index(dev_fwnode(dev),id,index,flags,id);
}
static struct device_node *of_parse_phandle(struct device_node *np, const char *key, int i) {
 if (!np) return NULL;
 assert(np==&parent && !strcmp(key,"apple,helper-cpu") && !i && !strings);
 helper_lookups++; return NULL;
}
static void of_node_put(struct device_node *node) { assert(node==&child); }
/* These calls are beyond the intentionally absent helper and must not run. */
#define of_find_device_by_node(...) (assert(0), (struct platform_device *)NULL)
#define device_link_add(...) (assert(0), (struct device_link *)NULL)
#define put_device(...) assert(0)
#define dockchannel_init(...) (assert(0), (void *)NULL)
#define alloc_workqueue(...) (assert(0), (void *)NULL)
#define dchid_get_interface(...) (assert(0), (void *)NULL)
#define destroy_workqueue(...) assert(0)
#define dockchannel_await(...) assert(0)
'''

TESTS = r'''
static void setup(void) {
 assert(!strings);
 memset(props,0,sizeof(props)); memset(&child_prop,0,sizeof(child_prop));
 parent=(struct device_node){.fwnode={.node=&parent},.child=&child};
 child=(struct device_node){.fwnode={.node=&child},.properties=&child_prop};
 child_prop.name="apple,child-reset-gpios"; child_prop.result=-EPROBE_DEFER;
 pdev.dev.of_node=&parent;
 lookups=gpio_releases=helper_lookups=allocations=fail_string=writes=0;
 dma_error=0; fail_state=false;
}
static void property(unsigned i, const char *name, int result) {
 assert(i<12); props[i]=(struct property){.name=name,.result=result};
 if (i) props[i-1].next=&props[i]; else parent.properties=props;
}
static void check(int ret, unsigned queried, unsigned released, unsigned reached_helper) {
 assert(dockchannel_hid_probe(&pdev)==ret);
 assert(lookups==queried && gpio_releases==released && helper_lookups==reached_helper);
 assert(!strings && !writes);
 for (unsigned i=0;i<12;i++) assert(!props[i].gpio.held);
 assert(!child_prop.gpio.held);
}
int main(void) {
 setup(); dma_error=-ENODEV; check(-ENODEV,0,0,0);
 setup(); fail_state=true; check(-ENOMEM,0,0,0);
 setup(); pdev.dev.of_node=NULL; check(-EINVAL,0,0,0);
 setup(); check(-EINVAL,0,0,1);
 const char *ignored[]={"", "a", "apple,", "apple,reset", "reset-gpios", "other,reset-gpios", "apple,reset-gpios-extra"};
 for (unsigned i=0;i<sizeof(ignored)/sizeof(*ignored);i++) {
  setup(); property(0,ignored[i],-EPROBE_DEFER); check(-EINVAL,0,0,1);
 }
 puts("PASS: early failures and unrelated properties never acquire pins or inspect child GPIOs");
 setup(); property(0,"apple,afe-reset-gpios",-EPROBE_DEFER); check(-EPROBE_DEFER,1,0,0);
 /* A subsequent probe can proceed after the parent provider appears. */
 props[0].result=0; lookups=0; check(-EINVAL,1,1,1);
 setup(); property(0,"apple,afe-reset-gpios",0); property(1,"apple,aux-reset-gpios",-EPROBE_DEFER);
 check(-EPROBE_DEFER,2,1,0);
 const int errors[]={-ENOENT,-ENODEV,-EINVAL,-EBUSY,1};
 for (unsigned i=0;i<sizeof(errors)/sizeof(*errors);i++) {
  setup(); property(0,"apple,afe-reset-gpios",errors[i]); check(-EINVAL,1,0,1);
 }
 setup(); property(0,"apple,afe-reset-gpios",0); fail_string=1; check(-ENOMEM,0,0,0);
 setup(); property(0,"apple,afe-reset-gpios",0); property(1,"apple,aux-reset-gpios",0);
 fail_string=2; check(-ENOMEM,1,1,0);
 puts("PASS: parent-provider deferral and allocation failures release temporary names and GPIOs");
 setup(); property(0,"apple,afe-reset-gpios",0); check(-EINVAL,1,1,1);
 struct dchid_iface iface={.dchid=&allocated,.name="multi-touch",.gpio_id=7,.gpio_name="afe-reset"};
 assert(!dchid_request_gpio(&iface)); assert(iface.gpio==&props[0].gpio);
 assert(lookups==2 && writes==1 && props[0].gpio.held==1);
 assert(!dchid_request_gpio(&iface) && lookups==2 && writes==1);
 gpiod_put(iface.gpio); assert(!props[0].gpio.held && !strings);
 puts("PASS: preflight and later firmware request find the same parent GPIO; preflight uses ASIS");
 return 0;
}
'''

root = helpers['temporary_build']()
try:
    host = root / 'test.c'
    host.write_text(STUB + functions + TESTS)
    cc = shlex.split(os.environ.get('CC', 'gcc'))
    exe = root / 'test'
    subprocess.run([*cc, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-function', '-UNDEBUG', '-fno-pie', '-no-pie',
                    '-fsanitize=address,undefined', str(host), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=30)
finally:
    subprocess.run(['trash-put', str(root)], check=True)
