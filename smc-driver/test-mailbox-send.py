#!/usr/bin/env python3
"""Exercise the optional mailbox send patch with controlled host threads."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

PINS = {
    'drivers/soc/apple/mailbox.c': '7f501ab286effea3268cd9bcb2d172b48ee27585fb848b0f192d04ed445a50dc',
    'include/linux/soc/apple/mailbox.h': '4ac9fe47a9110c98ad0b5e7a52fc479b1b4d11373f95a4722f1a84ea6915e05d',
}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-tree', required=True, type=Path, help='Pinned kernel source root')
args = parser.parse_args()
inputs = {p: (args.source_tree / p).read_bytes() for p in PINS}
for path, data in inputs.items():
    if hashlib.sha256(data).hexdigest() != PINS[path]:
        parser.exit(1, 'REFUSED: wrong source checksum for ' + path + '; no output created\n')
if not shutil.which('trash-put'):
    parser.exit(1, 'Install trash-cli: sudo apt-get install -y trash-cli\n')
root = Path(tempfile.mkdtemp(prefix='azahi-mailbox-send-'))
try:
    for path, data in inputs.items():
        p = root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(root), '-i',
                    str(Path(__file__).with_name('mailbox-send-waiters.patch').resolve())],
                   check=True, capture_output=True)
    source = (root / 'drivers/soc/apple/mailbox.c').read_text()
    stub = r'''
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
typedef uint32_t u32;
typedef int irqreturn_t;
#define IRQ_HANDLED 1
#define EXPORT_SYMBOL(x)
#define APPLE_MBOX_TX_TIMEOUT 500
#define APPLE_MBOX_MSG1_MSG 0xffffffffULL
#define FIELD_PREP(mask,value) ((value)&(mask))
#define READ_ONCE(x) __atomic_load_n(&(x),__ATOMIC_RELAXED)
#define WRITE_ONCE(x,v) __atomic_store_n(&(x),(v),__ATOMIC_RELAXED)
#define msecs_to_jiffies(x) (x)
struct completion { unsigned done; };
struct apple_mbox_hw { unsigned a2i_control,a2i_send0,a2i_send1,irq_ack;u32 control_full,irq_bit_send_empty;bool has_irq_controls; };
struct apple_mbox_msg { uint64_t msg0;u32 msg1; };
struct apple_mbox {
 unsigned char *regs;struct apple_mbox_hw *hw;int irq_send_empty;
 pthread_mutex_t tx_lock;struct completion tx_empty;
 bool tx_irq_unmasked;unsigned tx_waiters;unsigned long tx_seq;int tx_wait;
};
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed=PTHREAD_COND_INITIALIZER;
static _Thread_local unsigned slot, locked;
static struct apple_mbox *active;
static unsigned char regs[32];
static atomic_int fifo_full;
static int irq_depth,unbalanced,atomic_error;
static unsigned irq_enables,irq_disables,ack_count,writes[2],entered[2];
static bool waiting[2];
static long forced[2];
static int result[2];
static void lock(pthread_mutex_t *p) { assert(!locked);assert(!pthread_mutex_lock(p));locked=1; }
static void unlock(pthread_mutex_t *p) { assert(locked);locked=0;assert(!pthread_mutex_unlock(p)); }
#define spin_lock(p) lock(p)
#define spin_unlock(p) unlock(p)
#define spin_lock_irqsave(p,flags) do { (flags)=42;lock(p); } while(0)
#define spin_unlock_irqrestore(p,flags) do { assert((flags)==42);unlock(p); } while(0)
static void enable_irq(int irq) {
 assert(irq==7 && locked);irq_enables++;
 if(!irq_depth)unbalanced++;else irq_depth--;
}
static void disable_irq_nosync(int irq) { assert(irq==7 && locked);irq_disables++;irq_depth++; }
static u32 readl_relaxed(unsigned char *p) {
 assert(locked && p==regs+active->hw->a2i_control);
 return atomic_load(&fifo_full)?active->hw->control_full:0;
}
static void writel_relaxed(u32 value,unsigned char *p) {
 assert(locked && p==regs+active->hw->irq_ack && value==active->hw->irq_bit_send_empty);ack_count++;
}
static void writeq_relaxed(uint64_t value,unsigned char *p) {
 assert(locked && !atomic_load(&fifo_full));
 if(p==regs+active->hw->a2i_send0) { assert(value==0x100+slot && writes[slot]%2==0); }
 else { assert(p==regs+active->hw->a2i_send1 && value==0x200+slot && writes[slot]%2==1); }
 writes[slot]++;
}
#define readl_poll_timeout_atomic(addr,value,condition,delay,timeout) \
 ({ (void)(addr);(void)(delay);(void)(timeout);if(!atomic_error) { atomic_store(&fifo_full,0);(value)=0;assert(condition); } atomic_error; })
static struct timespec deadline(void) {
 struct timespec d;assert(!clock_gettime(CLOCK_REALTIME,&d));d.tv_sec+=2;return d;
}
static void reinit_completion(struct completion *c) { assert(locked);pthread_mutex_lock(&gate);c->done=0;pthread_mutex_unlock(&gate); }
static void complete(struct completion *c) { assert(locked);pthread_mutex_lock(&gate);c->done++;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&gate); }
static void wake_up_all(int *q) { (void)q;pthread_mutex_lock(&gate);pthread_cond_broadcast(&changed);pthread_mutex_unlock(&gate); }
static long wait_for_completion_interruptible_timeout(struct completion *c,unsigned timeout) {
 assert(!locked && timeout==500);struct timespec d=deadline();pthread_mutex_lock(&gate);
 waiting[slot]=true;entered[slot]++;pthread_cond_broadcast(&changed);
 while(!c->done && forced[slot]==LONG_MIN) {
  int e=pthread_cond_timedwait(&changed,&gate,&d);assert(!e || e==ETIMEDOUT);
  if(e==ETIMEDOUT)forced[slot]=0;
 }
 long r=forced[slot]!=LONG_MIN?forced[slot]:1;
 if(r>0)c->done--;
 forced[slot]=LONG_MIN;waiting[slot]=false;pthread_mutex_unlock(&gate);return r;
}
#define wait_event_interruptible_timeout(q,condition,timeout) \
 ({ assert(!locked && (timeout)==500);(void)(q);struct timespec d=deadline(); \
 pthread_mutex_lock(&gate);waiting[slot]=true;entered[slot]++;pthread_cond_broadcast(&changed); \
 while(!(condition) && forced[slot]==LONG_MIN) { \
  int e=pthread_cond_timedwait(&changed,&gate,&d);assert(!e || e==ETIMEDOUT);if(e==ETIMEDOUT)forced[slot]=0; \
 } \
 long r=forced[slot]!=LONG_MIN?forced[slot]:1;forced[slot]=LONG_MIN;waiting[slot]=false;pthread_mutex_unlock(&gate);r; })
'''
    tests = r'''
static struct apple_mbox_hw hw={.a2i_control=0,.a2i_send0=8,.a2i_send1=16,.irq_ack=24,.control_full=1,.irq_bit_send_empty=4};
static struct apple_mbox m={.regs=regs,.hw=&hw,.irq_send_empty=7,.tx_lock=PTHREAD_MUTEX_INITIALIZER};
static void reset(bool full,unsigned controls) {
 active=&m;hw.has_irq_controls=controls;atomic_store(&fifo_full,full);
 irq_depth=1;unbalanced=atomic_error=0;irq_enables=irq_disables=ack_count=0;
 memset(writes,0,sizeof(writes));memset(entered,0,sizeof(entered));memset(waiting,0,sizeof(waiting));
 forced[0]=forced[1]=LONG_MIN;result[0]=result[1]=123;
 m.tx_irq_unmasked=false;m.tx_waiters=0;m.tx_seq=0;m.tx_empty.done=0;slot=0;
}
static struct apple_mbox_msg message(void) { return (struct apple_mbox_msg){.msg0=0x100+slot,.msg1=0x200+slot}; }
static void *sender(void *id) { slot=(uintptr_t)id;result[slot]=apple_mbox_send(&m,message(),false);return NULL; }
static void await_sender(unsigned id) {
 struct timespec d=deadline();pthread_mutex_lock(&gate);
 while(!waiting[id])assert(!pthread_cond_timedwait(&changed,&gate,&d));
 pthread_mutex_unlock(&gate);
}
static void expire(unsigned id,long value) { pthread_mutex_lock(&gate);assert(waiting[id]);forced[id]=value;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&gate); }
static bool fire_if_enabled(void) {
 lock(&m.tx_lock);bool enabled=irq_depth==0;unlock(&m.tx_lock);
 if(enabled)assert(apple_mbox_send_empty_irq(7,&m)==IRQ_HANDLED);
 return enabled;
}
int main(int argc,char **argv) {
 assert(argc==2);unsigned which=(unsigned)(argv[1][0]-'0');
 for(unsigned controls=0;controls<2;controls++) {
  pthread_t a,b;
  if(which==0) {
   reset(false,controls);assert(apple_mbox_send(&m,message(),false)==0 && writes[0]==2 && !irq_enables);
   reset(true,controls);atomic_error=-ETIMEDOUT;assert(apple_mbox_send(&m,message(),true)==-ETIMEDOUT);
   assert(!writes[0] && !irq_enables && irq_depth==1);
   atomic_error=0;assert(apple_mbox_send(&m,message(),true)==0 && writes[0]==2 && !irq_enables);
  } else if(which<=3) {
   reset(true,controls);assert(!pthread_create(&a,NULL,sender,(void *)0));await_sender(0);
   expire(0,which==2?-EINTR:0);assert(!pthread_join(a,NULL));
   assert(result[0]==(which==2?-EINTR:-ETIMEDOUT) && !writes[0]);
   if(which==3)assert(apple_mbox_send_empty_irq(7,&m)==IRQ_HANDLED);
   assert(irq_depth==1 && !unbalanced && !m.tx_waiters);
  } else if(which==4 || which==7) {
   reset(true,controls);if(which==7)m.tx_seq=ULONG_MAX;
   assert(!pthread_create(&a,NULL,sender,(void *)0));await_sender(0);
   atomic_store(&fifo_full,0);assert(fire_if_enabled());assert(!pthread_join(a,NULL));
   assert(result[0]==0 && writes[0]==2 && irq_depth==1 && !unbalanced && !m.tx_waiters);
  } else if(which==5) {
   reset(true,controls);assert(!pthread_create(&a,NULL,sender,(void *)0));await_sender(0);
   assert(!pthread_create(&b,NULL,sender,(void *)1));await_sender(1);
   expire(0,0);assert(!pthread_join(a,NULL));assert(result[0]==-ETIMEDOUT);
   atomic_store(&fifo_full,0);if(!fire_if_enabled())expire(1,0);
   assert(!pthread_join(b,NULL));
   assert(result[1]==0 && writes[1]==2 && irq_depth==1 && !unbalanced && !m.tx_waiters);
  } else if(which==6) {
   reset(true,controls);assert(!pthread_create(&a,NULL,sender,(void *)0));await_sender(0);
   assert(!pthread_create(&b,NULL,sender,(void *)1));await_sender(1);
   atomic_store(&fifo_full,0);assert(fire_if_enabled());
   assert(!pthread_join(a,NULL) && !pthread_join(b,NULL));
   assert(result[0]==0 && result[1]==0 && writes[0]==2 && writes[1]==2);
   assert(irq_depth==1 && !unbalanced && !m.tx_waiters);
  } else assert(false);
 }
 printf("PASS: case %u, both hardware IRQ variants\n",which);return 0;
}
'''
    variants = {
        'candidate': (source, range(8)),
        'original': (inputs['drivers/soc/apple/mailbox.c'].decode(), (1, 2, 5, 6)),
        'mask-another-waiter': (source.replace('!mbox->tx_waiters && mbox->tx_irq_unmasked',
                                              'mbox->tx_irq_unmasked'), (5,)),
        'no-sequence-change': (source.replace('WRITE_ONCE(mbox->tx_seq, mbox->tx_seq + 1);',
                                              'WRITE_ONCE(mbox->tx_seq, mbox->tx_seq);'), (4,)),
        'double-enable': (source.replace('if (!mbox->tx_irq_unmasked) {', 'if (true) {'), (5,)),
        'late-double-disable': (source.replace('if (mbox->tx_irq_unmasked) {\n\t\tdisable_irq_nosync',
                                               'if (true) {\n\t\tdisable_irq_nosync'), (3,)),
    }
    for name, (implementation, cases) in variants.items():
        if name not in ('candidate', 'original') and implementation == source:
            raise RuntimeError('Mutation no longer matches: ' + name)
        start = implementation.index('int apple_mbox_send(')
        end = implementation.index('static int apple_mbox_poll_locked(', start)
        file = root / (name + '.c')
        file.write_text(stub + implementation[start:end] + tests)
        binary = root / name
        subprocess.run(shlex.split(os.environ.get('CC', 'gcc')) +
                       ['-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-function', '-Wno-unused-parameter', '-pthread',
                        '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                        str(file), '-o', str(binary)], check=True)
        for case in cases:
            result = subprocess.run([str(binary), str(case)], capture_output=True,
                                    text=True, timeout=8)
            if name == 'candidate':
                if result.returncode:
                    raise RuntimeError(result.stderr)
                print(result.stdout, end='')
            elif result.returncode == 0 or 'Assertion' not in result.stderr:
                raise RuntimeError(name + ' did not fail its intended assertion: ' + result.stderr)
    print('Original timeout/concurrency failures and four mutations detected')
finally:
    subprocess.run(['trash-put', str(root)], check=True)
