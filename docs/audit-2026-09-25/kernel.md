# Kernel C audit, 2026-09-25

Scope: `usb-driver/*.c`, `usb-driver/dts/`, `usb-driver/pd-backport/`,
`input-driver/`, `nvme-driver/`, their tests and READMEs. Reference sources:
the vendored originals in the tree and the exact Fedora Asahi
`kernel-7.0.13-400.asahi` source (`$KDIR` below), plus the public macOS 27.0
(26A428) J714s ADT and Mac17,9 kernelcache read with `ipsw` in the m5-build
cache. No target hardware was available. Nothing here was run on the Mac, and
no claim below about hardware behaviour goes beyond the recorded evidence.

The PR 1 audit (`kernel-c.md` in that PR, written at commit 843d290) was the
starting list. Every item was checked against the current code. Verdicts:
CONFIRMED-FIXED (real, and fixed now or earlier), CONFIRMED-NOT-FIXED (real
or partly real, left open for the stated reason), REJECTED (the claim is
wrong, with the reason).

## Summary of verdicts

Line numbers are for the files as they are after this pass.

### input-driver/dockchannel-hid.c

| ID | Where | Verdict | Reason |
| --- | --- | --- | --- |
| C1 | :1147 | CONFIRMED-FIXED (2cfd6cf) | Upstream has the same missing `goto`; it is not a local regression. |
| H1 | :347, :376, :1071 | CONFIRMED-FIXED | Real race, also upstream. Fixed with a `resp_lock` spinlock, not `out_mutex` (see fixes). |
| M1 | :1094 | CONFIRMED-FIXED | Returned length now reflects bytes stored. HID core used it as the buffer size. |
| M2 | :1290, :1306 | Partly fixed | sysfs unbind suppressed, module has no exit. `BUG_ON(1)` kept on purpose: a returning remove lets devres free live state. |
| M3 | :265 | CONFIRMED-FIXED (workqueue) / REJECTED (OF ref) | The OF reference is held for the interface lifetime. |
| M4 | :1171 | CONFIRMED-FIXED (2cfd6cf) | Upstream still has the bare `return`. |
| M5 | :401 | REJECTED | Design preference. A phase-0 error does return early. Bytes are hardware-verified and pinned by a test. |
| M6 | :476 | CONFIRMED-FIXED | Size check before the header dereference. |
| L1 | :900 | CONFIRMED-FIXED | Zero-length product block rejected. |
| L2 | :880 | CONFIRMED-NOT-FIXED | Read stays inside the packet buffer; a stricter check could drop the real afe-reset request. |
| L3 | :1142 | CONFIRMED-FIXED | Short packets dropped before the sub-header is read. |
| L4 | :21 | CONFIRMED-NOT-FIXED | Portability only; needs a build-script change that cannot be tested here. |
| L5 | :771 | CONFIRMED-NOT-FIXED | Clearing the flag would allow a repeat enable, new hardware interaction. |
| L6 | :1274 | Partly fixed | Probe error-path leak fixed; the rest follows from having no teardown. |
| L7 | :784 | CONFIRMED-NOT-FIXED | Bounded leak; freeing the old copy would race `dchid_parse()`. |
| M29 | n/a | CONFIRMED-NOT-FIXED | Vendoring `$KDIR/drivers/hid/dockchannel-hid/dockchannel-hid.c` is an orchestrator decision (new file). |

### usb-driver/phy-apple-t6050-usb2.c

| ID | Where | Verdict | Reason |
| --- | --- | --- | --- |
| M7 | :244, :263 | REJECTED | Apple's own sequences read both banks with the gate bits set (see kernelcache notes), and the "after shutdown" dump runs on every boot where the loader left the PHY active. |
| M8 | :1 | CONFIRMED-NOT-FIXED | Provenance/licence decision for the owner; `docs/PROVENANCE.md` already records the derivation. Not a code defect. |
| M9 | :385, :204 | CONFIRMED-NOT-FIXED | Accurate but unreachable: the shipped overlay forces host mode and registers no role switch. |
| L8 | :386 | REJECTED | Lockdep keys are per call site; `CONFIG_DEBUG_MUTEXES` is off. No leak or stale class. |
| L9 | :343 | CONFIRMED-NOT-FIXED | Only reachable with a hand-edited overlay; the embedded overlay has entries. |
| L10 | :301 | REJECTED | Nothing calls `phy_reset()`; refusing a pulse on an unclocked PHY is intended. |
| L11 | :140 | REJECTED | Style. |

### usb-driver/dwc3-apple-t6050.c

| ID | Where | Verdict | Reason |
| --- | --- | --- | --- |
| M10 | :233, :541 | CONFIRMED-NOT-FIXED | Latent only: a bound node's properties cannot change without a second overlay changeset, and the only overlay is pinned. |
| M11 | :246 | CONFIRMED-NOT-FIXED | True (NULL phy, no-op, same as upstream). No effect: the provider applies the host tunables unconditionally. |
| M12 | :323 | CONFIRMED-NOT-FIXED | Correct for the exact 7.0.13 core the module is pinned to; `dwc3_host_init()` leaves `dwc->xhci` dangling on failure, so clearing it is required. Maintenance risk only. |
| L12 | :469 | REJECTED | Same as L8. |
| L13 | :523 | REJECTED | Style; no early return between lock and unlock. |
| L14 | :474 | REJECTED | `dwc3_core_probe()` already fails probe through `dwc3_core_is_valid()` (GSNPSID), and the overlay preflight checks GSNPSID too. |

### usb-driver/azahi-usb-overlay.c

| ID | Where | Verdict | Reason |
| --- | --- | --- | --- |
| H2 | :38-55 | CONFIRMED-NOT-FIXED (by design) | Every base address and power-state offset matches the 26A428 J714s ADT (pmgr reg[0]/reg[9], atc-phy2 reg[0]/reg[1], usb-drd2 reg[0]/reg[3], device-table offsets). Reads only, after the `apple,j714s`, AIC phandle and PMGR-active checks. `request_mem_region()` adds no safety at preflight, when the overlay devices do not exist yet. |
| M13 | :29, :234 | CONFIRMED-NOT-FIXED | Cosmetic: the parameter text mentions a variant that is refused. Left so a working module binary does not change for a string. |
| M14 | :254 | REJECTED | `of_overlay_fdt_apply()` sets `*ret_ovcs_id = 0` on entry, sets it only after `of_overlay_apply()`, ids start at 1, and its comment asks the caller to call `of_overlay_remove()` in exactly that case. |
| L15 | :154 | REJECTED | Style; same result as `of_machine_is_compatible()`. |
| L16 | :32 | CONFIRMED-NOT-FIXED | Deliberate runtime-verified guard, documented in the dtso. |
| L17 | :60 | REJECTED | Accumulator pattern; a mapping failure logs `cannot map` first. |
| L18 | :273 | REJECTED | Harmless. |

### usb-driver/pd-backport/

| ID | Where | Verdict | Reason |
| --- | --- | --- | --- |
| H3 | hpm-once.c:14-78 | CONFIRMED-NOT-FIXED (by design) | The `mode` parameter is the explicit opt-in and the default is status-only. The "collision detected in only one ordering" claim is wrong: both drivers claim a busy region, so the second always gets -EBUSY. Header comment now states that probe/awake write. |
| M15 | spmi4-controller.c:126 | CONFIRMED-NOT-FIXED | Needs `allow_probe=1` and a DT node that does not exist; the domain choice needs hardware evidence. |
| M16 | spmi4-controller.c | CONFIRMED-FIXED | Poison latch now survives unbind/rebind and pins the module. |
| M17 | spmi4-controller.c | REJECTED | devm teardown is correct; `spmi_controller_alloc()` and the in-tree Apple controller set `of_node` the same way. |
| M18 | spmi4-controller.c | REJECTED | The driver core already logs the -EBUSY probe failure. |
| M19 | no-tbt-switch.patch | REJECTED | After the patch the cd321x paths match the exact 7.0.13 core; switch get/put and every set call go together; `$KDIR` has no TBT switch API. |
| M20 | headers | REJECTED (kernel) | 0 W=1 warnings; a `static inline` change alters the pinned hpm-once binary. |
| L8 (spmi4) | :121 | REJECTED | As L8. |
| L19 | :111 | REJECTED | Required containment literal. |
| L20 | hpm-once.c:18 | REJECTED | 0444 outputs, read by the startup script and its tests. |
| L21 | hpm-awake.h:56-63 | CONFIRMED-NOT-FIXED | Real diagnostic flaw (mismatch reported as -ETIMEDOUT). Any change alters the hardware-verified module; proposed one-liner for the next deliberate rebuild: `return i == 100 ? -ETIMEDOUT : -EPROTO;`. |
| L22 | spmi4-transport.h:161 | REJECTED | `in_len` is capped at 16 before this line; tests cover the ACK rule. |
| L23 | test-spmi4.c:133 | REJECTED | The test builds `replies[]` itself, so a packing change fails. |
| L24 | spmi4-host-bridge.c | REJECTED | No Kbuild references it; header functions are static. |

### nvme-driver/

| ID | Where | Verdict | Reason |
| --- | --- | --- | --- |
| H4 | apple.c:1160-1188 | CONFIRMED-NOT-FIXED (guard) | On timeout the controller goes RESETTING to DELETING and the disk is removed; it is not stuck. The suggested soft reset would stop RTKit first and hit the same refusal. |
| M21 | :869-905 | CONFIRMED-NOT-FIXED | No non-read opcode reaches media. A driver `set_disk_ro()` is overwritten by nvme core and would also affect the private rootguard build, which shares the hw struct. |
| M22 | :881-892 | CONFIRMED-FIXED | Queue create/delete refused for ioctl passthrough (`NVME_REQ_USERCMD`). The audit's `blk_rq_is_passthrough()` would have blocked the driver's own commands. |
| M23 | :1245 | CONFIRMED-NOT-FIXED | Readability only; 63 comes from the HV trace and the other sites are correct. |
| M24 | :109-110 | CONFIRMED-NOT-FIXED | HV-traced, hardware-verified register writes. |
| M25 | root-write-policy.h:9 | CONFIRMED-NOT-FIXED (guard) | With the `#error` removed in a scratch copy only, the rootguard blocks compile with 0 warnings. |
| M26 | sart.c:180-206 | CONFIRMED-NOT-FIXED | No field-width evidence: the ADT `sart-ans` node has none and macOS programs SART through the PPL. |
| M27 | root-write-policy.h | CONFIRMED-NOT-FIXED | Partition geometry, not an identifier; blocked by the `#error` and DT checks. |
| M28 (nvme) | apple.c, sart.c | REJECTED | Offsets and values from HV tracing, no transcribed Apple code. |
| L25, L26, L28-L34 | various | CONFIRMED-NOT-FIXED | Dead code behind the `#error`, fail-closed checks, or style. |
| L27 | :1897 | REJECTED | Same module and driver name as in-tree `nvme-apple`; only one can load. |

## Fixes made

Every fix keeps the existing guards. None changes a hardware register
sequence on a path that has run on the Mac.

### 1. PHY: gated reinitialisation before the DWC3 soft reset (-110)

`usb-driver/phy-apple-t6050-usb2.c`: new `.init`/`.exit` callbacks and a
`reinit_after_shutdown` bool parameter (0644, default off).

- Defect: `dwc3_core_init()` in `$KDIR/drivers/usb/dwc3/core.c` runs
  `phy_init()`, then `dwc3_core_soft_reset()`, then `phy_power_on()`. This
  PHY did all its work in `power_on`, and `power_off` asserts reset, SIDDQ
  and both clock gates. Any second DWC3 probe (unbind/bind, module reload,
  deferred re-probe after a later failure) then issues the core soft reset
  with the PHY's UTMI clock stopped.
- With the parameter off, `.init` only reads CTL and USBCTL. If the PHY is
  in the shut-down state it logs `PHY is shut down before the DWC3 core soft
  reset; expect -ETIMEDOUT`, so the next -110 names its cause. The first
  probe after boot, where the loader left the PHY running, writes nothing new.
- With the parameter on, `.init` runs the unchanged host sequence only when it
  finds the shut-down state, before the soft reset. `power_on` then sees
  `powered` and returns. `.exit` shuts the PHY down only if `.init` powered
  it and `power_on` never ran (the DWC3 error path).
- Hypothesis: the earlier live DWC3 reload failed with -110 because the soft
  reset ran against a clock-gated PHY.
- Expected observation (attended test A below): with the parameter on, the
  `reinit_after_shutdown:` line appears, then no `DWC3 controller soft reset
  failed`, and a right-port root hub comes back.
- Rollback: leave the parameter at 0 (default), or write 0 before the next
  probe. A reboot restores the previous state in every case.
- Test: `usb-driver/test-usb-glue.py::test_phy_reinit_after_shutdown_is_gated`
  compiles the real PHY functions against a fake register file. It checks
  that with the parameter off `.init`/`.exit` write nothing in either state,
  that the loader-running path is unchanged, that the shut-down path
  initialises and makes `power_on` a no-op, and that `.exit` undoes an
  init-only power-up. Three mutations (gate removed, `.exit` emptied,
  `powered` not set) each make it fail.

### 2. SPMI4 controller: persistent poison latch and non-posted check

`usb-driver/pd-backport/spmi4-controller.c` (compile-only, default-off
driver). The poison latch moved from devm memory to a file-scope flag. It
now survives unbind/rebind, pins the module and makes a later probe return
-EIO before any MMIO. This is what the README already promised. Probe also
refuses a resource without `IORESOURCE_MEM_NONPOSTED`, because
`devm_ioremap_resource()` maps posted otherwise and hpm-once's verified path
uses `ioremap_np()`. `hpm-once.c` got a comment-only change; its `.ko` is
byte-identical with this toolchain. `hpm-awake.h` and `spmi4-transport.h` are
unchanged.

### 3. DockChannel HID

`input-driver/dockchannel-hid.c`, tested by `input-driver/test-power-request.py`
(new third block runs the real `dchid_cmd()`/`dchid_handle_ack()` under
ASan/UBSan; each fix was reverted in turn in a scratch copy and the test
failed each time).

- H1: `spinlock_t resp_lock` taken by the ACK path around the checks, the
  copy and `complete()`, and by `dchid_cmd()` around setup and timeout
  cleanup. It never touches `out_mutex`, which the sender holds while
  waiting (the PR 1 suggestion would deadlock). The ACK runs in the
  DockChannel rx IRQ thread, which is process context, so a plain spinlock
  is enough.
- M1: stored length is the report number plus the bytes copied.
- M3, L6: workqueue destroyed on the ignored-interface and probe-failure
  paths; `devm_kstrdup()` failure checked.
- M6, L1, L3: firmware header size, zero-length product block, short packet.
- M2: `.suppress_bind_attrs = true` and `builtin_platform_driver()` (no
  module exit, `rmmod` returns -EBUSY). Unbinding the MTP helper or the
  parent DockChannel still reaches `BUG_ON(1)`.
- Found in this pass: `kfree(work)` on the bad sub-header path; a
  zero-length event no longer reads one byte past the allocation; the
  16-byte init name from the device is copied into a NUL-terminated buffer;
  `ret < (int)sizeof(...)` so a negative error takes the fake-ID path;
  `dchid_send()` refuses messages that would overflow the 16-bit length
  (a GPIO ACK echoes a device-sized event); `HOST_VENDOR_ID_APPLE` wrapped in
  `#ifndef` (the only W=1 warning before).

### 4. ANS NVMe

`nvme-driver/apple.c`.

- M22: create/delete CQ/SQ are allowed on the admin queue only when not
  flagged `NVME_REQ_USERCMD` (set only by `nvme_alloc_user_request()`), so
  the driver's own queue setup is unchanged and ioctl passthrough cannot
  delete the I/O queues.
- Found in this pass: system sleep removed the disk on the J714S read-only
  build. Suspend stops the ANS CPU, and resume needs the power reset that the
  reset work refuses. A `.prepare` callback now returns -EBUSY when
  `j714s_readonly` is set, before any device suspends. A lid close with
  default logind/KDE settings would otherwise have dropped the root disk.
  The installed private rootguard build shares the same hw struct but does
  not get this until it is rebuilt. Until then `HandleLidSwitch=ignore` or a
  masked `sleep.target` on the target avoids the problem.

### 5. PR 2 changes re-applied by hand (credit: PR 2, commit 921db7b)

- The errno and `Acquired GPIO` logs in `dchid_request_gpio()`, and the
  `GPIO event:` and `GPIO ack:` logs in `dchid_handle_gpio()`: log-only,
  applied as written.
- The one-shot start retry after `start timed out`: the logic is correct, but
  it re-sends firmware and the v2 power OFF/ON pair, so it is new hardware
  interaction. It is now behind `start_retry` (0644, default off) with an
  `AZAHI_START_RETRY` marker. Hypothesis, expected observation, risk and
  rollback are in `input-driver/README.md`.
- Not applied: the `safety/allowed-paths.txt` reorder and
  `docs/trackpad-alternating-boot.md`. Useful content from that note: the
  AFE probably keeps state across the forced reboot (nothing power-gates or
  resets it), `->starting` stays latched after one failure, `0xe00002c2` is
  kIOReturnBadArgument, and earlier dmesg filters hid every GPIO line, so the
  next failed boot needs an unfiltered dmesg. It also notes that the
  probe-time GPIO pre-check can never fire. That is confirmed and left
  alone, because making it work could leave the keyboard waiting forever if
  SMC GPIO never binds.

## Kernelcache and ADT evidence (26A428)

Located by symbol in the `com.apple.driver.AppleT6050TypeCPhy` fileset
entry of `kernelcache.release.Mac17,6_7_8_9_14_15_16` with
`ipsw macho disass --fileset-entry ... --symbol ... --force`. Addresses differ
from the older saved kernelcache named in the PHY header.

- `AppleT6050TypeCPhy::eusb2phy_init(bool,bool)` at `0xfffffe0009f02a38`.
  The host branch (first argument false) matches the transcription in
  `t6050_usb2_init_seq()` step for step: DFLT then HOST tunables, 10 ms,
  CTL clear bit 3, 10 us, clear bit 0, clear bit 1, event-bank +0x0 set
  LOAD_CNT|EVT_EN in one write, CTL set bit 2, MISCTUNE clear bit 29 then 30,
  30 us, read event +0x20 (`C0_UTMI_CLK_ACTIVE.EVT_CNT is 0` log), 5 ms,
  USBCTL mode 2. The device branch applies `tunable_USB2PHY_DEV` and sets
  SIG bits 2 and 3 (`VBUS_VALID_EXT_FORCE_VAL/EN`); the host branch does not.
  That supports the `azahi,sig-clear-mask` deviation.
- `eusb2phy_shutdown()` at `0xfffffe0009f0414c` matches
  `t6050_usb2_shutdown_seq()`: PORT_RESET (then 5 ms) only if clear, USBCTL
  mode 4, CTL set bits 3 then 0, MISCTUNE set bit 29 then bit 30 (a
  read-modify-write of MISCTUNE after the APB gate is set), 500 ns.
- The init sequence reads bank 0 and event-bank +0x0 while both MISCTUNE gate
  bits are still set. That is the evidence behind the M7 rejection.
- The `C0_UTMI_CLK_ACTIVE` event counter checked after init shows that the
  PHY's UTMI clock only runs after this sequence. That supports fix 1.
- `AppleT8160USBXHCI::reset` in `com.apple.driver.usb.AppleSynopsysUSBXHCI`
  (register block names say DWC_usb31) writes GCTL.PWRDNSCALE = 0xd and
  GBL_HIBERNATION_EN, clears GUSB2PHYCFG.SUSPENDUSB20 and GUSB3PIPECTL
  SUSPENDENABLE around the PRTCAPDIR change, sets both again, and sets the
  pipe handler `DUMMY_PHY_READY`. Linux sets SUSPHY the same way. It leaves
  PWRDNSCALE alone without a suspend clock (glue uses
  `ignore_clocks_and_resets`).
- ADT: `usb-drd2` has a `usb-repeater` property; `atc-phy2` in this
  restore-image ADT carries only `tunable-host` (+0x8 mask 0x7000 to 0x7000)
  and `tunable-device` (same mask, 0). The overlay's DFLT/HOST values come
  from the real machine's ADT, which iBoot fills; the restore-image values
  agree with the host bits 12-14.

## USB failure analysis: -110 and -71

### -110 on live DWC3 reload

Ranked cause, high confidence from code: the DWC3 core soft reset ran while the
PHY was shut down (fix 1). Evidence:
- the `dwc3_core_init()` ordering;
- the DWC3 comment that CSFTRST clears only after all clocks are
  synchronised;
- `power_off` gating both PHY clocks;
- upstream `$KDIR/drivers/phy/apple/atc.c`, which has no USB2 power_on/off
  in its phy_ops and powers the USB2 PHY from the Type-C mux before DWC3
  init;
- on first boot the loader leaves the PHY running.

The pipe handler dummy PHY state is not touched by Linux, so it is the same on
reload.

Attended test A (validates fix 1). Do it only when losing USB until a reboot
is acceptable, with a local keyboard, no SSH over USB and the phone unplugged:
1. Build and install the new PHY module in place of the old one through the
   normal hash-checked bundle, then boot as usual.
2. `echo 1 > /sys/module/phy_apple_t6050_usb2/parameters/reinit_after_shutdown`
3. `echo 382280000.usb > /sys/bus/platform/drivers/dwc3-apple-t6050/unbind`,
   then the same name into `.../bind`.
4. Pass: `reinit_after_shutdown:` in dmesg, no `soft reset failed`, and
   `/sys/bus/usb/devices/usb*` resolves to `382280000.usb` again. Fail: the
   -110 repeats, and the hypothesis is wrong or incomplete. Rollback: reboot.

### -71 at SET_CONFIGURATION, and the wrong phone function

No code change is justified yet. Ranked hypotheses:

1. USB2 hardware LPM (L1) through the eUSB2 repeater. xHCI enables USB2
   hardware LPM at address time when the device's BOS advertises BESL
   (`hub_set_initial_usb2_lpm_policy()` in `$KDIR/drivers/usb/core/hub.c`).
   The L1 timeout is 512 us. The first idle gap longer than that usually
   falls between the descriptor reads and SET_CONFIGURATION, which is where
   -71 appears. DWC3 sets GUSB2PHYCFG.ENBLSLPM by default. The overlay sets
   neither `snps,usb2-lpm-disable` nor `snps,dis_enblslpm_quirk`. Against
   it: earlier boots worked with the same configuration, so this only fits
   if L1 exit fails intermittently.
   - Read-only check: once the phone enumerates in any mode, capture
     `power/usb2_hardware_lpm`, `power/usb2_lpm_besl`,
     `power/usb2_lpm_l1_timeout` under its `/sys/bus/usb/devices/` node, and
     the "USB 2.0 Extension" block of `lsusb -v`. No file, or `disabled`,
     rules this out.
   - Test (attended, no rebuild): before plugging, write the phone's
     VID:PID values with flag `k` (USB_QUIRK_NO_LPM) to
     `/sys/module/usbcore/parameters/quirks`, for example
     `18d1:4ee1:k,18d1:4e11:k` plus the tethering PID once known. Pass:
     SET_CONFIGURATION succeeds on repeated plugs. Rollback: write an empty
     string, or reboot.
2. eUSB2 repeater reset out of band by the HPM while the PHY keeps running.
   Upstream glue tears the PHY and DWC3 down on every CC event because the PD
   chip resets the repeater. Forced-host mode never sees those events. The
   phone's "Couldn't switch" suggests a rejected DR_Swap, and a PD soft or
   hard reset could reset the repeater. Against it: the delayed-start test
   (phone attached before host start) also failed.
   - Read-only check: HPM `mode=probe` status right before plugging and
     right after a -71, looking for changed role or plug bits.
   - Test: once test A passes, with the phone attached and failing, repeat
     the unbind/bind. Pass: a fresh PHY init with the CC state settled
     enumerates and configures.
3. Phone-side role or function state. The phone shows "USB controlled by:
   This device" while the HPM reports the Mac as source and host, and the
   interface fell back to ADB and then Imaging. A phone that re-composes its
   gadget drops D+ and re-enumerates, which can look like -71.
   - Test (read-only on Linux): `udevadm monitor --kernel` plus `dmesg -w`
     while the phone toggles tethering once, recording PIDs and disconnects
     per toggle.
4. VBUS droop when the phone starts drawing its configured current after
   SET_CONFIGURATION.
   - Read-only check: xHCI over-current messages, and the HPM power word
     before and after the event.
5. DWC3 timing registers left at loader or reset values (GCTL.PWRDNSCALE,
   GFLADJ, GUCTL.REFCLKPER). macOS writes PWRDNSCALE = 0xd.
   - Read-only check: `/sys/kernel/debug/usb/382280000.usb/regdump`, for
     GCTL, GFLADJ, GUCTL and GUSB2PHYCFG(0).

"Only root hubs" snapshot: the root hub runtime-suspends after 2 s with
nothing attached, which is normal. The earlier `power/control=on` write came
after the phone was plugged in. Test: write `on` to both root hubs before
plugging, then plug once. This is low priority, because macOS also enables
SUSPHY.

A USB Wi-Fi adapter goes through the same enumeration path. Hypothesis 1
applies to any LPM-capable adapter, and fix 1 would allow controller
recovery without a reboot once test A passes.

The withheld `t6050-j714s-usb-right-pmgr.dtso` would give genpd control of
ATC2_USB and lacks ATC2_PHYMXWRAP. If it is ever enabled, runtime PM could
power the domain down under the PHY, and it needs its own review.

## PR 4 review (read-only; files outside this area)

- 6d43d57 (step names, `HPM_TUPLE`, ERR trap, optional `cdc_ether` and
  `rndis_host`): correct and useful for diagnosis, and it does not change the
  hardware steps. It belongs to `usb-driver/start-native-usb.sh` and
  `test-native-startup.py`, which are not in this area. Recommend the tooling
  owner re-apply it by hand. Only one remark: making `rndis_host` optional is
  fine only while the phone tethers over NCM.
- 95400e7 (exit 75 plus `RestartForceExitStatus=75`, `RestartSec=10`, no
  start limit): rejected.
  - Each retry unloads and reloads hpm-once in `mode=awake`, which issues an
    SPMI WAKEUP and selector writes. It is not the "read-only status probe"
    the commit says.
  - The loop is unbounded while a phone stays attached, against the
    handoff's no-blind-retry rule.
  - Its phone-side explanation ("the Mac never became a host") is
    contradicted by the later attached HPM status (source and host bits set)
    and by Linux enumerating the phone.

## Compile checks

Environment: `source <m5-build>/env.sh` (aarch64-linux-gcc 16.1, `$KDIR` =
exact `kernel-7.0.13-400.asahi`, `modules_prepare` done). Each module was
copied to a scratch directory with a one-line Kbuild and built with
`make -C $KDIR M=<dir> KBUILD_MODPOST_WARN=1 W=1 modules`. Unresolved-symbol
modpost warnings are expected (no Module.symvers) and not counted.

| Module | Kbuild | Before | After |
| --- | --- | --- | --- |
| phy-apple-t6050-usb2 | `obj-m := phy-apple-t6050-usb2.o` | 0 warnings | 0 |
| dwc3-apple-t6050 | same, `CFLAGS_dwc3-apple-t6050.o := -I<repo>/usb-driver/vendor/dwc3` | 0 | 0 |
| azahi-usb-overlay | same, `CFLAGS_azahi-usb-overlay.o := -I$(src)`, `overlay-blobs.h` generated as in `build.sh` | 0 | 0 |
| hpm-once | `obj-m := azahi_hpm_once.o`, `azahi_hpm_once-y := hpm-once.o` | 0 | 0, byte-identical `.ko` |
| spmi4-controller | `obj-m := spmi4-controller.o` | 0 | 0 |
| vendor tipd | `vendor/tipd/Makefile` as Kbuild, `CONFIG_TYPEC_TPS6598X= CONFIG_TYPEC_TPS6598X_CORE=m CONFIG_TYPEC_SN201202X=m` | 14 errors unpatched (no TBT switch API in `$KDIR`); 0 with `no-tbt-switch.patch` | unchanged |
| dockchannel-hid | `obj-m := dockchannel-hid.o`, `$KDIR/drivers/hid/hid-ids.h` copied to `build/linux-7.0.13/drivers/hid/` | 1 (`HOST_VENDOR_ID_APPLE` redefined) | 0 |
| nvme apple + sart | `azahi-nvme-apple-y := apple.o`, `azahi-apple-sart-y := sart.o`, `ccflags-y := -I$(srctree)/drivers/nvme/host` | 0 | 0 |
| nvme rootguard blocks | as above with `-DAZAHI_ROOT_WRITES=1` and a scratch header without the `#error` (repo header untouched) | 0 | 0 |

Overlay blobs: `dtc -@ -I dts -O dtb` with the `build.sh` warning flags,
`dtc -I dtb -O dts | strip-symbols.py`, `dtc` again, then
`mk-blob-header.py overlay-blobs.h overlay_minimal=... overlay_pmgr=...`.

## Host tests

clang is not installed here. For the tests that hard-code it, a scratch
`clang` shim forwarding to gcc was put first in PATH. It maps the macOS-only
`-dynamiclib` to `-shared -fPIC` and does not change test semantics.

| Test | Before | After |
| --- | --- | --- |
| `python3 input-driver/test-power-request.py` | 2 PASS lines | 3 PASS lines |
| `bash nvme-driver/test-root-write-policy.sh` | 525366 checks pass | 525366 checks pass |
| `python3 usb-driver/test-usb-glue.py` | 4/4 | 5/5 |
| `python3 usb-driver/test-usb-runner.py` | 19/19 | 19/19 |
| `python3 usb-driver/test-native-startup.py` | 8/8 | 9/9 (test added outside this area) |
| `CC=gcc sh usb-driver/pd-backport/test-spmi4.sh` | 4/4 groups | 4/4 |
| `test-hpm-awake.c` (gcc, ASan/UBSan, needs `-Wno-unused-function`) | 3/3 | 3/3 |
| `python3 usb-driver/pd-backport/test-proxy-hpm.py` | 18/19 | 18/19 |
| `usb-driver/test-usb-candidate.py`, `test-transfer-*.py`, `test-courier-vm.py` | cannot run | cannot run |

The one proxy-hpm failure and `test-usb-candidate.py` need the `m1n1` Python
package. The transfer and courier tests need private image fixtures.

## Open risks

- Fix 1 is untested on hardware. Test A is the only validation. Until then
  the parameter must stay 0 on normal boots.
- Nothing here explains -71. The ranked checks above are read-only first on
  purpose.
- NVMe: nested admin/I/O timeouts can deadlock on the single admin tag
  (inherited from upstream). A root `nvme reset` or sysfs `reset_controller`
  removes the root disk through the same refusal.
- DockChannel: `BUG_ON(1)` is still reachable through MTP helper or parent
  unbind. A failed header read still does not re-arm the receiver (upstream
  design). Each `start_retry` keeps another firmware buffer.
- SPMI4: `hpm-once` holds no power reference between its PMGR check and FIFO
  use. M15 stands.
- Every changed module needs a rebuild and a new pinned hash in the install
  bundle before it can be tested. Hash pins live outside this area.
