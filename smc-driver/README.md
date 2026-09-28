# SMC SRAM candidate

Offline only. Battery support remains unverified and blacklisted on J714s.
No module was installed, no key was queried and no hardware was accessed.
This patch targets the exact Fedora Asahi kernel already recorded on the
laptop. It does not enable battery, hwmon, RTC or lid-event drivers.

## Evidence

The September 6 native boot panicked in `memcpy_fromio` through
`apple_smc_read` and `macsmc_power_probe`. A later guest trace recorded a
64-bit shared-memory read fault at `0x28de8c080` while reading `BMDN`.
The historical observations are in
[PROGRESS.md](../research-archive/PROGRESS.md). The raw private trace is not
included here. The pinned kernel's `lib/iomem_copy.c` uses 64-bit MMIO for
aligned blocks of eight bytes. Smaller trailing accesses use bytes.

The public Apple `26A428` kernelcache supplies a specific alternative. In
`com.apple.driver.AppleSMC`:

- `AppleSMCKeysEndpoint::_readKeyGated` compares the received length against
  destination capacity at `0xfffffe0009aa04b0`. It selects mailbox data for
  received lengths up to four at `0xfffffe0009aa04c4`, and otherwise calls
  `memCpy32fromSMC` at `0xfffffe0009aa0520`.
- `memCpy32fromSMC`, `0xfffffe0009aa09a8`, reads SRAM in 32-bit words. For a
  final one to three bytes, it reads one whole word and copies only the
  requested bytes from that local word.
- `_writeMsg`, `0xfffffe0009aa15e4`, writes SRAM in 32-bit words. Its tail
  starts with a zeroed local word, copies the remaining bytes into it and
  writes the entire word at `0xfffffe0009aa1684`.
- The tail-copy stub at `0xfffffe0009ab9020` resolves to `memmove`.

Kernelcache SHA-256:
`a691760372651464138779c3201c1886a385ca656397362d8e7701ba19ebf436`.
Component: `kernelcache.release.Mac17,6_7_8_9_14_15_16`.
Reproduce with `ipsw macho disass --fileset-entry com.apple.driver.AppleSMC
--symbol SYMBOL --force KERNELCACHE`. The relevant mangled symbols are:

```text
__ZN20AppleSMCKeysEndpoint13_readKeyGatedEPvS0_S0_S0_
__ZL15memCpy32fromSMCPhPvm
__ZN20AppleSMCKeysEndpoint9_writeMsgEP9ApcKeyMsgPv
```

This supports a transfer-width hypothesis. It does not prove that 32-bit
accesses succeed on the laptop or exclude address, mapping, firewall or
firmware-state problems. Small inline keys working would not prove that
SRAM access works.

## Patch behavior

[sram32.patch](sram32.patch) applies to `drivers/mfd/macsmc.c` at
`kernel-7.0.13-400.asahi`, commit
`49f6f1df5a69149f32205ae034e77495910c9a43`.
Base file SHA-256:
`6a8004c39af84de5757ffac8453b3d9822a3e590ff6ac3bf7b1415f52373af0a`.
The [pinned source](https://gitlab.com/fedora-asahi/kernel-asahi/-/blob/49f6f1df5a69149f32205ae034e77495910c9a43/drivers/mfd/macsmc.c)
remains the baseline, with its existing dual MIT/GPL license.

The `sram32` module parameter defaults off and is read-only after loading.
Enabling it on a board other than `apple,j714s` refuses probe before allocation
or hardware calls. Enabling it with an unaligned negotiated SRAM address
refuses initialization. The new copy helpers use only 32-bit MMIO, support
unaligned RAM buffers and pad partial write words with zeros. The 255-byte
protocol limit fits within the already checked 4 KiB key buffer, including
the rounded-up final word. `__ioread32_copy` and `__iowrite32_copy` require
aligned RAM and whole-word lengths, so they cannot directly handle all callers.
The generic transfer helpers remain in use when the option is off.

Correctness changes also apply with the option off:

1. Reply copying uses the actual received length to choose mailbox versus
   SRAM. Oversized replies return `-EPROTO` without copying. Short replies
   leave the rest of the caller's buffer untouched; typed wrappers already
   reject lengths that do not match their type.
2. Key-info commands retain the mutex through the six-byte SRAM copy and
   metadata decoding. Previously another command could overwrite SRAM after
   `apple_smc_cmd` unlocked and before the copy.
3. Normal requests reject uninitialized, failed or atomic-mode SMC states
   before staging write data. The old path staged writes before the command
   function checked those states, potentially corrupting a shutdown request.
4. Failed key-index lookups return before byte-swapping the caller's output.
   The old error path could read an uninitialized key or change its old value.
5. Atomic writes stop after 5,000 unsuccessful polls, accounting for 500 ms
   of requested busy-wait delays, and return `-ETIMEDOUT`. A pending command
   blocks another atomic write with `-EBUSY` before SRAM or mailbox access.
   Send/poll failures and timeouts leave that flag pending until a reply;
   they do not cancel the command or replay it.

The receive callback now checks the command ID before changing the stored
reply or waking a waiter. Previously a late reply for another command could
clear the atomic pending flag, permitting SRAM reuse while the current
command was still outstanding. Both normal and atomic replies use this
check; notifications keep their existing dispatch. All 512 combinations of
the four-bit IDs and waiter modes pass, including a stale reply followed by
an attempted write and then the matching reply. The original and three
mutations fail assertions.

Probe initializes both completions and the blocking notifier before RTKit
can enable receive callbacks. The old order allowed an early message to
touch an uninitialized wait queue or notifier lock. Probe resets completion
counts before its explicit initialization request, so an earlier completion
does not satisfy that wait. This fixes object lifetime, not the boot protocol:
an unsolicited initialization reply during wake can still change the boot
stage and make the subsequent handshake time out.

Read, read/write, normal write, key-info and atomic-write paths use the same
copy helpers. The patch preserves `struct apple_smc` and its exported API.
It also explicitly initializes the atomic spinlock at probe. The existing
normal-command timeout is unchanged. The atomic bound avoids dependence on
jiffies while interrupts are disabled, but is not a hard wall-clock limit:
`apple_rtkit_poll` itself drains the mailbox until empty. A continuously
refilled FIFO could still keep that lower-level call busy. Ordinary command
timeouts are not turned into a permanent transport quarantine by this patch.
Normal commands can still reuse SRAM after a timeout, and the four-bit ID
can wrap. Filtering a mismatched ID does not resolve those protocol limits.
RTKit's separate log/crash-buffer copying still uses its generic helper; this
patch only changes the SMC key buffer. Those other SRAM reads need a separate
assessment if the width hypothesis is confirmed.

## Optional command timeout quarantine

[timeout-quarantine.patch](timeout-quarantine.patch) is a separate experiment
applied **after** `sram32.patch`. An ordinary command timeout sets a new failed
boot state. Existing state checks then reject reads, writes, metadata queries
and atomic shutdown writes before they touch SRAM or send another command.
A matching late reply does not restore service. This avoids treating a timeout
as proof that firmware has released the shared buffer.

The cost is loss of every SMC-dependent function after one transient timeout,
including later battery, sensor, GPIO and reboot/poweroff requests. Recovery
requires reinitialization, and no safe live firmware reset or driver rebind
has been established. Keep this patch out of routine module sets until its
tradeoff has been tested on hardware. It does not make battery support usable.
Send errors and the existing atomic-only timeout behavior are unchanged.

The patch adds one enum value without changing existing values, structure
fields or exports. It also patches `include/linux/mfd/macsmc.h`, whose pinned
SHA-256 is
`2d9a64e924e1aa5cf5d75db9f1570be3c7178aaf955a22121ff8f15b929eaa54`.
The default module builder does not apply this patch.

```sh
python3 smc-driver/test-timeout-quarantine.py --source-tree /path/to/linux
```

Two ASan/UBSan groups cover 48 timeout states across all sixteen message IDs,
late replies, deadline-boundary replies, preserved caller buffers and SRAM,
all normal command entry points and transition to atomic mode. Successful
commands and explicit firmware error replies remain usable. The previous
timeout behavior and four mutations fail assertions. Callback boundaries are
controlled by the fixture; this does not exercise real kernel concurrency.

The optional candidate compiles as an exact-header AArch64 module object
without warnings. No loadable module set includes it, and it has not been
installed or tested on the laptop.

## Optional kernel mailbox budget

[mailbox-poll-budget.patch](mailbox-poll-budget.patch) limits each explicit
`apple_mbox_poll()` call to 32 messages, letting the atomic SMC caller regain
control even when firmware keeps refilling the receive FIFO. It preserves
paired register reads, callbacks, locking, acknowledgements and the return
count. The interrupt handler retains its existing drain-until-empty behavior.
The driver documents receive interrupts as level triggered, so remaining
messages reassert the interrupt after acknowledgement.

This is a separate built-in kernel change. The pinned configuration has
`CONFIG_APPLE_MAILBOX=y`; the module builder does not include this patch.
Base `drivers/soc/apple/mailbox.c` SHA-256:
`7f501ab286effea3268cd9bcb2d172b48ee27585fb848b0f192d04ed445a50dc`.
It applies to the same pinned kernel commit as the SMC patch.

```sh
python3 smc-driver/test-mailbox-poll.py \
  --source /path/to/linux/drivers/soc/apple/mailbox.c
```

Two ASan/UBSan groups cover both interrupt-controller variants, finite queues
of zero through seventy messages, continuously refilled queues and interrupt
draining after a bounded poll. The original behavior and three mutations fail
runtime assertions. The test compiles the actual patched functions and moves
temporary files to Trash. An exact-kernel AArch64 built-in object also compiles
without warnings. No complete kernel was rebuilt, booted or installed.

This is a message-count bound, not a wall-clock guarantee. Lock contention,
callbacks and hardware accesses can still delay a poll, and the interrupt
path remains unbounded. Existing module candidates still depend on the
unmodified mailbox code in the installed kernel.

## Optional mailbox sender concurrency fix

[mailbox-send-waiters.patch](mailbox-send-waiters.patch) fixes send-empty IRQ
bookkeeping when a normal sender times out or receives a signal. It also
handles multiple waiting senders. One cancelled sender no longer masks the
IRQ needed by another, and an empty notification wakes every waiter to
recheck the FIFO. A sequence counter replaces the shared, consumable
completion. The atomic send path is unchanged.

The [Aurora IRQ-balance change](https://github.com/aurora-silicon/linux/commit/7a155e383d2d8e70fd76075ffb7427f4c7a3c326)
provided a useful comparison. The host fixture reproduces its remaining
two-sender failures as well as the original timeout failure. This candidate
tracks the number of waiters and masks only when the last waiter leaves or
the interrupt runs.

```sh
CC=gcc python3 smc-driver/test-mailbox-send.py \
  --source-tree /path/to/linux
```

Eight controlled-thread cases pass under ASan/UBSan with both hardware IRQ
variants. They cover immediate and atomic sends, timeout, interruption, late
IRQ, successful wakeup, competing senders and sequence wrap. Four deliberate
regressions fail. These checks compile the real send and interrupt functions
with host stubs; they do not emulate the interrupt controller or test a Mac.

The patch applies to the same pinned mailbox C source and to
`include/linux/soc/apple/mailbox.h`, SHA-256
`4ac9fe47a9110c98ad0b5e7a52fc479b1b4d11373f95a4722f1a84ea6915e05d`.
It changes the mailbox structure layout. It therefore requires a full kernel
build with matching consumers and Rust bindings, not a replacement `.ko`.
The standalone candidate and the candidate combined with the poll budget
both compile as exact-kernel AArch64 built-in objects without warnings.
The combined object has SHA-256
`5d3bcb95cd3b03927e6d46bc2bc209b54bdc9a4d4ddd47a0cb54451bcbb70830`.

Neither full kernel nor matching consumers have been rebuilt. Existing module
sets do not include either mailbox patch. Start/stop handling and the
per-wait timeout remain unchanged; neither patch establishes a total
wall-clock deadline. No candidate was installed or tested on hardware.

## Optional RTKit buffer checks

The optional [RTKit buffer patch](rtkit-buffer-bounds.patch) checks every
shared-memory copy against the mapped size, rejects missing backing memory,
and avoids zero-length pointer access. Syslog rejects zero-sized messages
and frees its prior text allocation before reinitialization. Failed copies
do not reach log printing; a failed crash-buffer copy supplies `NULL, 0` to
the crash callback instead of presenting an empty allocation as valid data.

These changes follow the problems described in the August 24
[syslog bounds proposal](https://lists.openwall.net/linux-kernel/2026/08/24/545)
and [reinitialization proposal](https://lkml.iu.edu/2608.3/00371.html), with
additional backing-pointer and crash-callback checks. The maintainer's
[review](https://lists.infradead.org/pipermail/linux-arm-kernel/2026-August/1164331.html)
requested hardware testing. These local checks do not provide that evidence.
The separate proposed index-count change is not included; the legacy
`idx <= syslog_n_entries` convention is preserved, with copy bounds checked
independently.

```sh
CC=gcc python3 smc-driver/test-rtkit-bounds.py \
  --source /path/to/linux/drivers/soc/apple/rtkit.c
```

Four sanitizer groups cover 261,120 exact/truncated log entries, 65,536
legacy count/index combinations, reinitialization, allocation failure,
zero size, copy overflow and crash callbacks. Four original failures and
six mutations are detected. The source is pinned to SHA-256
`c8683d97c9b8a2690c39a07db805637695c9c869353a1923bd44e92c523949ba`.

RTKit is built into this kernel too. Its candidate compiles without warnings
against the exact headers, and separately as a C consumer of the changed
mailbox header. Public structures and exports are unchanged by this RTKit
patch. No full kernel or matching Rust consumers were rebuilt; it is absent
from the module sets. Generic `memcpy_fromio` access widths remain unchanged,
so these bounds checks do not resolve the SMC SRAM-width hypothesis.

## Offline verification

From the repository root, with the pinned kernel source available locally:

```sh
CC=gcc python3 smc-driver/test-sram32.py \
  --source /path/to/linux/drivers/mfd/macsmc.c
```

Six groups compile the actual patched C under ASan/UBSan. They cover all
lengths from zero through 255, eight RAM alignments, both copy modes, every
combination of 255 destination capacities and 256 reply lengths, metadata
locking, atomic writes and board/alignment refusals. Atomic checks also cover
a silent device, send/poll errors, the last permitted poll succeeding and
refusal to overwrite a pending command's SRAM. A simulated competing
command overwrites SRAM as soon as the mutex is released; metadata still
comes from the first reply. The original five regression mutations fail
their intended assertions. Three further mutations independently restore the
endless atomic wait, pending-buffer reuse and failed key-output conversion;
the expanded tests detect each one. These checks do not emulate the SMC or bus.
Temporary test directories go to Trash. GCC's analyzer returned zero on the
earlier five-group candidate, with no defect diagnostics, but stopped
exploring some paths at its complexity limit. The later reply-ID and
probe-order changes have sanitizer and exact-kernel build checks, not a new
analyzer result.

The separate probe fixture executes the actual probe prefix and both receive
callbacks with injected RTKit messages:

```sh
CC=gcc python3 smc-driver/test-probe-order.py \
  --source /path/to/linux/drivers/mfd/macsmc.c
```

Nine paths cover early initialization, command and notification callbacks,
missing fresh replies, RTKit initialization/wake/endpoint/send failures, and the
remaining unsolicited-reply timeout. The original and four ordering or
completion mutations fail assertions. The fixture checks synchronization
object initialization; it does not run kernel threads or firmware.

The existing exact-kernel builder can include this candidate:

```sh
python3 usb-driver/build-linux.py \
  --devel-rpm /path/to/kernel-devel.rpm \
  --cross-prefix aarch64-linux- \
  --with-input \
  --smc-source /path/to/linux/drivers/mfd/macsmc.c \
  --output /path/to/new-smc-build
AZAHI_USB_BUILD=/path/to/new-smc-build python3 usb-driver/test-build-linux.py
```

Both the devel RPM and base SMC source must match their pinned hashes.
The builder keeps the original source tree untouched and saves the patched
copy, patch, commands and artifact hashes in the new output directory.
It performs strict export, AArch64 ELF, vermagic and module-layout checks.
The same compiler and instrumentation limitations described in
[BUILD-AND-TEST.md](../docs/BUILD-AND-TEST.md) apply.

## Attended hardware test boundary

This is a core driver used by SMC GPIO and built-in input. Do not unload or
replace it on a running system. A future experiment needs a separately
prepared boot candidate, the unchanged known-working boot entry and local
recovery that does not depend on the changed input stack.

Start with all existing SMC child blacklists preserved. Confirm the candidate
loaded and the requested parameter is active, then observe initialization and
existing input. An intentional large key read belongs in a later, separately
bounded experiment. Only a successful large read and battery-driver test can
justify removing its blacklist. Stop after any SRAM fault, timeout, failed
input or unexpected restart; cold-boot the preserved baseline. No automatic
retry, battery enablement, charging control or suspend experiment is included.

## Battery firmware compatibility backport

The pinned `macsmc-power.c` has the one-byte `BCF0` check but still always
byte-swaps `B0RM`, the remaining-charge value. Upstream
[macOS 27 support, commit 57694663d658](https://github.com/AsahiLinux/linux/commit/57694663d658899ab4843fc457b10df5155dbbab)
records that the same firmware changed `B0RM` from big endian to little
endian. This is separate from the earlier SRAM fault.

[power-macos27.patch](power-macos27.patch) applies that missing conversion
using the existing `bcf0_1byte` firmware discriminator and upstream's signed
16-bit interpretation. It fixes both charge-now and energy-now. Those two
property paths also return read errors before using their output, and the
one-byte critical-status temporary now starts at zero, as in upstream.
Charging policy and notification actions are unchanged. Probe now initializes
both work items before registering the notifier. Previously an immediate
critical-battery notification could schedule an uninitialized work item.

Base `drivers/power/supply/macsmc-power.c` SHA-256:
`96b6da14e998a9872d11da9c634570c598f8dcbc7d9c305f6578b775b8803935`.
Run the offline conversion tests with:

```sh
CC=gcc python3 smc-driver/test-power-macos27.py \
  --source /path/to/linux/drivers/power/supply/macsmc-power.c
```

Three sanitizer-backed groups test every 16-bit value in both firmware byte
orders through the actual helper and both changed property cases, plus
critical-status sizes, read-error propagation and notification registration.
The last group compiles the real event handler and probe registration tail,
then injects a critical event before registration returns. The original
ordering fails; the patched ordering passes with logging both on and off.
These are host stubs with synthetic values, not battery observations. No
device, charging or power-off API runs.

Add `--smc-power-source /path/to/linux/drivers/power/supply/macsmc-power.c`
to the builder command above to include the battery module. It requires the
pinned SMC core source too. The candidate remains blacklisted and uninstalled.
Loading the existing battery driver is not a read-only diagnostic: its probe
already clears several charging-policy keys. That behavior needs review in
an attended test, after SRAM reads have been shown to work.
Removal now clears the parameter setter's global pointer under the kernel's
parameter lock, unregisters the blocking notifier, and synchronously drains
both work items. Probe uses the same lock when publishing that pointer.
Previously cancellation neither stopped in-flight work nor prevented a
late notifier or parameter write from queuing more work.

```sh
CC=gcc python3 smc-driver/test-power-lifecycle.py \
  --source /path/to/linux/drivers/power/supply/macsmc-power.c
```

This additional sanitizer-backed group checks 32 combinations of pending
and running work with logging enabled or disabled. It injects a notifier
before unregister returns, a parameter write after the pointer is cleared,
and a debug callback that requeues itself. The original and five regression
mutations fail assertions. The pinned kernel's parameter and workqueue APIs
provide the locking and drain guarantees modeled by these stubs. Actual SMC
latency and live reload remain unvalidated; the no-live-replacement rule
still applies.

The rebuilt battery candidate has SHA-256
`2397d022715bef52f2e4b149ee7e8bb17ca1064209650ccbe2302f64f084a462`.
It is identical in the nine-module and optional ten-module builds. All other
artifacts retain their prior hashes; all fourteen paired-builder checks pass.
