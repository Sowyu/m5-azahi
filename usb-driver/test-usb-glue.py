#!/usr/bin/env python3
"""Compile the real glue init function with mocked kernel calls, no hardware.

Checks control flow only, not kernel API correctness or physical teardown.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def function(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


class GlueTest(unittest.TestCase):
    def test_fixed_host_remove_control_flow(self):
        source = (HERE / 'dwc3-apple-t6050.c').read_text()
        remove = function(source, 'static void dwc3_apple_remove(')
        harness = r'''
#include <assert.h>
#include <stdbool.h>
enum dwc3_apple_state { DWC3_APPLE_PROBE_PENDING, DWC3_APPLE_NO_CABLE,
                       DWC3_APPLE_HOST, DWC3_APPLE_DEVICE };
struct dwc3 { int unused; };
struct device { int unused; };
struct platform_device { struct device dev; struct dwc3 *data; };
struct dwc3_apple { struct dwc3 dwc; int lock; void *reset, *role_sw;
                   enum dwc3_apple_state state; };
static int removes, resets, exits, unregisters, locks;
static struct dwc3 *platform_get_drvdata(struct platform_device *p) { return p->data; }
static struct dwc3_apple *to_dwc3_apple(struct dwc3 *d) { return (void *)d; }
#define guard(x) lock_guard
static void lock_guard(int *p) { ++locks; }
static bool device_property_read_bool(struct device *d, const char *s) { return true; }
static void dwc3_core_remove(struct dwc3 *d) { ++removes; }
static int reset_control_assert(void *r) { ++resets; return 0; }
static void usb_role_switch_unregister(void *s) { ++unregisters; }
static int dwc3_apple_exit(struct dwc3_apple *a) { ++exits; return 0; }
'''
        cases = r'''
int main(void) {
    struct dwc3_apple a = {.state=DWC3_APPLE_HOST};
    struct platform_device p = {.data=&a.dwc};
    dwc3_apple_remove(&p);
    assert(removes == 1 && resets == 1 && locks == 1);
    assert(exits == 0 && unregisters == 0);
    a.state = DWC3_APPLE_PROBE_PENDING;
    dwc3_apple_remove(&p);
    assert(removes == 1 && resets == 2 && locks == 2);
    assert(exits == 0 && unregisters == 0);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='usb-remove-test-') as temporary:
            path = Path(temporary)
            (path / 'test.c').write_text(harness + remove + cases)
            subprocess.run(['/usr/bin/cc', '-std=c11', '-Wall', '-Werror',
                            str(path / 'test.c'), '-o', str(path / 'test')], check=True)
            subprocess.run([str(path / 'test')], check=True)

    def test_real_init_failure_and_success_paths(self):
        source = (HERE / 'dwc3-apple-t6050.c').read_text()
        init = function(source, 'static int dwc3_apple_init(')
        harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <errno.h>
enum dwc3_apple_state { DWC3_APPLE_PROBE_PENDING, DWC3_APPLE_NO_CABLE,
                       DWC3_APPLE_HOST, DWC3_APPLE_DEVICE };
enum { USB_DR_MODE_UNKNOWN, USB_DR_MODE_HOST, USB_DR_MODE_PERIPHERAL,
       PHY_MODE_USB_HOST, PHY_MODE_USB_DEVICE, DWC3_GCTL_PRTCAP_HOST,
       DWC3_GCTL_PRTCAP_DEVICE };
struct dwc3 { void *usb2_generic_phy[1], *usb3_generic_phy[1], *xhci; int dr_mode; };
struct dwc3_apple { struct dwc3 dwc; void *dev, *reset; int lock; enum dwc3_apple_state state; };
static int fixed, core_fail, host_fail, reset_fail, exits, removes, resets;
#define lockdep_assert_held(...) ((void)0)
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define WARN_ON_ONCE(...) ((void)0)
static bool device_property_read_bool(void *d, const char *s) { return fixed; }
static void phy_set_mode(void *p, int m) {}
static int reset_control_deassert(void *p) { return reset_fail; }
static int reset_control_assert(void *p) { ++resets; return 0; }
static int dwc3_apple_core_init(struct dwc3_apple *a) {
    if (!core_fail) a->state = DWC3_APPLE_NO_CABLE;
    return core_fail;
}
static void dwc3_apple_setup_cio(struct dwc3_apple *a) {}
static void dwc3_apple_set_ptrcap(struct dwc3_apple *a, int mode) {}
static void dwc3_enable_susphy(struct dwc3 *d, bool b) {}
static int dwc3_host_init(struct dwc3 *d) { d->xhci = (void *)1; return host_fail; }
static int dwc3_gadget_init(struct dwc3 *d) { return host_fail; }
static void dwc3_core_exit(struct dwc3 *d) { ++exits; }
static void dwc3_core_remove(struct dwc3 *d) {
    assert(d->dr_mode == USB_DR_MODE_UNKNOWN);
    assert(d->xhci == NULL);
    ++removes; dwc3_core_exit(d);
}
'''
        cases = r'''
int main(void) {
    struct dwc3_apple a = {0};
    fixed = 1; core_fail = -EIO;
    assert(dwc3_apple_init(&a, DWC3_APPLE_HOST) == -EIO);
    assert(removes == 0 && exits == 0 && resets == 1);
    core_fail = 0; host_fail = -ENOMEM; resets = 0;
    assert(dwc3_apple_init(&a, DWC3_APPLE_HOST) == -ENOMEM);
    assert(removes == 1 && exits == 1 && resets == 1);
    assert(a.state == DWC3_APPLE_PROBE_PENDING);
    host_fail = 0; exits = removes = resets = 0;
    assert(dwc3_apple_init(&a, DWC3_APPLE_HOST) == 0);
    assert(a.state == DWC3_APPLE_HOST);
    assert(exits == 0 && removes == 0 && resets == 0);
    a.state = DWC3_APPLE_PROBE_PENDING; reset_fail = -EIO;
    assert(dwc3_apple_init(&a, DWC3_APPLE_HOST) == -EIO);
    assert(exits == 0 && removes == 0);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='usb-glue-test-') as temporary:
            path = Path(temporary)
            (path / 'test.c').write_text(harness + init + cases)
            subprocess.run(['/usr/bin/cc', '-std=c11', '-Wall', '-Werror', '-Wno-unused-function',
                            str(path / 'test.c'), '-o', str(path / 'test')], check=True)
            subprocess.run([str(path / 'test')], check=True)

    def test_phy_reinit_after_shutdown_is_gated(self):
        source = (HERE / 'phy-apple-t6050-usb2.c').read_text()
        defines = '\n'.join(line for line in source.splitlines()
                            if line.startswith('#define USB2PHY_'))
        names = ['struct t6050_tunable {', 'struct t6050_usb2_phy {']
        structs = '\n'.join(function(source, n) + ';' for n in names)
        bodies = '\n'.join(function(source, s) for s in (
            'static inline void t6050_mask32(', 'static inline void t6050_set32(',
            'static inline void t6050_clear32(', 'static void t6050_usb2_dump(',
            'static void t6050_apply_tunables(', 'static void t6050_usb2_shutdown_seq(',
            'static void t6050_usb2_init_seq(', 'static int t6050_usb2_power_on(',
            'static int t6050_usb2_power_off(', 'static bool t6050_usb2_is_shut_down(',
            'static int t6050_usb2_init(', 'static int t6050_usb2_exit('))
        harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
typedef unsigned int u32;
#define __iomem
#define BIT(n) (1u << (n))
#define GENMASK(h, l) (((~0u) >> (31 - (h))) & ~((1u << (l)) - 1))
#define FIELD_PREP(m, v) (((u32)(v) << __builtin_ctz(m)) & (m))
#define FIELD_GET(m, v) (((v) & (m)) >> __builtin_ctz(m))
#define TUNABLE_MAX_ENTRIES 16
#define READ_ONCE(x) (x)
#define guard(x) lock_guard
struct device;
static void dev_info(struct device *d, const char *f, ...) { (void)d; (void)f; }
static void dev_warn(struct device *d, const char *f, ...) { (void)d; (void)f; }
static void dev_dbg(struct device *d, const char *f, ...) { (void)d; (void)f; }
enum phy_mode { PHY_MODE_INVALID, PHY_MODE_USB_HOST };
struct mutex { int unused; };
struct device { int unused; };
struct phy { void *drvdata; };
static void lock_guard(struct mutex *m) { (void)m; }
static void *phy_get_drvdata(struct phy *p) { return p->drvdata; }
static void msleep(int ms) { (void)ms; }
static void udelay(int us) { (void)us; }
static int writes;
static u32 readl(const void *p) { u32 v; memcpy(&v, p, 4); return v; }
static void writel(u32 v, void *p) { ++writes; memcpy(p, &v, 4); }
static bool reinit_after_shutdown;
'''
        cases = r'''
static u32 bank0[0x4000 / 4], bank1[0x4000 / 4];
static void set_state(bool shut_down) {
    memset(bank0, 0, sizeof(bank0)); memset(bank1, 0, sizeof(bank1));
    if (shut_down) {
        bank0[USB2PHY_CTL / 4] = USB2PHY_CTL_RESET | USB2PHY_CTL_PORT_RESET | USB2PHY_CTL_SIDDQ;
        bank0[USB2PHY_USBCTL / 4] = USB2PHY_USBCTL_MODE_ISOLATION;
        bank0[USB2PHY_MISCTUNE / 4] = USB2PHY_MISCTUNE_APBCLK_GATE_OFF | USB2PHY_MISCTUNE_REFCLK_GATE_OFF;
    } else {
        bank0[USB2PHY_USBCTL / 4] = USB2PHY_USBCTL_MODE_RUN;
    }
    writes = 0;
}
static bool running(void) {
    return !(bank0[USB2PHY_CTL / 4] & (USB2PHY_CTL_RESET | USB2PHY_CTL_SIDDQ)) &&
           !(bank0[USB2PHY_MISCTUNE / 4] & (USB2PHY_MISCTUNE_APBCLK_GATE_OFF | USB2PHY_MISCTUNE_REFCLK_GATE_OFF)) &&
           (bank0[USB2PHY_USBCTL / 4] & 7) == USB2PHY_USBCTL_MODE_RUN;
}
int main(void) {
    struct t6050_usb2_phy t = {0};
    struct phy p = { &t };
    t.usb2 = (void *)bank0; t.evt = (void *)bank1; t.mode = PHY_MODE_USB_HOST;

    /* Default off: init never writes, loader-running and shut-down alike. */
    for (int s = 0; s < 2; s++) {
        set_state(s); t.powered = false; reinit_after_shutdown = false;
        assert(t6050_usb2_init(&p) == 0 && writes == 0 && !t.powered);
        assert(t6050_usb2_exit(&p) == 0 && writes == 0);
    }
    /* Loader-running PHY: even when enabled, init leaves it to power_on. */
    set_state(false); reinit_after_shutdown = true;
    assert(t6050_usb2_init(&p) == 0 && writes == 0 && !t.powered);
    assert(t6050_usb2_power_on(&p) == 0 && writes > 0 && t.powered && running());
    assert(t6050_usb2_power_off(&p) == 0 && !t.powered && !running());
    /* Shut-down PHY with the parameter: init brings it up, power_on is then a no-op. */
    set_state(true); reinit_after_shutdown = true;
    assert(t6050_usb2_init(&p) == 0 && writes > 0 && t.powered && running());
    writes = 0;
    assert(t6050_usb2_power_on(&p) == 0 && writes == 0);
    assert(t6050_usb2_power_off(&p) == 0 && !t.powered && t6050_usb2_is_shut_down(&t));
    writes = 0;
    assert(t6050_usb2_exit(&p) == 0 && writes == 0);
    /* dwc3 error path after init (soft reset failed): exit shuts it down again. */
    set_state(true);
    assert(t6050_usb2_init(&p) == 0 && t.powered);
    assert(t6050_usb2_exit(&p) == 0 && !t.powered && t6050_usb2_is_shut_down(&t));
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='usb-phy-test-') as temporary:
            path = Path(temporary)
            (path / 'test.c').write_text(harness + defines + '\n' + structs + '\n' +
                                         bodies + cases)
            subprocess.run(['/usr/bin/cc', '-std=gnu11', '-Wall', '-Werror',
                            '-Wno-unused-function', str(path / 'test.c'),
                            '-o', str(path / 'test')], check=True)
            subprocess.run([str(path / 'test')], check=True)

    def test_fixed_host_does_not_register_role_switch(self):
        source = (HERE / 'dwc3-apple-t6050.c').read_text()
        probe = function(source, 'static int dwc3_apple_probe(')
        guarded = function(probe, 'if (!device_property_read_bool(dev, "azahi,force-host-mode"))')
        self.assertIn('dwc3_apple_setup_role_switch', guarded)
        self.assertEqual(probe.count('dwc3_apple_setup_role_switch'), 1)

    def test_overlay_dry_run_precedes_peripheral_reads(self):
        source = (HERE / 'azahi-usb-overlay.c').read_text()
        init = function(source, 'static int __init azahi_usb_overlay_init(')
        dry = function(init, 'if (dry_run)')
        self.assertIn('return 0;', dry)
        self.assertLess(init.index('if (dry_run)'), init.index('preflight_blocks()'))
        self.assertLess(init.index('if (!active)'), init.index('preflight_blocks()'))
        self.assertNotIn('module_param(force', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
