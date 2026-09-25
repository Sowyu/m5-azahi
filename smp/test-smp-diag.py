#!/usr/bin/env python3
"""Host guards for the T6050 secondary-CPU diagnostic. No target access.

Two things must hold for azahi_smp.c to stay safe:

1. It is default-off and the token match is word-bounded, so a stray substring
   never trips it and "start" never fires when only "probe" was asked for.
2. Probe mode writes no hardware. The only hardware writes in the whole file
   come from the stock smp_start_secondaries() call in start mode.

The first is checked by compiling the actual token helpers and exercising them.
The second is a static check over the source: no write32/write64 outside the
one start path. Both fail loudly if someone loosens the gate later.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parent.parent / 'standalone-loader/m1n1-20260911/src'
SMP = (SRC / 'azahi_smp.c').read_text()


def extract(name):
    """Pull one function (signature line through matching brace) from the source."""
    begin = SMP.rindex('\n', 0, SMP.index(name)) + 1
    depth = 0
    j = SMP.index('{', begin)
    while True:
        if SMP[j] == '{':
            depth += 1
        elif SMP[j] == '}':
            depth -= 1
            if depth == 0:
                break
        j += 1
    return SMP[begin:j + 1]


def run_c(body):
    with tempfile.TemporaryDirectory(prefix='azahi-smp-test-') as tmp:
        exe = Path(tmp) / 'check'
        subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-x', 'c', '-', '-o', str(exe)], input=body, text=True, check=True)
        subprocess.run([str(exe)], check=True)


class TokenGate(unittest.TestCase):
    def test_token_word_boundaries(self):
        helpers = extract('static const char *azahi_smp_mode(') + '\n' + \
            extract('static bool azahi_smp_mode_is(')
        run_c('''#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
''' + helpers + '''
int main(void) {
    /* default-off: no token means no-op */
    assert(azahi_smp_mode("maxcpus=1 idle=nop") == NULL);
    assert(azahi_smp_mode(NULL) == NULL);

    /* probe / start recognised, with surrounding args */
    assert(azahi_smp_mode_is(azahi_smp_mode("x azahi.smp=probe y"), "probe"));
    assert(azahi_smp_mode_is(azahi_smp_mode("azahi.smp=start"), "start"));
    assert(azahi_smp_mode_is(azahi_smp_mode("azahi.smp=start\\tx"), "start"));

    /* word boundary: a longer token must not match the shorter mode */
    assert(!azahi_smp_mode_is(azahi_smp_mode("azahi.smp=startle"), "start"));
    assert(!azahi_smp_mode_is(azahi_smp_mode("azahi.smp=probes"), "probe"));

    /* start must never fire when only probe was asked for */
    assert(!azahi_smp_mode_is(azahi_smp_mode("azahi.smp=probe"), "start"));
    return 0;
}
''')


class ProbeIsReadOnly(unittest.TestCase):
    def test_probe_paths_have_no_writes(self):
        # The only hardware writes allowed are inside smp_start_secondaries(),
        # which the source calls only from the start path. probe/dump helpers
        # must contain no write32/write64.
        for fn in ('static void azahi_smp_dump_cpu_start(',
                   'static void azahi_smp_probe('):
            body = extract(fn)
            self.assertNotIn('write32', body, f'{fn} must not write hardware')
            self.assertNotIn('write64', body, f'{fn} must not write hardware')

    def test_only_start_path_starts_cpus(self):
        # The call statement appears exactly once, in azahi_smp_start().
        self.assertEqual(SMP.count('smp_start_secondaries();'), 1)
        start_body = extract('static void azahi_smp_start(')
        self.assertIn('smp_start_secondaries();', start_body)


class OffsetsMatchLoader(unittest.TestCase):
    def test_cpu_start_offset(self):
        self.assertIn('#define CPU_START_OFF_T6050 0x88000', SMP)

    def test_only_die0_is_read(self):
        # No evidence for a die-1 PMGR on J714s; an unmapped read can SError.
        self.assertNotIn('PMGR_DIE_OFF', SMP)
        self.assertNotIn('0x2000000000', SMP.split('*/', 1)[1].replace('+0x2000000000 on this SoC', ''))
        self.assertIn('if (die != 0) {', extract('static void azahi_smp_probe('))


if __name__ == '__main__':
    unittest.main()
