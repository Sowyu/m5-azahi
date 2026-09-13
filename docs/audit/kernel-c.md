# Kernel C audit: m5-azahi

Scope: usb-driver/{phy-apple-t6050-usb2.c, dwc3-apple-t6050.c, azahi-usb-overlay.c},
usb-driver/pd-backport/*, input-driver/dockchannel-hid.c, nvme-driver/{apple.c, sart.c,
root-write-policy.h, test-root-write-policy.c}. Read in full; dwc3-apple-t6050.c, apple.c
and sart.c were diffed against the vendored 7.0.13 originals in the tree.

**Counts: 1 critical, 4 high, 29 medium, 34 low (68 findings).**

---

## input-driver/dockchannel-hid.c

### C1 (critical) — line 1079-1081: out-of-range interface index is logged but not rejected

```c
	if (hdr.iface >= MAX_INTERFACES) {
		dev_err(dchid->dev, "Bad iface %d\n", hdr.iface);
	}

	iface = dchid->ifaces[hdr.iface];
```

The `goto done;` is missing, so execution falls through and indexes `ifaces[16..255]`.
Upstream Asahi's `dchid_handle_packet()` bails out here; this is a local regression.

Why it matters: `hdr.iface` is a `u8` taken straight off the wire from the MTP
coprocessor. `struct dockchannel_hid` lays out `ifaces[16]` immediately before
`u8 pkt_buf[MAX_PKT_SIZE]`, and `pkt_buf` has already been filled with this packet's
body (line 1064) by the time the read happens. Indices 16..255 therefore read a
64-bit pointer built from packet bytes the peer controls. That pointer is then
dereferenced and written through: `dchid_handle_ack()` does `iface->resp_size = ...`,
`iface->out_report = -1`, `complete(&iface->out_complete)`, and the report path does
`queue_work(iface->wq, ...)`. This is arbitrary kernel read/write from a
firmware-controlled field, on the always-listening keyboard/trackpad transport.

Fix: add `goto done;` inside the `if`.

### H1 (high) — line 1005-1044 / 323-357: ACK handler touches `resp_buf` with no lock against the timeout path

`dchid_handle_ack()` runs in the dockchannel receive callback and reads
`iface->out_flags`, `iface->out_report`, `iface->resp_buf`, `iface->resp_size` with no
synchronisation. `dchid_cmd()` clears those fields under `iface->out_mutex` after a
1 s `wait_for_completion_timeout()` expires.

Why it matters: a late ACK that races the timeout can pass the `iface->resp_buf &&
iface->resp_size` test and then `memcpy()` into the caller's stack buffer after
`dchid_cmd()` has returned (see `dchid_handle_ready()`, which passes `&dchid->device_id`
and `dchid->serial`, and `dchid_raw_request()`, which passes a HID core buffer).
Stack/heap corruption with device-supplied bytes.

Fix: take `iface->out_mutex` in `dchid_handle_ack()` (it already runs in a sleepable
context), or snapshot `resp_buf`/`resp_size` under a spinlock and have `dchid_cmd()`
clear them under the same lock before returning on timeout.

### M1 (medium) — line 1038-1043: returned response length is the device's, not the copied length

```c
	if (iface->resp_buf && iface->resp_size)
		memcpy(iface->resp_buf, payload + 1, min((size_t)shdr->length - 1, iface->resp_size));

	iface->resp_size = shdr->length;
```

`dchid_cmd()` then returns `iface->resp_size`. If the device reports a length larger
than the caller's buffer, the caller is told more bytes arrived than were copied.
`dchid_handle_ready()` uses that value to decide whether the STM ID is valid
(`ret < sizeof(dchid->device_id)`), and `dchid_get_report_cmd()` returns `ret - 1` to
the HID core, which will read uninitialised bytes.

Fix: set `iface->resp_size` to the number of bytes actually copied.

### M2 (medium) — line 1214-1217: `dockchannel_hid_remove()` is `BUG_ON(1)`

A `driver_unbind` write from root panics the machine, and the module can never be
unloaded. The README warns about it, so it is known, but a `BUG_ON` in a remove hook is
still a denial of service reachable from sysfs.

Fix: set `.suppress_bind_attrs = true` in the driver struct and make remove a no-op
(or implement real teardown). At minimum the `BUG_ON` should be `WARN_ON` plus a
refusal, not a panic.

### M3 (medium) — line 236-250: workqueue and OF node leak in `dchid_get_interface()`

`alloc_ordered_workqueue()` succeeds, then the `!iface->of_node` path returns NULL
without `destroy_workqueue()`. The `devm_kzalloc`'d `iface` and the `devm_kstrdup`'d
name also stay allocated. Each init packet naming an unknown subdevice repeats the leak,
and the coprocessor controls how many such packets arrive.

Additionally `of_get_child_by_name()` (line 246) takes a reference that is never
released on any path.

Fix: `destroy_workqueue(iface->wq)` before the error return; drop the OF reference in a
teardown path, or use `of_node_put()` once the node pointer is no longer needed.

### M4 (medium) — line 1102-1104: allocation failure stops the receive pipeline forever

```c
	work = kzalloc(sizeof(*work) + hdr.length, GFP_KERNEL);
	if (!work)
		return;
```

Every other error path uses `goto done`, which re-arms `dockchannel_await()`. This one
returns without re-arming, so a single failed allocation permanently kills the keyboard
and trackpad until reboot.

Fix: `goto done;`.

### M5 (medium) — line 373-397: the J714s v2 power path is keyed off the machine compatible inside the transport

Local change (the `AZAHI_V2_POWER` log line marks it). Three problems:

1. `of_machine_is_compatible("apple,j714s")` is consulted on every reset call rather
   than being resolved once into driver match data or a DT property on the node. Any
   other T6050-class board that needs the same protocol has to be added by editing C.
2. Each `dchid_reset_interface()` call now issues *two* comm commands (will/has phases),
   so `dchid_start_interface()`'s `reset(0)` + `reset(2)` becomes four round trips; the
   `state` byte is placed at `v2[3]` and the phase at `v2[4]`, and only the second
   command's return value reaches the caller.
3. `msg[]` is left declared and unused on the J714s path (`-Wunused-variable` is not
   triggered because it is initialised, but it is dead on that branch).

Fix: move the selection to `of_device_id.data` or a `azahi,power-protocol = <2>`
property on the dockchannel node, and check both phase results.

### M6 (medium) — line 448-453: firmware header is dereferenced before the size check

```c
	hdr = (struct fw_header *)fw->data;

	if (hdr->magic != FW_MAGIC || ...)
```

`request_firmware()` can return a file shorter than `sizeof(struct fw_header)` (20
bytes); the magic/version/length reads are then out of bounds of the firmware buffer.

Fix: `if (fw->size < sizeof(*hdr)) { ret = -EINVAL; goto done; }` first.

### L1 (low) — line 853-862: zero-length product-name block reads `product[-1]`

`INIT_PRODUCT_NAME` handling does `product[blk->length - 1]` with no `blk->length > 0`
check. A block header claiming length 0 reads one byte before the buffer.
Fix: skip the block when `blk->length == 0`.

### L2 (low) — line 833-837: GPIO request block validated against the wrong length

`if (sizeof(*req) > length)` uses the bytes remaining in the whole packet, not
`blk->length`. A short GPIO block can read fields belonging to the following block.
Fix: validate against `blk->length`.

### L3 (low) — line 976-988: sub-header is read before it is known to exist

`dchid_packet_work()` dereferences `shdr->flags` and `shdr->length` before checking
`shdr->length + sizeof(*shdr) > work->hdr.length`. If `hdr.length < 8` the allocation
`kzalloc(sizeof(*work) + hdr.length)` is shorter than the sub-header. The `dev_err`
argument `work->hdr.length - sizeof(*shdr)` also underflows as `size_t`.
Fix: check `work->hdr.length >= sizeof(*shdr)` first.

### L4 (low) — line 21: include path points into a build tree

`#include "build/linux-7.0.13/drivers/hid/hid-ids.h"` hard-codes a relative path into a
kernel source checkout. Upstream uses `#include "hid-ids.h"` with `-I drivers/hid`.
Fix: add the include directory in the build script and use the bare name.

### L5 (low) — line 725-733: `iface->creating` is never cleared

If `hid_add_device()` fails in the work item, `creating` stays true and
`dchid_create_interface()` returns `-EBUSY` forever, so the interface can never come
back without a reboot.
Fix: clear `iface->creating` at the end of `dchid_create_interface_work()`.

### L6 (low) — line 1198, 236: workqueues are never destroyed

`new_iface_wq` and every `iface->wq` are plain `alloc_workqueue()` allocations with no
`destroy_workqueue()` anywhere (remove is `BUG_ON`). They leak on the probe error path
at line 1202-1206 as well.
Fix: use `devm_add_action_or_reset()` for each workqueue.

### L7 (low) — line 743: descriptor is re-duplicated on every init packet

`devm_kmemdup()` per `INIT_HID_DESCRIPTOR` block; repeated init packets accumulate
devm allocations for the life of the device.
Fix: free the previous `hid_desc` or ignore a second descriptor for the same interface.

---

## usb-driver/phy-apple-t6050-usb2.c

### M7 (medium) — line 146-147 vs 231, 250: registers are read after their clocks are gated

`t6050_usb2_shutdown_seq()` finishes by setting `USB2PHY_MISCTUNE_APBCLK_GATE_OFF` and
`USB2PHY_MISCTUNE_REFCLK_GATE_OFF`, and asserting `USB2PHY_CTL_RESET`. Both callers then
immediately call `t6050_usb2_dump()` ("after shutdown", "after power_off"), which does
seven `readl()`s against that same bank, including the event block.

Why it matters: the driver's own comments and the sibling overlay module state that
touching a gated block on this SoC SErrors. At best the dump prints meaningless values;
at worst it hangs or faults the CPU. `t6050_usb2_init_seq()` clears the same two bits
before doing anything that reads status, which shows the author knows the ordering.

Fix: drop the dump after shutdown, or read the snapshot before setting the gate bits.

### M8 (medium) — line 5-19: register sequence transcribed from an Apple kernelcache, shipped under GPL-2.0 OR BSD-2-Clause

The file header names three `AppleT6050TypeCPhy` methods and their virtual addresses in
a saved Mac17,9 kernelcache and says the sequence is a "transcription" of them. The file
then carries an SPDX line claiming a dual GPL/BSD grant the authors are not in a
position to give for Apple-derived material. `docs/PROVENANCE.md` should be the single
place this is resolved before any publication; the same issue applies to
`nvme-driver/apple.c`'s new `APPLE_ANS_IOQ_*` registers and `sart.c`'s v4 layout.

Fix: state explicitly that only register offsets and an ordering (facts, not
expression) were recovered, cite the tooling, and keep the "not for upstream" marker.
Do not ship transcribed code under a permissive SPDX tag.

### M9 (medium) — line 332-337 + 191-203: the documented "set_mode still rejects anything else" guard is inert

`probe()` pre-sets `tphy->mode = PHY_MODE_USB_HOST` because dwc3 powers the PHY on
before any `set_mode()` arrives. `set_mode()` then only rejects a *later* switch to
device mode. Since `power_on()` only checks `tphy->mode`, the PHY will happily run the
host sequence for a consumer that never asked for host mode. On the paired dwc3 driver
the first `phy_set_mode()` is a no-op anyway (see M11), so nothing ever validates the
mode against the consumer's intent.

Fix: track "mode was explicitly set" separately from the default, and have `power_on()`
log when it is running on the default.

### L8 (low) — line 338: `mutex_init()` on devm memory with no `mutex_destroy()`

`tphy` is `devm_kzalloc`'d and freed at unbind without the mutex ever being destroyed;
with `CONFIG_DEBUG_MUTEXES`/lockdep this leaves a stale lock class.
Fix: `devm_mutex_init(dev, &tphy->lock)`. Same issue in `dwc3-apple-t6050.c:469` and
`pd-backport/spmi4-controller.c:108`.

### L9 (low) — line 292-297: an empty tunable property is accepted

`of_property_count_u32_elems()` returns 0 for a present-but-empty property; `0 % 3 == 0`
so the function returns 0 entries and the PHY comes up with no tunables applied and no
warning, which is indistinguishable from a working config in the log.
Fix: reject `count == 0`.

### L10 (low) — line 255-267: `.reset` refuses to run when the PHY is not powered

`t6050_usb2_reset()` returns `-EINVAL` unless `powered`. The comment at line 54-57 of the
dwc3 glue says a PHY reset is exactly what is needed to resynchronise the eUSB2 repeater
after a cable event, which is when the PHY may well be down.
Fix: either allow the pulse when the block is clocked, or document why the framework
never calls it in that state.

### L11 (low) — line 127: local variable named `new`

Harmless in C but blocks any future move to a C++-adjacent tool and reads badly.

---

## usb-driver/dwc3-apple-t6050.c

### M10 (medium) — line 541-549: `remove()` re-reads the DT property instead of the flag latched at probe

```c
	if (device_property_read_bool(&pdev->dev, "azahi,force-host-mode")) {
```

`probe()` already made an irreversible decision from this property (no role switch
registered, core brought up synchronously). If the overlay is changed, or the property
is removed while the driver is bound, `remove()` takes the other branch and runs
`dwc3_apple_exit()` (host_exit + `dwc3_core_exit`) *and* `dwc3_core_remove()` (which in
7.0.13 does `dwc3_exit_mode()` + `dwc3_core_exit()` again) — a double PHY exit and a
second teardown of the already-freed xhci device.

Fix: store `bool force_host` in `struct dwc3_apple` at probe and branch on that
everywhere (lines 232, 541).

### M11 (medium) — line 244-254: USB2 PHY mode is set before the PHY handle exists

`dwc3_apple_init()` calls `phy_set_mode(appledwc->dwc.usb2_generic_phy[0], ...)` before
`dwc3_apple_core_init()`, but in the `DWC3_APPLE_PROBE_PENDING` state the PHYs have not
been acquired yet — `dwc3_core_probe()` is what fills `usb2_generic_phy[]`. The pointer
is NULL, `phy_set_mode_ext()` returns 0 for a NULL phy, and the call silently does
nothing.

Why it matters: the comment directly above (lines 237-243) says the USB2 PHY "must be
configured for host or device mode while it is still powered off and before dwc3 tries
to access it. Otherwise, the new configuration will sometimes only take affect after the
*next* time dwc3 is brought up". In `azahi,force-host-mode` that first bring-up is the
only one that ever happens, so the stated requirement is never satisfied. The T6050 PHY
driver works around it by defaulting `mode` to host (see M9) — an undocumented coupling
between the two drivers.

Fix: acquire the PHYs before the first mode set, or at minimum `WARN_ON` when the phy
pointer is NULL and note the dependency on the provider's default in both files.

### M12 (medium) — line 316-329: the failure path reaches into dwc3 core internals

```c
		appledwc->dwc.dr_mode = USB_DR_MODE_UNKNOWN;
		appledwc->dwc.xhci = NULL;
		dwc3_core_remove(&appledwc->dwc);
```

Poking `dr_mode` and `xhci` to steer `dwc3_core_remove()`'s internal `dwc3_exit_mode()`
away from a second teardown works only against the exact 7.0.13 core implementation the
comment cites. Any change to `dwc3_exit_mode()` (for example keying off `prtcap_mode`
instead of `dr_mode`) silently turns this into a leak or a double free, with no build
error.

Fix: ask the core for the right primitive (an exported `dwc3_core_probe_cleanup()` or a
flag in `struct dwc3_probe_data`) rather than mutating its state from the glue layer.

### L12 (low) — line 469: `mutex_init()` with no `mutex_destroy()` — see L8.

### L13 (low) — line 523-525: probe takes the lock with bare `mutex_lock`/`mutex_unlock`

Every other site in the file uses `guard(mutex)`. Mixing styles in a file that relies on
`lockdep_assert_held()` invites a missed unlock on a future early return.

### L14 (low) — line 474-479: reset made optional with only an info log

`devm_reset_control_get_optional_exclusive()` plus "relying on loader pipehandler/DWC3
state" means the driver silently proceeds on a machine where the loader did not run.
Nothing verifies the DWC3 is actually out of reset before `dwc3_core_probe()` touches it.
Fix: read `GSNPSID` (the overlay module already does this at
`azahi-usb-overlay.c:126`) and fail probe if it does not respond.

---

## usb-driver/azahi-usb-overlay.c

### H2 (high) — line 38-55, 60-74: nine hard-coded physical addresses mapped with raw `ioremap_np()`

`PMGR0_BASE`, `PMGR2_BASE`, `USB2PHY_BASE`, `USB2EVT_BASE`, `PIPEHANDLER_BASE`,
`DWC3_BASE` are compile-time constants for one board. `read_block()` maps 0x4000 at each,
reads one register and unmaps, with no `request_mem_region()` and no reference to any DT
node or power domain.

Why it matters: the only thing standing between this and a wild MMIO access on a
different machine is the `apple,j714s` root-compatible check in `check_live_tree()`. Any
board that reuses that compatible string, or any change to the T6050 memory map between
silicon revisions, turns a diagnostic read into a bus fault. No region reservation also
means the module can read a block another driver has already claimed and is mid-sequence
on. `PIPEHANDLER_BASE` in particular is not described in the overlay at all, so no
driver owns it and nothing will ever notice a conflict.

Fix: describe these blocks in the overlay (they mostly already are — the PHY and DWC3
banks appear in `dts/t6050-j714s-usb-right-minimal.dtso`) and read them through
`of_iomap()`/`platform_get_resource()` after the overlay is applied, or take the
addresses from `reserved-memory`/a `azahi,preflight-regs` property. At minimum wrap the
maps in `request_mem_region()`.

### M13 (medium) — line 234-269: the `pmgr` variant is dead code

`if (use_pmgr) return -EOPNOTSUPP;` at line 234 makes the `use_pmgr` branches at
246-251 and 266-269 unreachable, along with `populate_pmgr()` (line 182), the
`PMGR0_NODE_PATH`/`PMGR2_NODE_PATH` defines, and the entire `overlay_pmgr` blob that
`build.sh` compiles and embeds into `overlay-blobs.h`.

Meanwhile `MODULE_PARM_DESC(variant, ...)` advertises "pmgr" as a supported value, so
the documented interface promises something the code refuses. `README.md` line 13 says
"`pmgr` live mode is withheld", which is accurate, but the module parameter description
is not.

Fix: delete the unreachable branches and the blob, or move the refusal behind a build
switch; either way update `MODULE_PARM_DESC`.

### M14 (medium) — line 254-260: `overlay_id` is a file-scope static reused across the error path

```c
	ret = of_overlay_fdt_apply(blob, blob_size, &overlay_id, NULL);
	if (ret) {
		...
		if (overlay_id)
			of_overlay_remove(&overlay_id);
```

`overlay_id` is `static int` and `of_overlay_fdt_apply()` sets it on both the success and
several failure paths. The `if (overlay_id)` test cannot distinguish "the core already
freed this changeset" from "the changeset exists and needs removing", and a changeset id
of 0 is treated as absent. On the kernels where `of_overlay_fdt_apply()` frees the
changeset itself before returning an error, this is a double removal.

Fix: initialise `overlay_id` to a sentinel before the call and follow the exact
contract of the `of_overlay_fdt_apply()` version being built against; if in doubt, do not
call `of_overlay_remove()` on the error path at all.

### L15 (low) — line 154: `of_root` used directly instead of `of_machine_is_compatible()`

`of_device_is_compatible(of_root, "apple,j714s")` open-codes what
`of_machine_is_compatible()` does, and `of_root` is exactly the module-visible global
that upstream has been removing. Every other module in this repo
(`spmi4-controller.c:94`, `hpm-once.c:50`, `sart.c:220`, `apple.c:1593`) uses the helper.
Fix: use `of_machine_is_compatible("apple,j714s")`.

### L16 (low) — line 31-32, 163-168: the AIC phandle is pinned to the literal 2

The overlay blob encodes `interrupt-parent = <2>` numerically because the live tree has
no `__symbols__`, and the module verifies phandle 2 at runtime. That is an honest guard,
but it binds the module to one specific DTB build; a rebuilt DTB with a different
phandle numbering silently fails probe with a confusing message.
Fix: resolve the phandle from the live tree and fix up the blob before applying, or
document the DTB hash the number came from.

### L17 (low) — line 60-74: `read_block()` never sets `*ok` on success

The out-parameter is write-only-on-failure and relies on every caller pre-initialising
`ok = true` and never reusing it across independent groups. `preflight_pmgr()` returns
`false` for both "mapping failed" and "domain not active", so a mapping failure is
reported to the user as "NOT all active".
Fix: return an `int` error and pass the value out, or set `*ok = true` on success.

### L18 (low) — line 273-277: `__exit` handler cannot do anything useful

Because `__module_get(THIS_MODULE)` (line 263) pins the module after a successful apply,
`azahi_usb_overlay_exit()` only ever runs in the dry-run/failure case, which the comment
acknowledges. The `applied` static therefore only ever prints 0. Harmless, but it is
three lines of code that exist to log a constant.

---

## usb-driver/pd-backport/

### H3 (high) — hpm-once.c:14-78 bypasses every containment gate the README claims for this directory

`spmi4-controller.c` is carefully gated: `allow_probe` and `allow_transactions` both
default false, and the README states "Both `allow_probe` and `allow_transactions` default
false and are read-only module parameters. ... These checks are containment".

`hpm-once.c` sits in the same directory, does not use the controller at all, and reaches
the same hardware directly:

- line 14: `#define BASE 0x28a1a8000ULL` — the same physical address, hard-coded.
- line 58-60: `request_mem_region()` + `ioremap_np()` at module init.
- line 67: `transfer(NULL, 0x13, ...)` — an SPMI **WAKEUP write** on the real bus.
- line 70: `hpm_awake_once(&h, &snapshot, !strcmp(mode, "awake"))` — with `mode=awake`
  this performs the two-write SSPS task against the USB-PD controller.

The only gate is a `charp` module parameter (`mode`, line 16). There is no `allow_*`
equivalent, no `taint`, and no attended-operation interlock in the code. `mode=probe`
also sends a bus write despite the file header advertising "Default: power/FIFO reads
only" — that sentence is true only for the literal default.

Why it matters: the USB-PD controller drives VBUS and the eUSB2 repeater for a port that
may be charging the machine. A single `insmod hpm-once.ko mode=awake` performs an
unrecoverable-by-design ("Keep ambiguous bus state pinned until reboot") state change,
with no cross-check that the sibling SPMI controller driver is not bound to the same
block. The `request_mem_region()` at line 58 is the only thing that would catch that, and
`spmi4-controller.c` claims its region through `devm_ioremap_resource()`, so the collision
is detected only in that one ordering.

Fix: give `hpm-once.c` the same two-stage `allow_*` gating, refuse to run when a driver
is already bound to the SPMI node, and rename `probe` to something that does not read as
read-only (or make it genuinely read-only).

### M15 (medium) — spmi4-controller.c:113: FIFO register is read with no power-domain check

```c
	if (!spmi4_idle(readl(s->base + SPMI4_STATUS)))
		return -EBUSY;
```

`hpm-once.c:51-57` documents the rule for this exact block — "Always-on power status
only; never write PMGR or read a gated FIFO" — and checks PMGR `0x288300000 + 0x68`
before touching `0x28a1a8000`. The controller driver does no such check, and its DT node
has no `power-domains`. With `allow_probe=1` on a machine where the controller domain is
down, this is an SError.

Fix: add `power-domains` to the binding and a `pm_runtime_resume_and_get()`, or replicate
the PMGR read-only check before the first FIFO access.

### M16 (medium) — spmi4-controller.c: the README's "rebinding is not a recovery procedure" guard is not implemented

README: "a mismatch stops the instance, even if a later hardware state might have
recovered. Rebinding is not a safe recovery procedure and must not be used to bypass a
poisoned controller."

The poisoned latch lives in `s->io.poisoned`, inside a `devm_spmi_controller_alloc()`
allocation. Unbind through sysfs frees it; rebind allocates a fresh zeroed one and the
latch is gone. The code enforces the opposite of what the document promises.

Fix: keep the latch in a file-scope static keyed by the resource address (the driver
already refuses any resource other than `0x28a1a8000`), or set `.suppress_bind_attrs =
true` so the only way to clear it is a module reload, and say so in the README.

### M17 (medium) — spmi4-controller.c:84-124: no `.remove`, no `mutex_destroy()`, `of_node` reference not taken

- There is no `.remove` callback at all; teardown relies entirely on devm.
- `mutex_init(&s->lock)` at line 108 is never paired with `mutex_destroy()`.
- Line 115 `ctrl->dev.of_node = pdev->dev.of_node;` stores the node pointer in a second
  device without `of_node_get()`. Other SPMI controllers take the reference.

Fix: `devm_mutex_init()`, and `device_set_node(&ctrl->dev, dev_fwnode(&pdev->dev))`.

### M18 (medium) — spmi4-controller.c:113 runs before `devm_spmi_controller_add()` but after the resource check; ordering is right, the *reporting* is not

If the FIFO is not idle at probe the driver returns `-EBUSY` with no message. The device
then sits unbound, and because `allow_probe` is a boot-time-only parameter (0444) the
only diagnosis available is the absence of a `dev_warn`. Given the README treats a
non-idle FIFO as a latching, reboot-requiring condition, that state deserves a loud
`dev_err` naming the observed status word.

Fix: `dev_err(&pdev->dev, "SPMI4 FIFO not idle (%#x); refusing\n", status)`.

### M19 (medium) — no-tbt-switch.patch: removes the "switch off on disconnect" calls, not just the compile-time dependency

The patch drops `typec_thunderbolt_switch_set(cd321x->tbt_switch, &tbt_switch_data)` from
the disconnect path (`cd321x_typec_update_mode()` safe-state branch, the plain-USB
branch, and `cd321x_update_work()`'s "If there was a disconnection, set PHY to off"), not
only from the TBT/USB4 connect branches. It keeps every `typec_mux_set()` call, including
the ones that push `TYPEC_TBT_MODE` and `TYPEC_MODE_USB4` states into the mux.

Why it matters: on a kernel that does have the Thunderbolt switch API, applying this
patch produces a driver that puts the mux into TBT/USB4 modes and never switches the TBT
path off on cable removal. The README is explicit that this is a compile experiment and
"does NOT itself enforce USB2-only operation", which is exactly the risk — the patch name
suggests "no Thunderbolt" but the behaviour is "Thunderbolt with the safety call
removed".

Fix: if the goal is USB2-only, force the `TPS_DATA_STATUS_TBT_CONNECTION` and
`CD321X_DATA_STATUS_USB4_CONNECTION` branches to fall through to the safe/USB state
instead of deleting the switch calls, and rename the patch.

### M20 (medium) — spmi4-transport.h:47-51 / hpm-awake.h:22-32: non-inline `static` functions in headers shared by three translation units

`spmi4_transfer()`, `spmi4_wait()`, `spmi4_fault()`, `spmi4_idle()` and the whole
`hpm_*` family are `static` (not `static inline`) in headers included by
`spmi4-controller.c`, `spmi4-host-bridge.c`, `hpm-once.c`, `test-spmi4.c` and
`test-hpm-awake.c`. Every TU gets its own copy; the build only survives because
`build.sh` passes `-Wno-unused-function`. It also means the "the tests exercise the actual
shared C transport" claim in the README is true only at source level — the host test and
the kernel module compile independent copies with different compilers and flags.

Fix: make them `static inline`, or move the implementation to a `.c` file that both the
module and the host tests link.

### L19 (low) — spmi4-controller.c:99: physical address literal used as a probe guard

`if (!r || r->start != 0x28a1a8000ULL || resource_size(r) != 0x4000) return -EINVAL;`
pins the driver to one board's memory map from C rather than from the compatible string.
It is defensible as containment, but it belongs next to the other J714s constants with a
comment naming the ADT source, not as a bare literal.

### L20 (low) — hpm-once.c:16-23: status is exported through module parameters

`result`, `ready` and `poisoned` are `module_param`s used as outputs. They show up in
`/sys/module/hpm_once/parameters/` and are writable-looking to anyone reading the module
metadata, and `result` starts at `-EINPROGRESS` which prints as `-115`.
Fix: a debugfs file or a single `pr_info` line (which the module already emits).

### L21 (low) — hpm-awake.h:50-63: protocol mismatch is reported as a timeout

`hpm_select()` breaks out of the poll loop when the selector reads back as neither `reg`
nor `reg | 0x80`, then falls into `h->failed = 1; return -ETIMEDOUT;`. A wrong selector
value and an unresponsive controller produce the same errno, which matters because the
latch is permanent and the errno is the only diagnostic.
Fix: return `-EPROTO` for the mismatch case.

### L22 (low) — spmi4-transport.h:161: `mask = (1u << in_len) - 1u` is a reply-ACK check with no name

The reply's bits 31:16 are compared against a mask derived from the byte count. It is
correct for `in_len` in 0..16, but the expression encodes a wire-format assumption with
no comment, and `in_len == 0` folds to "the top half must be zero", which is a different
rule than the read case.
Fix: split the write-ack and read-ack checks and name the field.

### L23 (low) — test-spmi4.c:133: the write test asserts against the read fixture

`assert(f.writes[i] == replies[i])` reuses the `replies[]` array (built for the extended
*read* case) as the expected packed payload for the extended *write* case. It happens to
be correct because both directions use the same little-endian packing, but a future
change to either packing rule would make the test pass for the wrong reason.

### L24 (low) — spmi4-host-bridge.c: host-only file carries a kernel SPDX tag and no build guard

It defines non-static `azahi_spmi4_transfer`/`azahi_spmi4_io_size`. Nothing prevents it
from being added to a kernel build, where it would export duplicate symbols for the
header's static functions.
Fix: `#ifdef __KERNEL__ #error` at the top, matching the pattern already used in
`root-write-policy.h`.

---

## nvme-driver/apple.c

### H4 (high) — line 1156-1162 vs 1026-1080: the read-only build makes controller timeout recovery impossible

```c
	if (apple_rtkit_is_running(anv->rtk)) {
		if (anv->hw->j714s_readonly) {
			dev_err(anv->dev, "J714S_RO refuses runtime reset; power cycle required\n");
			ret = -EIO;
			goto out;
		}
```

`apple_nvme_timeout()` (line 1075-1080) documents that "aborting commands isn't
supported which leaves a full reset as our only option" and calls `nvme_reset_ctrl()`.
On the J714s read-only path that reset work now fails immediately with `-EIO`.

Why it matters: any single command timeout — which is the expected outcome of the
`J714S_IO_GUARD` path itself under some workloads, and of any firmware hiccup — leaves
the controller in `NVME_CTRL_RESETTING` with no path back to `LIVE`. The root filesystem
is on this device. The `out:` label's normal behaviour (`nvme_change_ctrl_state(...,
NVME_CTRL_DEAD)` or similar in the upstream flow) means the machine loses its disk
rather than recovering, and the log line tells the user to power cycle a machine whose
root device just went away.

Fix: allow the soft reset path (it does not mutate media) and keep the refusal only for
the coprocessor power reset at line 1178-1185, or mark the controller dead explicitly and
document that a timeout is fatal by design.

### M21 (medium) — line 869-902: the guard blocks writes at submit time instead of presenting a read-only device

The comment says the guard is "enforced before mapping/submitting, independent of
BLKROSET". That is exactly the problem: the block layer, the page cache and any mounted
filesystem still see a writable device. `mount -o rw` succeeds, journal recovery is
attempted, dirty pages accumulate, and each write fails with `BLK_STS_IOERR` somewhere in
the middle. An ext4/btrfs journal replay that is interrupted this way is worse than a
refused mount.

Fix: additionally call `set_disk_ro(ns->disk, true)` (or set `NVME_NS_ATTR_RO` from the
Identify path) so the device is read-only from the top of the stack down, and keep the
submit-time guard as the backstop it is described as.

### M22 (medium) — line 879-895: the admin allow-list lets userspace tear down the I/O queues

`nvme_admin_create_cq`, `create_sq`, `delete_cq` and `delete_sq` are unconditionally
allowed so that the driver's own `apple_nvme_create_cq()`/`create_sq()` work. But those
same opcodes are reachable from userspace through `NVME_IOCTL_ADMIN_CMD` on `/dev/nvme0`.
Root can delete the I/O submission queue while the driver still has commands and NVMMU
TCBs pointing at it.

The header comment calls this "an accidental-write guard, not a security boundary against
root", which covers intent, but deleting a queue is not a write and is easy to do by
accident with `nvme-cli`.

Fix: distinguish driver-internal admin commands from passthrough — reject anything with
`blk_rq_is_passthrough(req)` on the admin queue except identify/get-log-page/get-features.

### M23 (medium) — line 1242: `max_queue_depth - anv->hw->j714s_readonly` does bool arithmetic and only touches one register

```c
		u32 limit = anv->hw->max_queue_depth - anv->hw->j714s_readonly;
		writel(limit | (limit << 16), anv->mmio_nvme + APPLE_ANS_MAX_PEND_CMDS_CTRL);
```

Subtracting a `bool` from a `u32` to mean "63 on J714s, 64 elsewhere" is unreadable and
un-greppable. It also applies to both halves of the register (the low half and the high
half are the two queues), while `APPLE_NVMMU_NUM_TCBS` (line 1247), `create_cq`/`create_sq`
`qsize` (793, 824), `ctrl.sqsize` (1281) and `tagset.queue_depth` (1451) are all still
computed from the unmodified `max_queue_depth`. Nothing in the file explains why the
pending-command ceiling alone needs to be one lower, so a future reader cannot tell
whether the other five sites are bugs.

Fix: add a `u32 max_pend_cmds` field to `struct apple_nvme_hw` with an explicit 63, and a
comment naming the observation that motivated it.

### M24 (medium) — line 106-107, 779-782, 811-814: undocumented registers from a hypervisor trace

`APPLE_ANS_IOQ_CMDS 0x1200` / `APPLE_ANS_IOQ_CQES 0x1208` are written with the IO queue
DMA addresses before CreateCQ/CreateSQ, justified only by "Match the verified HV
handoff". There is no reference to a published register map (unlike the SPMI work, which
cites m1n1), no explanation of why the standard NVMe CreateCQ/CreateSQ PRP is
insufficient on this part, and `writeq()` is used on registers whose width is unknown.

Fix: cite the trace artefact and its location, state whether a 32-bit pair also works,
and gate the `writeq()` on a `has_ioq_base_regs` capability flag rather than
`j714s_readonly` — the two are unrelated properties.

### M25 (medium) — line 37-97 + 1776-1782 + root-write-policy.h:8-10: the entire rootguard write path is unbuildable dead code

`root-write-policy.h` starts with

```c
#if defined(__KERNEL__) && defined(AZAHI_ROOT_WRITES)
#error "Public reference only: independently audit storage boundaries before enabling writes"
#endif
```

and every `AZAHI_ROOT_WRITES` block in `apple.c` includes that header. So no kernel build
can ever define `AZAHI_ROOT_WRITES`: `apple_nvme_root_io_allowed()`, `root_write_arm_set()`,
the `root_write_armed` module parameter, the `azahi,root-partuuid` DT validation, and the
`azahi,j714s-nvme-rootguard` compatible are all dead in every buildable configuration.

This is deliberate (`nvme-driver/README.md`: "Public rootguard kernel builds are
blocked"), and the intent is good. But it means several hundred lines of security-relevant
code in the audited tree have never been compiled by the shipped build script, so ordinary
compile errors in them would go unnoticed, and a reader can reasonably conclude the guard
is active when it cannot be.

Fix: keep the `#error`, but compile the policy header and the `apple_nvme_root_io_allowed()`
wrapper under a `AZAHI_ROOT_WRITES_COMPILE_TEST` define in CI so the dead branch at least
still builds; and put a one-line note at the top of `apple.c` saying the blocks below are
unbuildable by design.

### L25 (low) — line 44-58: `root_write_arm_set()` races `apple_nvme_remove()`

`rootguard_bound` is read with `READ_ONCE()` and `root_write_armed` written with
`WRITE_ONCE()`, with no mutual exclusion against `apple_nvme_remove()` (line 1797-1800)
clearing both. A sysfs write interleaved with unbind can leave `root_write_armed` true
after the controller is gone. Harmless today because the code cannot be built, but the
pattern is wrong.
Fix: a small mutex around both, or make arming take a reference on the device.

### L26 (low) — research-archive/t6050-j714s-native-rootguard.dts:6 vs root-write-policy.h:15

The DT says `azahi,root-partuuid = "PRIVATE-UUID-REMOVED"`; the header expects
`"PRIVATE-LINUX-PARTUUID-NOT-CONFIGURED"`. `strcmp()` fails, so even with the `#error`
removed the rootguard driver would always `-ENODEV`. Intentional sanitisation, but the
two placeholders should at least match so the failure is a UUID check rather than a typo.

### L27 (low) — line 1867-1878: the read-only build still claims the stock Apple compatibles

The `#else` branch keeps `apple,t8015-nvme-ans2`, `apple,t8103-nvme-ans2` and
`apple,nvme-ans2` in the match table. The forked module therefore competes with the
in-tree `nvme-apple` for every Apple NVMe node, not just the `azahi,` one.
Fix: drop the stock compatibles from the fork, the way `dwc3-apple-t6050.c:564` does.

### L28 (low) — line 1673-1676: `anv->reset = NULL` for the read-only path

```c
	anv->reset = anv->hw->j714s_readonly ? NULL :
		devm_reset_control_array_get_exclusive(anv->dev);
	if (IS_ERR(anv->reset)) {
```

Correct today (both `reset_control_assert/deassert` call sites at 1187/1195 are behind
the `j714s_readonly` early return, and the reset API tolerates NULL), but the invariant
"reset is NULL exactly when every user is unreachable" is enforced nowhere.
Fix: use `devm_reset_control_array_get_optional_exclusive()` and let the DT decide,
or `WARN_ON(!anv->reset)` at the two use sites.

---

## nvme-driver/sart.c

### M26 (medium) — line 180-206: the v4 ops reuse v3's masks and limits with no evidence

`sart_ops_j714s` takes `flags_allow = APPLE_SART3_FLAGS_ALLOW` (0xff),
`size_max = APPLE_SART3_SIZE_MAX` (`GENMASK(29,0)`) and both v3 shifts, while the entry
layout (`0x00` config, `0x60` paddr, `0xc0` size) is different from v3's
(`0x00`/`0x40`/`0x80`). The comment justifies only the entry offsets ("same first 16
entries used by the verified HV translation"), not the field widths.

Why it matters: `apple_sart_add_allowed_region()` validates the requested size against
`ops->size_max` before programming the entry. If SARTv4's size field is narrower than 30
bits, an oversized region passes validation and is written truncated — the DMA window the
ANS coprocessor is allowed to touch then does not match what the driver believes it
granted. On a storage controller that is a silent data-integrity hazard, not just a
functional bug.

Fix: read back each entry after writing it (the driver already has `get_entry`) and
`WARN`/fail when the readback does not match, at least for the v4 ops.

### L29 (low) — line 180-196: bare offset literals instead of `APPLE_SART4_*` macros

Every other generation in the file defines `APPLE_SARTn_CONFIG(idx)`, `..._PADDR(idx)`,
`..._SIZE(idx)` macros. The v4 helpers open-code `0x60 + 4 * index` and `0xc0 + 4 * index`.
The 16-entry spacing (0x40 bytes) fits between the banks, but nothing in the file records
that constraint.
Fix: add the macros next to the v3 block.

### L30 (low) — line 197: `sart_ops_j714s` is not `const`

Matches the existing (also non-const) `sart_ops_v0/v2/v3`, so this is a pre-existing
file-wide issue rather than a new one, but function-pointer tables reachable from
`of_device_get_match_data()` should be `const` / `__ro_after_init`.

### L31 (low) — line 220-221: the machine guard compares an ops pointer

```c
	if (sart->ops == &sart_ops_j714s && !of_machine_is_compatible("apple,j714s"))
		return -ENODEV;
```

Works, but couples the guard to the ops table identity rather than to the compatible
string that selected it. If a second board ever shares `sart_ops_j714s`, the guard
silently blocks it.
Fix: put the machine name in `struct apple_sart_ops` (or a wrapper match-data struct)
and compare that.

---

## nvme-driver/root-write-policy.h and test-root-write-policy.c

### M27 (medium) — root-write-policy.h:16-17: real LBAs of a specific disk are shipped as compile-time constants

`AZAHI_ROOT_FIRST_LBA 204034123` / `AZAHI_ROOT_END_LBA 242798667` are the actual bounds
of the author's root partition, published in a repo whose README says the identifiers are
"invalid placeholders" — the UUID is, the LBAs are not. The file says "These bounds are
NOT configurable parameters", which is the right instinct, but anyone who copies this
header onto a differently-partitioned disk gets a guard that authorises writes to
whatever now lives at sector 204034123.

Fix: derive the bounds at probe time from the DT properties that `apple.c:1595-1608`
already reads and cross-check them against the GPT, instead of hard-coding them and using
the DT only for confirmation. Failing that, put a loud comment at the constant, not only
in the README.

### L32 (low) — root-write-policy.h:48: `io->length > 65535U` is dead

`length` is populated from `le16_to_cpu(cmd->rw.length)`, so it can never exceed 65535.
`test-root-write-policy.c:37` tests the impossible case. Harmless, but it makes the
policy look like it is bounding something it is not.

### L33 (low) — root-write-policy.h:31-55: the policy validates the command, not the requester

Once `armed` is true, every write in the LBA range from any process is permitted. The
comment says "This is an accidental-write guard, not a security boundary against root",
which is honest; worth restating at the `azahi_root_io_allowed()` call site in `apple.c`
so a future reader of the fast path sees it too.

### L34 (low) — test-root-write-policy.c: no coverage of the `armed`/`bound` transition

The host test exercises the pure predicate thoroughly (the 65536-iteration length/control
sweep and the protected-LBA list are genuinely good). What is untested is the part with
the actual race: `root_write_arm_set()`'s `rootguard_bound` check and the
probe/remove ordering in `apple.c`. That logic is also the part that cannot be compiled
(M25), so it has neither a test nor a build.

---

## Cross-cutting: licensing and provenance

### M28 (medium) — three files carry code transcribed from Apple binaries under permissive or unqualified SPDX tags

1. `usb-driver/phy-apple-t6050-usb2.c:1-19` — `GPL-2.0 OR BSD-2-Clause`, header names
   `AppleT6050TypeCPhy::eusb2phy_init/shutdown/initUSB2` and their kernelcache virtual
   addresses, and describes the file as "a transcription" of them.
2. `nvme-driver/apple.c:106-107, 779-782, 811-814` — new registers from a "verified HV
   handoff" trace, added to a file that keeps its original Asahi copyright line.
3. `nvme-driver/sart.c:180-206` — SARTv4 entry layout from the same source.

The Asahi project's own practice for this material is to publish the *facts* (offsets,
ordering, bit meanings) in documentation with a citation, and write the driver from the
documentation. `docs/PROVENANCE.md` exists in this repo but these three files do not
reference it.

Fix: make each transcribed block cite `docs/PROVENANCE.md`, state that only offsets and
ordering were recovered, and drop the BSD half of the PHY driver's SPDX tag. Keep the
"Private one-machine bring-up code. Not for upstream submission." markers — they are the
strongest thing protecting this tree right now.

### M29 (medium) — `dockchannel-hid.c` has no vendored upstream copy to diff against

`usb-driver/vendor/dwc3/dwc3-apple.original.c`, `nvme-driver/vendor/apple-7.0.13.c` and
`nvme-driver/vendor/sart-7.0.13.c` make the local deltas in those files reviewable in
seconds. `input-driver/dockchannel-hid.c` is a 1238-line fork of Asahi's driver with no
pinned original and no patch file, which is how C1 (a one-line deletion of a bounds-check
`goto`) survived into the tree.

Fix: vendor the exact upstream `dockchannel-hid.c` next to it and keep the local changes
as a patch, the same way `pd-backport/` does with `no-tbt-switch.patch`.
