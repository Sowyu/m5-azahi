#!/usr/bin/env python3
"""Check the optional built-in mailbox patch. No device or live kernel access."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

BASE_SHA256 = '7f501ab286effea3268cd9bcb2d172b48ee27585fb848b0f192d04ed445a50dc'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True,
                    help='Exact kernel drivers/soc/apple/mailbox.c')
args = parser.parse_args()
data = args.source.read_bytes()
if hashlib.sha256(data).hexdigest() != BASE_SHA256:
    parser.exit(1, 'REFUSED: wrong mailbox source checksum; no output created\n')
if not shutil.which('trash-put'):
    raise SystemExit('Install trash-cli: sudo apt-get install -y trash-cli')
root = Path(tempfile.mkdtemp(prefix='azahi-mailbox-poll-'))
try:
    file = root / 'drivers/soc/apple/mailbox.c'
    file.parent.mkdir(parents=True)
    file.write_bytes(data)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(root),
                    '-i', str(Path(__file__).with_name('mailbox-poll-budget.patch').resolve())],
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    source = file.read_text()
    old = data.decode()
    stub=r'''
    #include <assert.h>
    #include <stdbool.h>
    #include <stdint.h>
    #include <stdio.h>
    #include <string.h>
    typedef uint32_t u32;
    typedef int irqreturn_t;
    #define IRQ_HANDLED 1
    #define EXPORT_SYMBOL(x)
    #define APPLE_MBOX_MSG1_MSG 0xffffffffULL
    #define FIELD_GET(mask,value) ((value)&(mask))
    struct apple_mbox_msg { uint64_t msg0,msg1; };
    struct apple_mbox_hw { unsigned i2a_control,i2a_recv0,i2a_recv1,irq_ack;
                          u32 control_empty,irq_bit_recv_not_empty;bool has_irq_controls; };
    struct apple_mbox { unsigned char *regs;struct apple_mbox_hw *hw;int rx_lock;
                       void (*rx)(struct apple_mbox *,struct apple_mbox_msg,void *);void *cookie; };
    static unsigned char regs[64];
    static struct apple_mbox *active;
    static unsigned pending, received, consumed, acknowledgements, control_reads, data_reads;
    static bool endless;
    static void lock(int *p) { assert(*p==0);*p=1; }
    static void unlock(int *p) { assert(*p==1);*p=0; }
    #define spin_lock(p) lock(p)
    #define spin_unlock(p) unlock(p)
    #define spin_lock_irqsave(p,flags) do { (flags)=42;lock(p); } while(0)
    #define spin_unlock_irqrestore(p,flags) do { assert((flags)==42);unlock(p); } while(0)
    static u32 readl_relaxed(unsigned char *p) {
     assert(active->rx_lock==1 && p==regs+active->hw->i2a_control);control_reads++;
     return (endless||pending)?0:active->hw->control_empty;
    }
    static uint64_t readq_relaxed(unsigned char *p) {
     assert(active->rx_lock==1 && (endless||pending));data_reads++;
     /* Abort a regressed infinite loop before the test can hang. */
     assert(consumed<128);
     if (p==regs+active->hw->i2a_recv0) { assert(data_reads%2==1);return consumed+1000; }
     assert(p==regs+active->hw->i2a_recv1 && data_reads%2==0);
     if (!endless) pending--;
     return 0xab00000000000000ULL|consumed++;
    }
    static void writel_relaxed(u32 value,unsigned char *p) {
     assert(active->rx_lock==1 && p==regs+active->hw->irq_ack);
     assert(value==active->hw->irq_bit_recv_not_empty);acknowledgements++;
    }
    static void receive(struct apple_mbox *m,struct apple_mbox_msg msg,void *cookie) {
     assert(m==active && m->rx_lock==1 && cookie==&pending);
     assert(msg.msg0==received+1000 && msg.msg1==received);received++;
    }
    static void reset(unsigned count,bool infinite) {
     pending=count;endless=infinite;received=consumed=acknowledgements=control_reads=data_reads=0;
    }
    '''
    tests=r'''
    int main(void) {
     struct apple_mbox_hw hw={.i2a_control=0,.i2a_recv0=8,.i2a_recv1=16,.irq_ack=24,
                             .control_empty=1,.irq_bit_recv_not_empty=8};
     struct apple_mbox m={.regs=regs,.hw=&hw,.rx=receive,.cookie=&pending};active=&m;
     for (unsigned controls=0;controls<2;controls++) {
      hw.has_irq_controls=controls;
      for (unsigned count=0;count<=70;count++) {
       reset(count,false);
       int n=apple_mbox_poll(&m);unsigned expected=count<32?count:32;
       assert(n==(int)expected && pending==count-expected && received==expected);
       assert(data_reads==2*expected && control_reads==expected+1);
       assert(acknowledgements==controls && m.rx_lock==0);
       assert(apple_mbox_recv_irq(0,&m)==IRQ_HANDLED);
       assert(received==count && pending==0 && acknowledgements==2*controls && m.rx_lock==0);
      }
      reset(0,true);
      assert(apple_mbox_poll(&m)==32 && received==32 && m.rx_lock==0);
      assert(apple_mbox_poll(&m)==32 && received==64 && m.rx_lock==0);
      assert(acknowledgements==2*controls && data_reads==128);
     }
     puts("PASS: bounded polling preserves message pairs, callbacks, locks and acknowledgements");
     puts("PASS: both IRQ variants drain the remainder; a refilled FIFO yields after 32 messages");
     return 0;
    }
    '''
    variants={'current':source,'old':old,
              'no-budget':source.replace('if (budget && ret >= budget)','if (budget && false)'),
              'bounded-irq':source.replace('apple_mbox_poll_locked(mbox, 0)','apple_mbox_poll_locked(mbox, 32)'),
              'drop-message-half':source.replace('msg.msg0 = readq_relaxed(mbox->regs + mbox->hw->i2a_recv0);','msg.msg0 = 0;')}
    for name,text in variants.items():
     start=text.index('static int apple_mbox_poll_locked(');end=text.index('int apple_mbox_start(',start)
     file=root/(name+'-test.c');file.write_text(stub+text[start:end]+tests)
     binary=root/(name+'-test')
     subprocess.run(['gcc','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
                     '-fsanitize=address,undefined','-fno-pie','-no-pie',str(file),'-o',str(binary)],check=True)
     r=subprocess.run([str(binary)],capture_output=True,text=True,timeout=5)
     (root/(name+'-result.txt')).write_text(r.stdout+r.stderr)
     assert (r.returncode==0 if name=='current' else r.returncode!=0 and 'Assertion' in r.stderr),(name,r.stderr)
     if name=='current':print(r.stdout,end='')
    print('Original and three regressions fail runtime assertions')

finally:
    subprocess.run(['trash-put', str(root)], check=True)
