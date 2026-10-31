#!/usr/bin/env python3
"""Host tests of the actual S49 ownership gate and S55 stop callback.

Only these functions run with synthetic state; this does not test firmware,
DMA, kernel scheduling, or the rest of the hardware preflight.
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest


SOURCE = Path(os.environ.get("N1_SOURCE_ROOT", Path(__file__).with_name("experiments")))


def function(path, name):
    source = (SOURCE / path).read_text()
    match = re.search(r"^static [^\n]*\b" + name + r"\([^;{]*\{.*?^\}", source, re.M | re.S)
    if not match:
        raise AssertionError(f"function {name} not found in {path}")
    return match.group(0)


def run_c(source):
    with tempfile.TemporaryDirectory(prefix="n1-lifecycle-") as directory:
        src = Path(directory) / "test.c"
        exe = Path(directory) / "test"
        src.write_text(source)
        compiler = shlex.split(os.environ.get("CC", "cc"))
        subprocess.run(compiler + ["-std=c11", "-Wall", "-Wextra", "-Werror",
                                  str(src), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


class LifecycleTests(unittest.TestCase):
    def test_station_counter_request_is_exact_and_read_only(self):
        run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef uint8_t u8;
static uint16_t get_unaligned_le16(const u8 *p) { return p[0] | (uint16_t)p[1]<<8; }
static uint64_t get_unaligned_le64(const u8 *p) {
    uint64_t value=0; unsigned int i;
    for (i=0;i<8;i++) value |= (uint64_t)p[i]<<(8*i);
    return value;
}
''' + function("s49/n1-alpha-transport-v9.c", "valid_station_counters") + r'''
int main(void)
{
    u8 request[47]={0},changed[47];
    unsigned int length,byte,bit;
    request[28]=0x20; request[32]=1;
    request[33]=0x6b; request[34]=1; request[35]=9;
    assert(valid_station_counters(request,46,false));
    assert(!valid_station_counters(NULL,46,false));
    assert(!valid_station_counters(request,46,true));
    for (length=0;length<sizeof(request)+1;length++)
        if (length!=46) assert(!valid_station_counters(request,length,false));
    for (byte=24;byte<46;byte++) for (bit=0;bit<8;bit++) {
        memcpy(changed,request,sizeof(request)); changed[byte]^=1u<<bit;
        assert(!valid_station_counters(changed,46,false));
    }
    return 0;
}
''')

    def test_fresh_and_reset_owners_are_exclusive(self):
        run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
struct n1_alpha { int unused; };
struct alpha_restart {
    struct { void *memory; struct n1_alpha *owner; } shared;
    void *previous;
    uint64_t magic;
};
''' + function("s49/n1-alpha-transport-v9.c", "previous_matches") + r'''
int main(void)
{
    struct n1_alpha owner = {0}, other = {0};
    struct alpha_restart marker;
    unsigned int bits;
    assert(previous_matches(NULL, &owner, true));
    assert(!previous_matches(NULL, &owner, false));
    /* Fresh mode must reject a non-null owner without dereferencing it. */
    assert(!previous_matches((void *)(uintptr_t)1, &owner, true));
    for (bits = 0; bits < 16; bits++) {
        marker.shared.owner = bits & 1 ? &other : &owner;
        marker.magic = bits & 2 ? 0 : UINT64_C(0x533534414c504841);
        marker.shared.memory = bits & 4 ? &marker : NULL;
        marker.previous = bits & 8 ? NULL : &marker;
        assert(!previous_matches(&marker, &owner, true));
        assert(previous_matches(&marker, &owner, false) == (bits == 0));
    }
    return 0;
}
''')

    def test_stop_wins_over_worker_finishing_during_cancel(self):
        run_c(r'''
#include <assert.h>
#include <stdbool.h>
struct net_device { bool carrier, queue; void *priv; };
struct delayed_work { struct net_device *dev; bool in_flight, joined; };
struct sk_buff_head { struct delayed_work *work; unsigned int count; };
struct n1_front {
    bool stopping;
    struct delayed_work work;
    struct sk_buff_head tx;
};
#define WRITE_ONCE(value, new_value) ((value) = (new_value))
static void *netdev_priv(struct net_device *d) { return d->priv; }
static void netif_stop_queue(struct net_device *d) { d->queue = false; }
static void netif_carrier_off(struct net_device *d) { d->carrier = false; }
static void cancel_delayed_work_sync(struct delayed_work *w)
{
    struct n1_front *s = w->dev->priv;
    assert(s->stopping);
    assert(!w->dev->queue && !w->dev->carrier);
    /* A worker which already passed its stopping check can finish here. */
    if (w->in_flight) w->dev->queue = w->dev->carrier = true;
    w->joined = true;
}
static void skb_queue_purge(struct sk_buff_head *q)
{
    assert(q->work->joined);
    q->count = 0;
}
''' + function("s55/n1-packet-netdev.c", "net_stop") + r'''
int main(void)
{
    unsigned int mode;
    for (mode = 0; mode < 2; mode++) {
        struct n1_front s = {0};
        struct net_device dev = { .carrier = true, .queue = true, .priv = &s };
        s.work.dev = &dev;
        s.work.in_flight = mode;
        s.tx.work = &s.work;
        s.tx.count = 128;
        assert(net_stop(&dev) == 0);
        assert(s.stopping && s.work.joined && !s.tx.count);
        assert(!dev.carrier && !dev.queue);
    }
    return 0;
}
''')


if __name__ == "__main__":
    unittest.main()
