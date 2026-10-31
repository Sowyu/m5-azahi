# T6050 right-port USB2 candidate

**2026-10-31: tethering is working in the current Fedora session.** USB startup
is enabled, with the previously installed phone NO_LPM quirk. Earlier failure
reports below are historical. Native Wi-Fi still uses tethering for remote access.

Cable-at-boot wake support is now installed and passed one real reboot test.
The earlier one-shot HPM path refused to wake with a partner attached. It now
follows the pinned upstream SN201202x system-state wake sequence, while retaining
identity, idle-task, timeout, readback and fault checks. It leaves role negotiation
to the controller. Startup preserves an existing host controller without reload.
The previous bundle is backed up. With the cable attached during reboot, wake
and host startup succeeded, the phone enumerated, and RNDIS networking/SSH
returned after phone-side tethering was enabled. Repeated-boot reliability has
not yet been measured.

Sanitized transport/protocol tests, eleven mocked startup/installer tests and
six retry tests pass. The new HPM module built at W=1 against the exact target
kernel. Missing optional phone network drivers no longer abort host startup;
required DART/DWC3/xHCI failures still stop immediately. `USB_HOST_READY` means
only that a root hub exists, not that the phone enabled tethering or obtained IP.
See [current progress](../PROGRESS.md) and [handoff](../docs/HANDOFF.md).

The [USB2 LPM trace](../docs/audit-2026-09-25/kernel.md#usb2-lpm-policy-gate)
finds an explicit policy gate in Apple's port driver. Linux can enable LPM
from host and device capabilities before SET_CONFIGURATION. This supports
the existing attended NO_LPM comparison; it does not establish the failing
enumeration's LPM state or justify a driver change yet.

The five existing glue/PHY host tests now run on Linux with their temporary
files moved to Trash. Fixed-host error cleanup, removal, the default-off PHY
reinitialization path and overlay preflight ordering pass. Driver code is
unchanged; these checks do not validate cable reconnection or physical reset.

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

## Linux host builds, 2026-09-28

`build-linux.py` now builds the four USB modules against the exact public
Fedora devel RPM, with strict kernel-export checks and matching vermagic.
See [the Linux build instructions](../docs/BUILD-AND-TEST.md).
These candidates are not installed or hardware-tested. Existing installer
pins remain unchanged, and the missing live USB/network result still blocks
a claim of working tethering.
