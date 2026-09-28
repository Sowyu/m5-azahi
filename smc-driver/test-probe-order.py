#!/usr/bin/env python3
"""Exercise actual SMC probe and receive callbacks with early RTKit messages."""
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
parser.add_argument('--patch', type=Path, default=Path(__file__).with_name('sram32.patch'))
parser.add_argument('--init-handshake-header', type=Path,
                    help='Pinned macsmc.h; also test the optional init-handshake.patch')
args = parser.parse_args()
base = args.source.read_bytes()
if hashlib.sha256(base).hexdigest() != '6a8004c39af84de5757ffac8453b3d9822a3e590ff6ac3bf7b1415f52373af0a':
    parser.error('Wrong pinned macsmc.c checksum')
header = args.init_handshake_header.read_bytes() if args.init_handshake_header else None
if header is not None and hashlib.sha256(header).hexdigest() != \
        '2d9a64e924e1aa5cf5d75db9f1570be3c7178aaf955a22121ff8f15b929eaa54':
    parser.error('Wrong pinned macsmc.h checksum')
if not shutil.which('trash-put'):
    parser.error('Install trash-cli: sudo apt-get install -y trash-cli')
root = Path(tempfile.mkdtemp(prefix='azahi-smc-probe-'))

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
#define SMC_ENDPOINT 0x20
#define SMC_SHMEM_SIZE 4096
#define SMC_TIMEOUT_MS 500
#define SMC_MSG_INITIALIZE 0x17
#define SMC_MSG_NOTIFICATION 0x18
#define SMC_MSG UINT64_C(0xff)
#define SMC_ID UINT64_C(0xf000)
#define SMC_DATA UINT64_C(0xffffffff00000000)
#define FIELD_PREP(m,v) (((u64)(v) << __builtin_ctzll(m)) & (m))
#define FIELD_GET(m,v) (((u64)(v) & (m)) >> __builtin_ctzll(m))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define cmpxchg(p,old,new) __sync_val_compare_and_swap(p,old,new)
#define IS_ALIGNED(v,n) (((v) & ((n)-1)) == 0)
#define GFP_KERNEL 0
#define IS_ERR(p) ((intptr_t)(p) < 0 && (intptr_t)(p) >= -4095)
#define PTR_ERR(p) ((intptr_t)(p))
#define dev_err_probe(dev,err,...) (err)
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_warn_ratelimited(...) ((void)0)
#define msecs_to_jiffies(v) (v)
enum apple_smc_boot_stage { APPLE_SMC_BOOTING, APPLE_SMC_INITIALIZED,
 APPLE_SMC_ERROR_NO_SHMEM, APPLE_SMC_ERROR_CRASHED, APPLE_SMC_PRE_INIT };
struct completion { bool initialized; unsigned done; };
struct blocking_notifier_head { bool initialized; unsigned calls; };
struct device { void *data; };
struct platform_device { struct device dev; };
struct apple_rtkit_shmem { u64 iova; unsigned size; void *iomem; };
struct apple_smc {
 int mutex, lock, boot_stage;
 struct completion init_done, cmd_done;
 struct blocking_notifier_head event_handlers;
 struct device *dev;
 void *sram, *sram_base, *rtk;
 struct apple_rtkit_shmem shmem;
 u64 cmd_ret;
 unsigned msg_id;
 bool atomic_pending;
};
static struct apple_smc storage;
static bool sram32;
static unsigned scenario, sends, waits, early_messages, notifications;
static void mutex_init(int *p) { assert(!*p); *p=1; }
static void spin_lock_init(int *p) { assert(!*p); *p=1; }
static void init_completion(struct completion *c) {
 assert(!c->initialized); c->initialized=true; c->done=0;
}
static void reinit_completion(struct completion *c) {
 assert(c->initialized); c->done=0;
}
static void complete(struct completion *c) {
 assert(c->initialized); c->done++;
}
static void notifier_init(struct blocking_notifier_head *h) {
 assert(!h->initialized); h->initialized=true; h->calls=0;
}
#define BLOCKING_INIT_NOTIFIER_HEAD(h) notifier_init(h)
static void blocking_notifier_call_chain(struct blocking_notifier_head *h, u64 v, void *data) {
 assert(h->initialized && v==42 && !data); h->calls++; notifications++;
}
static void *devm_kzalloc(struct device *d, size_t n, unsigned flags) {
 assert(n==sizeof(storage)); memset(&storage,0,n); return &storage;
}
static void *devm_platform_get_and_ioremap_resource(struct platform_device *p, unsigned index, void **r) {
 assert(index==1); *r=&storage; return &storage;
}
static bool of_machine_is_compatible(const char *name) {
 assert(!strcmp(name,"apple,j714s")); return true;
}
static void apple_smc_rtkit_crashed(void *, const void *, size_t);
static int apple_smc_rtkit_shmem_setup(struct apple_smc *s, struct apple_rtkit_shmem *b) {
 assert(b->size==SMC_SHMEM_SIZE); b->iomem=&storage;
 if (scenario==13 || scenario==14) apple_smc_rtkit_crashed(s,NULL,0);
 return scenario==14 ? -EIO : 0;
}
static void apple_smc_rtkit_shutdown(void *p) { assert(!"must not shut down hardware"); }
static int devm_add_action_or_reset(struct device *d, void (*action)(void *), void *data) {
 assert(action==apple_smc_rtkit_shutdown && data==&storage); return 0;
}
static void dev_set_drvdata(struct device *d, void *p) { d->data=p; }
static int apple_smc_rtkit_ops;
static bool apple_smc_rtkit_recv_early(void *, u8, u64);
static void apple_smc_rtkit_recv(void *, u8, u64);
static void deliver(u64 message) {
 early_messages++;
 if (!apple_smc_rtkit_recv_early(&storage,SMC_ENDPOINT,message))
  apple_smc_rtkit_recv(&storage,SMC_ENDPOINT,message);
}
static void *devm_apple_rtkit_init(struct device *d, void *cookie, const char *name,
                                  unsigned index, const void *ops) {
 assert(cookie==&storage && !name && !index && ops==&apple_smc_rtkit_ops);
 assert(storage.mutex && storage.dev==d && storage.sram_base);
 if (scenario==1 || scenario==2) {
  /* A stale initialization reply, then a command reply and notification. */
  deliver(0x1000);
  assert(storage.boot_stage==(PHASE_GUARD ? APPLE_SMC_PRE_INIT : APPLE_SMC_INITIALIZED));
  deliver(FIELD_PREP(SMC_ID,storage.msg_id));
  deliver(SMC_MSG_NOTIFICATION | FIELD_PREP(SMC_DATA,42));
 }
 if (scenario==10) apple_smc_rtkit_crashed(&storage,NULL,0);
 return scenario==4 ? (void *)(intptr_t)-ENOMEM : &storage;
}
static int apple_rtkit_wake(void *rtk) {
 if (scenario==3) {
  deliver(0x1000);
  deliver(FIELD_PREP(SMC_ID,storage.msg_id));
  deliver(SMC_MSG_NOTIFICATION | FIELD_PREP(SMC_DATA,42));
 }
 if (scenario==11) apple_smc_rtkit_crashed(&storage,NULL,0);
 return scenario==5 ? -EIO : 0;
}
static int apple_rtkit_start_ep(void *rtk, u8 endpoint) {
 if (scenario==9) {
  deliver(0x1000);
  deliver(FIELD_PREP(SMC_ID,storage.msg_id));
  deliver(SMC_MSG_NOTIFICATION | FIELD_PREP(SMC_DATA,42));
 }
 if (scenario==12) apple_smc_rtkit_crashed(&storage,NULL,0);
 assert(endpoint==SMC_ENDPOINT); return scenario==6 ? -EIO : 0;
}
static int apple_rtkit_send_message(void *rtk, u8 ep, u64 message, void *done, bool atomic) {
 assert(ep==SMC_ENDPOINT && message==SMC_MSG_INITIALIZE && !done && !atomic);
 sends++;
 if (scenario==7) return -EIO;
 if (scenario!=2 && scenario!=8) deliver(0x2000);
 return 0;
}
static unsigned wait_for_completion_timeout(struct completion *c, unsigned ms) {
 assert(c==&storage.init_done && c->initialized && ms==SMC_TIMEOUT_MS);
 waits++;
 if (!c->done) return 0;
 c->done--; return 1;
}
'''
TEST = r'''
int main(void) {
 for (scenario=0; scenario<=(PHASE_GUARD ? 14 : 8); scenario++) {
  struct platform_device p={0};
  sends=waits=early_messages=notifications=0;
  sram32=scenario&1;
  int ret=apple_smc_probe(&p);
  int expected=(scenario==2 || (!PHASE_GUARD && scenario==3) || scenario==8) ? -ETIMEDOUT :
               scenario==4 ? -ENOMEM :
               (scenario==5 || scenario==6 || scenario==7 || scenario>=10) ? -EIO : 123;
  assert(ret==expected);
  if (ret==123) {
   assert(p.dev.data==&storage && storage.boot_stage==APPLE_SMC_INITIALIZED);
   assert(storage.shmem.iova==0x2000 && sends==1 && waits==1);
  }
  if (scenario==1 || scenario==2 || scenario==3 || scenario==9) {
   assert(notifications==(PHASE_GUARD ? 0 : 1));
   assert(storage.event_handlers.calls==notifications);
   assert(!storage.cmd_done.done);
  }
  if (scenario>=4 && scenario<=6) assert(!sends && !waits);
  if (scenario==7) assert(sends==1 && !waits);
  if (scenario>=10) assert(storage.boot_stage==APPLE_SMC_ERROR_CRASHED);
  if (scenario>=10 && scenario<=12) assert(!sends && !waits);
  if (ret==123) {
   unsigned previous=notifications;
   deliver(SMC_MSG_NOTIFICATION | FIELD_PREP(SMC_DATA,42));
   deliver(FIELD_PREP(SMC_ID,storage.msg_id));
   assert(notifications==previous+1 && storage.cmd_done.done==1);
  }
 }
 puts(PHASE_GUARD ? "PASS: 15 probe paths, pre-init replies discarded, wake/endpoint success, crash stays terminal" :
                   "PASS: 9 probe paths, early init/command/notification, fresh reply required, error propagation");
}
'''

def fixture(source):
    crashed = source[source.index('static void apple_smc_rtkit_crashed('):
                     source.index('static int apple_smc_rtkit_shmem_setup(')]
    callbacks = source[source.index('static bool apple_smc_rtkit_recv_early('):
                       source.index('static const struct apple_rtkit_ops')]
    probe = source[source.index('static int apple_smc_probe('):
                   source.index('\tret = apple_smc_read_u32(')]
    return f'#define PHASE_GUARD {int(header is not None)}\n' + STUB + crashed + callbacks + probe + '\treturn 123;\n}\n' + TEST

def run(name, source, fail=False):
    c = root / (name + '.c')
    binary = root / name
    c.write_text(fixture(source))
    subprocess.run(shlex.split(os.environ.get('CC', 'cc')) + [
        '-std=gnu11', '-Wall', '-Wextra', '-Wno-unused-parameter',
        '-Wno-unused-function', '-Wno-unused-variable', '-fsanitize=address,undefined',
        '-fno-omit-frame-pointer', '-g', '-no-pie', str(c), '-o', str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
    (root / (name + '.log')).write_text(result.stdout + result.stderr)
    if fail:
        assert result.returncode and 'Assertion' in result.stderr, name + ' did not catch regression'
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        print(result.stdout.strip())

try:
    p = root / 'drivers/mfd/macsmc.c'
    p.parent.mkdir(parents=True)
    p.write_bytes(base)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(root),
                    '-i', str(args.patch.resolve())], check=True)
    if header is not None:
        h = root / 'include/linux/mfd/macsmc.h'
        h.parent.mkdir(parents=True)
        h.write_bytes(header)
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(root),
                        '-i', str(Path(__file__).with_name('init-handshake.patch').resolve())], check=True)
    source = p.read_text()
    run('candidate', source)
    run('original', base.decode(), fail=True)
    if header is not None:
        line = '\tsmc->boot_stage = APPLE_SMC_PRE_INIT;\n'
        assert source.count(line)==1
        run('unarmed', source.replace(line,'',1), fail=True)
        line = '\tif (stage == APPLE_SMC_PRE_INIT)\n\t\treturn true;\n'
        assert source.count(line)==1
        run('accept-pre-init', source.replace(line,'',1), fail=True)
        line = '\t\tcmpxchg(&smc->boot_stage, APPLE_SMC_BOOTING,\n\t\t\tret < 0 ? APPLE_SMC_ERROR_NO_SHMEM : APPLE_SMC_INITIALIZED);'
        assert source.count(line)==1
        run('revive-after-crash', source.replace(line,
            '\t\tWRITE_ONCE(smc->boot_stage, ret < 0 ? APPLE_SMC_ERROR_NO_SHMEM : APPLE_SMC_INITIALIZED);',1), fail=True)
        line = '\tif (cmpxchg(&smc->boot_stage, APPLE_SMC_PRE_INIT, APPLE_SMC_BOOTING) !=\n\t    APPLE_SMC_PRE_INIT)\n\t\treturn dev_err_probe(dev, -EIO, "SMC failed before initialization\\n");'
        assert source.count(line)==1
        run('rearm-after-crash', source.replace(line,
            '\tWRITE_ONCE(smc->boot_stage, APPLE_SMC_BOOTING);',1), fail=True)
        print('PASS: original failure and four init-phase/crash mutations detected')
        raise SystemExit(0)
    initial = '\tinit_completion(&smc->{field});\n'
    for field in ('init_done', 'cmd_done'):
        line = initial.format(field=field)
        assert source.count(line)==1
        mutant=source.replace(line,'',1).replace('\tret = apple_rtkit_start_ep(',
                                               line+'\tret = apple_rtkit_start_ep(',1)
        run('late-'+field, mutant, fail=True)
    line='\tBLOCKING_INIT_NOTIFIER_HEAD(&smc->event_handlers);\n'
    assert source.count(line)==1
    run('late-notifier', source.replace(line,'',1).replace('\tdev_set_drvdata(',
        line+'\tdev_set_drvdata(',1), fail=True)
    line='\treinit_completion(&smc->init_done);\n'
    assert source.count(line)==1
    run('stale-init',source.replace(line,'',1),fail=True)
    print('PASS: original failure and four ordering/completion mutations detected')
finally:
    subprocess.run(['trash-put', str(root)], check=True)
