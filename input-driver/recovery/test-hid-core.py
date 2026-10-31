#!/usr/bin/env python3
"""Run the actual HID-core wrapper with modeled device/open bookkeeping."""
from pathlib import Path
import subprocess
import tempfile
source = Path(__file__).with_name('input-recovery.c').read_text()
body = source[source.index('static int recovery_hw_open('):source.index('static struct klp_func funcs[]')]
stub = r'''

#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#define HID_TYPE_SPI_MOUSE 2
struct hid_device;
struct ll {int (*open)(struct hid_device *);};
struct driver {void (*on_hid_hw_open)(struct hid_device *);};
struct hid_device {int ll_open_lock;unsigned int ll_open_count;struct {void *parent;} dev;int type;struct ll *ll_driver;struct driver *driver;};
static int transport_storage, *transport=&transport_storage, old_calls,new_calls,callbacks,open_error,lock_error;
static int orig(struct hid_device *h){(void)h;old_calls++;return open_error;}
static int (*original_open)(struct hid_device *)=orig;
static int recovery_open(struct hid_device *h){(void)h;new_calls++;return open_error;}
static void cb(struct hid_device *h){(void)h;callbacks++;}
static int mutex_lock_killable(int *l){if(lock_error)return lock_error;assert(!*l);*l=1;return 0;}
static void mutex_unlock(int *l){assert(*l);*l=0;}
'''
tests = r'''
int main(void){
 struct ll ll={.open=orig};struct driver d={.on_hid_hw_open=cb};
 for(int match=0;match<2;match++)for(int err=0;err<2;err++)for(int count=0;count<3;count++){
  old_calls=new_calls=callbacks=0;open_error=err?-5:0;
  struct hid_device h={.ll_open_count=count,.dev.parent=match?transport:NULL,.type=2,.ll_driver=&ll,.driver=&d};
  int ret=recovery_hw_open(&h);
  assert(!h.ll_open_lock && ret==(count?0:open_error));
  assert(h.ll_open_count==(unsigned)(count+(count||!err)));
  assert(callbacks==!count && new_calls==(!count&&match) && old_calls==(!count&&!match));
 }
 lock_error=-4;struct hid_device h={0};assert(recovery_hw_open(&h)==-4);
 puts("PASS: HID core open locking/counts, existing clients, target-only dispatch, unrelated devices, callback and error behavior");
}
'''
with tempfile.TemporaryDirectory(prefix='azahi-hid-open-test-') as directory:
    c = Path(directory) / 'test.c'
    binary = Path(directory) / 'test'
    c.write_text(stub + body + tests)
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
