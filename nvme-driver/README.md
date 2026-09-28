# ANS / SART storage experiments

The original native diagnostic blocks media writes. A separate private
rootguard variant allowed audited Linux-root writes and supported SSD KDE.
The source includes split NVMe/NVMMU mapping, explicit buffer registration,
SARTv4 handling and command-policy tests. Unmodified source references remain
in `vendor/` with their original notices.

Public disk identifiers are invalid placeholders. **Public rootguard kernel
builds are blocked**: the historical bounds must never be reused on another
disk. The host boundary test remains runnable and does not access hardware.

These software checks do not prove that experimental firmware/DMA behavior
cannot damage storage. Never touch the daily-driving macOS partition and do
not use reset or vendor commands as an attempted recovery shortcut.

## Offline Linux build

The shared [Linux builder](../docs/BUILD-AND-TEST.md) now accepts
`--nvme-header /path/to/linux/drivers/nvme/host/nvme.h`. It pins the internal
header to the exact Fedora kernel, builds `nvme-apple.ko` and `apple-sart.ko`,
and checks both against the package's full export table. It also checks the
three SART exports in the finished provider module and its generated table.
There is no rootguard option. The J714s result blocks media writes and cannot
replace the private driver used for the writable SSD root.

The nine-module build with USB, input, SMC and storage passes strict `modpost`
and all eleven builder tests. Run `python3 nvme-driver/test-readonly.py` for
the separate ASan/UBSan submission checks. They exercise all 256 opcodes in
4,096 combinations of queue, caller, Save bit and buffer-mapping paths, plus
queue/setup/map failures and J714s sleep refusal. They also confirm that the
public rootguard kernel build still fails. Five injected guard regressions
fail runtime assertions. A type-only fix aligns the queue count with the
exact kernel's `int *` argument. Write and reset policies remain unchanged.

These remain uninstalled candidates. The admin-tag timeout deadlock and safe
DMA shutdown are still unresolved, as recorded in
[the storage audit](../docs/audit-2026-09-25/kernel.md#open-risks).

`python3 nvme-driver/test-sart.py` checks the actual four SART backends against
a register array under ASan/UBSan. It exposed an inherited address truncation:
the entry helper accepted shifted addresses wider than the `writel()` used by
every backend. The helper now rejects those addresses before register writes
and returns the reserved slot. The checks cover alignment, existing size
limits, all slot positions, full tables and protected firmware entries. Four
injected regressions fail their assertions. This bounds the software write
width; the narrower hardware field limits for SARTv4 remain unverified.

## Queue lifecycle follow-up

Two later upstream fixes are backported to the offline candidate. Queue
initialization now publishes its enabled flag with a release store, and
readers use acquire loads. The previous barrier followed the flag store,
which did not order the earlier initialization. This follows
[upstream f61c934](https://github.com/torvalds/linux/commit/f61c934aa084b7440fec681be3f4b481eb5a8609).

Controller removal now drains and destroys the admin queue before releasing
the controller. This stops its timeout work before the final queue reference
is dropped, following
[upstream 87d5b986](https://github.com/torvalds/linux/commit/87d5b9864c8118d26f54de4b66d2bddf2c659272).
The exact kernel provides the required queue API and export. The reset
deadlock occurs earlier and remains unresolved.

`python3 nvme-driver/test-lifecycle.py` exercises the actual initialization
and removal functions under ASan/UBSan. Both defects reproduced before the
fixes. Five mutations fail assertions. Host checks cover initialization
before publication and teardown order; they do not model ARM memory
reordering. Disassembly of the exact-kernel module separately confirms
`stlrb` for publication and `ldarb` in the request, IRQ and disable paths.
The lifecycle-only nine-module set passed all eleven builder checks. Its NVMe
module had SHA-256
`45e3388bf4be876dc7a531e22874e2297a9f37de5f155e1b4842db8b0c8cc85d`.
It remains uninstalled, read-only on J714s and unsuitable for the writable
root. Firmware commands, reset refusal and write policy are unchanged.

## Completion validation

The completion handler now validates the request ID before using it to
invalidate an NVMMU entry. Previously even an unknown tag or mismatched
generation reached that register write before the handler rejected it.
After validation, invalidation uses the tag portion of the ID, matching
submission. Valid completions retain their existing routing and status.

```sh
python3 nvme-driver/test-completion.py \
  --nvme-header /path/to/linux/drivers/nvme/host/nvme.h
```

Two ASan/UBSan groups compile the actual completion handler and pinned
`nvme_find_rq()` helper. They cover all 65,536 IDs with two generations,
both queues and both hardware variants, plus missing requests and completion
routing. The original and four regression mutations fail runtime assertions.
The nonzero-generation cases check tag extraction; this driver's existing
quirk disables generation increments during actual operation.

The standard candidate now has NVMe SHA-256
`7409e120fd57bbf9ef60b4d2beff0648edb993b3f91237c165a02b95b2766140`.
Only the Apple NVMe module changed in each rebuilt set. This validates tag
lookup and generation handling, not duplicate completions, queue identity,
safe DMA shutdown or reset recovery. No candidate was loaded or installed.

## Optional firmware compatibility pair

A separate opt-in build applies the newer upstream firmware fixes to both
the Apple driver and the exact 7.0.13 NVMe core. The standard nine-module
build above retains its previous firmware behavior.

Upstream found that newer firmware rejects the old TCB opcode and DMA flags,
requires page-aligned admin buffers, and can raise an SError on the obsolete
PRP-control register access. The patch follows the upstream
[no-data DMA fix](https://github.com/torvalds/linux/commit/94dd5804938d6681dbf26f023b1356d511f4fc48),
[TCB opcode fix](https://github.com/torvalds/linux/commit/cc0fec9b42cfbc69d70cb4c4b616408a7037b445),
[core alignment support](https://github.com/torvalds/linux/commit/69d22a6b2f6984200d92dac689f8b00cc3d7d736),
[Apple alignment flag](https://github.com/torvalds/linux/commit/ea2160c7b78187ea9ab08c3190eef237c4ee99a7)
and [obsolete-register removal](https://github.com/torvalds/linux/commit/8ce883fd068b7ba9ab493cd3ecca3a7ea868c375).
The M5-specific split between NVMe and NVMMU mappings is preserved.
These upstream results do not establish compatibility with this J714s.

Pass `--nvme-core-source /path/to/linux/drivers/nvme/host` to the shared Linux
builder. This selects read-only storage automatically and adds `nvme-core.ko`.
All twelve core sources must match [core-source-pins.json](core-source-pins.json)
before any output is created. The builder applies
[firmware-compat.patch](firmware-compat.patch) to isolated copies. Its nine
core object files match the pinned configuration. Existing installed
packages and installation hashes are not changed.

The paired driver requires the custom `nvme_azahi_admin_page_align_v1` export
before its probe allocates hardware state. The stock core cannot satisfy
that dependency. This prevents loading the firmware-patched Apple driver
without the alignment support it needs. The rebuilt core preserves the
original seventy exports, their types and namespaces, and adds only that
pairing symbol. Export checks inspect the final ELF as well as the generated
table. The guard has been checked by strict modpost and disassembly, without
loading either module.

The ten-module build passes all fourteen builder checks. The other eight
modules and both USB overlays are byte-identical to the standard build.
The paired Apple module is SHA-256
`a2338965f8d5c951f9388894d76c6d1d9d2d5ef0064067883c3d0c332336ca77`;
its core is
`7273bdd837bb7e05647a8b3d6d72b9526f0b810672cac62b697ee80a6eba5e60`.
The manual core compile reports existing `objpool.h` warnings and pointer
signedness warnings in unchanged authentication code. Missing exports and
incompatible pointer types remain build errors.

After a paired build, run:

```sh
AZAHI_USB_BUILD=/path/to/new-build python3 usb-driver/test-build-linux.py
python3 nvme-driver/test-firmware-compat.py --source-dir /path/to/new-build/src/nvme-driver
AZAHI_NVME_SOURCE=/path/to/new-build/src/nvme-driver/apple.c python3 nvme-driver/test-readonly.py
AZAHI_NVME_SOURCE=/path/to/new-build/src/nvme-driver/apple.c python3 nvme-driver/test-lifecycle.py
AZAHI_NVME_SOURCE=/path/to/new-build/src/nvme-driver/apple.c python3 nvme-driver/test-completion.py --nvme-header /path/to/linux/drivers/nvme/host/nvme.h
```

The firmware host checks cover all 32,768 tag/opcode/data combinations and
admin versus I/O alignment. Alignment is 4 KiB, the controller page size,
even though this kernel uses 16 KiB pages. Three regression mutations fail
assertions. These checks do not execute firmware or prove DMA safety.

This is an uninstalled research candidate. It is read-only on J714s and
cannot replace the private writable-root driver. No live module replacement,
firmware restart, boot-image update or reset recovery is provided. Sleep
remains refused and the admin-tag timeout deadlock remains unresolved.

## Optional queue-deletion allocation candidate

[delete-nowait.patch](delete-nowait.patch) changes only the two queue-deletion
helpers. They use `__nvme_submit_sync_cmd()` with `NVME_SUBMIT_NOWAIT`, so an
occupied admin tag returns an allocation error instead of waiting. Once a
tag is acquired, command execution is still synchronous. Queue creation,
timeout/reset policy, media-write guards and the default source are unchanged.

The exact kernel maps this flag to `BLK_MQ_REQ_NOWAIT` before allocating the
request. Its tag allocator returns before entering the wait loop when that
flag is set. The timeout iterator holds a request reference across the
callback, so the admin tag cannot be recycled underneath it. These details
explain the original self-wait and the candidate's narrower change. The
[upstream PCI driver](https://github.com/torvalds/linux/blob/master/drivers/nvme/host/pci.c)
also allocates deletion requests with NOWAIT, but uses a different,
asynchronous completion sequence. This patch does not import that sequence.

```sh
python3 nvme-driver/test-delete-nowait.py \
  --nvme-core /path/to/linux/drivers/nvme/host/core.c
```

The test pins the original 7.0.13 `core.c`, extracts its real synchronous
command helper, and compiles it with the driver's actual deletion, disable
and timeout functions under ASan/UBSan. It compares the original and patched
paths, including both a live admin timeout and an I/O timeout whose deletion
command times out. It also checks command results, allocation errors, missed
interrupts and non-live timeouts. The candidate avoids both modeled tag-wait
cycles; reverting either helper or selecting reserved tags fails assertions.
The same host checks pass with the optional firmware-compatible Apple source
using `--apple-source /path/to/paired-build/src/nvme-driver/apple.c`.

The standalone candidate compiles and passes strict modpost against the exact
target headers and export table, with four warnings in the target's unchanged
`objpool.h`. Disassembly passes flag value 2 to both deletion submissions.
The module is SHA-256
`d150ca024f992f2725fbcf570c8be511e46bcac349a63ca9e2b03e0ff8c7120a`.
No exports or dependencies beyond the existing kernel API are added.

This does not establish safe recovery. Both original and candidate paths
still cancel requests after `nvme_disable_ctrl()` reports failure. The test
deliberately demonstrates that inherited path with a modeled stop failure;
it does not prove that real DMA has stopped. Cancellation may release buffers
still used by hardware, and the J714s runtime reset refusal remains. Full
Linux workqueue concurrency and firmware behavior are not modeled. The patch
is excluded from default builds and install recipes. Nothing was loaded or
installed, and the writable-root driver is unchanged.
