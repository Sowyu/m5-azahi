# Standalone one-core bundle work

This directory includes bundle validators/builders and the custom
`azahi_standalone.c/.h`, SMP/PCIe helpers and the reviewed `kboot.c` snapshot.
The full link check below combines these with pinned upstream sources.
It does not produce a replacement for the installed boot image.

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

The current standalone component calls the default-off SMP probe. Rebuilding
the private loader now requires `azahi_smp.c/.h` and `azahi_smp.o` in OBJECTS.
The integration patch and checks are in [smp/](../smp/README.md). The installed
one-core image is unchanged; these sources do not establish working SMP.

2026-09-28 local guard fix: the loader now requires exact, unique `maxcpus=1`,
`azahi.ssd_root=1` and pinned `root=` arguments before `--`. Substring matches
previously accepted `maxcpus=18`, longer root identities and duplicate
overrides. The bundle validator also rejects CPU/root-mode overrides. Eight
host loader tests pass, including the actual C argument guard. No new loader
has been installed.
PCIe mode arguments now require an exact, unique token before `--` and the
same J714s board identity. CPU probes ignore init arguments after `--` too.
PCIe bring-up requires both overlay nodes before MMIO and stops kernel
handoff on an initialization error. No live teardown or retry is added.
Before controller reads or power changes, it also checks the translated ADT
register ranges against J714s and validates every local tunable's width,
alignment and offset. Missing tunable properties remain optional; neither
the preflight nor the cross-build establishes a working PCIe link.

## Read-only PMGR lookup dependency

`azahi_standalone.c` already required `pmgr_lookup_device_addr` to verify its
four ANS power-register addresses before MMIO. The published snapshot omitted
that private helper. [pmgr-lookup.patch](pmgr-lookup.patch) supplies it through
the existing m1n1 PMGR address resolver. It only resolves die 0, refuses use
before PMGR initialization, requires an exact unique non-virtual name, and
rejects missing or truncated power-register tables. It performs no MMIO or
power-state change and does not widen the caller's hardcoded address checks.

The patch targets `pmgr.c/.h` from m1n1 commit
`4184923ffb2dff079b384d6a32cc02142aa14572`. The offline builder pins both base
file hashes before applying it to an external scratch copy. Reproduce with:

```sh
CC=gcc python3 standalone-loader/test-pmgr-lookup.py --m1n1 /path/to/m1n1
python3 smp/build-offline.py --m1n1 /path/to/m1n1 --output /path/to/new-build
```

Three sanitizer-backed groups cover both PMGR layouts, all 256 group/index
values, missing and ambiguous names, virtual devices and mapping errors.
The tests link no MMIO or power functions. The builder cross-compiles the
standalone caller, PMGR, SMP and read-only diagnostic with `-Werror`.
Combining those four objects with a relocatable link resolves the custom
lookup and diagnostic references. The separate full check below also links
the archived main/payload path with the current guarded components.

## Complete offline link check

`check-full-link.py` reconstructs a source tree from the pinned upstream
commit above, the archived standalone integration and current source fixes.
It reuses the component builder's source checks, then builds the complete
C, assembly and Rust loader with `--no-undefined`. It creates two ELF files,
not a packaged boot image. The public disk placeholder and one-core guard
remain present; no kernel, initrd or DT is included.

Requirements: Python with tar extraction filters, Git, Make, AArch64 GCC and
binutils, Rust with `aarch64-unknown-none-softfloat`, and cached Cargo
dependencies. Cargo runs with `--locked --offline`; prepare its cache from
the pinned tree with `cargo fetch --locked --manifest-path /path/to/m1n1/rust/Cargo.toml`.
Install the Rust target with `rustup target add aarch64-unknown-none-softfloat`.

```sh
python3 standalone-loader/check-full-link.py \
  --m1n1 /path/to/m1n1 \
  --cc /path/to/aarch64-linux-gcc \
  --output /path/to/new-loader-link-check
```

Both links passed on 2026-09-28. There were no C/link warnings and two
upstream Rust warnings about an unused import and unused feature. The check
verifies AArch64 ELF identity, resolved custom entry points, no undefined
symbols, the raw entry at offset `0x800` and preserved guard strings. It saves
disassembly for inspection, source hashes, commands and logs. It refuses an
existing output directory and retains all intermediates, including failures.

Inspection of the linked code confirms that `payload_run` branches directly
to `azahi_standalone_run`, the SMP diagnostic precedes DT preparation, and
the T6050 NVMe refusal remains before the legacy controller initialization.
These are build/integration results. The upstream base differs from the
original private loader, the exact v7 payload is absent, and no image has
been loaded or booted on the laptop.
