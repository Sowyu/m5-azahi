#!/usr/bin/env python3
"""Check firmware staging-copy lifetime using the actual lookup/upload/start C.

No firmware file or hardware is used. The synthetic DMA copies stay alive
through each test case, including failed commands and repeated attempts.
"""
import os
from pathlib import Path
import runpy
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent
helpers = runpy.run_path(str(ROOT / 'smp/test-smp-diag.py'))
extract = helpers['extract']
source = Path(os.environ.get('AZAHI_INPUT_SOURCE', ROOT / 'input-driver/dockchannel-hid.c')).read_text()
header = source[source.index('struct fw_header {'):source.index('} __packed;', source.index('struct fw_header {')) + len('} __packed;')]
functions = '\n'.join(extract(source, name) for name in (
    'static int dchid_send_firmware(', 'static int dchid_get_firmware(',
    'static int dchid_start_interface('))

STUB = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
typedef uint64_t dma_addr_t;
#define __packed __attribute__((packed))
#define FW_MAGIC 0x46444948
#define FW_VER 1
#define CMD_SEND_FIRMWARE 0x95
#define GFP_KERNEL 0
#define dev_warn(...) ((void)0)
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define wmb() ((void)0)
#define IS_ERR_OR_NULL(p) (!(p) || (uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
struct firmware { const u8 *data; size_t size; };
struct dockchannel_hid { void *dev; };
struct dchid_iface { bool starting; unsigned gpio_id, index; const char *name;
                    void *of_node; struct dockchannel_hid *dchid; };
static struct dockchannel_hid dchid;
static u8 image[84];
static struct firmware firmware={.data=image,.size=sizeof(image)};
static void *staging, *dma_buffers[64];
static unsigned duplicates, frees, releases, uploads, resets, dma_count;
static bool no_firmware, cpu_alloc_fails, dma_alloc_fails;
static int lookup_error, gpio_error, upload_error, reset_error;
static struct dchid_iface iface;
static int of_property_read_string(void *node, const char *key, const char **name) {
 (void)node; assert(!strcmp(key,"firmware-name")); *name="synthetic";
 return no_firmware ? -EINVAL : 0;
}
static int request_firmware(const struct firmware **fw, const char *name, void *dev) {
 assert(dev==&dchid && !strcmp(name,"synthetic"));
 if (lookup_error) return lookup_error;
 *fw=&firmware; return 0;
}
static void release_firmware(const struct firmware *fw) { assert(fw==&firmware); releases++; }
static void *devm_kmemdup(void *dev, const void *data, size_t size, unsigned flags) {
 (void)flags; assert(dev==&dchid && !staging && size==64 && data==image+20);
 if (cpu_alloc_fails) return NULL;
 staging=malloc(size); assert(staging); memcpy(staging,data,size); duplicates++; return staging;
}
static void devm_kfree(void *dev, const void *ptr) {
 assert(dev==&dchid);
 if (!ptr) return;
 assert(ptr==staging); free(staging); staging=NULL; frees++;
}
static void *dmam_alloc_coherent(void *dev, size_t size, dma_addr_t *addr, unsigned flags) {
 (void)flags; assert(dev==&dchid && size==64 && staging && dma_count<64);
 if (dma_alloc_fails) return NULL;
 void *p=malloc(size); assert(p); *addr=(uintptr_t)p; dma_buffers[dma_count++]=p; return p;
}
static void verify_dma(void) {
 for (unsigned b=0;b<dma_count;b++) {
  const u8 *p=dma_buffers[b];
  for (unsigned i=0;i<64;i++) assert(p[i]==(i==5 ? iface.index : (u8)(i+1)));
 }
}
static int dchid_comm_cmd(struct dockchannel_hid *d, void *cmd, size_t size) {
 assert(d==&dchid && size==16 && staging && dma_count);
 const u8 *p=cmd; u64 addr; u32 length;
 memcpy(&addr,p+4,sizeof(addr)); memcpy(&length,p+12,sizeof(length));
 assert(p[0]==CMD_SEND_FIRMWARE && p[1]==2 && !p[2] && p[3]==iface.index);
 assert(addr==(uintptr_t)dma_buffers[dma_count-1] && length==64);
 verify_dma(); uploads++; return upload_error ? upload_error : 1;
}
static int dchid_request_gpio(struct dchid_iface *i) { assert(i==&iface); return gpio_error; }
static int dchid_reset_interface(struct dchid_iface *i, int state) {
 assert(i==&iface && (state==0 || state==2)); resets++;
 verify_dma(); return reset_error==(int)resets ? -EIO : 1;
}
'''
TESTS = r'''
static void cleanup(void) {
 assert(!staging);
 for (unsigned i=0;i<dma_count;i++) free(dma_buffers[i]);
 dma_count=0;
}
static void setup(void) {
 cleanup();
 dchid.dev=&dchid;
 iface=(struct dchid_iface){.gpio_id=1,.index=7,.name="synthetic",.dchid=&dchid};
 struct fw_header hdr={FW_MAGIC,FW_VER,20,64,5}; memcpy(image,&hdr,sizeof(hdr));
 for (unsigned i=0;i<64;i++) image[20+i]=i+1;
 duplicates=frees=releases=uploads=resets=0;
 no_firmware=cpu_alloc_fails=dma_alloc_fails=false;
 lookup_error=gpio_error=upload_error=reset_error=0;
}
int main(void) {
 setup(); iface.starting=true;
 assert(dchid_start_interface(&iface)==-EINPROGRESS && !duplicates && !releases);
 setup(); no_firmware=true; iface.gpio_id=0;
 assert(!dchid_start_interface(&iface) && iface.starting && !duplicates && !releases);
 const int errors[]={-ENOENT,-EINVAL,-ENOMEM,1};
 for (unsigned i=0;i<4;i++) {
  setup(); lookup_error=errors[i];
  assert(dchid_start_interface(&iface)==errors[i]);
  assert(!iface.starting && !staging && !duplicates && !releases);
 }
 setup(); image[0]=0;
 assert(dchid_start_interface(&iface)==-EINVAL && releases==1 && !staging && !duplicates);
 setup(); cpu_alloc_fails=true;
 assert(dchid_start_interface(&iface)==-ENOMEM && releases==1 && !staging && !duplicates);
 puts("PASS: early exits and absent, invalid or unavailable firmware do not free an unowned pointer");
 for (unsigned failure=0;failure<6;failure++) {
  setup();
  if (failure==0) gpio_error=-EBUSY;
  if (failure==1) dma_alloc_fails=true;
  if (failure==2) upload_error=-ETIMEDOUT;
  if (failure==3) reset_error=1;
  if (failure==4) reset_error=2;
  int expected=failure==0 ? -EBUSY : failure==1 ? -ENOMEM :
               failure==2 ? -ETIMEDOUT : failure<5 ? -EIO : 0;
  assert(dchid_start_interface(&iface)==expected);
  assert(iface.starting==(expected==0));
  assert(duplicates==1 && frees==1 && !staging && releases==1);
  assert(dma_count==(failure<2 ? 0U : 1U));
  assert(uploads==(failure<2 ? 0U : 1U));
  assert(resets==(failure<=2 ? 0U : failure==3 ? 1U : 2U));
  verify_dma(); assert(image[25]==6); /* The firmware service's image was not modified. */
 }
 puts("PASS: GPIO/allocation/upload/power failures and success release exactly one staging copy");
 setup(); upload_error=-ETIMEDOUT;
 for (unsigned n=1;n<=32;n++) {
  assert(dchid_start_interface(&iface)==-ETIMEDOUT);
  assert(!iface.starting && !staging && duplicates==n && frees==n);
  assert(dma_count==n && uploads==n && !resets); verify_dma();
 }
 cleanup();
 puts("PASS: 32 failed uploads release CPU copies while all DMA buffers and bytes remain retained");
 return 0;
}
'''

root = helpers['temporary_build']()
try:
    host = root / 'test.c'
    host.write_text(STUB + header + functions + TESTS)
    cc = shlex.split(os.environ.get('CC', 'gcc'))
    exe = root / 'test'
    subprocess.run([*cc, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-function', '-UNDEBUG', '-fno-pie', '-no-pie',
                    '-fsanitize=address,undefined',
                    str(host), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=30)
finally:
    subprocess.run(['trash-put', str(root)], check=True)
