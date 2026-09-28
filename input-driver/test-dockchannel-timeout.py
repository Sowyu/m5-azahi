#!/usr/bin/env python3
"""Exercise actual DockChannel timeout paths with modeled IRQ interleavings."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path)
args = parser.parse_args()
original = args.source.read_text()
if hashlib.sha256(original.encode()).hexdigest() != '83cc73986312a06d99f7e5828a078964a581be00dc5826195e4622d5c6a7bede':
    parser.error('Wrong pinned DockChannel source checksum')
if not shutil.which('trash-put'):
    parser.error('Install trash-cli: sudo apt-get install -y trash-cli')

STUB = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef int irqreturn_t;
#define IRQ_HANDLED 1
#define IRQ_WAKE_THREAD 2
#define __iomem
#define EXPORT_SYMBOL(x)
#define BIT(n) (1U << (n))
#define min(a,b) ((a)<(b)?(a):(b))
#define msecs_to_jiffies(n) (n)
struct device { int unused; };
struct completion { unsigned done; };
'''

MODEL = r'''
static irqreturn_t dockchannel_tx_irq(int, void *);
static irqreturn_t dockchannel_rx_irq(int, void *);
static struct dockchannel *active;
static unsigned char config[8], regs[64], input[256], output[256];
static unsigned available[2], depth[2], pos[2], waits, deadlocks;
static int pending = -1;
static bool rx_thread;
enum timing { SUCCESS, NO_IRQ, BEFORE_CANCEL, DURING_CANCEL };
static enum timing timing;
static int dispatch(unsigned irq) {
 assert(irq<2);
 return irq ? dockchannel_rx_irq(irq,active) : dockchannel_tx_irq(irq,active);
}
static void enable_irq(unsigned irq) { assert(irq<2 && depth[irq]); depth[irq]--; }
static void disable_irq_nosync(unsigned irq) { assert(irq<2); depth[irq]++; }
static bool synchronize_hardirq(unsigned irq) {
 assert(depth[irq]);
 if(pending==(int)irq) { pending=-1; assert(dispatch(irq)==IRQ_HANDLED); }
 return !(irq==1 && rx_thread);
}
static void synchronize_irq(unsigned irq) {
 synchronize_hardirq(irq);
 /* Record the self-wait instead of hanging the host test indefinitely. */
 if(irq==1 && rx_thread) deadlocks++;
}
static void disable_irq(unsigned irq) { disable_irq_nosync(irq); synchronize_irq(irq); }
static void reinit_completion(struct completion *c) { assert(pending==-1); c->done=0; }
static void complete(struct completion *c) { c->done++; }
static bool try_wait_for_completion(struct completion *c) {
 if(!c->done) return false;
 c->done--; return true;
}
static unsigned long wait_for_completion_timeout(struct completion *c,unsigned timeout) {
 unsigned irq=c==&active->rx_comp;
 assert(c==&active->tx_comp || c==&active->rx_comp);
 assert(timeout==1000 && !depth[irq] && !c->done);
 assert(++waits<64);
 if(timing==NO_IRQ) return 0;
 if(timing==DURING_CANCEL) { pending=irq; return 0; }
 if(timing==SUCCESS) available[irq]=7;
 assert(dispatch(irq)==IRQ_HANDLED && c->done==1);
 if(timing==BEFORE_CANCEL) return 0;
 c->done--; return 1;
}
static u32 get_unaligned_le32(const void *p) {
 const u8 *b=p;return (u32)b[0]|(u32)b[1]<<8|(u32)b[2]<<16|(u32)b[3]<<24;
}
static void put_unaligned_le32(u32 v,void *p) {
 u8 *b=p;for(unsigned i=0;i<4;i++)b[i]=v>>(8*i);
}
static u32 readl_relaxed(const unsigned char *p) {
 if(p==regs+DATA_TX_FREE) return available[0];
 if(p==regs+DATA_RX_COUNT) return available[1];
 unsigned n=p==regs+DATA_RX32?4:1;
 assert(p==regs+DATA_RX32 || p==regs+DATA_RX8);
 assert(available[1]>=n && pos[1]+n<=sizeof(input));
 u32 v=n==4?get_unaligned_le32(input+pos[1]):(u32)input[pos[1]]<<8;
 available[1]-=n;pos[1]+=n;return v;
}
static void writel_relaxed(u32 v,unsigned char *p) {
 if(p==config+CONFIG_TX_THRESH || p==config+CONFIG_RX_THRESH) { assert(v>0 && v<=8); return; }
 assert(p==regs+DATA_TX32 && available[0]>=4 && pos[0]+4<=sizeof(output));
 put_unaligned_le32(v,output+pos[0]);available[0]-=4;pos[0]+=4;
}
static void writeb_relaxed(u8 v,unsigned char *p) {
 assert(p==regs+DATA_TX8 && available[0] && pos[0]<sizeof(output));
 output[pos[0]++]=v;available[0]--;
}
'''

TESTS = r'''
static struct dockchannel dc;
static unsigned char received[32];
static int callback_result;
static void reset(void) {
 memset(&dc,0,sizeof(dc));memset(received,0,sizeof(received));memset(output,0,sizeof(output));
 for(unsigned i=0;i<sizeof(input);i++)input[i]=0x30+i;
 active=&dc;dc.tx_irq=0;dc.rx_irq=1;dc.fifo_size=8;dc.config_base=config;dc.data_base=regs;
 depth[0]=depth[1]=1;available[0]=available[1]=pos[0]=pos[1]=waits=deadlocks=0;
 pending=-1;rx_thread=false;timing=SUCCESS;callback_result=123;
}
static void settled(unsigned irq) {
 assert(!deadlocks && pending==-1 && depth[irq]==1);
 assert(!dc.tx_comp.done && !dc.rx_comp.done);
}
static void callback(void *cookie,size_t avail) {
 assert(cookie==&dc && rx_thread && avail==3 && !dc.awaiting);
 callback_result=dockchannel_recv(&dc,received,17);
}
int main(int argc,char **argv) {
 assert(argc==2);unsigned which=(unsigned)atoi(argv[1]);
 if(which==0) {
  const unsigned lengths[]={0,1,3,4,5,17};
  for(unsigned i=0;i<sizeof(lengths)/sizeof(*lengths);i++)for(unsigned immediate=0;immediate<2;immediate++) {
   unsigned n=lengths[i];reset();available[0]=immediate?n:0;
   assert(dockchannel_send(&dc,input,n)==(int)n && pos[0]==n);
   assert(!memcmp(input,output,n));settled(0);
   reset();available[1]=immediate?n:0;
   assert(dockchannel_recv(&dc,received,n)==(int)n && pos[1]==n);
   assert(!memcmp(input,received,n));settled(1);
  }
  puts("PASS: TX/RX zero, word and tail transfers, immediate and interrupt-driven");
 } else if(which==1) {
  for(unsigned mode=NO_IRQ;mode<=DURING_CANCEL;mode++) {
   reset();timing=mode;available[1]=3;
   assert(dockchannel_await(&dc,callback,&dc,3)==3 && !depth[1]);
   assert(dispatch(1)==IRQ_WAKE_THREAD);
   rx_thread=true;assert(dockchannel_rx_irq_thread(1,&dc)==IRQ_HANDLED);rx_thread=false;
   assert(callback_result==-ETIMEDOUT && pos[1]==3 && !memcmp(input,received,3));
   settled(1);
   /* Test IRQ reuse, not recovery of a partially consumed HID packet. */
   timing=SUCCESS;
   assert(dockchannel_recv(&dc,received+3,14)==14 && !memcmp(input,received,17));settled(1);
   assert(dockchannel_await(&dc,callback,&dc,3)==3 && !depth[1]);
   assert(dockchannel_await(&dc,NULL,NULL,0)==0 && depth[1]==1);
  }
  puts("PASS: receive-thread timeout, both late IRQ orders and subsequent rearm");
 } else if(which==2) {
  for(unsigned mode=NO_IRQ;mode<=DURING_CANCEL;mode++) {
   reset();timing=mode;available[0]=3;
   assert(dockchannel_send(&dc,input,17)==-ETIMEDOUT && pos[0]==3);
   settled(0);timing=SUCCESS;
   assert(dockchannel_send(&dc,input+3,14)==14 && !memcmp(input,output,17));settled(0);
  }
  puts("PASS: send timeout, both late IRQ orders and subsequent rearm");
 } else assert(false);
 return 0;
}
'''


def section(source, start, end):
    offset = source.index(start)
    return source[offset:source.index(end, offset)]


root = Path(tempfile.mkdtemp(prefix='azahi-dockchannel-timeout-'))
try:
    path = root / 'drivers/soc/apple/dockchannel.c'
    path.parent.mkdir(parents=True)
    path.write_text(original)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(root), '-i',
                    str(Path(__file__).with_name('dockchannel-timeout.patch').resolve())],
                   check=True, capture_output=True)
    candidate = path.read_text()
    variants = {
        'candidate': (candidate, range(3)),
        'original': (original, (1, 2)),
        'wait-for-own-thread': (candidate.replace('synchronize_hardirq(irq);', 'synchronize_irq(irq);'), (1,)),
        'no-hardirq-drain': (candidate.replace('\tsynchronize_hardirq(irq);', ''), (2,)),
        'no-depth-repair': (candidate.replace('\t\tenable_irq(irq);', '\t\t(void)0;'), (2,)),
        'always-reenable': (candidate.replace('if (try_wait_for_completion(completion))', 'if (true)'), (2,)),
    }
    for name, (source, cases) in variants.items():
        if name not in ('candidate', 'original') and source == candidate:
            raise RuntimeError('Mutation did not change source: ' + name)
        declarations = section(source, '#define DOCKCHANNEL_MAX_IRQ', '\nstruct dockchannel_common')
        functions = section(source, '/* Dockchannel FIFO functions */', '\nstruct dockchannel *dockchannel_init(')
        host, binary = root / (name + '.c'), root / name
        host.write_text(STUB + declarations + MODEL + functions + TESTS)
        subprocess.run(shlex.split(os.environ.get('CC', 'gcc')) + [
            '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
            '-Wno-unused-function', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
            '-g', '-no-pie', str(host), '-o', str(binary)], check=True)
        for case in cases:
            result = subprocess.run([str(binary), str(case)], capture_output=True, text=True, timeout=10)
            if name == 'candidate':
                if result.returncode:
                    raise RuntimeError(result.stdout + result.stderr)
                print(result.stdout, end='')
            elif not result.returncode or 'Assertion' not in result.stderr:
                raise RuntimeError('Regression did not fail: ' + name)
    print('PASS: two original failures and four regression mutations detected')
finally:
    subprocess.run(['trash-put', str(root)], check=True)
