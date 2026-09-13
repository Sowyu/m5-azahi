# Standalone one-core bundle work

This directory includes bundle validators/builders and the custom
`azahi_standalone.c/.h` component only. It is not a complete m1n1 tree and is
not directly buildable as a standalone distribution.

The aligned v3 booted native SSD KDE. Installed courier v4 fails the loader's
exact **70,698,084-byte** initrd requirement. Fixed v5 preserves this length
and reached a RAM-only Linux handoff; persistent replacement is still pending.
See [PROGRESS.md](../PROGRESS.md) before interpreting historical source comments.

Machine-specific Recovery installation/authentication and live proxy mutation
tools are deliberately not published. Do not construct an installer from
guessed partition IDs or assume a successful bundle hash means it will boot.
