#!/usr/bin/env python3
"""Exercise the actual J714s submission/sleep guards without hardware access."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
source = Path(os.environ.get('AZAHI_NVME_SOURCE', HERE / 'apple.c')).read_text()


def section(start, end):
    offset = source.index(start)
    return source[offset:source.index(end, offset)]


functions = section('static blk_status_t apple_nvme_queue_rq(',
                    'static int apple_nvme_init_hctx(')
functions += section('static int apple_nvme_prepare(',
                     'static const struct dev_pm_ops apple_nvme_pm_ops')
stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <errno.h>
#define READ_ONCE(x) (x)
#define smp_load_acquire(p) (*(p))
#define unlikely(x) (x)
#define BIT(n) (UINT32_C(1) << (n))
#define le32_to_cpu(x) (x)
#define dev_warn_ratelimited(...) ((void)0)
#define dev_err(...) ((void)0)
#define NVME_REQ_USERCMD 2
enum { nvme_cmd_read=2, nvme_admin_delete_sq=0, nvme_admin_create_sq=1,
 nvme_admin_get_log_page=2, nvme_admin_delete_cq=4, nvme_admin_create_cq=5,
 nvme_admin_identify=6, nvme_admin_set_features=9, nvme_admin_get_features=10 };
typedef int blk_status_t;
enum { BLK_STS_OK, BLK_STS_IOERR, SETUP_ERROR, MAP_ERROR, NOT_READY };
struct nvme_ns { int unused; };
struct nvme_command { union {
 struct { uint8_t opcode; } common;
 struct { uint8_t opcode; uint32_t fid; } features;
}; };
struct apple_nvme_iod { int npages, nents; struct nvme_command cmd; };
struct nvme_request { unsigned flags; };
struct request { struct apple_nvme_iod iod; struct nvme_request nvme; int segments; };
struct apple_nvme_hw { bool j714s_readonly, has_lsq_nvmmu; };
struct apple_nvme { struct apple_nvme_hw *hw; int ctrl; };
struct apple_nvme_queue { struct apple_nvme *anv; bool enabled, is_adminq; };
struct request_queue { struct nvme_ns *queuedata; };
struct blk_mq_hw_ctx { struct request_queue *queue; struct apple_nvme_queue *driver_data; };
struct blk_mq_queue_data { struct request *rq; };
struct device { struct apple_nvme *data; };
static bool ready=true;
static int setup_result, map_result, setups, maps, starts, submits, cleanups;
static struct apple_nvme *queue_to_apple_nvme(struct apple_nvme_queue *q) { return q->anv; }
static struct apple_nvme_iod *blk_mq_rq_to_pdu(struct request *r) { return &r->iod; }
static struct nvme_request *nvme_req(struct request *r) { return &r->nvme; }
static bool nvme_check_ready(int *ctrl, struct request *r, bool queue) { return ready; }
static int nvme_fail_nonready_command(int *ctrl, struct request *r) { return NOT_READY; }
static int nvme_setup_cmd(struct nvme_ns *ns, struct request *r) { setups++; return setup_result; }
static int blk_rq_nr_phys_segments(struct request *r) { return r->segments; }
static int apple_nvme_map_data(struct apple_nvme *a, struct request *r, struct nvme_command *c) {
 assert(setups==1 && !starts && !submits); maps++; return map_result;
}
static void nvme_start_request(struct request *r) { assert(!submits); starts++; }
static void apple_nvme_submit_cmd_t8103(struct apple_nvme_queue *q, struct nvme_command *c) {
 assert(starts==1); submits++;
}
static void apple_nvme_submit_cmd_t8015(struct apple_nvme_queue *q, struct nvme_command *c) {
 assert(starts==1); submits++;
}
static void nvme_cleanup_cmd(struct request *r) { assert(!starts && !submits); cleanups++; }
static struct apple_nvme *dev_get_drvdata(struct device *d) { return d->data; }
static void reset_counts(void) { setups=maps=starts=submits=cleanups=0; }
'''
tests = r'''
int main(void) {
 struct apple_nvme_hw hw={.j714s_readonly=true,.has_lsq_nvmmu=true};
 struct apple_nvme anv={.hw=&hw};
 struct apple_nvme_queue q={.anv=&anv,.enabled=true};
 struct request req={.segments=1};
 struct request_queue queue={0};
 struct blk_mq_hw_ctx ctx={.queue=&queue,.driver_data=&q};
 struct blk_mq_queue_data bd={.rq=&req};
 /* All opcodes, both queues, ioctl/internal origin, Save bit and DMA paths. */
 for (unsigned admin=0;admin<2;admin++)
 for (unsigned user=0;user<2;user++)
 for (unsigned save=0;save<2;save++)
 for (unsigned dma=0;dma<2;dma++)
 for (unsigned op=0;op<256;op++) {
  q.is_adminq=admin; req.nvme.flags=user?NVME_REQ_USERCMD:0;
  req.iod.cmd.common.opcode=op; req.iod.cmd.features.fid=save?BIT(31):0;
  req.segments=dma; req.iod.npages=99; req.iod.nents=99;
  bool allowed=admin ? (op==2 || op==6 || op==10 || (op==9 && !save) ||
                       ((op==0 || op==1 || op==4 || op==5) && !user)) : op==2;
  reset_counts(); int ret=apple_nvme_queue_rq(&ctx,&bd);
  assert(req.iod.npages==-1 && req.iod.nents==0 && setups==1);
  assert(ret==(allowed?BLK_STS_OK:BLK_STS_IOERR));
  assert(maps==(allowed && dma) && starts==allowed && submits==allowed);
  assert(cleanups==!allowed);
 }
 puts("PASS: all 4096 command combinations enforce the read-only guard before DMA/submission");

 req.iod.cmd.common.opcode=2; req.segments=1; q.is_adminq=false;
 q.enabled=false; reset_counts();
 assert(apple_nvme_queue_rq(&ctx,&bd)==BLK_STS_IOERR && !setups && !maps && !submits);
 q.enabled=true; ready=false; reset_counts();
 assert(apple_nvme_queue_rq(&ctx,&bd)==NOT_READY && !setups && !maps && !submits);
 ready=true; setup_result=SETUP_ERROR; reset_counts();
 assert(apple_nvme_queue_rq(&ctx,&bd)==SETUP_ERROR && !maps && !submits && !cleanups);
 setup_result=0; map_result=MAP_ERROR; reset_counts();
 assert(apple_nvme_queue_rq(&ctx,&bd)==MAP_ERROR && maps==1 && cleanups==1 && !submits);
 map_result=0;
 /* Legacy boards retain their submission path; this is a J714s restriction. */
 hw.j714s_readonly=false;
 for (unsigned lsq=0;lsq<2;lsq++) {
  hw.has_lsq_nvmmu=lsq; req.iod.cmd.common.opcode=1; reset_counts();
  assert(apple_nvme_queue_rq(&ctx,&bd)==BLK_STS_OK && maps==1 && submits==1);
 }
 struct device dev={.data=&anv};
 assert(apple_nvme_prepare(&dev)==0);
 hw.j714s_readonly=true;
 assert(apple_nvme_prepare(&dev)==-EBUSY);
 puts("PASS: queue/error paths contained, legacy submission retained, J714s sleep refused");
 return 0;
}
'''

if not shutil.which('trash-put'):
    raise SystemExit('Install trash-cli: sudo apt-get install -y trash-cli')
root = Path(tempfile.mkdtemp(prefix='azahi-readonly-test-'))
try:
    host = root / 'test.c'
    host.write_text(stub + functions + tests)
    cc = shlex.split(os.environ.get('CC', 'gcc'))
    subprocess.run([*cc, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-parameter', '-UNDEBUG', '-fno-pie', '-no-pie',
                    '-fsanitize=address,undefined', str(host), '-o', str(root / 'test')], check=True)
    subprocess.run([str(root / 'test')], check=True, timeout=30)
    guard = subprocess.run([*cc, '-x', 'c', '-fsyntax-only', '-D__KERNEL__',
                            '-DAZAHI_ROOT_WRITES=1', '-include', 'stdbool.h',
                            '-include', str(HERE / 'root-write-policy.h'), '-'],
                           input='', text=True, capture_output=True)
    assert guard.returncode != 0
    assert 'Public reference only: independently audit storage boundaries' in guard.stderr
    print('PASS: public rootguard kernel compilation remains blocked')
finally:
    subprocess.run(['trash-put', str(root)], check=True)
