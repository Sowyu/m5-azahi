# J714s native read-only NVMe diagnostic

**Later root-only variant:** this directory now also contains the separate
`build-rootguard/nvme-apple.ko` used for the successful native SSD-root KDE boot.
The read-only scope described below applies to the original diagnostic, not
that explicitly armed fixed-root variant. The tested SART remains
`build/apple-sart.ko`. See [current handoff](../CURRENT-STATE.md) and
[rootguard checkpoint](../probe/ROOTGUARD-CHECKPOINT.md) for exact pins and limits.

Private, uncommitted experiment. No target media writes are permitted by the
diagnostic NVMe command path. This is **not** a writable installation driver.

## First native result and build correction

The v2 service failed before NVMe probe with three unresolved SART symbols.
Webcam `logs/native-ssd-ro-service-failure-20260906.jpg` shows the exact names.
The custom build omitted modpost's `-M` (CONFIG_MODULES), so SART's source
export records were not converted into the final kernel export table.
This was a local build error, not an SSD hardware failure.

Build script now uses `-M` and asserts all three `__ksymtab_` symbols exist
in the finished module and its generated symvers. NVMe module is unchanged;
corrected apple-sart.ko SHA256 is
`58ba58e4a6dd0b4574751d224772d9bfe447fa3f4e8bdba8cfa9e7c52b80305d`.
Old broken module preserved as `vendor/apple-sart-missing-exports.ko`.
Native v3 hardware retest resolved module loading: namespaces discovered,
both test regions read consistently four times each (128MiB total). Final
comparison with pre-installation HV hashes failed; cause/write counters are
still being checked. See the checkpoint; do not claim complete storage safety.

## Provenance and scope

`vendor/` preserves the unmodified Linux 7.0.13 `apple.c` and `sart.c`, extracted
from the Fedora source archive already recorded in `input-driver/README.md`.
The NVMe private header is from that same archive. The Fedora delayed-flush
addition is deliberately not included: this diagnostic accepts no media writes
or flushes. Both modules use the exact running kernel headers and Module.symvers.

The split NVMMU mapping follows Yureka Lilian's
[M4 ANS2 patch](https://lists.infradead.org/pipermail/linux-arm-kernel/2026-August/1160801.html).
The I/O buffer registration is done before CreateCQ/CreateSQ, matching this
machine's successfully tested HV hooks. Queue limit 63 and SARTv4 offsets
0x60/0xc0 follow the local HV hardware result, not an assertion that upstream
has verified these M5 changes. SART uses only the first 16 entries and preserves
every occupied firmware entry; higher entries are untouched.

The board-specific compatible `azahi,j714s-nvme-readonly` enables:

- Separate NVMe and NVMMU resources, explicit I/O buffer registration, and
  zero-based pending-command limit 63.
- Rejection of every I/O opcode except Read before DMA mapping/submission.
  Admin operations are restricted to identify/log/features/queue setup;
  saved feature writes and destructive/vendor opcodes are rejected.
- Refusal of cold power reset and runtime recovery reset. The preexisting
  firmware must already be running. A crash requires a physical cycle.
- No Linux PMGR/reset providers. Only the loader-side, ADT-checked
  APCIE_SYS_ST0 activation already verified under HV may change power state.

This does not prevent SSD firmware's own internal housekeeping. It prevents
host-requested media writes; it is not a claim that experimental drivers can
eliminate all hardware risk.

## Build and validation

`bash nvme-driver/build-modules.sh` builds both modules with Homebrew LLVM/LLD.
The only compile warning is the base source's unsigned queue-count pointer
passed to an int-pointer declaration. Module versions resolve without forcing.
Module struct size is 0x540, matching the input module/kernel ABI.

- nvme-apple.ko: `94755503e7677412fa63e23cbe42c03cc9c2a44308abeea1aa930c021e55b46e`
- apple-sart.ko (corrected exports): `58ba58e4a6dd0b4574751d224772d9bfe447fa3f4e8bdba8cfa9e7c52b80305d`

`python3 probe/test-prepare-native-ans.py`: seven offline real-ADT/mock tests
pass, including unknown power state/fault/parent rejection before any write.
`probe/build-native-ssd-ro.py` appends modules and a one-shot panel test to the
unchanged native input initramfs. The original source image is SHA-verified.
`probe/boot-native.py --ssd-readonly --offline IMAGE` verifies its manifest,
module identities, DT, kernel and RAM placement before connecting.

Live test and result: see `probe/NATIVE-SSD-CHECKPOINT.md`.
