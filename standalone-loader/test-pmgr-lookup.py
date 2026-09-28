#!/usr/bin/env python3
"""Check the read-only PMGR lookup against the pinned source, with no MMIO stubs."""
import argparse
import hashlib
import os
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
pins = runpy.run_path(str(ROOT / 'smp/build-offline.py'))['PMGR_INPUTS']
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--m1n1', required=True, type=Path)
args = parser.parse_args()
for name, expected in pins.items():
    if hashlib.sha256((args.m1n1 / name).read_bytes()).hexdigest() != expected:
        parser.error('Wrong source hash: ' + name)
if not shutil.which('trash-put'):
    parser.error('Install trash-cli: sudo apt-get install -y trash-cli')
root = Path(tempfile.mkdtemp(prefix='azahi-pmgr-test-'))
try:
    (root / 'src').mkdir()
    for name in pins:
        shutil.copyfile(args.m1n1 / name, root / name)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(root), '-i',
                    str(ROOT / 'standalone-loader/pmgr-lookup.patch')], check=True)
    source = (root / 'src/pmgr.c').read_text()

    def section(start, end):
        return source[source.index(start):source.index(end, source.index(start))]

    functions = section('struct pmgr_device {', 'int pmgr_set_mode(')
    functions += section('static uintptr_t pmgr_device_get_addr(', 'static void pmgr_adt_get_parents(')
    stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#define PACKED __attribute__((packed))
#define PMGR_FLAG_VIRTUAL 0x10
#define PMGR_DIE_OFFSET UINT64_C(0x2000000000)
#define printf(...) ((void)0)
static void *adt;
static int reg_calls, fail_reg;
static u32 last_reg;
static int adt_get_reg(void *tree, int *path, const char *prop, u32 index, u64 *addr, u64 *size) {
 assert(!strcmp(prop,"reg")); reg_calls++; last_reg=index;
 *addr=UINT64_C(0x280900000); return fail_reg?-1:0;
}
'''
    tests = r'''
int main(void) {
 struct pmgr_device devices[5]={
  {.name="FAB6_SOC", .addr_offset=7}, {.name="APCIE_ST0", .addr_offset=5},
  {.name="ANS", .addr_offset=8}, {.name="APCIE_SYS_ST0", .addr_offset=10},
  {.name="ANS", .addr_offset=8}
 };
 u32 groups[]={7,0x100,0, 8,0x200,0};
 pmgr_devices=devices; pmgr_devices_len=4;
 pmgr_ps_regs=groups; pmgr_ps_regs_len=sizeof(groups);
 assert(pmgr_lookup_device_addr("ANS")==0 && !reg_calls);
 pmgr_initialized=1;
 assert(pmgr_lookup_device_addr(NULL)==0);
 assert(pmgr_lookup_device_addr("")==0);
 assert(pmgr_lookup_device_addr("0123456789abcdef")==0);
 assert(pmgr_lookup_device_addr("AN")==0);
 assert(pmgr_lookup_device_addr("ANS_suffix")==0);
 assert(!reg_calls);
 const char *names[]={"FAB6_SOC","APCIE_ST0","ANS","APCIE_SYS_ST0"};
 const uintptr_t expected[]={0x280900138,0x280900128,0x280900140,0x280900150};
 for (unsigned i=0;i<4;i++) assert(pmgr_lookup_device_addr(names[i])==expected[i]);
 assert(reg_calls==4 && last_reg==7);
 puts("PASS: initialized, exact unique die-0 names resolve all four ANS guards; missing/prefix names refused");

 reg_calls=0;
 pmgr_devices=NULL; assert(pmgr_lookup_device_addr("ANS")==0);
 pmgr_devices=devices; pmgr_devices_len=0; assert(pmgr_lookup_device_addr("ANS")==0);
 pmgr_devices_len=4; pmgr_ps_regs=NULL; assert(pmgr_lookup_device_addr("ANS")==0);
 pmgr_ps_regs=groups;
 for (unsigned n=0;n<24;n++) {
  if (n==12) continue;
  pmgr_ps_regs_len=n; assert(pmgr_lookup_device_addr("ANS")==0);
 }
 pmgr_ps_regs_len=24;
 devices[2].flags=PMGR_FLAG_VIRTUAL; assert(pmgr_lookup_device_addr("ANS")==0);
 devices[2].flags=0;
 pmgr_devices_len=5; assert(pmgr_lookup_device_addr("ANS")==0);
 pmgr_devices_len=4;
 assert(!reg_calls);
 puts("PASS: missing/truncated tables, virtual devices and duplicate names refused before address lookup");

 for (unsigned mode=0;mode<2;mode++) {
  pmgr_use_group_and_offset=mode;
  devices[2].group_and_offset.offset=0x38;
  for (unsigned index=0;index<256;index++) {
   devices[2].psreg_idx=index; devices[2].group_and_offset.group=index;
   reg_calls=0;
   uintptr_t got=pmgr_lookup_device_addr("ANS");
   if (index<2) {
    assert(got==0x280900000UL+(index+1)*0x100+(mode?0x38:0x40));
    assert(reg_calls==1 && last_reg==7+index);
   } else assert(!got && !reg_calls);
  }
 }
 devices[2].group_and_offset.group=0; fail_reg=1; reg_calls=0;
 assert(!pmgr_lookup_device_addr("ANS") && reg_calls==1);
 puts("PASS: all 256 indices in both PMGR layouts, address-resolution errors, no power or MMIO calls linked");
 return 0;
}
'''
    test = root / 'test.c'
    test.write_text(stub + functions + tests)
    binary = root / 'test'
    subprocess.run(shlex.split(os.environ.get('CC', 'cc')) +
                   ['-std=gnu11', '-Wall', '-Wextra', '-Wno-unused-parameter', '-Wno-unused-variable',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', str(test), '-o', str(binary)],
                   check=True)
    subprocess.run([str(binary)], check=True, timeout=10)
finally:
    subprocess.run(['trash-put', str(root)], check=True)
