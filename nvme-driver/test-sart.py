#!/usr/bin/env python3
"""Check actual SART encoding and slot ownership using a host register array."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
source = Path(os.environ.get('AZAHI_SART_SOURCE', HERE / 'sart.c')).read_text()


def section(start, end):
    offset = source.index(start)
    return source[offset:source.index(end, offset)]


functions = section('#define APPLE_SART_MAX_ENTRIES', 'static int apple_sart_probe(')
functions += section('static int sart_set_entry(', 'static void apple_sart_shutdown(')
stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t phys_addr_t;
#define __iomem
#define GENMASK(h,l) (((UINT64_C(1) << ((h)-(l)+1))-1) << (l))
#define FIELD_GET(mask,val) (((val)&(mask)) >> __builtin_ctzll(mask))
#define FIELD_PREP(mask,val) (((uint64_t)(val) << __builtin_ctzll(mask)) & (mask))
#define EXPORT_SYMBOL_GPL(...)
#define dev_dbg(...) ((void)0)
#define dev_warn(...) ((void)0)
struct apple_sart;
struct device { int unused; };
static u32 regs[128];
static unsigned writes;
static unsigned reg_index(const void *p) {
 uintptr_t off=(uintptr_t)p-(uintptr_t)regs;
 assert(!(off&3) && off<sizeof(regs));
 return off/4;
}
static u32 readl(const void *p) { return regs[reg_index(p)]; }
static void writel(u32 value, void *p) { regs[reg_index(p)]=value; writes++; }
static bool test_bit(unsigned bit, const unsigned long *p) { return (*p >> bit)&1; }
static bool test_and_set_bit(unsigned bit, unsigned long *p) {
 bool old=test_bit(bit,p); *p |= 1UL << bit; return old;
}
static void clear_bit(unsigned bit, unsigned long *p) { *p &= ~(1UL << bit); }
'''
tests = r'''
int main(void) {
 const struct apple_sart_ops *versions[]={&sart_ops_v0,&sart_ops_v2,&sart_ops_v3,&sart_ops_j714s};
 for (unsigned version=0;version<4;version++) {
  struct apple_sart sart={.regs=regs,.ops=versions[version]};
  memset(regs,0,sizeof(regs));
  for (unsigned bit=44;bit<64;bit++) {
   writes=0;
   assert(apple_sart_add_allowed_region(&sart,UINT64_C(1)<<bit,4096)==-EINVAL);
   assert(!writes && !sart.used_entries);
  }
  for (unsigned bit=0;bit<12;bit++) {
   writes=0;
   assert(apple_sart_add_allowed_region(&sart,(UINT64_C(1)<<40)|(1U<<bit),4096)==-EINVAL);
   assert(apple_sart_add_allowed_region(&sart,UINT64_C(1)<<40,4096|(1U<<bit))==-EINVAL);
   assert(!writes && !sart.used_entries);
  }
  writes=0;
  assert(apple_sart_add_allowed_region(&sart,UINT64_MAX&~UINT64_C(4095),4096)==-EINVAL);
  assert(apple_sart_add_allowed_region(&sart,0,(sart.ops->size_max+1)<<12)==-EINVAL);
  assert(!writes && !sart.used_entries);

  phys_addr_t max=(UINT64_C(1)<<44)-4096, address;
  size_t size; u8 flags;
  assert(apple_sart_add_allowed_region(&sart,max,4096)==0);
  sart.ops->get_entry(&sart,0,&flags,&address,&size);
  assert(flags==sart.ops->flags_allow && address==max && size==4096);
  assert(apple_sart_remove_allowed_region(&sart,max,4096)==0 && !sart.used_entries);
  assert(sart_set_entry(&sart,0,sart.ops->flags_allow,0,sart.ops->size_max<<12)==0);
  sart.ops->get_entry(&sart,0,&flags,&address,&size);
  assert(size==(sart.ops->size_max<<12));
  assert(sart_set_entry(&sart,0,0,0,0)==0);

  sart.protected_entries=(1UL<<0)|(1UL<<7)|(1UL<<15);
  for (unsigned i=0;i<16;i++)
   if (test_bit(i,&sart.protected_entries)) sart.ops->set_entry(&sart,i,0xf,0x100+i,2);
  u32 protected[128]; memcpy(protected,regs,sizeof(regs));
  for (unsigned i=0;i<16;i++) {
   if (test_bit(i,&sart.protected_entries)) continue;
   phys_addr_t p=(UINT64_C(1)<<40)+((phys_addr_t)(i+1)<<12);
   assert(apple_sart_add_allowed_region(&sart,p,4096)==0);
   sart.ops->get_entry(&sart,i,&flags,&address,&size);
   assert(address==p && size==4096 && flags==sart.ops->flags_allow);
  }
  assert(sart.used_entries==(0xffffUL ^ sart.protected_entries));
  writes=0;
  assert(apple_sart_add_allowed_region(&sart,UINT64_C(1)<<40,4096)==-EBUSY && !writes);
  for (unsigned i=0;i<16;i++) {
   if (test_bit(i,&sart.protected_entries)) {
    writes=0;
    assert(apple_sart_remove_allowed_region(&sart,(0x100ULL+i)<<12,8192)==-EINVAL);
    assert(!writes);
   } else {
    phys_addr_t p=(UINT64_C(1)<<40)+((phys_addr_t)(i+1)<<12);
    assert(apple_sart_remove_allowed_region(&sart,p,4096)==0);
    writes=0;
    assert(apple_sart_remove_allowed_region(&sart,p,4096)==-EINVAL && !writes);
   }
  }
  assert(!sart.used_entries && !memcmp(protected,regs,sizeof(regs)));
 }
 puts("PASS: v0/v2/v3/v4 address and size boundaries reject before writes and release reserved slots");
 puts("PASS: all unprotected slots round-trip; full tables, protected entries and untouched registers preserved");
 return 0;
}
'''
if not shutil.which('trash-put'):
    raise SystemExit('Install trash-cli: sudo apt-get install -y trash-cli')
root = Path(tempfile.mkdtemp(prefix='azahi-sart-test-'))
try:
    host = root / 'test.c'
    host.write_text(stub + functions + tests)
    cc = shlex.split(os.environ.get('CC', 'gcc'))
    subprocess.run([*cc, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-UNDEBUG', '-fno-pie', '-no-pie', '-fsanitize=address,undefined',
                    str(host), '-o', str(root / 'test')], check=True)
    subprocess.run([str(root / 'test')], check=True, timeout=30)
finally:
    subprocess.run(['trash-put', str(root)], check=True)
