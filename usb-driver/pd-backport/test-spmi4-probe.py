#!/usr/bin/env python3
"""Run the real SPMI4 probe with fake resources and an attached-domain marker.

Checks probe refusals and error ordering, not Linux genpd or hardware power.
"""
import argparse
import os
from pathlib import Path
import runpy
import subprocess

HERE = Path(__file__).resolve().parent
helpers = runpy.run_path(str(HERE.parent / 'test-usb-glue.py'))
function = helpers['function']
temporary_directory = helpers['temporary_directory']

PRELUDE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "spmi4-transport.h"
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define __iomem
#define IORESOURCE_MEM 1
#define IORESOURCE_MEM_NONPOSTED 2
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define ERR_PTR(n) ((void *)(intptr_t)(n))
struct mutex { int unused; };
struct device { void *of_node, *pm_domain; };
struct platform_device { struct device dev; };
struct resource { uint64_t start, size; unsigned int flags; };
struct spmi_controller {
    struct device dev;
    int (*read_cmd)(struct spmi_controller *, u8, u8, u16, u8 *, size_t);
    int (*write_cmd)(struct spmi_controller *, u8, u8, u16, const u8 *, size_t);
    int (*cmd)(struct spmi_controller *, u8, u8);
};
static bool allow_probe, azahi_spmi4_poisoned, right_machine, resource_present;
static int property_error, alloc_error, map_error, add_error;
static int reads, adds, warnings;
static u32 generation, bank[0x4000 / 4];
static struct resource resource;
static struct platform_device pdev;
static struct spmi_controller controller;
static int of_machine_is_compatible(const char *s) {
    assert(!strcmp(s, "apple,j714s")); return right_machine;
}
static int of_property_read_u32(void *n, const char *s, u32 *value) {
    assert(n == pdev.dev.of_node && !strcmp(s, "azahi,spmi-generation"));
    *value = generation; return property_error;
}
static struct resource *platform_get_resource(struct platform_device *p, int t, int i) {
    assert(p == &pdev && t == IORESOURCE_MEM && i == 0);
    return resource_present ? &resource : NULL;
}
static uint64_t resource_size(struct resource *r) { return r->size; }
static int dev_err_probe(struct device *d, int error, const char *s) {
    assert(d == &pdev.dev && s); return error;
}
static void *devm_ioremap_resource(struct device *d, struct resource *r) {
    assert(d == &pdev.dev && r == &resource);
    return map_error ? ERR_PTR(map_error) : bank;
}
static u32 readl(void *address) {
    /* A cold controller read is the original failure, even when FIFO is idle. */
    assert(pdev.dev.pm_domain);
    assert(address == (char *)bank + SPMI4_STATUS);
    ++reads; return bank[SPMI4_STATUS / 4];
}
static void mutex_init(struct mutex *m) { (void)m; }
static void dev_warn(struct device *d, const char *s) {
    assert(d == &pdev.dev && s); ++warnings;
}
static u32 azahi_spmi4_read(void *c, u32 o) { (void)c; (void)o; return 0; }
static void azahi_spmi4_write(void *c, u32 o, u32 v) { (void)c; (void)o; (void)v; }
static void azahi_spmi4_delay(void *c, unsigned int u) { (void)c; (void)u; }
static int azahi_spmi4_read_cmd(struct spmi_controller *c, u8 o, u8 s,
                              u16 a, u8 *b, size_t n) { return 0; }
static int azahi_spmi4_write_cmd(struct spmi_controller *c, u8 o, u8 s,
                               u16 a, const u8 *b, size_t n) { return 0; }
static int azahi_spmi4_cmd(struct spmi_controller *c, u8 o, u8 s) { return 0; }
'''

ALLOCATION = r'''
static struct azahi_spmi4 state;
static struct spmi_controller *devm_spmi_controller_alloc(struct device *d, size_t size) {
    assert(d == &pdev.dev && size == sizeof(state));
    return alloc_error ? ERR_PTR(alloc_error) : &controller;
}
static void *spmi_controller_get_drvdata(struct spmi_controller *c) {
    assert(c == &controller); return &state;
}
static int devm_spmi_controller_add(struct device *d, struct spmi_controller *c) {
    assert(d == &pdev.dev && c == &controller && reads == 1);
    assert(c->dev.of_node == pdev.dev.of_node);
    assert(c->read_cmd == azahi_spmi4_read_cmd);
    assert(c->write_cmd == azahi_spmi4_write_cmd && c->cmd == azahi_spmi4_cmd);
    assert(state.io.context == &state && state.io.read == azahi_spmi4_read);
    assert(state.io.write == azahi_spmi4_write && state.io.delay == azahi_spmi4_delay);
    ++adds; return add_error;
}
'''

CASES = r'''
static void reset(void) {
    allow_probe = right_machine = resource_present = true;
    azahi_spmi4_poisoned = false;
    property_error = alloc_error = map_error = add_error = 0;
    reads = adds = warnings = 0;
    generation = 4;
    resource = (struct resource){0x28a1a8000ULL, 0x4000,
                               IORESOURCE_MEM | IORESOURCE_MEM_NONPOSTED};
    pdev.dev.of_node = &pdev;
    pdev.dev.pm_domain = &controller;
    memset(&controller, 0, sizeof(controller));
    memset(&state, 0, sizeof(state));
    memset(bank, 0, sizeof(bank));
    bank[SPMI4_STATUS / 4] = SPMI4_RX_EMPTY | SPMI4_TX_EMPTY;
}
static void refused(int error) {
    assert(azahi_spmi4_probe(&pdev) == error);
    assert(reads == 0 && adds == 0 && warnings == 0);
}
int main(void) {
    reset(); allow_probe = false; refused(-EPERM);
    reset(); azahi_spmi4_poisoned = true; refused(-EIO);
    reset(); right_machine = false; refused(-ENODEV);
    reset(); property_error = -EINVAL; refused(-EINVAL);
    reset(); generation = 3; refused(-EINVAL);
    reset(); resource_present = false; refused(-EINVAL);
    reset(); resource.start += 0x4000; refused(-EINVAL);
    reset(); resource.size -= 4; refused(-EINVAL);
    reset(); resource.flags &= ~IORESOURCE_MEM_NONPOSTED; refused(-EINVAL);
    reset(); pdev.dev.pm_domain = NULL; refused(-ENODEV);
    reset(); alloc_error = -ENOMEM; refused(-ENOMEM);
    reset(); map_error = -EBUSY; refused(-EBUSY);
    reset(); bank[SPMI4_STATUS / 4] = 0;
    assert(azahi_spmi4_probe(&pdev) == -EBUSY);
    assert(reads == 1 && adds == 0 && warnings == 0);
    reset(); add_error = -EIO;
    assert(azahi_spmi4_probe(&pdev) == -EIO);
    assert(reads == 1 && adds == 1 && warnings == 0);
    reset(); assert(azahi_spmi4_probe(&pdev) == 0);
    assert(reads == 1 && adds == 1 && warnings == 1);
    puts("PASS: 15 probe paths; no MMIO without an attached power domain");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=HERE / 'spmi4-controller.c',
                        help='Controller source, including a regression mutation')
    args = parser.parse_args()
    source = args.source.read_text()
    struct = function(source, 'struct azahi_spmi4 {') + ';\n'
    probe = function(source, 'static int azahi_spmi4_probe(')
    with temporary_directory(prefix='spmi4-probe-') as output:
        unit = output / 'test.c'
        unit.write_text(PRELUDE + struct + ALLOCATION + probe + CASES)
        subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-O1', '-g',
                        '-Wall', '-Werror', '-Wno-unused-function', '-fno-pie', '-no-pie',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-I', str(HERE), str(unit), '-o', str(output / 'test')], check=True)
        subprocess.run([str(output / 'test')], check=True)


if __name__ == '__main__':
    main()
