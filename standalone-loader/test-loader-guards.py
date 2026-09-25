#!/usr/bin/env python3
"""Compile actual loader fragments on the host; no target access.

Checks the bootargs return-value test, the T6050 usable-RAM clamp and that the
hand-typed addresses shared by azahi_standalone.c and kboot.c still agree.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SRC = Path(__file__).parent / 'm1n1-20260911/src'
KBOOT = (SRC / 'kboot.c').read_text()
LOADER = (SRC / 'azahi_standalone.c').read_text()


def run_c(body):
    with tempfile.TemporaryDirectory(prefix='azahi-loader-test-') as temporary:
        exe = Path(temporary) / 'check'
        subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-x', 'c', '-',
                        '-o', str(exe)], input=body, text=True, check=True)
        subprocess.run([str(exe)], check=True)


class LoaderGuards(unittest.TestCase):
    def test_bootargs_accepts_any_slot(self):
        function = KBOOT[KBOOT.index('int kboot_set_chosen('):KBOOT.index('int kboot_set_uboot(')]
        condition = re.search(r'if \((kboot_set_chosen\("bootargs", args\)[^\n]*?)\)\s*(/\*.*\*/)?\n',
                              LOADER).group(1)
        run_c('''#include <assert.h>
#include <stdlib.h>
#include <string.h>
#define MAX_CHOSEN_PARAMS 16
static char *chosen_params[MAX_CHOSEN_PARAMS][2];
''' + function + '''
int main(void) {
    const char *args = "maxcpus=1";
    assert(kboot_set_chosen("other", "1") == 0);
    int refused = (''' + condition + ''');
    assert(!refused);
    assert(!strcmp(chosen_params[1][1], args));
    return 0;
}
''')

    def test_usable_ram_is_intersection(self):
        start = KBOOT.index('        u64 safe_min = 0x1010a960000UL;')
        block = KBOOT[start:KBOOT.index('\n        }\n', start) + len('\n        }\n')]
        run_c('''#include <assert.h>
#include <stdint.h>
#include <stdio.h>
typedef uint64_t u64;
static void clamp(u64 *low, u64 *high) {
    u64 dram_min = *low, dram_max = *high;
''' + block + '''    *low = dram_min; *high = dram_max;
}
int main(void) {
    u64 low = 0x10003af8000UL, high = low + 0xfc7008000UL; /* recorded J714s 64 GB */
    clamp(&low, &high);
    assert(low == 0x1010a960000UL && high == 0x10F4AB00000UL);
    low = 0x10003af8000UL; high = low + (24UL << 30);      /* smaller RAM: never extend */
    clamp(&low, &high);
    assert(low == 0x1010a960000UL && high == 0x10003af8000UL + (24UL << 30));
    return 0;
}
''')

    def test_shared_addresses_agree(self):
        define = dict(re.findall(r'#define (\w+) (0x[0-9a-fA-F]+)UL', LOADER))
        relocation = KBOOT[KBOOT.index('void kboot_set_initrd('):]
        initrd = re.search(r'void \*safe = \(void \*\)(0x[0-9a-fA-F]+)UL', relocation).group(1)
        fdt = re.search(r'void \*safe_dt = \(void \*\)(0x[0-9a-fA-F]+)UL', KBOOT).group(1)
        # The loader cleans INITRD_ADDR because kboot_set_initrd copies there.
        self.assertEqual(int(define['INITRD_ADDR'], 16), int(initrd, 16))
        self.assertEqual(int(define['SAFE_LOW'], 16), 0x1010a960000)
        self.assertEqual(int(define['SAFE_HIGH'], 16), 0x10F4AB00000)
        kernel_bytes = int(re.search(r'#define KERNEL_BYTES (\d+)U', LOADER).group(1))
        initrd_bytes = int(re.search(r'#define INITRD_BYTES (\d+)U', LOADER).group(1))
        self.assertLess(int(define['KERNEL_ADDR'], 16) + kernel_bytes, int(fdt, 16))
        self.assertLessEqual(int(fdt, 16) + 65536 + 0x10000, int(initrd, 16))
        self.assertLessEqual(int(initrd, 16) + initrd_bytes, 0x10F4AB00000)


if __name__ == '__main__':
    unittest.main(verbosity=2)
