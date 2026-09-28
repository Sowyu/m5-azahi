#!/usr/bin/env python3
"""Check completion validation before NVMMU access using the actual C functions."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--nvme-header', required=True, type=Path)
args = parser.parse_args()
header = args.nvme_header.read_bytes()
if hashlib.sha256(header).hexdigest() != '0ed6fec6c7e7067fca642241e1c8710391f7da949c41759b10ccfa45010b92cf':
    parser.exit(1, 'REFUSED: wrong NVMe header checksum; no output created\n')
source = Path(os.environ.get('AZAHI_NVME_SOURCE', Path(__file__).with_name('apple.c'))).read_text()


def section(text, start, end):
    offset = text.index(start)
    return text[offset:text.index(end, offset)]


lookup = section(header.decode(), 'static inline struct request *nvme_find_rq(',
                 'static inline struct request *nvme_cid_to_rq(')
handler = section(source, 'static inline void apple_nvme_handle_cqe(',
                  'static inline void apple_nvme_update_cq_head(')
stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint16_t __u16;
#define unlikely(x) (x)
#define READ_ONCE(x) (x)
#define NVME_SC_SUCCESS 0
#define nvme_genctr_mask(gen) ((gen) & 0xf)
#define nvme_genctr_from_cid(cid) (((cid) & 0xf000) >> 12)
#define nvme_tag_from_cid(cid) ((cid) & 0xfff)
struct nvme_ctrl { void *device; };
struct nvme_request { unsigned genctr, status; struct nvme_ctrl *ctrl; };
struct request { struct nvme_request nvme; };
struct blk_mq_tags { unsigned depth; struct request requests[64]; };
struct nvme_completion { u16 command_id, status; uint64_t result; };
struct io_comp_batch { unsigned count; };
struct apple_nvme_hw { bool has_lsq_nvmmu; };
struct apple_nvme { void *dev; struct apple_nvme_hw *hw; struct blk_mq_tags tags[2]; };
struct apple_nvme_queue { struct apple_nvme *anv; bool is_adminq; struct nvme_completion *cqes; };
static struct apple_nvme_queue *active;
static struct io_comp_batch *batch;
static unsigned lookups, invalidations, warnings, tried, batched, completed;
static u16 current_cid, current_status;
static unsigned current_gen;
static bool remote_completion, accept_batch, absent;
static bool valid(void) {
 return !absent && nvme_tag_from_cid(current_cid) < active->anv->tags[active->is_adminq].depth &&
        (unsigned)nvme_genctr_from_cid(current_cid) == nvme_genctr_mask(current_gen);
}
static struct nvme_request *nvme_req(struct request *rq) { return &rq->nvme; }
static struct request *blk_mq_tag_to_rq(struct blk_mq_tags *tags, unsigned tag) {
 assert(tags==&active->anv->tags[active->is_adminq]);
 assert(!lookups && !invalidations && !tried);lookups++;
 return tag<tags->depth && !absent ? &tags->requests[tag] : NULL;
}
#define pr_err(...) ((void)0)
#define dev_err(...) ((void)0)
#define dev_warn(...) (warnings++)
static struct apple_nvme *queue_to_apple_nvme(struct apple_nvme_queue *q) { return q->anv; }
static struct blk_mq_tags *apple_nvme_queue_tagset(struct apple_nvme *a, struct apple_nvme_queue *q) {
 assert(q==active && a==q->anv);return &a->tags[q->is_adminq];
}
static void apple_nvmmu_inval(struct apple_nvme_queue *q, unsigned tag) {
 assert(q==active && q->anv->hw->has_lsq_nvmmu);
 assert(lookups==1 && valid() && !invalidations && !tried);
 assert(tag==nvme_tag_from_cid(current_cid));invalidations++;
}
static bool nvme_try_complete_req(struct request *rq, u16 status, uint64_t result) {
 assert(valid() && lookups==1 && !tried && !warnings);
 assert(invalidations==active->anv->hw->has_lsq_nvmmu);
 assert(rq==&active->anv->tags[active->is_adminq].requests[nvme_tag_from_cid(current_cid)]);
 assert(status==current_status && result==UINT64_C(0x0123456789abcdef));
 rq->nvme.status=status>>1;tried++;return remote_completion;
}
static void apple_nvme_complete_batch(struct io_comp_batch *iob) { assert(iob==batch); }
static bool blk_mq_add_to_batch(struct request *rq, struct io_comp_batch *iob,
                              bool error, void (*complete)(struct io_comp_batch *)) {
 assert(tried==1 && !remote_completion && !batched && iob==batch);
 assert(complete==apple_nvme_complete_batch && error==(rq->nvme.status!=NVME_SC_SUCCESS));
 batched++;if(accept_batch)iob->count++;return accept_batch;
}
static void apple_nvme_complete_rq(struct request *rq) {
 assert(tried==1 && batched==1 && !remote_completion && !accept_batch && !completed);completed++;
}
'''
tests = r'''
static void run(struct apple_nvme_queue *q, u16 cid, unsigned gen, u16 status) {
 current_cid=cid;current_gen=gen;current_status=status;
 struct blk_mq_tags *tags=&q->anv->tags[q->is_adminq];
 for(unsigned i=0;i<64;i++)tags->requests[i].nvme.genctr=gen;
 q->cqes[1]=(struct nvme_completion){.command_id=cid,.status=status,.result=UINT64_C(0x0123456789abcdef)};
 lookups=invalidations=warnings=tried=batched=completed=0;batch->count=0;
 apple_nvme_handle_cqe(q,batch,1);
 assert(lookups==1);
 if(!valid()) {
  assert(warnings==1 && !invalidations && !tried && !batched && !completed && !batch->count);
 } else {
  assert(!warnings && tried==1 && invalidations==q->anv->hw->has_lsq_nvmmu);
  assert(batched==!remote_completion);
  assert(completed==(!remote_completion&&!accept_batch));
  assert(batch->count==(!remote_completion&&accept_batch));
 }
}
int main(void) {
 struct apple_nvme_hw hw={0};struct apple_nvme anv={.hw=&hw};
 struct nvme_completion cqes[3]={0};struct io_comp_batch iob={0};
 struct apple_nvme_queue q={.anv=&anv,.cqes=cqes};active=&q;batch=&iob;
 anv.tags[0].depth=63;anv.tags[1].depth=1;
 for(unsigned lsq=0;lsq<2;lsq++)for(unsigned admin=0;admin<2;admin++) {
  hw.has_lsq_nvmmu=lsq;q.is_adminq=admin;
  for(unsigned gen=0;gen<=15;gen+=15)
   for(int cid=UINT16_MAX;cid>=0;cid--)run(&q,cid,gen,0);
 }
 puts("PASS: all 65536 IDs, two generations, both queues and NVMMU variants");
 for(unsigned lsq=0;lsq<2;lsq++)for(unsigned admin=0;admin<2;admin++)
 for(unsigned remote=0;remote<2;remote++)for(unsigned batching=0;batching<2;batching++)
 for(unsigned missing=0;missing<2;missing++)for(unsigned error=0;error<2;error++) {
  hw.has_lsq_nvmmu=lsq;q.is_adminq=admin;remote_completion=remote;
  accept_batch=batching;absent=missing;
  run(&q,0,0,error?0x81:1);
 }
 puts("PASS: missing request, completion routing, status and batch behavior");
 return 0;
}
'''

if not shutil.which('trash-put'):
    parser.exit(1, 'Install trash-cli: sudo apt-get install -y trash-cli\n')
root = Path(tempfile.mkdtemp(prefix='azahi-nvme-completion-'))
try:
    host = root / 'test.c'
    host.write_text(stub + lookup + handler + tests)
    cc = shlex.split(os.environ.get('CC', 'gcc'))
    subprocess.run([*cc, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-parameter', '-Wno-unused-function', '-UNDEBUG',
                    '-fno-pie', '-no-pie', '-fsanitize=address,undefined',
                    str(host), '-o', str(root / 'test')], check=True)
    subprocess.run([str(root / 'test')], check=True, timeout=30)
finally:
    subprocess.run(['trash-put', str(root)], check=True)
