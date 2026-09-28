#!/usr/bin/env python3
"""Apply the pinned SMC patch and exercise its actual C functions without devices."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

BASE_SHA = '6a8004c39af84de5757ffac8453b3d9822a3e590ff6ac3bf7b1415f52373af0a'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path, help='Pinned kernel drivers/mfd/macsmc.c')
args = parser.parse_args()
base = args.source.read_bytes()
if hashlib.sha256(base).hexdigest() != BASE_SHA:
    parser.error('Wrong macsmc.c checksum')
if not shutil.which('trash-put'):
    parser.error('Install trash-cli: sudo apt-get install -y trash-cli')
root = Path(tempfile.mkdtemp(prefix='azahi-smc-test-'))
try:
    source_path = root / 'drivers/mfd/macsmc.c'
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(base)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(root), '-i',
                    str(Path(__file__).with_name('sram32.patch').resolve())], check=True)
    source = source_path.read_text()

    def section(start, end):
        return source[source.index(start):source.index(end, source.index(start))]

    functions = section('static bool sram32;', 'static const struct mfd_cell')
    functions += section('static int apple_smc_rw_locked(', '\nint apple_smc_read(')
    functions += section('int apple_smc_get_key_by_index(', '\nEXPORT_SYMBOL(apple_smc_get_key_by_index)')
    functions += section('int apple_smc_get_key_info(', '\nEXPORT_SYMBOL(apple_smc_get_key_info)')
    functions += section('int apple_smc_write_atomic(', '\nEXPORT_SYMBOL(apple_smc_write_atomic)')
    functions += section('static bool apple_smc_rtkit_recv_early(', '\nstatic void apple_smc_rtkit_recv(')
    # Exercise the exact probe prefix before its first allocation or hardware call.
    prefix = section('static int apple_smc_probe(', '\tsmc = devm_kzalloc(')
    functions += prefix + '\treturn 123;\n}\n'
    stub = r'''
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
#define __iomem
#define module_param(name, type, mode) _Static_assert(mode == 0444, "option must be read-only")
#define MODULE_PARM_DESC(...)
#define min_t(t, a, b) ((t)(a) < (t)(b) ? (t)(a) : (t)(b))
#define IS_ALIGNED(a, n) (((a) & ((n) - 1)) == 0)
#define SMC_MAX_SIZE 255
#define SMC_SHMEM_SIZE 4096
#define SMC_ENDPOINT 0x20
#define SMC_TIMEOUT_MS 500
#define SMC_MSG_READ_KEY 0x10
#define SMC_MSG_WRITE_KEY 0x11
#define SMC_MSG_RW_KEY 0x20
#define SMC_MSG_GET_KEY_INFO 0x13
#define SMC_MSG_GET_KEY_BY_INDEX 0x12
#define SMC_MSG_NOTIFICATION 0x18
#define SMC_DATA UINT64_C(0xffffffff00000000)
#define SMC_SIZE UINT64_C(0x00ff0000)
#define SMC_ID UINT64_C(0x0000f000)
#define SMC_MSG UINT64_C(0xff)
#define SMC_RESULT SMC_MSG
#define FIELD_PREP(m, v) (((u64)(v) << __builtin_ctzll(m)) & (m))
#define FIELD_GET(m, v) (((u64)(v) & (m)) >> __builtin_ctzll(m))
#define READ_ONCE(x) (x)
#define APPLE_SMC_BOOTING 0
#define APPLE_SMC_INITIALIZED 1
#define APPLE_SMC_ERROR_NO_SHMEM 2
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_warn_ratelimited(...) ((void)0)
#define dev_err_probe(d, err, ...) (err)
static unsigned delays;
static void udelay(unsigned us) { assert(us==100); delays++; }
#define swab32(v) __builtin_bswap32(v)
struct device { int unused; };
struct platform_device { struct device dev; };
struct apple_rtkit_shmem { u64 iova; size_t size; void *iomem; };
struct apple_smc {
 int mutex, lock, boot_stage, init_done, cmd_done;
 bool atomic_mode, atomic_pending;
 unsigned msg_id;
 u64 cmd_ret;
 void *rtk, *dev;
 struct apple_rtkit_shmem shmem;
};
struct apple_smc_key_info { u8 size; u32 type_code; u8 flags; };
static _Alignas(8) u8 sram[4096];
static size_t reads32, writes32, old_reads, old_writes, next_offset;
static bool poison_on_unlock;
static void lock(int *m) { assert(!*m); *m=1; }
static void unlock(int **m) {
 assert(**m); **m=0;
 if (poison_on_unlock) memset(sram, 0xdd, sizeof(sram));
}
#define guard(kind) int *locked_guard __attribute__((cleanup(unlock), unused)) = take_lock
static int *take_lock(int *m) { lock(m); return m; }
#define lockdep_assert_held(m) assert(*(m))
static void check_address(const void *p) {
 assert((uintptr_t)p % 4 == 0);
 assert((const u8 *)p == sram + next_offset);
 assert(next_offset + 4 <= sizeof(sram));
 next_offset += 4;
}
static u32 __raw_readl(const void *p) {
 u32 word; check_address(p); reads32++; memcpy(&word,p,4); return word;
}
static void __raw_writel(u32 word, void *p) {
 check_address(p); writes32++; memcpy(p,&word,4);
}
static void memcpy_fromio(void *dst, const void *src, size_t n) {
 old_reads++; memcpy(dst,src,n);
}
static void memcpy_toio(void *dst, const void *src, size_t n) {
 old_writes++; memcpy(dst,src,n);
}
static u32 get_unaligned_be32(const u8 *p) {
 return (u32)p[0]<<24 | (u32)p[1]<<16 | (u32)p[2]<<8 | p[3];
}
static int reply, command_calls;
static u32 inline_reply=0x44332211;
static u64 last_cmd, last_size, last_wsize;
static int apple_smc_cmd_locked(struct apple_smc *smc, u64 cmd, u64 key,
                               u64 size, u64 wsize, u32 *data) {
 assert(smc->mutex); command_calls++; last_cmd=cmd; last_size=size; last_wsize=wsize;
 if (data) *data=inline_reply;
 next_offset=0;
 return reply;
}
static int apple_smc_cmd(struct apple_smc *smc, u64 cmd, u64 key,
                        u64 size, u64 wsize, u32 *data) {
 assert(cmd==SMC_MSG_GET_KEY_BY_INDEX && !size && !wsize);
 command_calls++;
 if (reply>=0) *data=inline_reply;
 return reply;
}
static int setup_calls, setup_ret, board, send_ret, poll_ret, sends, polls;
static unsigned reply_after=1;
static struct apple_smc *atomic_smc;
static int apple_rtkit_send_message(void *rtk, u8 ep, u64 message, void *unused, bool atomic) {
 assert(ep==SMC_ENDPOINT && atomic && atomic_smc->lock);
 sends++; last_cmd=FIELD_GET(SMC_MSG,message); last_size=FIELD_GET(SMC_SIZE,message);
 return send_ret;
}
static int apple_rtkit_poll(void *rtk) {
 polls++;
 assert(polls<=SMC_TIMEOUT_MS*10+1); /* Detect the original endless wait without hanging the test. */
 if (poll_ret < 0) return poll_ret;
 if (!reply_after || polls<reply_after) return 0;
 atomic_smc->cmd_ret=FIELD_PREP(SMC_ID,atomic_smc->msg_id);
 atomic_smc->atomic_pending=false;
 return 0;
}
static int apple_smc_rtkit_shmem_setup(struct apple_smc *s, struct apple_rtkit_shmem *b) {
 setup_calls++; b->iomem=sram; return setup_ret;
}
static bool of_machine_is_compatible(const char *s) {
 assert(!strcmp(s,"apple,j714s")); return board;
}
static void complete(int *c) { (*c)++; }
'''
    tests = r'''
static void reset_counts(void) {
 reads32=writes32=old_reads=old_writes=next_offset=0;
 command_calls=0;
}
static void copy_checks(void) {
 assert(!sram32);
 for (unsigned mode=0; mode<2; mode++) {
  sram32=mode;
  for (unsigned n=0; n<=255; n++) {
   for (unsigned offset=0; offset<8; offset++) {
    u8 input[272], output[272];
    for (unsigned i=0;i<sizeof(input);i++) input[i]=(i*37+11)&255;
    memset(output,0xa5,sizeof(output)); memset(sram,0xc7,sizeof(sram)); reset_counts();
    apple_smc_copy_toio(sram,input+offset,n);
    assert(!memcmp(sram,input+offset,n));
    unsigned touched=mode ? (n+3)/4*4 : n;
    for (unsigned i=n;i<touched;i++) assert(sram[i]==0);
    for (unsigned i=touched;i<sizeof(sram);i++) assert(sram[i]==0xc7);
    assert(writes32==(mode?(n+3)/4:0) && old_writes==!mode);
    next_offset=0;
    apple_smc_copy_fromio(output+offset,sram,n);
    assert(!memcmp(output+offset,input+offset,n));
    for (unsigned i=0;i<offset;i++) assert(output[i]==0xa5);
    for (unsigned i=offset+n;i<sizeof(output);i++) assert(output[i]==0xa5);
    assert(reads32==(mode?(n+3)/4:0) && old_reads==!mode);
   }
  }
 }
 puts("PASS: lengths 0..255, eight RAM alignments, 32-bit MMIO only, padded write tails, unchanged default");
}
static void reply_checks(void) {
 struct apple_smc s={.mutex=1,.boot_stage=APPLE_SMC_INITIALIZED,.shmem={.iomem=sram}};
 u8 out[257], in[257];
 memset(in,0x72,sizeof(in));
 for (unsigned mode=0;mode<2;mode++) {
  sram32=mode;
  for (unsigned capacity=1;capacity<=255;capacity++) {
   for (reply=0;reply<=255;reply++) {
    memset(sram,0x68,sizeof(sram)); memset(out,0xa5,sizeof(out)); reset_counts();
    int ret=apple_smc_rw_locked(&s,0,NULL,0,out+1,capacity);
    assert(command_calls==1 && last_cmd==SMC_MSG_READ_KEY && last_size==capacity && !last_wsize);
    unsigned copied=reply<=capacity ? reply : 0;
    assert(ret==(reply<=capacity?reply:-EPROTO));
    if (copied<=4) assert(!memcmp(out+1,&inline_reply,copied));
    else for (unsigned i=1;i<=copied;i++) assert(out[i]==0x68);
    assert(out[0]==0xa5);
    for (unsigned i=copied+1;i<sizeof(out);i++) assert(out[i]==0xa5);
    assert(reads32==(mode&&copied>4?(copied+3)/4:0));
    assert(old_reads==(!mode&&copied>4));
   }
  }
 }
 sram32=true;
 for (unsigned n=1;n<=255;n++) {
  memset(sram,0,sizeof(sram)); reset_counts(); reply=0;
  assert(apple_smc_rw_locked(&s,0,in,n,NULL,0)==0);
  assert(last_cmd==SMC_MSG_WRITE_KEY && last_size==n && !last_wsize);
  assert(writes32==(n+3)/4 && !memcmp(sram,in,n));
  reset_counts(); reply=4;
  assert(apple_smc_rw_locked(&s,0,in,n,out,4)==4);
  assert(last_cmd==SMC_MSG_RW_KEY && last_size==4 && last_wsize==n);
  assert(writes32==(n+3)/4 && !reads32 && !memcmp(out,&inline_reply,4));
 }
 reset_counts(); reply=-ETIMEDOUT; memset(out,0xa5,sizeof(out));
 assert(apple_smc_rw_locked(&s,0,NULL,0,out,8)==-ETIMEDOUT && !reads32);
 assert(out[0]==0xa5);
 reset_counts();
 assert(apple_smc_rw_locked(&s,0,NULL,0,out,256)==-EINVAL);
 assert(apple_smc_rw_locked(&s,0,in,256,NULL,0)==-EINVAL);
 assert(apple_smc_rw_locked(&s,0,NULL,0,NULL,0)==-EINVAL && !command_calls && !writes32);
 for (unsigned state=0;state<3;state++) {
  s.boot_stage=state;
  for (unsigned atomic=0;atomic<2;atomic++) {
   if (state==APPLE_SMC_INITIALIZED && !atomic) continue;
   s.atomic_mode=atomic; reset_counts(); memset(sram,0xa7,sizeof(sram));
   assert(apple_smc_rw_locked(&s,0,in,8,NULL,0)==-EIO);
   assert(apple_smc_rw_locked(&s,0,in,8,out,8)==-EIO);
   assert(apple_smc_rw_locked(&s,0,NULL,0,out,8)==-EIO);
   assert(!command_calls && !reads32 && !writes32 && !old_reads && !old_writes);
   for (unsigned i=0;i<sizeof(sram);i++) assert(sram[i]==0xa7);
  }
 }
 puts("PASS: all 255 capacities x 256 reply lengths, oversized/error/state refusals before MMIO, normal/RW writes");
}
static void metadata_checks(void) {
 struct apple_smc s={.shmem={.iomem=sram}};
 struct apple_smc_key_info info;
 const u8 data[]={8,'u','i','6','4',0x80};
 sram32=true; reply=0; reset_counts(); memcpy(sram,data,sizeof(data));
 poison_on_unlock=true;
 assert(apple_smc_get_key_info(&s,0,&info)==0);
 assert(info.size==8 && info.type_code==0x75693634 && info.flags==0x80);
 assert(reads32==2 && !s.mutex && sram[0]==0xdd);
 poison_on_unlock=false;
 reset_counts(); assert(apple_smc_get_key_info(&s,0,NULL)==0 && !reads32 && !s.mutex);
 reply=-EIO; info.size=0xfe; reset_counts();
 assert(apple_smc_get_key_info(&s,0,&info)==-EIO && !reads32 && info.size==0xfe && !s.mutex);
 smc_key key=0x10203040;
 reset_counts(); reply=-ETIMEDOUT;
 assert(apple_smc_get_key_by_index(&s,0,&key)==-ETIMEDOUT && key==0x10203040);
 assert(command_calls==1 && !reads32 && !writes32);
 reply=0;
 assert(apple_smc_get_key_by_index(&s,0,&key)==0 && key==swab32(inline_reply));
 puts("PASS: metadata locked through copy, nullable result, failed key lookup leaves output untouched");
}
static void atomic_checks(void) {
 struct apple_smc s={.atomic_mode=true,.boot_stage=APPLE_SMC_INITIALIZED,.shmem={.iomem=sram}};
 u8 data[256]; memset(data,0x3c,sizeof(data)); atomic_smc=&s; sram32=true;
 for (unsigned n=1;n<=255;n++) {
  reset_counts(); sends=polls=0;
  assert(apple_smc_write_atomic(&s,0,data+1,n)==0);
  assert(writes32==(n+3)/4 && !memcmp(sram,data+1,n));
  assert(sends==1 && polls==1 && !s.lock && !s.atomic_pending);
  assert(last_cmd==SMC_MSG_WRITE_KEY && last_size==n);
 }
 reset_counts(); sends=0;
 assert(apple_smc_write_atomic(&s,0,data,0)==-EINVAL);
 assert(apple_smc_write_atomic(&s,0,data,256)==-EINVAL);
 s.atomic_mode=false; assert(apple_smc_write_atomic(&s,0,data,1)==-EIO);
 s.atomic_mode=true; s.boot_stage=APPLE_SMC_BOOTING;
 assert(apple_smc_write_atomic(&s,0,data,1)==-EIO && !sends && !writes32 && !s.lock);
 s.boot_stage=APPLE_SMC_INITIALIZED;
 /* A timeout/error retains the pending command and blocks SRAM reuse. */
 for (unsigned failure=0;failure<3;failure++) {
  send_ret=failure==0 ? -EIO : 0;
  poll_ret=failure==1 ? -EIO : 0;
  reply_after=0; s.atomic_pending=false; reset_counts(); sends=polls=delays=0;
  int expected=failure==2 ? -ETIMEDOUT : -EIO;
  assert(apple_smc_write_atomic(&s,0,data,8)==expected);
  assert(s.atomic_pending && !s.lock && sends==1 && writes32==2);
  assert(polls==(failure==0 ? 0 : failure==1 ? 1 : SMC_TIMEOUT_MS*10));
  assert(delays==(failure==2 ? SMC_TIMEOUT_MS*10 : 0));
  unsigned id=s.msg_id;
  reset_counts(); sends=polls=0; memset(sram,0xa6,sizeof(sram));
  assert(apple_smc_write_atomic(&s,0,data,8)==-EBUSY);
  assert(!writes32 && !old_writes && !sends && !polls && !s.lock && s.msg_id==id);
  for (unsigned i=0;i<sizeof(sram);i++) assert(sram[i]==0xa6);
 }
 send_ret=poll_ret=0; s.atomic_pending=false; reply_after=SMC_TIMEOUT_MS*10;
 reset_counts(); sends=polls=delays=0;
 assert(apple_smc_write_atomic(&s,0,data,8)==0);
 assert(polls==SMC_TIMEOUT_MS*10 && delays==polls && !s.atomic_pending && !s.lock);
 reply_after=1;
 puts("PASS: atomic lengths/states, bounded missing reply, send/poll errors, no pending SRAM reuse, last-poll success");
}
static void guard_checks(void) {
 struct platform_device p={0};
 for (unsigned mode=0;mode<2;mode++) {
  sram32=mode;
  for (board=0;board<2;board++) assert(apple_smc_probe(&p)==(mode&&!board?-ENODEV:123));
  for (unsigned offset=0;offset<8;offset++) {
   struct apple_smc s={.boot_stage=APPLE_SMC_BOOTING}; setup_calls=0; setup_ret=0;
   bool bad=mode&&offset%4;
   assert(apple_smc_rtkit_recv_early(&s,SMC_ENDPOINT,0x1000+offset));
   assert(setup_calls==!bad && s.init_done==1);
   assert(s.boot_stage==(bad?APPLE_SMC_ERROR_NO_SHMEM:APPLE_SMC_INITIALIZED));
  }
 }
 struct apple_smc s={.boot_stage=APPLE_SMC_BOOTING}; setup_ret=-EFAULT; setup_calls=0;
 assert(apple_smc_rtkit_recv_early(&s,SMC_ENDPOINT,0x1000));
 assert(setup_calls==1 && s.boot_stage==APPLE_SMC_ERROR_NO_SHMEM && s.init_done==1);
 puts("PASS: J714s restriction before allocation, unaligned SRAM refused, mapping error propagated");
}
static void reply_identity_checks(void) {
 for(int atomic=1;atomic>=0;atomic--)for(unsigned expected=0;expected<16;expected++)
 for(unsigned received=0;received<16;received++) {
  struct apple_smc s={.boot_stage=APPLE_SMC_INITIALIZED,.msg_id=expected,
                     .atomic_mode=atomic,.atomic_pending=atomic,.cmd_ret=UINT64_C(0xdeadbeef)};
  u64 msg=FIELD_PREP(SMC_ID,received)|FIELD_PREP(SMC_DATA,0x12345678)|FIELD_PREP(SMC_SIZE,4);
  assert(apple_smc_rtkit_recv_early(&s,SMC_ENDPOINT,msg));
  if(expected==received) {
   assert(s.cmd_ret==msg && !s.atomic_pending && s.cmd_done==!atomic);
  } else {
   assert(s.cmd_ret==UINT64_C(0xdeadbeef) && s.atomic_pending==atomic && !s.cmd_done);
  }
 }
 struct apple_smc s={.boot_stage=APPLE_SMC_INITIALIZED,.msg_id=7,.atomic_mode=true,
                    .atomic_pending=true,.cmd_ret=UINT64_C(0xdeadbeef),.shmem={.iomem=sram}};
 u8 data[8]={0};
 atomic_smc=&s;sram32=true;reset_counts();sends=polls=delays=0;send_ret=poll_ret=0;reply_after=1;
 memset(sram,0xa6,sizeof(sram));
 assert(!apple_smc_rtkit_recv_early(&s,SMC_ENDPOINT,SMC_MSG_NOTIFICATION));
 assert(!apple_smc_rtkit_recv_early(&s,SMC_ENDPOINT+1,FIELD_PREP(SMC_ID,7)));
 assert(apple_smc_rtkit_recv_early(&s,SMC_ENDPOINT,FIELD_PREP(SMC_ID,6)));
 assert(apple_smc_write_atomic(&s,0,data,sizeof(data))==-EBUSY);
 assert(!writes32 && !old_writes && !sends && !polls && s.msg_id==7 && s.atomic_pending);
 for(unsigned i=0;i<sizeof(sram);i++)assert(sram[i]==0xa6);
 assert(apple_smc_rtkit_recv_early(&s,SMC_ENDPOINT,FIELD_PREP(SMC_ID,7)));
 assert(!s.atomic_pending && !s.cmd_done);
 assert(apple_smc_write_atomic(&s,0,data,sizeof(data))==0 && s.msg_id==8 && sends==1);
 puts("PASS: all reply IDs preserve unrelated commands; stale atomic reply cannot release SRAM; notifications retained");
}
int main(void) {
 copy_checks(); reply_checks(); metadata_checks(); atomic_checks(); guard_checks(); reply_identity_checks();
 return 0;
}
'''
    test_source = root / 'test.c'
    test_source.write_text(stub + functions + tests)
    binary = root / 'test'
    subprocess.run(shlex.split(os.environ.get('CC', 'cc')) +
                   ['-std=gnu11', '-Wall', '-Wextra', '-Wno-unused-parameter',
                    '-Wno-unused-variable', '-Wno-sign-compare', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', '-g', str(test_source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
finally:
    subprocess.run(['trash-put', str(root)], check=True)
