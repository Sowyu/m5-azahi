#!/usr/bin/env python3
"""Check actual queue publication and removal functions without hardware.

The host shim checks publication order, not ARM memory ordering. The exact
kernel build and AArch64 disassembly provide the separate instruction check.
"""
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


functions = section('static void apple_nvme_init_queue(', 'static void apple_nvme_reset_work(')
functions += section('static void apple_nvme_remove(', 'static void apple_nvme_shutdown(')
stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define WRITE_ONCE(x, v) ((x) = (v))
#define wmb() ((void)0)
#define NVME_CTRL_DELETING 7
#define APPLE_ANS_COPROC_CPU_CONTROL 0
struct apple_nvmmu_tcb { unsigned char data[128]; };
struct nvme_completion { unsigned char data[16]; };
struct request_queue { bool dying; };
struct nvme_ctrl { struct request_queue *admin_q; int reset_work; };
struct apple_nvme_hw { bool has_lsq_nvmmu; unsigned max_queue_depth; };
struct apple_nvme { struct nvme_ctrl ctrl; struct apple_nvme_hw *hw; bool *rtk;
                    uint32_t *mmio_coproc; };
struct apple_nvme_queue { struct apple_nvme *anv; bool is_adminq, enabled;
 unsigned sq_tail, cq_head, cq_phase; struct apple_nvmmu_tcb *tcbs;
 struct nvme_completion *cqes; };
struct platform_device { struct apple_nvme *anv; };
static struct apple_nvme_queue *publishing;
static unsigned publications, stage, destroys, unquiesces;
static struct apple_nvme *queue_to_apple_nvme(struct apple_nvme_queue *q) { return q->anv; }
static unsigned apple_nvme_queue_depth(struct apple_nvme_queue *q) {
 return q->is_adminq && q->anv->hw->has_lsq_nvmmu ? 2 : q->anv->hw->max_queue_depth;
}
static bool all_zero(const void *data, unsigned length) {
 const unsigned char *p=data;
 for (unsigned i=0;i<length;i++) if (p[i]) return false;
 return true;
}
static void release_enabled(bool *flag, bool enabled) {
 assert(flag==&publishing->enabled && enabled && !*flag);
 assert(publishing->sq_tail==0 && publishing->cq_head==0 && publishing->cq_phase==1);
 assert(all_zero(publishing->cqes, apple_nvme_queue_depth(publishing)*sizeof(*publishing->cqes)));
 if (publishing->anv->hw->has_lsq_nvmmu)
  assert(all_zero(publishing->tcbs, 64*sizeof(*publishing->tcbs)));
 publications++; *flag=enabled;
}
#define smp_store_release(p,v) release_enabled(p,v)
static struct apple_nvme *platform_get_drvdata(struct platform_device *p) { return p->anv; }
static void nvme_change_ctrl_state(struct nvme_ctrl *c, int state) {
 assert(stage++==0 && state==NVME_CTRL_DELETING);
}
static void flush_work(int *work) { assert(stage++==1); }
static void nvme_stop_ctrl(struct nvme_ctrl *c) { assert(stage++==2); }
static void nvme_remove_namespaces(struct nvme_ctrl *c) { assert(stage++==3); }
static void apple_nvme_disable(struct apple_nvme *a, bool shutdown) { assert(stage++==4 && shutdown); }
static bool blk_queue_dying(struct request_queue *q) { assert(q && stage==5); return q->dying; }
static void nvme_unquiesce_admin_queue(struct nvme_ctrl *c) { assert(stage==5); unquiesces++; }
static void blk_mq_destroy_queue(struct request_queue *q) {
 assert(stage==5 && q && !q->dying && unquiesces==1); destroys++; q->dying=true;
}
static void nvme_uninit_ctrl(struct nvme_ctrl *c) {
 assert(stage++==5 && (!c->admin_q || c->admin_q->dying));
}
static bool apple_rtkit_is_running(bool *r) { assert(stage==6); return *r; }
static void apple_rtkit_shutdown(bool *r) { assert(stage++==6 && *r); }
static void writel(uint32_t value, uint32_t *p) { assert(stage++==7 && value==0); *p=value; }
static void apple_nvme_detach_genpd(struct apple_nvme *a) { assert(stage==(*a->rtk?8:6)); stage=9; }
'''
tests = r'''
int main(void) {
 struct apple_nvmmu_tcb tcbs[64];
 struct nvme_completion cqes[64];
 struct apple_nvme_hw hw={.max_queue_depth=64};
 struct apple_nvme anv={.hw=&hw};
 struct apple_nvme_queue q={.anv=&anv,.tcbs=tcbs,.cqes=cqes};
 publishing=&q;
 for (unsigned lsq=0;lsq<2;lsq++) for (unsigned admin=0;admin<2;admin++) {
  hw.has_lsq_nvmmu=lsq; q.is_adminq=admin;
  q.sq_tail=29; q.cq_head=17; q.cq_phase=0; q.enabled=false; publications=0;
  memset(tcbs,0x5a,sizeof(tcbs)); memset(cqes,0x5a,sizeof(cqes));
  apple_nvme_init_queue(&q);
  assert(q.enabled && publications==1);
  if (!lsq) assert(((unsigned char *)tcbs)[0]==0x5a);
  if (lsq && admin) assert(((unsigned char *)&cqes[2])[0]==0x5a);
 }
 puts("PASS: complete queue initialization precedes release publication");
 struct request_queue adminq;
 struct platform_device pdev={.anv=&anv};
 bool running; uint32_t cpu=99;
 anv.rtk=&running; anv.mmio_coproc=&cpu;
 for (unsigned present=0;present<2;present++)
 for (unsigned dying=0;dying<2;dying++)
 for (unsigned firmware=0;firmware<2;firmware++) {
  running=firmware; adminq.dying=dying; anv.ctrl.admin_q=present?&adminq:NULL;
  stage=destroys=unquiesces=0;
  apple_nvme_remove(&pdev);
  assert(stage==9 && destroys==(present&&!dying) && unquiesces==destroys);
 }
 puts("PASS: admin queue drained and destroyed before controller release; null/dying queues preserved");
 return 0;
}
'''

if not shutil.which('trash-put'):
    raise SystemExit('Install trash-cli: sudo apt-get install -y trash-cli')
root = Path(tempfile.mkdtemp(prefix='azahi-nvme-lifecycle-'))
try:
    host = root / 'test.c'
    host.write_text(stub + functions + tests)
    cc = shlex.split(os.environ.get('CC', 'gcc'))
    subprocess.run([*cc, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-parameter', '-Wno-unused-function', '-UNDEBUG',
                    '-fno-pie', '-no-pie', '-fsanitize=address,undefined',
                    str(host), '-o', str(root / 'test')], check=True)
    subprocess.run([str(root / 'test')], check=True, timeout=30)
finally:
    subprocess.run(['trash-put', str(root)], check=True)
