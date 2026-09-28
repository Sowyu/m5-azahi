#!/usr/bin/env python3
"""Test the optional SMC timeout quarantine, without firmware or MMIO."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-tree', required=True, type=Path)
args = parser.parse_args()
pins = {
    'drivers/mfd/macsmc.c': '6a8004c39af84de5757ffac8453b3d9822a3e590ff6ac3bf7b1415f52373af0a',
    'include/linux/mfd/macsmc.h': '2d9a64e924e1aa5cf5d75db9f1570be3c7178aaf955a22121ff8f15b929eaa54',
}
inputs = {name: (args.source_tree / name).read_bytes() for name in pins}
if any(hashlib.sha256(inputs[name]).hexdigest() != digest for name, digest in pins.items()):
    parser.error('Wrong pinned SMC source or header checksum')
if not shutil.which('trash-put'):
    parser.error('Install trash-cli: sudo apt-get install -y trash-cli')

STUB = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
typedef u32 smc_key;
#define SMC_ENDPOINT 0x20
#define SMC_SHMEM_SIZE 4096
#define SMC_MAX_SIZE 255
#define SMC_TIMEOUT_MS 500
#define SMC_MSG_READ_KEY 0x10
#define SMC_MSG_WRITE_KEY 0x11
#define SMC_MSG_GET_KEY_BY_INDEX 0x12
#define SMC_MSG_GET_KEY_INFO 0x13
#define SMC_MSG_NOTIFICATION 0x18
#define SMC_MSG_RW_KEY 0x20
#define SMC_DATA UINT64_C(0xffffffff00000000)
#define SMC_WSIZE UINT64_C(0xff000000)
#define SMC_SIZE UINT64_C(0x00ff0000)
#define SMC_ID UINT64_C(0x0000f000)
#define SMC_MSG UINT64_C(0xff)
#define SMC_RESULT SMC_MSG
#define SMC_KEY(s) ((smc_key)0x4e544150)
#define FIELD_PREP(m,v) (((u64)(v) << __builtin_ctzll(m)) & (m))
#define FIELD_GET(m,v) (((u64)(v) & (m)) >> __builtin_ctzll(m))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define EXPORT_SYMBOL(x)
#define IS_ALIGNED(v,n) (((v) & ((n)-1)) == 0)
#define swab32(v) __builtin_bswap32(v)
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_warn_ratelimited(...) ((void)0)
#define msecs_to_jiffies(v) (v)
struct apple_rtkit_shmem { u64 iova; size_t size; void *iomem; };
struct apple_smc {
 int mutex, lock, boot_stage;
 unsigned cmd_done, init_done, msg_id;
 bool atomic_mode, atomic_pending;
 u64 cmd_ret;
 void *rtk, *dev;
 struct apple_rtkit_shmem shmem;
};
struct apple_smc_key_info { u8 size; u32 type_code; u8 flags; };
static bool sram32;
static unsigned sends, waits, copies, polls;
static u8 sram[SMC_SHMEM_SIZE];
static struct apple_smc *active;
static u64 sent;
enum scenario { SUCCESS, TIMEOUT, SEND_ERROR, REPLY_ERROR, WRONG_ID, TIMEOUT_BOUNDARY };
static enum scenario scenario;
static bool apple_smc_rtkit_recv_early(void *, u8, u64);
static int *take_lock(int *p) { assert(!*p); *p=1; return p; }
static void release_lock(int **p) { assert(**p); **p=0; }
#define guard(kind) int *held __attribute__((cleanup(release_lock),unused)) = take_lock
#define lockdep_assert_held(p) assert(*(p))
static void reinit_completion(unsigned *p) { *p=0; }
static void complete(unsigned *p) { (*p)++; }
static void apple_smc_copy_toio(void *dst, const void *src, size_t n) {
 assert(dst==sram && n<=SMC_MAX_SIZE); copies++; memcpy(dst,src,n);
}
static void apple_smc_copy_fromio(void *dst, const void *src, size_t n) {
 assert(src==sram && n<=SMC_MAX_SIZE); copies++; memcpy(dst,src,n);
}
static u32 get_unaligned_be32(const u8 *p) {
 return (u32)p[0]<<24 | (u32)p[1]<<16 | (u32)p[2]<<8 | p[3];
}
static int apple_rtkit_send_message(void *rtk, u8 ep, u64 msg, void *unused, bool atomic) {
 assert(ep==SMC_ENDPOINT && !unused);
 assert(atomic ? active->lock : active->mutex);
 sends++; sent=msg;
 return scenario==SEND_ERROR ? -EIO : 0;
}
static u64 reply_message(void) {
 unsigned id=FIELD_GET(SMC_ID,sent);
 unsigned size=FIELD_GET(SMC_MSG,sent)==SMC_MSG_WRITE_KEY ? 0 : FIELD_GET(SMC_SIZE,sent);
 if(scenario==WRONG_ID)id=(id+1)&15;
 return FIELD_PREP(SMC_ID,id)|FIELD_PREP(SMC_SIZE,size)|
        FIELD_PREP(SMC_DATA,0x12345678)|(scenario==REPLY_ERROR ? 1 : 0);
}
static unsigned wait_for_completion_timeout(unsigned *p, unsigned timeout) {
 assert(p==&active->cmd_done && timeout==SMC_TIMEOUT_MS); waits++;
 if(scenario!=TIMEOUT)apple_smc_rtkit_recv_early(active,SMC_ENDPOINT,reply_message());
 if(scenario==TIMEOUT_BOUNDARY)return 0;
 if(*p) { (*p)--; return 1; }
 return 0;
}
static int apple_rtkit_poll(void *rtk) {
 polls++;assert(polls<=SMC_TIMEOUT_MS*10+1);
 if(scenario!=TIMEOUT)apple_smc_rtkit_recv_early(active,SMC_ENDPOINT,reply_message());
 return 0;
}
static void udelay(unsigned us) { assert(us==100); }
static int apple_smc_rtkit_shmem_setup(struct apple_smc *smc, struct apple_rtkit_shmem *buf) {
 assert(0 && "No probe or hardware setup expected");return -EIO;
}
'''

TESTS = r'''
static struct apple_smc reset(void) {
 sends=waits=copies=polls=0;memset(sram,0xa5,sizeof(sram));
 return (struct apple_smc){.boot_stage=APPLE_SMC_INITIALIZED,.shmem={.iomem=sram}};
}
static void refusals(struct apple_smc *s) {
 u8 data[8],out[8];memset(data,0x72,sizeof(data));memset(out,0xc7,sizeof(out));
 u8 saved[sizeof(sram)];memcpy(saved,sram,sizeof(sram));
 struct apple_smc_key_info info={.size=0xee};smc_key key=0x12345678;
 unsigned old_sends=sends,old_copies=copies,old_id=s->msg_id;
 assert(apple_smc_write(s,0,data,sizeof(data))==-EIO);
 assert(apple_smc_read(s,0,out,sizeof(out))==-EIO);
 assert(apple_smc_rw(s,0,data,sizeof(data),out,sizeof(out))==-EIO);
 assert(apple_smc_get_key_by_index(s,0,&key)==-EIO && key==0x12345678);
 assert(apple_smc_get_key_info(s,0,&info)==-EIO && info.size==0xee);
 assert(sends==old_sends && copies==old_copies && s->msg_id==old_id);
 assert(!memcmp(sram,saved,sizeof(sram)) && !s->mutex && !s->lock);
 for(unsigned i=0;i<sizeof(out);i++)assert(out[i]==0xc7);
}
int main(void) {
 /* 16 message IDs, three timeout timings, and all normal command entry points. */
 for(unsigned id=0;id<16;id++)for(unsigned timing=0;timing<3;timing++) {
  struct apple_smc s=reset();active=&s;s.msg_id=id;
  u8 data[8];memset(data,0x11,sizeof(data));
  scenario=timing==2 ? TIMEOUT_BOUNDARY : TIMEOUT;
  assert(apple_smc_write(&s,0,data,sizeof(data))==-ETIMEDOUT && sends==1);
  if(timing==1)apple_smc_rtkit_recv_early(&s,SMC_ENDPOINT,reply_message());
  refusals(&s);
  /* Even a matching late success is not a cancellation or recovery protocol. */
  scenario=SUCCESS;
  apple_smc_rtkit_recv_early(&s,SMC_ENDPOINT,reply_message());
  for(unsigned retry=0;retry<16;retry++)refusals(&s);
  unsigned old_sends=sends,old_copies=copies;
  assert(apple_smc_enter_atomic(&s)==0);
  assert(apple_smc_write_atomic(&s,0,data,sizeof(data))==-EIO);
  assert(sends==old_sends && copies==old_copies && !s.lock && !s.mutex);
 }
 puts("PASS: 48 timeout states preserve SRAM and outputs; late replies and shutdown cannot reuse it");
 for(unsigned mode=0;mode<4;mode++) {
  struct apple_smc s=reset();active=&s;
  u8 out[4]={0};scenario=mode==0 ? SUCCESS : mode==1 ? SEND_ERROR : mode==2 ? REPLY_ERROR : WRONG_ID;
  int expected=mode==0 ? 4 : mode==3 ? -ETIMEDOUT : -EIO;
  assert(apple_smc_read(&s,0,out,sizeof(out))==expected);
  if(mode==3) { refusals(&s);continue; }
  assert(s.boot_stage==APPLE_SMC_INITIALIZED);
  scenario=SUCCESS;
  assert(apple_smc_read(&s,0,out,sizeof(out))==4 && sends==2);
  u32 value;memcpy(&value,out,sizeof(value));assert(value==0x12345678);
 }
 puts("PASS: successful and explicit error replies remain usable; mismatched reply leads to quarantine");
 return 0;
}
'''


def section(source, start, end):
    offset = source.index(start)
    return source[offset:source.index(end, offset)]


root = Path(tempfile.mkdtemp(prefix='azahi-smc-timeout-'))
try:
    for name, data in inputs.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for patch in ('sram32.patch', 'timeout-quarantine.patch'):
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(root), '-i',
                        str(Path(__file__).with_name(patch).resolve())], check=True,
                       capture_output=True)
        if patch == 'sram32.patch':
            previous = (root / 'drivers/mfd/macsmc.c').read_text()
    source = (root / 'drivers/mfd/macsmc.c').read_text()
    header = (root / 'include/linux/mfd/macsmc.h').read_text()
    stages = section(header, 'enum apple_smc_boot_stage {', '\n/**')
    timeout = '\t\tWRITE_ONCE(smc->boot_stage, APPLE_SMC_ERROR_TIMED_OUT);\n'
    state_guard = '\tif (smc->boot_stage != APPLE_SMC_INITIALIZED || smc->atomic_mode)\n\t\treturn -EIO;\n'
    assert source.count(timeout) == source.count(state_guard) == 1
    atomic = section(source, 'int apple_smc_write_atomic(', '\nEXPORT_SYMBOL(apple_smc_write_atomic)')
    atomic_guard = '\tif (smc->boot_stage != APPLE_SMC_INITIALIZED)\n\t\treturn -EIO;\n'
    variants = {
        'candidate': source,
        'previous': previous,
        'no-quarantine': source.replace(timeout, ''),
        'late-reply-recovery': source.replace('\t\tsmc->cmd_ret = message;',
            '\t\tsmc->boot_stage = APPLE_SMC_INITIALIZED;\n\t\tsmc->cmd_ret = message;'),
        'staging-before-check': source.replace(state_guard, ''),
        'atomic-ignores-state': source.replace(atomic, atomic.replace(atomic_guard, '')),
    }
    for name, text in variants.items():
        functions = section(text, 'static int apple_smc_cmd_locked(', '\nstatic void apple_smc_rtkit_crashed(')
        functions += section(text, 'static bool apple_smc_rtkit_recv_early(', '\nstatic void apple_smc_rtkit_recv(')
        host, binary = root / (name + '.c'), root / name
        host.write_text(STUB + stages + functions + TESTS)
        subprocess.run(shlex.split(os.environ.get('CC', 'gcc')) + [
            '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
            '-Wno-sign-compare', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
            '-g', '-no-pie', str(host), '-o', str(binary)], check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
        if name == 'candidate':
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            print(result.stdout, end='')
        elif not result.returncode or 'Assertion' not in result.stderr:
            raise RuntimeError('Regression did not fail: ' + name)
    print('PASS: previous timeout behavior and four mutations detected')
finally:
    subprocess.run(['trash-put', str(root)], check=True)
