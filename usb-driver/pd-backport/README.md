# SPMI4 transport prototype and SN201202x backport — host tests only

## Current Sep13 departure checkpoint

The broader SPMI/PD backport remains a host-tested prototype. The separate
guarded one-shot HPM helper WAS built and installed later; the historical
statements below that no native PD helper is installed no longer apply to it.
Latest attached probe: result0/ready1/poisoned0/state0, status0x108280fd,
power0xf0d. Networking is nevertheless currently unavailable. Do not force
a role swap from the phone UI alone or claim HPM success proves USB data.
Automatic USB startup was disabled during testing and remains disabled.
Read [the complete handoff](../../docs/HANDOFF.md) before older checkpoints.

2026-09-13. Host-only compile audit for USB2 tethering on T6050/J714s.
No loadable PD module, overlay or installer. The separate host proxy diagnostic
has now performed attended hardware tests, detailed below.
The existing three-module USB candidate and delivery manifest are unchanged.

Latest native result: after the attended HPM awake task and v6 RAM boot,
the candidate exposed right-port network interface enu1. NetworkManager
activation and DHCP succeeded, external DNS/ping worked, and Firefox loaded
Google search results. The user confirms phone tethering is enabled.
USB tethering therefore works for this boot. The runner's interface-bound
HTTPS check failed with curl60, "certificate is not yet valid"; incorrect
Linux time is suspected and still needs verification/correction. Do not use
insecure TLS flags or rerun driver loading. Persistent boot/network setup
is still unfinished, and no native PD module has been installed.

Follow-up: chronyd restart and chronyc makestep corrected the date. The
interface-bound, no-proxy HTTPS HEAD request then returned HTTP/2 200 with
certificate verification enabled. Native tethering and validated HTTPS now
work for this boot. This is not a throughput, endurance or reboot-persistence
test. Authenticated native remote access is the next proposed efficiency step;
no remote connection has been configured or verified yet.

## Attended proxy diagnostic route

`proxy-hpm.py` now provides a separate pre-Linux test route using the same
tested C FIFO code via `spmi4-host-bridge.c`. It executes on the helper host,
not on Linux. Default invocation does not open a device. Explicit `--status`
checks fresh proxy/ADT identity, right-HPM mapping, active controller power and
idle FIFO without sending bus commands. `--probe` adds WAKEUP and selections
of a small fixed logical-register set; selections are writes, not a read-only
hardware diagnostic. No automatic FIFO draining, reconnect, reset or IRQ-mask
write occurs. Errors latch the process; do not use repeated invocations as
recovery from ambiguous bus state.

Separately gated `--s0` permits only the pinned tipd driver's SSPS-to-S0 task,
after application-mode, nonzero/non-all-ones VID, known system state, no power
warning, and idle task-slot checks. It requires command completion, success
result and S0 readback. It neither forces electrical VBUS nor proves charging,
enumeration or networking. No generic task-writing command is exposed.
No changes are made to target storage or boot policy; proxy remains parked.

The selector-polling approach agrees with the saved HPM read path and
[Asahi's ACE3 transport documentation](https://asahilinux.org/docs/hw/peripherals/ace3/).
That document also describes separate AP/secondary-slave selections and the
unlisted select interrupt at BASE+2. This supports polling as a candidate,
but does not constitute a generation-4 hardware test. We do not access the
secondary slave or its logical interrupt registers.

`python3 test-proxy-hpm.py` passes 19 offline tests, including the real C/FFI
bridge, callback-error containment, selector timing, sleeping-device rejection,
logical-register allowlisting, S0 refusal cases, exact two-write task sequence
and readback. The saved-tree test needs private ADT dependencies; nothing is
transmitted. The existing four sanitized C test groups still pass.

Live status: the proxy appeared and fresh identity/power/FIFO checks passed.
NUB_SPMI_A1 power is `0x0f0000ff`, FIFO idle `0x40004000`. The C transport
successfully sent WAKEUP and polled logical selections on the real device.
Two successful snapshots report mode `APP `, VID `0x28`, status `0x10000000`,
system state `7`, and zero power/data status. This is first live evidence for
the transport, not electrical VBUS or phone enumeration.

Initial diagnostic: no SSPS task had been issued. State 7 was outside our known-state
guard; status bit 28 is labelled a voltage warning in the older tipd header.
Its meaning on this controller has not been resolved. Do not bypass either
guard just to force a test.

Subsequent attachment reads: status 0x1000b41d, power status 0x0f3f,
data status 0x800000f3, state 7. Pinned role definitions indicate sink/device.
The phone UI nevertheless reports "USB controlled by Connected device";
cable-to-controller correlation is pending, so do not assume which partner
these values describe. The separately gated `--host-data` sends one SWDF
data-role task only, with completion/result/role readback and no power-role
swap or SSPS. Its one live attempt completed with result 3 (rejected),
leaving roles/state unchanged. No automatic retry or fallback power task.
Tests cover refusal, timeout and unexpected power-role change. A host-side
success result would still not prove USB enumeration or networking.
Cable correlation subsequently passed: unplugging only the phone cleared the
right controller's attachment, power and data status. A new, separately gated
`--awake-disconnected` experiment follows the pinned upstream SN201202x
SSPS(S0) startup path, but requires the exact observed disconnected tuple:
APP, VID0x28, status0x10000000, state7, zero power/data and idle task slot.
It rechecks status before the two fixed writes and requires task completion,
zero result, S0 readback and continued disconnection. It does not declare
bit28 harmless, force electrical VBUS, or relax the default `--s0` guard.
No power-role swap or UFPf task is performed. Physical attendance is required.

The one attended SSPS experiment succeeded, changing state7 to0. After the
phone was reconnected, charging was reported and status0x108280fd confirmed
host/source; power0x0f0d, data0x80000073, state0. The corrected v6 RAM Linux
handoff with fresh layout/hash/readback checks completed. Tethering remains
unverified; awaiting native candidate load, phone enumeration and network test.
No target SSD boot update or daily macOS access. Old RAM pins must not be reused.

## New: default-disabled polling controller prototype

`spmi4-transport.h` implements bounded FIFO transactions using the audited
generation-4 offsets. `spmi4-controller.c` adapts this to Linux SPMI read,
write and command callbacks, serializing complete transactions with a mutex.
Only right-port HPM SID 12 is accepted; reset, shutdown, long-register commands,
queue flushing and interrupt-mask writes are deliberately absent.

Both `allow_probe` and `allow_transactions` default false and are read-only
module parameters. Probe additionally checks J714s, an explicit generation-4
DT property and the exact saved right-port controller resource. These checks
are containment, NOT proof of bus ownership, power state or hardware safety.
No overlay or loadable module is provided. Do not attempt live installation.

Reproduce the host tests with `sh test-spmi4.sh` (Clang with AddressSanitizer
and UndefinedBehaviorSanitizer required). The tests exercise the actual shared
C transport with fake IO, not a separately reimplemented protocol:

- Independently specified wire words for selector, register read/write,
  extended read/write, sleep and wakeup.
- All 16 extended lengths at both legal address boundaries, little-endian
  payload packing and zero padding.
- Invalid arguments and unsupported SIDs/commands rejected before IO.
- Busy FIFO, full TX, absent/partial replies, wrong SID/opcode, bad parity,
  ACK mismatch, nonzero padding and unexpected trailing FIFO data.
- No partial read output, no draining unexpected replies, permanent failure
  latch within the controller instance, and no IO after that latch.
- One shared 1,000-delay transaction budget; delayed success and partial-read
  timeout do not replenish it. This is a finite polling bound, not a hard
  wall-clock deadline: kernel delays and scheduling can run longer.

All four test groups pass under ASan/UBSan. `bash check-build.sh controller`
also passes compilation, relocatable linking and modpost against the exact
target headers/exports. No `.ko` is built and no target access occurs.

The command format and strict reply checks follow
[m1n1's pinned SPMI reference](https://github.com/AsahiLinux/m1n1/blob/5d6df45b2b7f9f1f925e469304122cfdd65694ba/proxyclient/m1n1/hw/spmi.py).
Polling deliberately clears ALERT; attended wake/read transactions succeeded.
Initial and final FIFO state must be idle; a mismatch stops the instance,
even if a later hardware state might have recovered. Rebinding is not a safe
recovery procedure and must not be used to bypass a poisoned controller.

**Still missing:** ownership/power and lifecycle validation, HPM logical
selector/wake completion handling, and a justified IRQ or polling integration
for the PD client. There is no IRQ domain, so the existing upstream SN201202x
client cannot simply be bound to this prototype. Its probe changes device
state. No phone enumeration, VBUS measurement or network success is claimed.
Next work is that HPM integration audit, not another user reboot or rerunning
the currently applied USB overlay. Daily macOS remains untouched.

Latest native report: `/sys/class/typec` is absent and the SPMI device directory
was reported as "0" (interpreted as `ls -l`'s `total 0`, not a device named 0).
This is consistent with no enumerated SPMI devices. An absent Type-C class can
also mean its class module is not loaded; it does not electrically diagnose
the phone or prove that a class module alone would solve the missing hardware.

## Source and reproduction

Seven verbatim source/config files under `vendor/tipd` come from
[AsahiLinux/linux at 236788cd2602a24c703fe7bdaddaf73ef77d2027](https://github.com/AsahiLinux/linux/tree/236788cd2602a24c703fe7bdaddaf73ef77d2027/drivers/usb/typec/tipd).
Original SPDX/copyright/attribution remain intact. `vendor/SHA256SUMS` pins
downloaded bytes. No Apple firmware, target dumps or private identifiers here.

On the existing host build environment, run `bash check-build.sh` from here.
Requires the private project's exact 7.0.13-400.asahi.fc44.aarch64+16k headers,
modpost, and Homebrew LLVM tools. Not a standalone public build environment.
The script verifies source hashes, independently compiles core/spmi/trace,
then links objects and runs modpost only if all three compile. Every run uses
a fresh output directory; failed builds cannot reuse stale objects. It never
links a `.ko` or refreshes the delivered USB bundle.

The default `upstream` variant preserves the original failure as a control.
`bash check-build.sh without-tbt-switch` applies `no-tbt-switch.patch` to a
fresh build copy with zero fuzz, never to the pinned vendor files.

## Actual result

- Exact kernel enables SPMI, SPMI_APPLE as module, TYPEC as module, and USB role
  switching. SPMI zero-write/sleep/wakeup APIs are declared and exported.
  TYPEC_SN201202X and the newer separate TPS6598X core option are absent.
- `spmi.c`: compilation passes with a pointer-to-enum cast warning in upstream
  match-data selection. `trace.c`: compilation passes.
- `core.c`: fails with 15 diagnostics for absent
  `typec_thunderbolt_switch_data`, `TYPEC_THUNDERBOLT_SWITCH_*`,
  `typec_thunderbolt_switch_set/put` and
  `fwnode_typec_thunderbolt_switch_get`. No compatibility stubs introduced.
- The unmodified control still exits 1; combined linking/modpost are not reached.
- The `without-tbt-switch` experiment compiles all three objects, links their
  combined relocatable object, and passes modpost against the exact kernel's
  symbol exports. No `.ko` is produced. The upstream pointer-cast warning remains.
  This does not verify device tables, load-time ABI or hardware operation.

The compatibility patch removes only the dedicated Thunderbolt-switch consumer
hooks added by [Asahi commit a8a9d4be6e108051c8f1bc876351436cdc312ec6](https://github.com/AsahiLinux/linux/commit/a8a9d4be6e108051c8f1bc876351436cdc312ec6),
adapted to the later core/header split. It introduces no fake-success stubs,
changes no SPMI transport bytes, and preserves generic Type-C/mux handling.
It does NOT itself enforce USB2-only operation or make DP/TBT/USB4 functional.
Do not install this compile experiment as a finished hardware driver.

## Integration facts and unresolved risks

The saved Linux rootguard DTB has no SPMI/USB-PD nodes. Native sysfs now reports
an empty SPMI device directory; the runtime USB overlay adds only DART/PHY/DWC3.
Adding a PD driver alone would not describe its controller or IRQ topology.

More importantly, the saved target ADT identifies nub-spmi-a1 as **generation 4**.
The 7.0.13 source archive's controller uses the old FIFO layout, has no `.cmd`
callback and no IRQ domain. Neither Fedora patchset changes drivers/spmi.
The newer [pinned Asahi controller source](https://github.com/AsahiLinux/linux/blob/236788cd2602a24c703fe7bdaddaf73ef77d2027/drivers/spmi/spmi-apple-controller.c)
adds commands and IRQ handling but still uses the older register layout.
Do not bind either implementation to generation 4 merely by adding a compatible.

| Field | Old controller | Generation 4 evidence |
| --- | --- | --- |
| FIFO status / command / reply offsets | 0 / 4 / 8 | 0x200 / 0x210 / 0x220 |
| RX-empty bit | 24 | 30 |
| IRQ mask / acknowledge banks | 0x20 / 0x60 in newer IRQ-capable source | 0x400 / 0x600, stride 4 |

Generation-4 FIFO definitions agree with [m1n1's published register map](https://github.com/AsahiLinux/m1n1/blob/5d6df45b2b7f9f1f925e469304122cfdd65694ba/proxyclient/m1n1/hw/spmi4.py).
Saved AppleGen4SPMIHandler initialization independently confirms these offsets,
status masks and IRQ-bank pointers. Its register-view accessor and IRQ handling
confirm the pointer/stride interpretation. `audit-spmi4.py` pins private input
hashes and checks those facts, target identity, the HPM interrupt list and Fedora
patch coverage: **seven offline tests passed**. Run with the existing Capstone
environment; it needs the private fixtures and extracted 7.0.13 controller file.
No firmware bytes or raw disassembly are published. These are static-analysis
facts, not a tested controller implementation or permission to reset queues.

The saved Apple HPM read path also contains bounded polling of logical selector
register 0, followed by length register 0x1f and data window 0x20. This is a
possible alternative to requiring a select IRQ, but its error/retry and wake
semantics need further review; it has not been implemented or tested here.

Saved hardware-description inspection maps right-port HPM2 to nub-spmi-a1,
with device interrupts 11/17/19 and interrupt-type entries 0/2/3. The upstream
[SN201202x binding](https://github.com/AsahiLinux/linux/blob/236788cd2602a24c703fe7bdaddaf73ef77d2027/Documentation/devicetree/bindings/usb/apple%2Csn201202x.yaml)
requires irq/select/sleep/wake and its example uses 11/13/17/19. The missing
select mapping must be independently established; do not copy example IRQ13
as a verified target fact. Controller generation/register translation and
interrupt-parent relationships also need review before any controller overlay.

Upstream SPMI probe requests IRQs and issues WAKEUP; logical-register reads
themselves first send an SPMI zero-write. Core initialization switches the
controller to S0, writes an interrupt mask and registers Type-C roles. This
is not a read-only diagnostic, and cannot be treated as a harmless probe.
Its optional Thunderbolt interfaces need a deliberate USB2-only integration
or a proper dependency backport, not fake-success compatibility functions.

Root hubs without a phone and the user's no-charging observation make power /
role handling a hypothesis; no electrical measurement establishes absent
VBUS, and neither cable nor PHY problems have been eliminated. No network
interface, DHCP or HTTPS success yet. Do not unload the current live overlay.

## Preserved target state

User reports four checksum OKs after copying the existing candidate from
`/run/azahi-usb-20260913` to `/root/usb-candidate` on Linux's SSD. This preserves
the bundle, not the repaired bootloader: permanent v4 still falls into proxy;
the current KDE session came from the v6 RAM handoff. No reboot requested.
Daily macOS remains out of scope and untouched.
