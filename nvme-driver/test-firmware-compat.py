#!/usr/bin/env python3
"""Check patched NVMe core alignment and actual firmware command encoding."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-dir', type=Path, required=True,
                    help='The paired build src/nvme-driver directory')
args = parser.parse_args()
src = args.source_dir
if not shutil.which('trash-put'):
    raise SystemExit('Install trash-cli: sudo apt-get install -y trash-cli')
out = Path(tempfile.mkdtemp(prefix='azahi-nvme-firmware-'))
try:
    def section(text,start,end):
        i=text.index(start);return text[i:text.index(end,i)]
    core=(src/'core.c').read_text();apple=(src/'apple.c').read_text()
    limits=section(core,'static u32 nvme_max_drv_segments(', 'static bool nvme_update_disk_info(')
    tcb=section(apple,'struct apple_nvmmu_tcb {','/*\n * The Apple NVMe controller')
    submit=section(apple,'static void apple_nvme_submit_cmd_t8103(', '/*\n * From pci.c:')
    preamble=r'''
    #include <assert.h>
    #include <stdbool.h>
    #include <stdint.h>
    #include <stdio.h>
    #include <string.h>
    #include <limits.h>
    typedef uint8_t u8;
    typedef uint16_t __le16;
    typedef uint64_t __le64;
    typedef uint32_t u32;
    #define EXPORT_SYMBOL_GPL(x)
    #define BIT(n) (1U<<(n))
    #define NVME_CTRL_PAGE_SIZE 4096
    #define PAGE_SIZE 16384
    #define SECTOR_SHIFT 9
    #define NVME_QUIRK_ADMIN_PAGE_ALIGN (1U<<23)
    #define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
    #define min_not_zero(a,b) (!(a)?(b):(!(b)?(a):((a)<(b)?(a):(b))))
    struct nvme_ctrl;
    struct nvme_ctrl_ops { unsigned (*get_virt_boundary)(struct nvme_ctrl *,bool); };
    struct nvme_ctrl { unsigned max_hw_sectors,max_segments,max_integrity_segments,quirks; struct nvme_ctrl_ops *ops; };
    struct queue_limits { unsigned max_hw_sectors,max_segments,max_integrity_segments,virt_boundary_mask,max_segment_size,dma_alignment; };
    struct nvme_command { union {
     struct { uint8_t opcode,flags; uint16_t command_id; uint32_t nsid,cdw2[2]; uint64_t metadata;
              struct { uint64_t prp1,prp2; } dptr; uint32_t cdw10[6]; } common;
     struct { uint8_t opcode,flags; uint16_t command_id; uint32_t nsid; uint64_t rsvd2,metadata;
              struct { uint64_t prp1,prp2; } dptr; uint64_t slba; uint16_t length,control;
              uint32_t dsmgmt,reftag; uint16_t apptag,appmask; } rw;
    }; };
    _Static_assert(sizeof(struct nvme_command)==64,"command layout");
    #define nvme_tag_from_cid(cid) ((cid)&0xfff)
    static bool nvme_is_write(struct nvme_command *c) { return c->common.opcode&1; }
    '''
    stub=r'''
    struct apple_nvme { unsigned lock; };
    struct apple_nvme_queue { struct apple_nvme *anv; struct apple_nvmmu_tcb *tcbs;
     struct nvme_command *sqes; unsigned *sq_db; };
    static struct apple_nvme_queue *active;
    static struct nvme_command *current_cmd;
    static unsigned doorbells;
    static struct apple_nvme *queue_to_apple_nvme(struct apple_nvme_queue *q) { return q->anv; }
    static void spin_lock_irq(unsigned *l) { assert(!*l);*l=1; }
    static void spin_unlock_irq(unsigned *l) { assert(*l==1);*l=0; }
    static void writel(unsigned tag, unsigned *db) {
     assert(db==active->sq_db && active->anv->lock==1 && tag<64);
     struct apple_nvmmu_tcb *t=&active->tcbs[tag];
     assert(t->opcode==0 && t->command_id==tag && t->length==current_cmd->rw.length);
     assert(t->prp1==current_cmd->common.dptr.prp1 && t->prp2==current_cmd->common.dptr.prp2);
     assert(t->dma_flags==(!t->prp1?0:(nvme_is_write(current_cmd)?2:1)));
     assert(!memcmp(&active->sqes[tag],current_cmd,sizeof(*current_cmd)));
     doorbells++;*db=tag;
    }
    static unsigned boundary(struct nvme_ctrl *c,bool admin) { return 4095; }
    '''
    tests=r'''
    int main(void) {
     struct nvme_ctrl_ops ops={.get_virt_boundary=boundary};
     struct nvme_ctrl ctrl={.ops=&ops,.max_hw_sectors=8192,.max_segments=127,.max_integrity_segments=1};
     for (unsigned admin=0;admin<2;admin++) for (unsigned quirk=0;quirk<2;quirk++) {
      struct queue_limits lim={0};ctrl.quirks=quirk?NVME_QUIRK_ADMIN_PAGE_ALIGN:0;
      nvme_set_ctrl_limits(&ctrl,&lim,admin);
      assert(lim.dma_alignment==((admin&&quirk)?4095:3));
      assert(lim.max_hw_sectors==8192 && lim.max_segments==127 && lim.max_integrity_segments==1);
      assert(lim.virt_boundary_mask==4095 && lim.max_segment_size==UINT_MAX);
     }
     puts("PASS: only quirked admin queues require 4 KiB alignment on a 16 KiB host");
     struct apple_nvmmu_tcb tcbs[64];struct nvme_command sqes[64];
     struct apple_nvme anv={0};unsigned db=0;
     struct apple_nvme_queue q={.anv=&anv,.tcbs=tcbs,.sqes=sqes,.sq_db=&db};
     struct nvme_command cmd={0};active=&q;current_cmd=&cmd;
     for (unsigned tag=0;tag<64;tag++) for (unsigned op=0;op<256;op++) for (unsigned dma=0;dma<2;dma++) {
      memset(tcbs,0x5a,sizeof(tcbs));memset(sqes,0,sizeof(sqes));
      cmd.common.opcode=op;cmd.common.command_id=tag;cmd.common.dptr.prp1=dma?0x1000:0;
      cmd.common.dptr.prp2=dma?0x2000:0;cmd.rw.length=73;doorbells=0;
      apple_nvme_submit_cmd_t8103(&q,&cmd);
      assert(doorbells==1 && anv.lock==0 && db==tag && cmd.common.opcode==op);
     }
     puts("PASS: 32768 TCB encodings preserve commands, use zero metadata opcode and correct DMA flags");
     return 0;
    }
    '''
    variants={
    'current':limits+submit,
    'old-alignment':limits.replace('if (is_admin && (ctrl->quirks & NVME_QUIRK_ADMIN_PAGE_ALIGN))','if (false)')+submit,
    'old-opcode':limits+submit.replace('tcb->opcode = 0;','tcb->opcode = cmd->common.opcode;'),
    'old-no-data-direction':limits+submit.replace('if (!cmd->common.dptr.prp1)','if (false)'),
    }
    for name,funcs in variants.items():
        file=out/(name+'.c');file.write_text(preamble+tcb+stub+funcs+tests)
        binary=out/name
        subprocess.run(['gcc','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
                        '-fno-pie','-no-pie','-fsanitize=address,undefined',str(file),'-o',str(binary)],check=True)
        r=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30)
        (out/(name+'.out')).write_text(r.stdout+r.stderr)
        assert (r.returncode==0 if name=='current' else r.returncode!=0 and 'Assertion' in r.stderr),(name,r.stderr)
        if name=='current':print(r.stdout,end='')

    print('Three regressions detected by runtime assertions')

finally:
    subprocess.run(['trash-put', str(out)], check=True)
