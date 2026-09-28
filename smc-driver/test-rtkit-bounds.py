#!/usr/bin/env python3
"""Exercise RTKit shared-buffer and logging guards without device access."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path, help='Pinned drivers/soc/apple/rtkit.c')
args = parser.parse_args()
base = args.source.read_bytes()
if hashlib.sha256(base).hexdigest() != 'c8683d97c9b8a2690c39a07db805637695c9c869353a1923bd44e92c523949ba':
    parser.exit(1, 'REFUSED: wrong RTKit source checksum; no output created\n')
if not shutil.which('trash-put'):
    parser.exit(1, 'Install trash-cli: sudo apt-get install -y trash-cli\n')
stub = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint64_t u64;
#define GFP_KERNEL 0
#define APPLE_RTKIT_EP_CRASHLOG 1
#define APPLE_RTKIT_EP_SYSLOG 2
#define APPLE_RTKIT_CRASHLOG_CRASH 1
#define APPLE_RTKIT_SYSLOG_TYPE UINT64_C(0x0ff0000000000000)
#define APPLE_RTKIT_SYSLOG_N_ENTRIES UINT64_C(0xff)
#define APPLE_RTKIT_SYSLOG_MSG_SIZE UINT64_C(0xff000000)
#define FIELD_GET(mask,value) (((value)&(mask))>>__builtin_ctzll(mask))
#define FIELD_PREP(mask,value) (((u64)(value)<<__builtin_ctzll(mask))&(mask))
struct apple_rtkit_shmem { void *buffer,*iomem; size_t size; };
struct apple_rtkit_ops { void (*crashed)(void *,const void *,size_t); };
struct apple_rtkit {
 void *dev,*cookie;struct apple_rtkit_ops *ops;bool crashed;
 struct apple_rtkit_shmem syslog_buffer,crashlog_buffer;
 size_t syslog_n_entries,syslog_msg_size;char *syslog_msg_buffer;
};
static unsigned char shared[80000];
static size_t access_limit, message_size;
static unsigned copies,io_copies,warnings,acks,logs,allocs,frees,live,crash_callbacks,crash_dumps,buffer_requests;
static bool allow_copy=true, fail_alloc, expected_crash_data;
static u64 expected_ack;
static void *kzalloc(size_t size,int flags) {
 assert(!flags);allocs++;
 if(fail_alloc)return NULL;
 if(!size)return (void *)16;
 void *p=calloc(1,size);assert(p);live++;return p;
}
static void kfree(void *p) { if(p && p!=(void *)16) { assert(live);free(p);live--;frees++; } }
static void free_shadow(void *p) { kfree(*(void **)p); }
#define __free(fn) __attribute__((cleanup(free_shadow)))
static void *checked_memcpy(void *dst,const void *src,size_t count) {
 assert(allow_copy);
 uintptr_t address=(uintptr_t)src,base=(uintptr_t)shared;
 assert(address>=base && address-base<=access_limit && count<=access_limit-(address-base));
 copies++;return memcpy(dst,src,count);
}
static void memcpy_fromio(void *dst,const void *src,size_t count) { io_copies++;checked_memcpy(dst,src,count); }
static void log_message(void *dev,const char *format,const char *context,const char *text) {
 assert(message_size && strnlen(context,24)<24 && strnlen(text,message_size)<message_size);logs++;
}
#define dev_info(...) log_message(__VA_ARGS__)
#define dev_warn(...) (warnings++)
#define dev_warn_ratelimited(...) (warnings++)
#define dev_err(...) (warnings++)
#define dev_dbg(...) ((void)0)
static int apple_rtkit_send_message(struct apple_rtkit *r,u8 ep,u64 msg,void *completion,bool atomic) {
 assert(ep==APPLE_RTKIT_EP_SYSLOG && msg==expected_ack && !completion && !atomic);acks++;return 0;
}
static int apple_rtkit_common_rx_get_buffer(struct apple_rtkit *r,struct apple_rtkit_shmem *b,u8 ep,u64 msg) {
 assert(b==&r->crashlog_buffer && ep==APPLE_RTKIT_EP_CRASHLOG);buffer_requests++;return 0;
}
static void apple_rtkit_crashlog_dump(struct apple_rtkit *r,const void *p,size_t size) {
 assert(expected_crash_data && size==64 && !memcmp(p,shared,size));crash_dumps++;
}
static void crash_callback(void *cookie,const void *p,size_t size) {
 struct apple_rtkit *r=cookie;assert(r->crashed);crash_callbacks++;
 if(expected_crash_data)assert(p && size==64 && !memcmp(p,shared,size));
 else assert(!p && !size);
}
#define memcpy checked_memcpy
'''

# Preserve the existing idx <= count convention. Only mapped buffer bounds
# determine memory safety; changing that protocol convention needs hardware.
tests = r'''
#undef memcpy
static void reset(void) { copies=io_copies=warnings=acks=logs=crash_callbacks=crash_dumps=buffer_requests=0;allow_copy=true;fail_alloc=false; }
static void run_log(struct apple_rtkit *r,unsigned idx) {
 reset();access_limit=r->syslog_buffer.size;message_size=r->syslog_msg_size;
 allow_copy=message_size!=0;expected_ack=UINT64_C(0x0050000012340000)|idx;
 bool valid=r->syslog_msg_buffer && message_size && r->syslog_buffer.size &&
  (r->syslog_buffer.buffer || r->syslog_buffer.iomem) && idx<=r->syslog_n_entries &&
  (idx+1)*(32+message_size)<=r->syslog_buffer.size;
 apple_rtkit_syslog_rx_log(r,expected_ack);
 assert(acks==1 && logs==valid);
 if(valid)assert(copies==2 && io_copies==(r->syslog_buffer.iomem?2:0));
 if(!message_size)assert(!copies);
}
static void logs_test(void) {
 char text[255];struct apple_rtkit r={.syslog_msg_buffer=text};
 memset(shared,'Z',sizeof(shared));
 for(unsigned io=0;io<2;io++)for(unsigned size=1;size<=255;size++) {
  r.syslog_buffer.buffer=io?NULL:shared;r.syslog_buffer.iomem=io?shared:NULL;
  r.syslog_msg_size=size;r.syslog_n_entries=255;
  for(unsigned idx=0;idx<256;idx++) {
   size_t end=(idx+1)*(32+size);
   r.syslog_buffer.size=end;run_log(&r,idx);
   r.syslog_buffer.size=end-1;run_log(&r,idx);
  }
 }
 for(unsigned count=0;count<256;count++)for(unsigned idx=0;idx<256;idx++) {
  r.syslog_n_entries=count;r.syslog_msg_size=8;r.syslog_buffer.size=sizeof(shared);run_log(&r,idx);
 }
 r.syslog_buffer.buffer=r.syslog_buffer.iomem=NULL;run_log(&r,0);
 r.syslog_buffer.buffer=shared;r.syslog_msg_buffer=NULL;run_log(&r,0);
 r.syslog_msg_buffer=text;r.syslog_msg_size=0;run_log(&r,0);
 r.syslog_msg_buffer=(void *)16;run_log(&r,0);
 puts("PASS: 261120 exact/truncated log entries, 65536 count/index combinations, RAM/MMIO and zero-size refusals");
}
static void init_test(void) {
 struct apple_rtkit r={0};allocs=frees=live=0;
 for(unsigned size=1;size<=255;size++) {
  apple_rtkit_syslog_rx_init(&r,FIELD_PREP(APPLE_RTKIT_SYSLOG_MSG_SIZE,size)|7);
  assert(r.syslog_msg_size==size && r.syslog_n_entries==7 && r.syslog_msg_buffer && live==1);
 }
 unsigned before=allocs;
 apple_rtkit_syslog_rx_init(&r,7);
 assert(!r.syslog_msg_buffer && !r.syslog_msg_size && !live && allocs==before);
 fail_alloc=true;apple_rtkit_syslog_rx_init(&r,FIELD_PREP(APPLE_RTKIT_SYSLOG_MSG_SIZE,8)|7);
 assert(!r.syslog_msg_buffer && !live);fail_alloc=false;
 puts("PASS: repeated log initialization frees prior memory, zero size and allocation failure remain disabled");
}
static void copy_test(void) {
 unsigned char dst[100];struct apple_rtkit r={0};
 for(unsigned io=0;io<2;io++) {
  struct apple_rtkit_shmem b={.size=64,.buffer=io?NULL:shared,.iomem=io?shared:NULL};
  size_t offsets[]={0,1,63,64,65,SIZE_MAX};size_t lengths[]={SIZE_MAX,0,1,2,63,64,65};
  for(unsigned i=0;i<6;i++)for(unsigned j=0;j<7;j++) {
   reset();access_limit=64;memset(dst,0xa6,sizeof(dst));
   size_t off=offsets[i],len=lengths[j];bool valid=off<=64 && len<=64-off;
   apple_rtkit_memcpy(&r,dst,&b,off,len);
   assert(copies==(valid&&len!=0));
   if(!valid || !len)for(unsigned k=0;k<100;k++)assert(dst[k]==0xa6);
  }
 }
 struct apple_rtkit_shmem b={.size=64};reset();access_limit=64;
 apple_rtkit_memcpy(&r,dst,&b,0,64);assert(!copies);
 puts("PASS: shared copy bounds, overflow-sized arguments, absent backing and zero-length copies");
}
static void crash_test(void) {
 struct apple_rtkit_ops ops={.crashed=crash_callback};
 for(unsigned io=0;io<2;io++)for(unsigned missing=0;missing<2;missing++)for(unsigned failure=0;failure<2;failure++) {
  reset();fail_alloc=failure;access_limit=64;expected_crash_data=!missing&&!failure;
  struct apple_rtkit r={.ops=&ops};r.cookie=&r;r.crashlog_buffer.size=64;
  if(!missing) { r.crashlog_buffer.buffer=io?NULL:shared;r.crashlog_buffer.iomem=io?shared:NULL; }
  apple_rtkit_crashlog_rx(&r,FIELD_PREP(APPLE_RTKIT_SYSLOG_TYPE,APPLE_RTKIT_CRASHLOG_CRASH));
  assert(r.crashed && crash_callbacks==1 && crash_dumps==expected_crash_data && !live);
 }
 reset();struct apple_rtkit r={.ops=&ops};r.cookie=&r;
 apple_rtkit_crashlog_rx(&r,FIELD_PREP(APPLE_RTKIT_SYSLOG_TYPE,APPLE_RTKIT_CRASHLOG_CRASH));
 assert(buffer_requests==1 && !crash_callbacks && !r.crashed);
 puts("PASS: valid crash dump retained; missing backing or allocation returns a null crash buffer");
}
int main(int argc,char **argv) {
 int mode=argc>1?atoi(argv[1]):-1;
 if(mode<0||mode==0)logs_test();
 if(mode<0||mode==1)init_test();
 if(mode<0||mode==2)copy_test();
 if(mode<0||mode==3)crash_test();
 return 0;
}
'''

def section(text, start, end):
    offset = text.index(start)
    return text[offset:text.index(end, offset)]


root = Path(tempfile.mkdtemp(prefix='azahi-rtkit-bounds-'))
try:
    source_path = root / 'drivers/soc/apple/rtkit.c'
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(base)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(root), '-i',
                    str(Path(__file__).with_name('rtkit-buffer-bounds.patch').resolve())],
                   check=True, capture_output=True)
    source = source_path.read_text()
    guard = 'if (offset > bfr->size || len > bfr->size - offset ||\n\t    (len && !bfr->iomem && !bfr->buffer))'
    payload_copy = '''\tif (apple_rtkit_memcpy(rtk, rtk->syslog_msg_buffer, &rtk->syslog_buffer,
\t\t\t      idx * entry_size + 8 + sizeof(log_context),
\t\t\t      rtk->syslog_msg_size) < 0)
\t\tgoto done;'''
    unchecked = payload_copy.replace('\tif (apple_rtkit_memcpy', '\tapple_rtkit_memcpy').replace(
        ') < 0)\n\t\tgoto done;', ');')
    variants = {
        'no-copy-bounds': (source.replace(guard, 'if (len && !bfr->iomem && !bfr->buffer)'), 0),
        'null-backing-unchecked': (source.replace(guard, 'if (offset > bfr->size || len > bfr->size - offset)'), 3),
        'old-buffer-leaked': (source.replace('\tkfree(rtk->syslog_msg_buffer);\n', ''), 1),
        'zero-log-accepted': (source.replace('if (!rtk->syslog_msg_buffer || !rtk->syslog_msg_size) {',
                                              'if (!rtk->syslog_msg_buffer) {'), 0),
        'failed-crash-copy-passed': (source.replace('\t\t\tkfree(bfr);\n\t\t\tbfr = NULL;', '\t\t\t;'), 3),
        'failed-log-copy-printed': (source.replace(payload_copy, unchecked), 0),
    }
    for name, (text, mode) in variants.items():
        if text == source:
            raise RuntimeError('Mutation did not change source: ' + name)
    cases = [('current', source, -1)]
    cases += [('original-' + str(mode), base.decode(), mode) for mode in range(4)]
    cases += [(name, text, mode) for name, (text, mode) in variants.items()]
    for name, text, mode in cases:
        signature = ('static int apple_rtkit_memcpy(' if 'static int apple_rtkit_memcpy(' in text
                     else 'static void apple_rtkit_memcpy(')
        functions = section(text, signature, 'static void apple_rtkit_ioreport_rx(')
        functions += section(text, 'static void apple_rtkit_syslog_rx_init(',
                             'static void apple_rtkit_syslog_rx(')
        host = root / (name + '.c')
        host.write_text(stub + functions + tests)
        binary = root / name
        cc = shlex.split(os.environ.get('CC', 'gcc'))
        subprocess.run([*cc, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-function', '-UNDEBUG',
                        '-fno-pie', '-no-pie', '-fsanitize=address,undefined',
                        str(host), '-o', str(binary)], check=True)
        result = subprocess.run([str(binary), str(mode)], capture_output=True, text=True, timeout=30)
        if name == 'current':
            if result.returncode:
                raise RuntimeError(result.stderr)
            print(result.stdout, end='')
        elif result.returncode == 0 or not any(marker in result.stderr for marker in
                                               ('Assertion', 'AddressSanitizer')):
            raise RuntimeError('Original or regression did not fail: ' + name)
    print('Four original failures and six mutations detected')
finally:
    subprocess.run(['trash-put', str(root)], check=True)
