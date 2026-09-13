# T6050 right-port USB2 candidate

**Offline-tested experimental source; live USB tethering not yet demonstrated.**
See [current progress](../PROGRESS.md), [handoff](../docs/HANDOFF.md) and
[build limitations](../docs/BUILD-AND-TEST.md).

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
Never install v4. The corrected v5 RAM handoff awaits target confirmation.
