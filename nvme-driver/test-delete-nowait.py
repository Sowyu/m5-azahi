#!/usr/bin/env python3
"""Compare the original and optional queue-deletion paths without hardware.

Uses the pinned kernel's actual synchronous-command helper and the driver's
actual deletion, disable and timeout functions. Tag allocation, completions
and controller stop are host models. Failed-stop cancellation remains an
expected inherited defect, not evidence of safe recovery.
"""
import argparse
import hashlib
import os
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
helpers = runpy.run_path(str(ROOT / 'smp/test-smp-diag.py'))
extract = helpers['extract']
CORE_SHA = '4fd0aa8a17a44d5fa20ea4d92af5dac989fe2f596f19419eb9ac871a65b68122'

STUB = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <setjmp.h>
typedef uint32_t u32;
typedef unsigned nvme_submit_flags_t;
typedef unsigned blk_mq_req_flags_t;
enum nvme_ctrl_state { NVME_CTRL_LIVE, NVME_CTRL_RESETTING, NVME_CTRL_DELETING };
enum blk_eh_timer_return { BLK_EH_DONE };
#define NVME_SUBMIT_AT_HEAD 1
#define NVME_SUBMIT_NOWAIT 2
#define NVME_SUBMIT_RESERVED 4
#define NVME_SUBMIT_RETRY 8
#define BLK_MQ_REQ_NOWAIT 1
#define BLK_MQ_REQ_RESERVED 2
#define NVME_QID_ANY -1
#define REQ_FAILFAST_DRIVER 1
#define NVME_REQ_CANCELLED 1
#define NVME_SC_HOST_ABORTED_CMD 0x371
#define NVME_REG_CSTS 0
#define NVME_CSTS_RDY 1
#define NVME_CSTS_CFS 2
#define NVME_IO_TIMEOUT 30
#define GFP_KERNEL 0
#define cpu_to_le16(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define smp_load_acquire(p) (*(p))
#define mb() ((void)0)
#define spin_lock_irqsave(lock,flags) ((void)(lock),(flags)=0)
#define spin_unlock_irqrestore(lock,flags) ((void)(lock),(void)(flags))
#define dev_warn(...) ((void)0)
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define ERR_PTR(n) ((void *)(intptr_t)(n))
enum { nvme_admin_delete_sq=0, nvme_admin_delete_cq=4 };
union nvme_result { u32 u32; };
struct nvme_command { struct { unsigned opcode, qid; } delete_queue; };
struct apple_nvme;
struct apple_nvme_queue { struct apple_nvme *anv; bool is_adminq, enabled; };
struct apple_nvme_iod { struct apple_nvme_queue *q; };
struct nvme_request { unsigned status, flags; union nvme_result result; };
struct request {
 unsigned tag, cmd_flags; bool started, completed;
 struct apple_nvme_iod iod; struct nvme_request nvme; struct nvme_command cmd;
};
struct request_queue { struct request *owner; };
struct nvme_ctrl { enum nvme_ctrl_state state; struct request_queue *admin_q; };
struct apple_nvme {
 struct nvme_ctrl ctrl; struct apple_nvme_queue ioq, adminq;
 u32 *mmio_nvme; bool *rtk; int lock;
};
static struct request_queue admin;
static struct apple_nvme anv;
static struct request original, allocated;
static u32 csts;
static bool crashed, stalled_delete, polled, stopped, stop_fails;
static unsigned allocations, executions, frees, blocks, stops, cancels, resets, unsafe_cancels;
static int command_status, allocation_error;
static jmp_buf escaped;
static enum blk_eh_timer_return apple_nvme_timeout(struct request *req);
static struct nvme_request *nvme_req(struct request *r) { return &r->nvme; }
static struct apple_nvme_iod *blk_mq_rq_to_pdu(struct request *r) { return &r->iod; }
static struct apple_nvme *queue_to_apple_nvme(struct apple_nvme_queue *q) { return q->anv; }
static enum nvme_ctrl_state nvme_ctrl_state(struct nvme_ctrl *c) { return c->state; }
static u32 readl(u32 *p) { assert(p==&csts); return *p; }
static bool apple_rtkit_is_crashed(bool *r) { return *r; }
static bool blk_mq_request_started(struct request *r) { return r->started; }
static bool blk_mq_request_completed(struct request *r) { return r->completed; }
static void blk_mq_complete_request(struct request *r) { r->completed=true; }
static unsigned nvme_req_op(struct nvme_command *cmd) {
 assert(cmd->delete_queue.opcode==nvme_admin_delete_sq || cmd->delete_queue.opcode==nvme_admin_delete_cq);
 assert(cmd->delete_queue.qid==1); return cmd->delete_queue.opcode;
}
static struct request *blk_mq_alloc_request(struct request_queue *q, unsigned op, unsigned flags) {
 assert(q==&admin && (op==0 || op==4)); allocations++;
 assert(!(flags & BLK_MQ_REQ_RESERVED));
 if (q->owner) {
  if (!(flags & BLK_MQ_REQ_NOWAIT)) { blocks++; longjmp(escaped,1); }
  return ERR_PTR(-EWOULDBLOCK);
 }
 if (allocation_error) return ERR_PTR(allocation_error);
 memset(&allocated,0,sizeof(allocated)); allocated.iod.q=&anv.adminq;
 q->owner=&allocated; return &allocated;
}
static struct request *blk_mq_alloc_request_hctx(struct request_queue *q, unsigned op, unsigned flags, int hctx) {
 (void)q; (void)op; (void)flags; (void)hctx; assert(0); return NULL;
}
static void nvme_init_request(struct request *r, struct nvme_command *cmd) { r->cmd=*cmd; }
static int blk_rq_map_kern(struct request *r, void *b, unsigned n, unsigned gfp) {
 (void)r; (void)b; (void)n; (void)gfp; assert(0); return 0;
}
static int nvme_execute_rq(struct request *r, bool head) {
 assert(r==&allocated && !head); executions++; r->started=true;
 if (stalled_delete && anv.adminq.enabled) {
  stalled_delete=false;
  assert(apple_nvme_timeout(r)==BLK_EH_DONE);
  assert(r->completed);
  return -EINTR;
 }
 r->completed=true;
 return command_status;
}
static void blk_mq_free_request(struct request *r) {
 assert(r==admin.owner && r->completed); admin.owner=NULL; frees++;
}
static void nvme_start_freeze(struct nvme_ctrl *c) { (void)c; }
static void nvme_wait_freeze_timeout(struct nvme_ctrl *c, unsigned t) { (void)c; assert(t==NVME_IO_TIMEOUT); }
static void nvme_quiesce_io_queues(struct nvme_ctrl *c) { (void)c; }
static void nvme_quiesce_admin_queue(struct nvme_ctrl *c) { (void)c; }
static void nvme_unquiesce_io_queues(struct nvme_ctrl *c) { (void)c; }
static void nvme_unquiesce_admin_queue(struct nvme_ctrl *c) { (void)c; }
static int nvme_disable_ctrl(struct nvme_ctrl *c, bool shutdown) {
 (void)c; assert(!shutdown); stops++; stopped=!stop_fails;
 return stop_fails ? -ENODEV : 0;
}
static void apple_nvme_handle_cq(struct apple_nvme_queue *q, bool force) {
 (void)q;
 if (polled && !force) original.completed=true;
}
static void nvme_cancel_tagset(struct nvme_ctrl *c) {
 (void)c;
 if (!stopped) { unsafe_cancels++; longjmp(escaped,2); }
 cancels++; if (original.iod.q==&anv.ioq) original.completed=true;
}
static void nvme_cancel_admin_tagset(struct nvme_ctrl *c) {
 (void)c; assert(stopped); cancels++;
 if (admin.owner) admin.owner->completed=true;
}
static void nvme_reset_ctrl(struct nvme_ctrl *c) { resets++; c->state=NVME_CTRL_RESETTING; }
'''
TESTS = r'''
static void setup(void) {
 memset(&anv,0,sizeof(anv)); memset(&original,0,sizeof(original));
 memset(&allocated,0,sizeof(allocated)); admin.owner=NULL;
 anv.ctrl.state=NVME_CTRL_LIVE; anv.ctrl.admin_q=&admin;
 anv.ioq=(struct apple_nvme_queue){.anv=&anv,.enabled=true};
 anv.adminq=(struct apple_nvme_queue){.anv=&anv,.is_adminq=true,.enabled=true};
 original.iod.q=&anv.adminq; original.started=true;
 csts=NVME_CSTS_RDY; anv.mmio_nvme=&csts; anv.rtk=&crashed;
 crashed=stalled_delete=polled=stopped=stop_fails=false;
 allocations=executions=frees=blocks=stops=cancels=resets=unsafe_cancels=0;
 command_status=allocation_error=0;
}
int main(void) {
 int (*remove[])(struct apple_nvme *)={apple_nvme_remove_sq,apple_nvme_remove_cq};
 for (volatile unsigned i=0;i<2;i++) {
  const int statuses[]={0,0x123,-EIO};
  for (unsigned n=0;n<3;n++) {
   setup(); command_status=statuses[n];
   assert(remove[i](&anv)==statuses[n]);
   assert(allocations==1 && executions==1 && frees==1 && !admin.owner);
  }
  const int errors[]={-ENOMEM,-ENODEV,-EWOULDBLOCK};
  for (unsigned n=0;n<3;n++) {
   setup(); allocation_error=errors[n];
   assert(remove[i](&anv)==errors[n]);
   assert(allocations==1 && !executions && !frees);
  }
  setup(); admin.owner=&original;
  if (!setjmp(escaped)) {
   assert(remove[i](&anv)==-EWOULDBLOCK); assert(EXPECT_NOWAIT);
  } else assert(!EXPECT_NOWAIT);
  assert(blocks==!EXPECT_NOWAIT && !executions && !frees);
  assert(admin.owner==&original && !original.completed);
 }
 puts("PASS: command results, allocation errors and occupied-tag behavior compared");
 setup(); admin.owner=&original;
 if (!setjmp(escaped)) {
  assert(apple_nvme_timeout(&original)==BLK_EH_DONE); assert(EXPECT_NOWAIT);
 } else assert(!EXPECT_NOWAIT);
 if (EXPECT_NOWAIT) {
  assert(allocations==2 && !executions && stops==1 && cancels==2 && resets==1);
  assert(original.completed && (original.nvme.flags & NVME_REQ_CANCELLED));
 } else assert(blocks==1 && !stops && !cancels && !resets);
 puts("PASS: original live-admin timeout cycle reproduced; candidate passes allocation");
 setup(); original.iod.q=&anv.ioq; stalled_delete=true;
 if (!setjmp(escaped)) {
  assert(apple_nvme_timeout(&original)==BLK_EH_DONE); assert(EXPECT_NOWAIT);
 } else assert(!EXPECT_NOWAIT);
 if (EXPECT_NOWAIT) assert(original.completed && !admin.owner && cancels==4 && resets==2 && frees==2);
 else assert(blocks==1 && !stops && !cancels);
 puts("PASS: nested delete timeout modeled with the admin tag held until command release");
 setup(); admin.owner=&original; polled=true;
 assert(apple_nvme_timeout(&original)==BLK_EH_DONE);
 assert(original.completed && !allocations && !stops && !resets);
 setup(); admin.owner=&original; anv.ctrl.state=NVME_CTRL_RESETTING;
 assert(apple_nvme_timeout(&original)==BLK_EH_DONE);
 assert(original.completed && original.nvme.status==NVME_SC_HOST_ABORTED_CMD && !allocations);
 puts("PASS: missed-interrupt and non-live timeout branches preserved");
 setup(); stop_fails=true;
 int reason=setjmp(escaped);
 if (!reason) { apple_nvme_disable(&anv,false); assert(0); }
 assert(reason==2 && unsafe_cancels==1 && stops==1 && !stopped);
 puts("EXPECTED LIMIT: both versions reach cancellation after a failed controller stop");
 return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nvme-core', required=True, type=Path)
    parser.add_argument('--apple-source', type=Path, default=ROOT / 'nvme-driver/apple.c')
    parser.add_argument('--patch', type=Path, default=ROOT / 'nvme-driver/delete-nowait.patch')
    args = parser.parse_args()
    core = args.nvme_core.read_bytes()
    if hashlib.sha256(core).hexdigest() != CORE_SHA:
        parser.error('Pass the unmodified core.c from the pinned 7.0.13 kernel')
    core = core.decode()
    sync = extract(core, 'int __nvme_submit_sync_cmd(') + '\n' + extract(core, 'int nvme_submit_sync_cmd(')
    root = helpers['temporary_build']()
    try:
        shutil.copyfile(args.apple_source, root / 'apple.c')
        original = (root / 'apple.c').read_text()
        subprocess.run(['patch', '--batch', '--fuzz=0', '--forward', '--no-backup-if-mismatch',
                        '-p1', '-d', str(root), '-i', str(args.patch.resolve())], check=True)
        candidate = (root / 'apple.c').read_text()
        for index, source in enumerate((original, candidate)):
            print('Checking candidate' if index else 'Checking original', flush=True)
            functions = '\n'.join(extract(source, name) for name in (
                'static int apple_nvme_remove_cq(', 'static int apple_nvme_remove_sq(',
                'static void apple_nvme_disable(', 'static enum blk_eh_timer_return apple_nvme_timeout('))
            host = root / f'check-{index}.c'
            host.write_text(f'#define EXPECT_NOWAIT {index}\n' + STUB + sync + functions + TESTS)
            cc = shlex.split(os.environ.get('CC', 'gcc'))
            exe = root / f'check-{index}'
            subprocess.run([*cc, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-function', '-UNDEBUG', '-fno-pie', '-no-pie',
                            '-fsanitize=address,undefined', str(host), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True, timeout=30)
    finally:
        subprocess.run(['trash-put', str(root)], check=True)


if __name__ == '__main__':
    main()
