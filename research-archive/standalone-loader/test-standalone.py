#!/usr/bin/env python3
"""Host-only inspection and compiled tests of the actual ANS preparation C."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('bundle', HERE / 'build-bundle.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = bundle.OUTPUT.read_bytes()
        cls.receipt = json.loads(bundle.OUTPUT.with_suffix('.json').read_text())

    def test_valid_bundle(self):
        self.assertEqual(set(bundle.inspect(self.data, self.receipt)), {'args', 'dt', 'gzip', 'initrd'})

    def test_corrupt_payload_refused(self):
        for delta in (1, 1000, 1000000):
            data = bytearray(self.data)
            data[-delta] ^= 1
            receipt = copy.deepcopy(self.receipt)
            receipt['image_sha256'] = bundle.sha(data)
            with self.assertRaises(AssertionError):
                bundle.inspect(data, receipt)

    def test_bad_header_bounds(self):
        for field, value in ((1, 2), (2, 0), (2, 4097), (3, 0), (4, 33 << 20), (5, 0)):
            data = bytearray(self.data)
            offset = self.receipt['loader_bytes']
            fields = list(bundle.HEADER.unpack_from(data, offset))
            fields[field] = value
            bundle.HEADER.pack_into(data, offset, *fields)
            receipt = copy.deepcopy(self.receipt)
            receipt['image_sha256'] = bundle.sha(data)
            with self.assertRaises(AssertionError):
                bundle.inspect(data, receipt)

    def test_same_kernel_dt_initrd_as_v3(self):
        parts = bundle.inspect(self.data, self.receipt)
        v3 = bundle.SOURCE.read_bytes()
        dt = v3.index(b'\n', v3.index(b'chosen.bootargs=')) + 1
        gz = dt + struct.unpack_from('>I', v3, dt + 4)[0]
        marker = v3.index(b'm1n1_initramfs', gz)
        initrd = marker + len(b'm1n1_initramfs') + 4
        self.assertEqual(parts['dt'], v3[dt:gz])
        self.assertEqual(parts['gzip'], v3[gz:marker])
        self.assertEqual(parts['initrd'], v3[initrd:])
        oldargs = v3[v3.index(b'chosen.bootargs=') + len(b'chosen.bootargs='):dt - 1]
        self.assertEqual(parts['args'], oldargs + b' azahi.standalone=1 drm.panic_screen=qr_code\0')

    def test_no_diagnostic_secondary_starts(self):
        src = (bundle.TREE / 'src/smp.c').read_text()
        body = src[src.index('spin_table[boot_cpu_idx].mpidr ='):]
        self.assertLess(body.index('AZAHI_ONE_CORE'), body.index('smp_start_cpu('))
        self.assertNotIn('smp_reset_mark', src)
        auto = (bundle.TREE / 'src/azahi_standalone.c').read_text()
        self.assertNotIn('nvme_init(', auto)
        self.assertNotIn('cpufreq_init(', auto)
        self.assertIn('dapf_init("/arm-io/dart-mtp", 1)', auto)
        self.assertIn('end > cur_boot_args.top_of_kernel_data', auto)
        self.assertIn('chip_id != T6050 || board_id != 8', auto)
        self.assertIn('bool high_test = (u64)_base == 0x10400000000UL', auto)
        kboot = (bundle.TREE / 'src/kboot.c').read_text()
        self.assertIn('0x10400000000UL ? 0x10000000UL', kboot)
        main = (bundle.TREE / 'src/main.c').read_text()
        self.assertIn('heapblock_set_limit((void *)0x10410000000UL)', main)

    def test_actual_c_ans_guard(self):
        src = (bundle.TREE / 'src/azahi_standalone.c').read_text()
        functions = src[src.index('static bool reg_matches'):src.index('int azahi_standalone_run')]
        harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define BIT(n) (1UL << (n))
static void *adt;
static u32 state[4], firmware;
static int writes, delays, badbar, badname, timeout;
static const u64 addresses[] = {0x280900138,0x280900128,0x280900140,0x280900150};
static int stop(const char *s) { (void)s; return -1; }
static int adt_path_offset_trace(void *a, const char *p, int *t) {
    (void)a; t[0] = !strcmp(p,"/arm-io/ans") ? 1 : 2; return 1;
}
static int adt_get_reg(void *a, int *t, const char *p, unsigned i, u64 *b, u64 *s) {
    (void)a; (void)p;
    if (badbar) return -1;
    if (t[0] == 2) { *b=0x41dc50000; *s=0xc000; return 0; }
    *s=0x10000;
    switch(i) { case 0:*b=0x419600000;break; case 3:*b=0x41dcc0000;break;
                case 9:*b=0x45dcc0000;break; default:return -1; }
    return 0;
}
static u64 pmgr_lookup_device_addr(const char *n) {
    const char *names[]={"FAB6_SOC","APCIE_ST0","ANS","APCIE_SYS_ST0"};
    for(int i=0;i<4;i++) if(!strcmp(n,names[i])) return badname ? 0 : addresses[i];
    assert(0); return 0;
}
static u32 read32(u64 a) {
    if(a==0x419600044) return firmware;
    for(int i=0;i<4;i++) if(a==addresses[i]) return state[i];
    assert(0); return 0;
}
static void mask32(u64 a,u32 clear,u32 set) {
    assert(a==addresses[3]); assert(clear==(BIT(28)|BIT(9)|BIT(8)|15));
    assert(set==15); writes++;
    if(!timeout) state[3]=0xff;
}
static void mdelay(unsigned n) { assert(n==10); delays++; }
'''
        cases = r'''
static void reset(void) {
    state[0]=0xf0000ff;state[1]=0x2ff;state[2]=0xf0000ff;state[3]=0x1000030f;
    firmware=16;writes=delays=badbar=badname=timeout=0;
}
int main(void) {
    reset(); assert(prepare_ans()==0 && writes==1);
    reset(); state[3]=0xff; assert(prepare_ans()==0 && writes==0);
    reset(); badbar=1; assert(prepare_ans()<0 && writes==0);
    reset(); badname=1; assert(prepare_ans()<0 && writes==0);
    reset(); firmware=0; assert(prepare_ans()<0 && writes==0);
    reset(); firmware=0xabad1dea; assert(prepare_ans()<0 && writes==0);
    for(int i=0;i<4;i++) {
        reset();state[i]=0xabad1dea;assert(prepare_ans()<0 && writes==0);
        reset();state[i]=0;assert(prepare_ans()<0 && writes==0);
    }
    reset();timeout=1;assert(prepare_ans()<0 && writes==1 && delays==200);
    puts("ACTUAL_C_ANS_GUARD_PASS 15 scenarios");
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='azahi-standalone-c-') as temp:
            path = Path(temp)
            (path / 'test.c').write_text(harness + functions + cases)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            str(path / 'test.c'), '-o', str(path / 'test')], check=True)
            completed = subprocess.run([str(path / 'test')], capture_output=True, text=True, check=True)
            self.assertIn('ACTUAL_C_ANS_GUARD_PASS', completed.stdout)


if __name__ == '__main__':
    unittest.main()
