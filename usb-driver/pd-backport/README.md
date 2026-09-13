# SN201202x backport feasibility check — not a runnable driver

2026-09-13. Host-only compile audit for USB2 tethering on T6050/J714s.
No loadable module, overlay, installer, target access or hardware writes.
The existing three-module USB candidate and delivery manifest are unchanged.

## Source and reproduction

Seven verbatim source/config files under `vendor/tipd` come from
[AsahiLinux/linux at 236788cd2602a24c703fe7bdaddaf73ef77d2027](https://github.com/AsahiLinux/linux/tree/236788cd2602a24c703fe7bdaddaf73ef77d2027/drivers/usb/typec/tipd).
Original SPDX/copyright/attribution remain intact. `vendor/SHA256SUMS` pins
downloaded bytes. No Apple firmware, target dumps or private identifiers here.

On the existing host build environment, run `bash check-build.sh` from here.
Requires the private project's exact 7.0.13-400.asahi.fc44.aarch64+16k headers,
modpost, and Homebrew LLVM tools. Not a standalone public build environment.
The script verifies source hashes, independently compiles core/spmi/trace,
then would link objects and run modpost only if all three compile. It never
links a `.ko` or refreshes the delivered USB bundle.

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
- Overall check exits 1. Combined linking and modpost were NOT reached.
  Compilation of individual objects is not a module ABI or hardware test.

## Integration facts and unresolved risks

The saved Linux rootguard DTB has no SPMI/USB-PD nodes. Native sysfs inventory
is still requested; the runtime USB overlay adds only DART/PHY/DWC3 devices.
Adding a PD driver alone would not describe its controller or IRQ topology.

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
