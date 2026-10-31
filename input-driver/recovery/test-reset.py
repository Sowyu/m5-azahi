#!/usr/bin/env python3
"""Check the real reset helper's edge/error/descriptor lifetime behavior."""
from pathlib import Path
import subprocess
import tempfile
source = Path(__file__).with_name('input-recovery.c').read_text()
body = source[source.index('static int prepare_retry('):source.index('#include "recovery-open.h"')]
stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
struct gpio_desc {int unused;};
static struct gpio_desc pin;
static bool afe_reset;
static int transport_store, *transport=&transport_store;
static int fault, gpio_gets,puts_count,reads,asserts,releases,delays;
#define GPIOD_ASIS 0
#define IS_ERR(p) ((p)==(void *)-1)
#define PTR_ERR(p) (-EIO)
#define pr_info(...) ((void)0)
static struct gpio_desc *gpiod_get_index(int *d,const char *n,int i,int f) {
 assert(d==transport && !strcmp(n,"apple,afe-reset") && !i && f==GPIOD_ASIS);
 gpio_gets++;return fault==1?(void *)-1:&pin;
}
static int gpiod_get_value_cansleep(struct gpio_desc *g) {
 assert(g==&pin);reads++;return fault==2?-EIO:0;
}
static int gpiod_direction_output(struct gpio_desc *g,int v) {
 assert(g==&pin && v==1);asserts++;return fault==3?-EIO:0;
}
static int gpiod_set_value_cansleep(struct gpio_desc *g,int v) {
 assert(g==&pin && v==0 && delays==1);releases++;return fault==4?-EIO:0;
}
static void msleep(unsigned int ms) {assert(ms==50);delays++;}
static void gpiod_put(struct gpio_desc *g) {assert(g==&pin);puts_count++;}
'''
tests = r'''
int main(void) {
 assert(!prepare_retry() && !gpio_gets);
 afe_reset=true;
 for(fault=0;fault<=4;fault++) {
  gpio_gets=puts_count=reads=asserts=releases=delays=0;
  assert(prepare_retry()==(fault?-EIO:0));
  assert(gpio_gets==1 && puts_count==(fault!=1));
  assert(reads==(fault!=1));
  assert(asserts==(fault!=1 && fault!=2));
  assert(releases==asserts); /* Release is attempted even if assertion fails. */
  assert(delays==(fault==0?2:(fault>=3?1:0)));
 }
 puts("PASS: actual AFE reset helper, default off, descriptor lifetime, 50ms edges/settle, read/assert/release failures");
}
'''
with tempfile.TemporaryDirectory(prefix='azahi-reset-test-') as directory:
    c = Path(directory) / 'test.c'
    binary = Path(directory) / 'test'
    c.write_text(stub + body + tests)
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
