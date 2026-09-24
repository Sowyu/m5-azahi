# T6050 right-port USB2 candidate

**Experimental source: earlier live tethering worked, but current networking
is broken and reliability is unresolved.** Automatic azahi-usb startup was
disabled for a diagnostic boot and has NOT been restored. Current phone
interface is Imaging, not network; attached HPM probe succeeds. Installed
boot is v7; old v4/v5 checkpoints below are historical. No new USB driver
was installed during the latest screenshot-driven tests. User departure
pauses hardware testing; do not repeat live controller/overlay reloads.
See [current progress](../PROGRESS.md), [handoff](../docs/HANDOFF.md) and
[build limitations](../docs/BUILD-AND-TEST.md).

2026-09-25 source changes, none installed or hardware-tested (details in
[the kernel audit](../docs/audit-2026-09-25/kernel.md) and
[the tooling audit](../docs/audit-2026-09-25/tooling-loader.md)):

- The PHY now has `.init`/`.exit`. A new parameter `reinit_after_shutdown`
  (default 0) runs the host sequence before the DWC3 core soft reset when the
  PHY was left shut down. That ordering is the leading explanation for the
  earlier `-110` live-reload failure. With the default, the first-boot
  register sequence is unchanged; `.init` only reads two registers.
- `install-native-startup.py` now reads every file from its staging argument
  and pins `start-native-usb.sh` and `azahi-usb.service` as well as the
  modules. Any edit to those two files needs its pin updated.
- `build.sh` had a `! cmd` guard that `set -e` never enforced; fixed.
- Rebuilt modules get new hashes, so the install bundle pins must be
  regenerated before any attended test.

The three modules implement a host-only eUSB2 PHY, DWC3 glue and runtime DT
overlay. The right-socket mapping is USB instance 2, port number 3. Reference
bases are DWC3 `0x382280000`, PHY `0x382a90000`/`0x382800000`, and DART
`0x382f00000`/`0x382f80000`. These are board-specific, not a probing recipe.

`usb-tether-test.sh` defaults to a diagnostic preflight; its public root identity
guard intentionally cannot match. `pmgr` live mode is withheld. Open questions
include VBUS/Type-C role, PHY signal control, gated accesses and DART SIDs.
Neither artifact checks nor an xHCI root hub would prove usable tethering.

The file courier only copies verified assets into `/run` before switch-root;
it does not load drivers or write SSD files. `build-transfer.py` documents the
known-bad v4 packaging and is retained as a dependency of the fixed builder.
Never install v4. Corrected v5 and v6 RAM handoffs later worked, and the
installed image is now v7.
