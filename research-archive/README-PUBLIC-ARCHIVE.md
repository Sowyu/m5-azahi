# Full research source/history archive

This expands the initial curated snapshot with **284 project source,
configuration and historical-note files**. The user explicitly requested the
broader archive and then clarified that personal photos and private data must
remain excluded. Identifying details were redacted from 89 files.

The original relative directory layout is preserved beneath this directory.
See [the manifest](../docs/research-archive-manifest.json) for every exported
file, its public-content hash and whether it was redacted. The manifest also
lists 41 large top-level binary artifacts that were not uploaded.

## Important: historical reference, not runnable instructions

This archive includes old failed experiments, superseded handoffs, Recovery
tool source, live hardware probes and installation scripts. **Do not run these
scripts or follow old next-step instructions.** They were written for particular
boot sessions and disk layouts. Redaction intentionally invalidates identities,
paths and addresses; the resulting source may not parse or pass historical
tests. It is not an installable or independently reproduced release.

The current [PROGRESS.md](../PROGRESS.md) and [handoff](../docs/HANDOFF.md) at the
repository root take precedence over every archived note. No new hardware
test or persistent installation was performed while publishing this archive.

The loader integration files are from the isolated research tree, not an
upstream submission. Its base commit and license are documented in the curated
snapshot. Do not mistake a few integration files for a full upstream checkout.

## Exclusions

No photos/audio/video, passwords or authentication material, raw device logs,
device identity dumps, recovery backups, LocalPolicy receipts, extracted Apple
firmware, kernelcache, DriverKit cache, or operating-system/boot/rootfs images
are uploaded. Those images may contain machine-specific or private data.
Downloaded dependency trees, generated build directories and large binary
outputs also remain local; their absence is not hidden by this manifest.

This archive covers authored research text and selected loader integration,
**not a byte-for-byte backup of the 56 GB workspace**. Original files remain
unchanged in the private workspace.
