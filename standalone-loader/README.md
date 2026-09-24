# Standalone one-core bundle work

This directory includes bundle validators/builders and the custom
`azahi_standalone.c/.h` component only. It is not a complete m1n1 tree and is
not directly buildable as a standalone distribution.

The aligned v3 booted native SSD KDE. Courier v4 failed the loader's exact
**70,698,084-byte** initrd requirement. Fixed v5 and v6 preserved that length;
v6 and then the full-height v7 were installed and cold-booted. v7 is the
installed image as of 2026-09-13.

2026-09-25: `build-shutdown.py` builds a v8 candidate that adds only an
`apple,smc-reboot` node under the SMC, for the poweroff hang. It is built
from the pinned v7 image on the host and is not installed or tested; see
[the tooling audit](../docs/audit-2026-09-25/tooling-loader.md) for the test
plan. Two loader fixes (bootargs return check, RAM clamp intersection) take
effect only when the private loader is rebuilt. `test-loader-guards.py`
compiles and runs the changed C.
See [PROGRESS.md](../PROGRESS.md) before interpreting historical source comments.

Machine-specific Recovery installation/authentication and live proxy mutation
tools are deliberately not published. Do not construct an installer from
guessed partition IDs or assume a successful bundle hash means it will boot.
