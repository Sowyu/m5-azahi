#!/usr/bin/env python3
"""Compile and run the actual full-height guard on the host, no target access."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).parent / 'm1n1-20260911/src/kboot.c').read_text()
guard = source[source.index('static bool azahi_full_height_fb_ok'):source.index('static int dt_set_fb')]
harness = '''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
typedef uint64_t u64;
#define T6050 0x6050
unsigned chip_id, board_id;
struct { struct { u64 base, width, height, stride, depth; } video; } cur_boot_args;
''' + guard + '''
int main(void) {
 chip_id=T6050; board_id=8;
 cur_boot_args.video.base=0x10000000000;
 cur_boot_args.video.width=3024; cur_boot_args.video.height=1964;
 cur_boot_args.video.stride=12096; cur_boot_args.video.depth=30;
 assert(azahi_full_height_fb_ok(1890));
 cur_boot_args.video.depth=32; assert(azahi_full_height_fb_ok(1890));
 cur_boot_args.video.depth=16; assert(!azahi_full_height_fb_ok(1890));
 cur_boot_args.video.depth=30;
 assert(!azahi_full_height_fb_ok(1964));
 chip_id=0x6040; assert(!azahi_full_height_fb_ok(1890)); chip_id=T6050;
 board_id=9; assert(!azahi_full_height_fb_ok(1890)); board_id=8;
 cur_boot_args.video.base=0; assert(!azahi_full_height_fb_ok(1890));
 cur_boot_args.video.base=0x10000000000;
 cur_boot_args.video.width=3023; assert(!azahi_full_height_fb_ok(1890));
 cur_boot_args.video.width=3024;
 cur_boot_args.video.height=1890; assert(!azahi_full_height_fb_ok(1890));
 cur_boot_args.video.height=1964;
 cur_boot_args.video.stride=12160; assert(!azahi_full_height_fb_ok(1890));
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='azahi-notch-test-') as td:
    exe = Path(td) / 'guard'
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-x', 'c', '-', '-o', str(exe)],
                   input=harness, text=True, check=True)
    subprocess.run([str(exe)], check=True)
assert 'full_len == sizeof(*full)' in source
assert 'fdt32_to_cpu(*full) == 1' in source
assert 'azahi,full-height-framebuffer' in source
print('PASS: actual C guard, ten accepted/refused cases; explicit opt-in checks present')
