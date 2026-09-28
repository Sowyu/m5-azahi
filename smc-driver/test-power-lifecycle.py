#!/usr/bin/env python3
"""Check battery notifier, parameter and work teardown without device access."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path)
args = parser.parse_args()
base = args.source.read_bytes()
if hashlib.sha256(base).hexdigest() != '96b6da14e998a9872d11da9c634570c598f8dcbc7d9c305f6578b775b8803935':
    parser.exit(1, 'REFUSED: wrong battery source checksum; no output created\n')
if not shutil.which('trash-put'):
    parser.exit(1, 'Install trash-cli: sudo apt-get install -y trash-cli\n')
stub = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define to_delayed_work(w) (w)
#define POWER_LOG_INTERVAL 100
#define THIS_MODULE NULL
struct work_struct { bool pending, running; };
struct notifier_block { unsigned unused; };
struct apple_smc { bool event_handlers; };
struct macsmc_power { struct apple_smc *smc; struct notifier_block nb; struct work_struct critical_work,dbg_log_work; };
struct device { struct macsmc_power *data; };
struct platform_device { struct device dev; };
struct kernel_param { bool *arg; };
static struct macsmc_power *g_power, *removing;
static bool log_power, locked, cancel_started;
static unsigned locks, unlocks, schedules, syncs, dsyncs, debugs;
static int macsmc_log_power_set(const char *, const struct kernel_param *);
static void macsmc_dbg_work(struct work_struct *);
static int param_set_bool(const char *s, const struct kernel_param *kp) {
 assert(locked && kp->arg==&log_power);
 if(!strcmp(s,"1")) *kp->arg=true;
 else if(!strcmp(s,"0")) *kp->arg=false;
 else return -EINVAL;
 return 0;
}
static void kernel_param_lock(void *module) { assert(!module && !locked);locked=true;locks++; }
static void kernel_param_unlock(void *module) {
 assert(!module && locked && g_power!=removing);locked=false;unlocks++;
}
static int set_parameter(const char *value) {
 assert(!locked);locked=true;
 struct kernel_param param={.arg=&log_power};
 int ret=macsmc_log_power_set(value,&param);
 locked=false;return ret;
}
static void schedule_delayed_work(struct work_struct *w,unsigned delay) {
 assert(delay==0 || delay==POWER_LOG_INTERVAL);
 w->pending=true;schedules++;
}
static void macsmc_do_dbg(struct macsmc_power *p) { assert(p==removing);debugs++; }
static struct macsmc_power *dev_get_drvdata(struct device *d) { return d->data; }
static void blocking_notifier_chain_unregister(bool *chain,struct notifier_block *nb) {
 assert(chain==&removing->smc->event_handlers && nb==&removing->nb && *chain);
 assert(!locked && !cancel_started);
 /* A parameter write arrives after the global pointer should be cleared. */
 unsigned before=schedules;assert(set_parameter("1")==0);
 assert(schedules==before && g_power!=removing);
 /* An in-flight notifier may still enqueue before unregister returns. */
 removing->critical_work.pending=true;
 *chain=false;
}
static void cancel_work(struct work_struct *w) { cancel_started=true;w->pending=false; }
static void cancel_delayed_work(struct work_struct *w) { cancel_work(w); }
static void cancel_work_sync(struct work_struct *w) {
 assert(w==&removing->critical_work && !removing->smc->event_handlers && !locked);
 assert(g_power!=removing && locks==1 && unlocks==1);
 cancel_started=true;w->pending=w->running=false;syncs++;
}
static void cancel_delayed_work_sync(struct work_struct *w) {
 assert(w==&removing->dbg_log_work && syncs==1 && !locked);
 /* The real debug callback can requeue itself while cancellation waits. */
 if(w->running)macsmc_dbg_work(w);
 w->pending=w->running=false;dsyncs++;
}
'''

tests = r'''
int main(void) {
 for(unsigned state=0;state<16;state++)for(unsigned debug=0;debug<2;debug++) {
  struct apple_smc smc={.event_handlers=true};
  struct macsmc_power power={.smc=&smc};
  struct platform_device pdev={.dev={.data=&power}};
  power.critical_work=(struct work_struct){state&1,state&2};
  power.dbg_log_work=(struct work_struct){state&4,state&8};
  g_power=removing=&power;log_power=debug;locked=cancel_started=false;
  locks=unlocks=schedules=syncs=dsyncs=debugs=0;
  assert(set_parameter("invalid")==-EINVAL && schedules==0 && log_power==debug);
  assert(set_parameter(debug?"1":"0")==0 && schedules==debug);
  macsmc_power_remove(&pdev);
  assert(!g_power && !locked && !smc.event_handlers && syncs==1 && dsyncs==1);
  assert(!power.critical_work.pending && !power.critical_work.running);
  assert(!power.dbg_log_work.pending && !power.dbg_log_work.running);
  unsigned before=schedules;assert(set_parameter("1")==0 && schedules==before);
 }
 puts("PASS: 32 teardown states, concurrent producer boundaries, self-requeue, parameter errors");
 return 0;
}
'''

def section(text, start, end):
    offset = text.index(start)
    return text[offset:text.index(end, offset)]


root = Path(tempfile.mkdtemp(prefix='azahi-power-lifecycle-'))
try:
    path = root / 'drivers/power/supply/macsmc-power.c'
    path.parent.mkdir(parents=True)
    path.write_bytes(base)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(root), '-i',
                    str(Path(__file__).with_name('power-macos27.patch').resolve())],
                   check=True, capture_output=True)
    source = path.read_text()
    remove = section(source, 'static void macsmc_power_remove(',
                     'static struct platform_driver macsmc_power_driver')
    unregister = '\tblocking_notifier_chain_unregister(&power->smc->event_handlers, &power->nb);\n'
    clear = '\tif (g_power == power)\n\t\tg_power = NULL;\n'
    variants = {
        'current': source,
        'original': base.decode(),
        'critical-not-synchronized': source.replace('cancel_work_sync(&power->critical_work);',
                                                    'cancel_work(&power->critical_work);'),
        'debug-not-synchronized': source.replace('cancel_delayed_work_sync(&power->dbg_log_work);',
                                                 'cancel_delayed_work(&power->dbg_log_work);'),
        'notifier-too-late': source.replace(remove, remove.replace(unregister, '').replace(
            '\tcancel_delayed_work_sync(&power->dbg_log_work);',
            '\tcancel_delayed_work_sync(&power->dbg_log_work);\n' + unregister)),
        'global-still-published': source.replace(clear, ''),
        'global-unlocked': source.replace(remove, remove.replace(
            '\tkernel_param_lock(THIS_MODULE);\n', '').replace(
            '\tkernel_param_unlock(THIS_MODULE);\n', '')),
    }
    for name, text in variants.items():
        setter = section(text,
                         'static int macsmc_log_power_set(const char *val, const struct kernel_param *kp)\n{',
                         'static void macsmc_power_critical_work(')
        teardown = section(text, 'static void macsmc_power_remove(',
                           'static struct platform_driver macsmc_power_driver')
        host = root / (name + '.c')
        host.write_text(stub + setter + teardown + tests)
        binary = root / name
        cc = shlex.split(os.environ.get('CC', 'gcc'))
        subprocess.run([*cc, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-function',
                        '-fno-pie', '-no-pie', '-fsanitize=address,undefined',
                        str(host), '-o', str(binary)], check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        if name == 'current':
            if result.returncode:
                raise RuntimeError(result.stderr)
            print(result.stdout, end='')
        elif result.returncode == 0 or 'Assertion' not in result.stderr:
            raise RuntimeError('Regression did not fail: ' + name)
    print('Original teardown and five mutations detected')
finally:
    subprocess.run(['trash-put', str(root)], check=True)
