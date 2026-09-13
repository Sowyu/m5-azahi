# SPMI4 transport prototype and SN201202x backport — host tests only

2026-09-13. Host-only compile audit for USB2 tethering on T6050/J714s.
No loadable module, overlay, installer, target access or hardware writes.
The existing three-module USB candidate and delivery manifest are unchanged.

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
Polling deliberately clears ALERT; acceptance on this hardware is untested.
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
