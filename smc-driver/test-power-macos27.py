#!/usr/bin/env python3
"""Exercise the patched battery conversion and its real property cases offline."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

BASE_SHA = '96b6da14e998a9872d11da9c634570c598f8dcbc7d9c305f6578b775b8803935'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path, help='Pinned drivers/power/supply/macsmc-power.c')
args = parser.parse_args()
base = args.source.read_bytes()
if hashlib.sha256(base).hexdigest() != BASE_SHA:
    parser.error('Wrong macsmc-power.c checksum')
if not shutil.which('trash-put'):
    parser.error('Install trash-cli: sudo apt-get install -y trash-cli')
root = Path(tempfile.mkdtemp(prefix='azahi-smc-power-test-'))
try:
    source_path = root / 'drivers/power/supply/macsmc-power.c'
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(base)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(root), '-i',
                    str(Path(__file__).with_name('power-macos27.patch').resolve())], check=True)
    source = source_path.read_text()

    def section(start, end):
        return source[source.index(start):source.index(end, source.index(start))]

    functions = section('static int macsmc_battery_read_bcf0(', 'static int macsmc_battery_get_capacity_level(')
    functions += section('static s16 macsmc_swap_b0rm(', 'static int macsmc_battery_get_property(')
    functions += '''static int property(struct macsmc_power *power, int psp, struct value *val) {
 int ret=0; u16 vu16;
 switch (psp) {
'''
    for prop in ('CHARGE_NOW', 'ENERGY_NOW'):
        start = source.index('\tcase POWER_SUPPLY_PROP_' + prop + ':')
        end = source.index('\tcase ', start + 1)
        functions += source[start:end]
    functions += 'default: return -EINVAL; } return ret; }\n'
    stub = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef int16_t s16;
typedef uint32_t u32;
#define swab16(x) __builtin_bswap16(x)
#define SMC_KEY(key) SMC_##key
#define SMC_BCF0 1
#define SMC_B0RM 2
#define POWER_SUPPLY_PROP_CHARGE_NOW 1
#define POWER_SUPPLY_PROP_ENERGY_NOW 2
struct macsmc_power { void *smc; bool bcf0_1byte; int nominal_voltage_mv; };
struct value { int intval; };
static unsigned reads8,reads16,reads32;
static int read_error;
static u16 raw_word;
static int apple_smc_read_u8(void *smc, int key, u8 *out) {
 assert(key==SMC_BCF0); reads8++;
 if (read_error) return read_error;
 *out=raw_word; return 0;
}
static int apple_smc_read_u16(void *smc, int key, u16 *out) {
 assert(key==SMC_B0RM); reads16++;
 if (read_error) return read_error;
 *out=raw_word; return 0;
}
static int apple_smc_read_u32(void *smc, int key, u32 *out) {
 assert(key==SMC_BCF0); reads32++;
 if (read_error) return read_error;
 *out=raw_word; return 0;
}
'''
    tests = r'''
int main(void) {
 struct macsmc_power power={.nominal_voltage_mv=15400};
 for (unsigned modern=0;modern<2;modern++) {
  power.bcf0_1byte=modern;
  for (unsigned word=0;word<=65535;word++) {
   raw_word=word;
   unsigned decoded=modern?word:(word/256)+(word%256)*256;
   int expected=decoded<=32767?(int)decoded:(int)decoded-65536;
   assert(macsmc_swap_b0rm(&power,raw_word)==expected);
   struct value val={0};
   assert(property(&power,POWER_SUPPLY_PROP_CHARGE_NOW,&val)==0);
   assert(val.intval==expected*1000);
   assert(property(&power,POWER_SUPPLY_PROP_ENERGY_NOW,&val)==0);
   assert(val.intval==expected*15400);
  }
 }
 assert(reads16==2*2*65536);
 puts("PASS: every 16-bit value in both firmware byte orders, signed charge and energy conversion in real cases");
 for (unsigned modern=0;modern<2;modern++) {
  power.bcf0_1byte=modern;
  for (unsigned critical=0;critical<256;critical++) {
   reads8=reads32=0; raw_word=critical; u32 val=0xa5;
   assert(macsmc_battery_read_bcf0(&power,&val)==0 && val==critical);
   assert(reads8==modern && reads32==!modern);
  }
  read_error=-EIO;
  for (unsigned prop=1;prop<=2;prop++) {
   struct value val={.intval=1234};
   assert(property(&power,prop,&val)==-EIO && val.intval==1234);
  }
  u32 val=0xa5;
  assert(macsmc_battery_read_bcf0(&power,&val)==-EIO);
  assert(val==(modern?0:0xa5));
  read_error=0;
 }
 puts("PASS: both critical-status sizes, read errors preserve property outputs, initialized one-byte failure result");
 return 0;
}
'''
    test = root / 'test.c'
    test.write_text(stub + functions + tests)
    binary = root / 'test'
    subprocess.run(shlex.split(os.environ.get('CC', 'cc')) +
                   ['-std=gnu11', '-Wall', '-Wextra', '-Wno-unused-parameter',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', str(test), '-o', str(binary)],
                   check=True)
    subprocess.run([str(binary)], check=True, timeout=10)
    # A notification can run on another CPU as soon as registration exposes it.
    # Compile the actual event handler and final probe section, then deliver
    # a critical event inside the registration stub before probe returns.
    event = section('static int macsmc_power_event(', 'static int macsmc_power_probe(')
    stub = r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char u8;
#define NOTIFY_OK 1
#define NOTIFY_DONE 0
#define SMC_KEY(k) 0
#define dev_info(...) ((void)0)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
struct notifier_block { int (*notifier_call)(struct notifier_block *,unsigned long,void *); };
struct work_struct { void (*func)(struct work_struct *); };
struct apple_smc { int event_handlers; };
struct macsmc_power {
 struct apple_smc *smc; void *dev,*batt,*ac;
 struct notifier_block nb;
 struct work_struct critical_work,dbg_log_work;
};
static struct macsmc_power *g_power;
static bool log_power;
static bool param_locked;
static unsigned param_locks;
#define THIS_MODULE 0
#define kernel_param_lock(m) do { assert(!(m) && !param_locked); param_locked=true; param_locks++; } while (0)
#define kernel_param_unlock(m) do { assert(!(m) && param_locked); param_locked=false; } while (0)
static unsigned critical_scheduled, debug_scheduled, supplies_changed, debug_calls;
#define INIT_WORK(w,f) do { (w)->func=(f); } while (0)
#define INIT_DELAYED_WORK(w,f) INIT_WORK(w,f)
static void macsmc_power_critical_work(struct work_struct *w) { (void)w; }
static void macsmc_dbg_work(struct work_struct *w) { (void)w; }
static void schedule_work(struct work_struct *w) {
 assert(w->func==macsmc_power_critical_work);critical_scheduled++;
}
static void schedule_delayed_work(struct work_struct *w,unsigned delay) {
 assert(!delay && w->func==macsmc_dbg_work && param_locked);debug_scheduled++;
}
static void power_supply_changed(void *p) { assert(p);supplies_changed++; }
static int apple_smc_read_u8(struct apple_smc *s,int k,u8 *v) {
 (void)s;(void)k;(void)v;return -1;
}
static void macsmc_do_dbg(struct macsmc_power *p) { assert(p);debug_calls++; }
static int blocking_notifier_chain_register(int *chain,struct notifier_block *nb) {
 assert(chain && nb->notifier_call);
 assert(nb->notifier_call(nb,0x71020000,NULL)==NOTIFY_OK);
 assert(nb->notifier_call(nb,0x71010101,NULL)==NOTIFY_OK);
 assert(nb->notifier_call(nb,0x72010000,NULL)==NOTIFY_OK);
 return 0;
}
"""
    tests = r"""
int main(void) {
 for(unsigned debug=0;debug<2;debug++) {
  struct apple_smc smc={0};
  struct macsmc_power power={.smc=&smc,.batt=&smc,.ac=&smc};
  log_power=debug;g_power=NULL;
  param_locked=false;param_locks=0;
  critical_scheduled=debug_scheduled=supplies_changed=debug_calls=0;
  assert(finish_probe(&power)==0);
  assert(critical_scheduled==1 && supplies_changed==2 && g_power==&power);
  assert(debug_scheduled==debug && debug_calls==debug);
  assert(!param_locked && param_locks==1);
 }
 puts("PASS: critical notifications during registration see initialized work; logging modes preserved");
 return 0;
}
"""
    for name, text in (('current', source), ('original', base.decode())):
        probe = text.index('static int macsmc_power_probe(')
        start = min(text.index('\tpower->nb.notifier_call =', probe),
                    text.index('\tINIT_WORK(&power->critical_work,', probe))
        end = text.index('static void macsmc_power_remove(', start)
        tail = text[start:end]
        function = ('static int finish_probe(struct macsmc_power *power) {\n'
                    ' struct apple_smc *smc=power->smc;\n' + tail)
        test = root / (name + '-notification.c')
        test.write_text(stub + event + function + tests)
        binary = root / (name + '-notification')
        subprocess.run(shlex.split(os.environ.get('CC', 'cc')) +
                       ['-std=gnu11', '-O1', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-variable',
                        '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                        str(test), '-o', str(binary)], check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        if name == 'current':
            if result.returncode:
                raise RuntimeError(result.stderr)
            print(result.stdout, end='')
        elif result.returncode == 0 or 'Assertion' not in result.stderr:
            raise RuntimeError('Original notification-order regression did not fail')

finally:
    subprocess.run(['trash-put', str(root)], check=True)
