#!/usr/bin/env python3
"""Check the optional HID receiver with fragmented FIFO input, without hardware."""
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

here = Path(__file__).resolve().parent
base = (here / 'dockchannel-hid.c').read_text()
if hashlib.sha256(base.encode()).hexdigest() != 'e4eef4a5e032a18eb2e2b5762fbb4ddfb6756a6ab8f04105cf1230880d8dcdd5':
    raise SystemExit('Wrong pinned HID source checksum')
if not shutil.which('trash-put'):
    raise SystemExit('Install trash-cli: sudo apt-get install -y trash-cli')


def section(source, start, end):
    offset = source.index(start)
    return source[offset:source.index(end, offset)]


STUB = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define __packed __attribute__((packed))
#define min(a,b) ((a)<(b)?(a):(b))
#define MAX_INTERFACES 16
#define MAX_PKT_SIZE (0xffff + 4)
#define DCHID_CHANNEL_CMD 0x11
#define DCHID_CHANNEL_REPORT 0x12
#define GFP_KERNEL 0
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define WARN_ON_ONCE(x) assert(!(x))
#define INIT_WORK(...) ((void)0)
'''

MODEL = r'''
struct dchid_iface { unsigned index; void *wq; };
struct dockchannel_hid {
 void *dev, *dc;
 struct dchid_iface *ifaces[MAX_INTERFACES];
 u8 pkt_buf[MAX_PKT_SIZE];
 struct dchid_hdr rx_hdr;
 size_t rx_count;
};
struct dchid_work {
 int work; struct dchid_iface *iface; struct dchid_hdr hdr; u8 data[];
};
static struct dockchannel_hid state;
static struct dchid_iface iface[16];
static u8 stream[200000];
static size_t stream_size, visible, consumed, threshold;
static unsigned dispatches, callbacks, reads, allocs, seq, expected_iface;
static bool armed, fail_alloc, advance_seq;
static int fail_read;
static u32 get_unaligned_le32(const void *p) {
 const u8 *b=p; return (u32)b[0]|(u32)b[1]<<8|(u32)b[2]<<16|(u32)b[3]<<24;
}
static void put32(u8 *p,u32 x) { for(unsigned i=0;i<4;i++)p[i]=x>>(8*i); }
static void dchid_handle_packet(void *,size_t);
static int dockchannel_recv(void *dc,void *buf,size_t count) {
 assert(dc==&state && count<=visible-consumed);
 reads++;
 if(fail_read==(int)reads) {
  size_t partial=count/2; memcpy(buf,stream+consumed,partial); consumed+=partial;
  return -ETIMEDOUT;
 }
 memcpy(buf,stream+consumed,count); consumed+=count; return count;
}
static void dockchannel_await(void *dc,void (*fn)(void *,size_t),void *cookie,size_t n) {
 assert(dc==&state && cookie==&state && fn==dchid_handle_packet && n && !armed);
 threshold=min(n,32); armed=true;
}
static void verify_packet(struct dchid_iface *i,struct dchid_hdr *h,const u8 *data) {
 assert(i->index==expected_iface && h->iface==expected_iface && h->seq==seq);
 assert(h->length>=sizeof(struct dchid_subhdr));
 for(size_t j=0;j<h->length;j++) assert(data[j]==(u8)(j+seq));
 dispatches++;
 if(advance_seq) { seq++;expected_iface=seq%15; }
}
static void dchid_handle_ack(struct dchid_iface *i,struct dchid_hdr *h,void *data) {
 verify_packet(i,h,data);
}
static void *kzalloc(size_t n,int flags) { allocs++;return fail_alloc?NULL:calloc(1,n); }
static void queue_work(void *wq,int *work) {
 struct dchid_work *w=(void *)((u8 *)work - offsetof(struct dchid_work,work));
 assert(wq==w->iface); verify_packet(w->iface,&w->hdr,w->data); free(w);
}
'''

TESTS = r'''
static void reset(void) {
 memset(&state,0,sizeof(state)); state.dc=&state;
 for(unsigned i=0;i<16;i++) { iface[i].index=i;iface[i].wq=&iface[i];state.ifaces[i]=&iface[i]; }
 stream_size=visible=consumed=callbacks=reads=allocs=dispatches=0;
 seq=37;expected_iface=3;fail_alloc=advance_seq=false;fail_read=0;
 threshold=sizeof(struct dchid_hdr);armed=true;
}
static void packet(unsigned length,u8 channel) {
 struct dchid_hdr h={.hdr_len=sizeof(h),.channel=channel,.length=length,.seq=seq,.iface=expected_iface};
 assert(stream_size+sizeof(h)+length+4<=sizeof(stream));
 u8 *p=stream+stream_size;memcpy(p,&h,sizeof(h));
 for(unsigned i=0;i<length;i++)p[sizeof(h)+i]=i+seq;
 u32 sum=dchid_checksum(p,sizeof(h)+length);
 put32(p+sizeof(h)+length,0xffffffffu-sum);
 stream_size+=sizeof(h)+length+4;
}
static void callback(void) {
 assert(armed && ++callbacks<200000); armed=false;
 dchid_handle_packet(&state,visible-consumed);
}
static void drain(void) {
 while(armed && visible-consumed>=threshold)callback();
}
static void expose(size_t n) { assert(visible+n<=stream_size);visible+=n;drain(); }
static void finished(unsigned n) {
 assert(dispatches==n && consumed==stream_size && armed && state.rx_count==0);
 assert(threshold==sizeof(struct dchid_hdr));
}
int main(int argc,char **argv) {
 assert(argc==2);unsigned test=atoi(argv[1]);
 if(test==0) {
  /* A real header-threshold IRQ, with only five body bytes available. */
  reset();packet(64,DCHID_CHANNEL_REPORT);expose(13);
  assert(!dispatches && consumed==13 && state.rx_count==13 && armed);
  expose(stream_size-visible);finished(1);
  /* Every split, including spurious callbacks below the programmed threshold. */
  for(unsigned channel=0x11;channel<=0x13;channel++)for(unsigned split=0;split<=76;split++) {
   reset();packet(64,channel);visible=split;callback();drain();
   if(split<stream_size)assert(!dispatches);
   expose(stream_size-visible);finished(1);
  }
  puts("PASS: all 77 byte splits, ACK/report/legacy channel, delayed header/body fragments");
 } else if(test==1) {
  const unsigned lengths[]={8,12,64,256,65532};
  const unsigned chunks[]={1,2,3,4,7,8,31,255,4096,65536};
  for(unsigned i=0;i<sizeof(lengths)/sizeof(*lengths);i++)for(unsigned j=0;j<sizeof(chunks)/sizeof(*chunks);j++) {
   reset();packet(lengths[i],DCHID_CHANNEL_REPORT);
   while(visible<stream_size)expose(min((size_t)chunks[j],stream_size-visible));
   finished(1);
  }
  reset();for(unsigned i=0;i<100;i++) {
   seq=i;expected_iface=i%15;packet(12,i&1?DCHID_CHANNEL_CMD:DCHID_CHANNEL_REPORT);
  }
  seq=expected_iface=0;advance_seq=true;
  expose(stream_size);finished(100);
  puts("PASS: 50 length/chunk schedules through 65532-byte payloads and 100 back-to-back packets");
 } else if(test==2) {
  for(unsigned kind=0;kind<5;kind++) {
   reset();packet(kind==0?4:64,DCHID_CHANNEL_REPORT);
   if(kind==1)stream[stream_size-1]^=1;
   if(kind==2) { stream[5]=255; put32(stream+stream_size-4,0xffffffffu-dchid_checksum(stream,stream_size-4)); }
   if(kind==3)state.ifaces[expected_iface]=NULL;
   if(kind==4)fail_alloc=true;
   expose(stream_size);finished(0);
   state.ifaces[expected_iface]=&iface[expected_iface];fail_alloc=false;
   packet(12,DCHID_CHANNEL_CMD);expose(stream_size-visible);finished(1);
  }
  puts("PASS: complete malformed/dropped packets preserve the next packet boundary");
 } else if(test==3) {
  reset();packet(64,DCHID_CHANNEL_REPORT);stream[0]=7;expose(stream_size);
  assert(!armed && !dispatches && consumed==sizeof(struct dchid_hdr));
  for(int which=1;which<=2;which++) {
   reset();packet(64,DCHID_CHANNEL_REPORT);fail_read=which;expose(stream_size);
   assert(!armed && !dispatches && consumed<stream_size);
  }
  puts("PASS: unknown framing and unexpected partial transport errors stop without dispatch");
 } else assert(false);
}
'''

root = Path(tempfile.mkdtemp(prefix='azahi-rx-fragments-'))
try:
    path = root / 'input-driver/dockchannel-hid.c'
    path.parent.mkdir()
    path.write_text(base)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(root),
                    '-i', str(here / 'rx-fragments.patch')], check=True, capture_output=True)
    candidate = path.read_text()
    variants = {'candidate': (candidate, range(4)), 'original': (base, (0,))}
    mutations = [
        ('forget-fragment', '\tdchid->rx_count += count;', '\tdchid->rx_count = 0;', 0),
        ('overread-body', '\tcount = min(avail, remaining);', '\tcount = remaining;', 0),
        ('dispatch-fragment', '\tif (remaining)\n\t\tgoto await;', '', 0),
        ('retain-complete', '\tdchid->rx_count = 0;', '\t(void)0;', 1),
        ('reuse-unknown-frame', '\t\treturn;\n\t}\n\n\treceived =', '\t\tgoto done;\n\t}\n\n\treceived =', 3),
    ]
    for name, old, new, case in mutations:
        assert old in candidate, name
        variants[name] = (candidate.replace(old, new), (case,))
    for name, (source, cases) in variants.items():
        headers = section(source, 'struct dchid_hdr {', '\n#define IFACE_COMM')
        headers += section(source, 'struct dchid_subhdr {', '\n#define EVENT_GPIO_CMD')
        checksum = section(source, 'static u32 dchid_checksum(', '\nstatic int dchid_send(')
        receiver = section(source, 'static void dchid_handle_packet(void *cookie, size_t avail)\n{',
                           '\nstatic int dockchannel_hid_probe(')
        host, binary = root / (name + '.c'), root / name
        host.write_text(STUB + headers + MODEL + checksum + receiver + TESTS)
        subprocess.run(shlex.split(os.environ.get('CC', 'gcc')) + [
            '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
            '-Wno-sign-compare', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
            '-g', '-no-pie', str(host), '-o', str(binary)], check=True)
        for case in cases:
            result = subprocess.run([str(binary), str(case)], capture_output=True, text=True, timeout=15)
            if name == 'candidate':
                if result.returncode:
                    raise RuntimeError(result.stdout + result.stderr)
                print(result.stdout, end='')
            elif not result.returncode or 'Assertion' not in result.stderr:
                raise RuntimeError('Regression did not fail: ' + name)
    print('PASS: original wait beyond available bytes and five receive-state mutations detected')
finally:
    subprocess.run(['trash-put', str(root)], check=True)
