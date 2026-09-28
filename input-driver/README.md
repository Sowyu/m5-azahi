# DockChannel input experiment

J714s uses a two-phase v2 interface-power request. The patch sends nine-byte
requests for the will/has phases and keeps the older board path unchanged.
The host test checks both OFF/ON encodings, ordering and error propagation.

Native keyboard and trackpad operation have been observed, but some boots
still fail early AFE attach/boot and time out. A successful boot logs
`Touch MT ready`; accepted power requests alone do not prove touch readiness.
The installed trackpad firmware was verified privately; it is not distributed.

The 2026-09-28 local source no longer depends on a private `hid-ids.h` path.
`python3 ../usb-driver/build-linux.py --with-input` can build this candidate
with the exact public devel RPM and the other required arguments from the
[Linux build instructions](../docs/BUILD-AND-TEST.md). Strict export/vermagic
checks pass. Firmware lookup now requires a zero success result before its
outputs are consumed. Eight original host groups and three firmware-lifetime
groups pass with GCC and ASan/UBSan.
No updated input module is installed, and intermittent AFE startup remains
unresolved.

## Optional FIFO timeout fix

The separate [dockchannel-timeout.patch](dockchannel-timeout.patch) changes
`drivers/soc/apple/dockchannel.c`, below the HID driver. A receive timeout can
call `disable_irq()` from that IRQ's own thread. The kernel then waits for
the same thread to exit, so the timeout never returns. A late TX or RX
interrupt can also disable an IRQ that timeout cancellation disables again,
leaving a disable depth of two. The next enable cannot restore delivery.
These follow from the pinned source and the kernel's
[IRQ synchronization rules](https://docs.kernel.org/core-api/genericirq.html).

The patch disables without waiting for the IRQ thread, drains the hard
handler, and consumes any late completion to balance the handler's extra
disable. A timeout still returns `-ETIMEDOUT`. No public API, structure,
register sequence or FIFO threshold changes. The zero-count `await` cancel
path is unchanged; this is not a general teardown or callback-lifetime fix.

Base source SHA-256:
`83cc73986312a06d99f7e5828a078964a581be00dc5826195e4622d5c6a7bede`.
Run from the repository root:

```sh
CC=gcc python3 input-driver/test-dockchannel-timeout.py \
  --source /path/to/linux/drivers/soc/apple/dockchannel.c
```

Three sanitizer-backed groups check 24 successful transfers and six timeout
interleavings, including the real receive callback path, partial transfers
and later IRQ reuse. Two original failures and four mutations fail assertions.
The test models the kernel's synchronization and completion contracts. It
does not run an interrupt controller or reproduce a captured laptop failure.

An optional `apple-dockchannel.ko` compiled against the exact devel RPM without
warnings. Strict modpost, final imports, the four existing exports, AArch64,
vermagic and module-layout checks pass. SHA-256:
`cbf30af36af34f21c054bfc05c9f0ddcb199f25f9f5e58bd614d37a0a66c6ae0`.
It is an optional addition to the daily module sets and has not been installed. The
manual-build limitations in [BUILD-AND-TEST.md](../docs/BUILD-AND-TEST.md) apply.
For a reproducible build, add
`--dockchannel-source /path/to/linux/drivers/soc/apple/dockchannel.c` to the
Linux builder command. This checks the same base-source pin and applies the
patch in its output directory. It names the result `apple-dockchannel.ko`,
matching the pinned kernel's module name. The option is independent of
`--with-input` and remains off unless the source argument is supplied.
The combined eleven-module build passes all sixteen builder tests. Its other
ten modules and both overlays match the prior paired build byte for byte.
Do not replace the running parent driver: its removal reaches the HID
driver's `BUG_ON(1)`. Any future test needs a separate boot candidate and
keyboard-independent rollback.

This is a concrete timeout-path bug, not an established explanation for the
intermittent AFE startup failure. The default HID receiver still loses packet
position after a partial body timeout and does not rearm after a header
failure. Successful IRQ reuse does not recover that position. The separate
candidate below preserves fragments before such a timeout occurs.

## Optional fragmented receive candidate

[rx-fragments.patch](rx-fragments.patch) changes this repository's HID
receiver. The old callback requests the entire body even when only its header
has arrived. If the one-second FIFO wait times out after consuming part of
the body, its error return does not say how many bytes were consumed. The
next callback treats remaining body bytes as a new header. Changing the
header-error return to rearm would have the same framing problem.

The candidate reads at most the IRQ callback's available-byte count and
retains the partial header/body until a later callback. It arms the existing
FIFO threshold for the remaining bytes, then checks and dispatches only a
complete packet. Complete bad-checksum, short-subheader, unknown-interface
and allocation-failure packets still leave the next boundary usable.
All functions outside the receiver remain byte identical.

An invalid header length or unexpected transport error stops reception with
an explicit log. The protocol has no established resynchronization method.
The candidate cannot recover lost bytes, a FIFO reset or a firmware restart.
It assumes the FIFO count is accurate and this driver is the only reader;
it has not verified those assumptions during hardware reset. A stalled
partial packet remains pending. TX timeout behavior and teardown are unchanged.

Base HID source SHA-256:
`ac8711e9da3c1b4b0d8abee5d72a0e5d81436b3c80ee1137d2b98f2e4fa301c7`.
The test pins this source and applies the patch in a temporary copy:

```sh
CC=gcc python3 input-driver/test-rx-fragments.py
```

Four ASan/UBSan groups cover all 77 byte splits of a sample packet across
three channels, 50 payload/chunk schedules through 65,532-byte payloads,
100 consecutive packets across fifteen interfaces, complete packet drops
and transport errors. The original request beyond available bytes and five
state mutations fail assertions. The fixture models byte availability and
callbacks; it does not run the FIFO driver, an IRQ controller or firmware.

The optional `dockchannel-hid.ko` passes exact-header AArch64 compilation,
strict modpost, imports, vermagic and module-layout checks. It retains the
same four packed-member warnings in the target's `objpool.h` as the baseline,
with no new warning messages. SHA-256:
`7d0296cc9406a4a6974eb6de0028f804157b5055bba41d589d063ca1f1f7a41c`.
It uses the existing DockChannel API and needs no public header change.

The normal builder does not apply this patch, and the existing module sets
remain unchanged. To prepare a separate build, apply it with
`patch --batch --fuzz=0 -p1 < input-driver/rx-fragments.patch` in a separate
repository copy, then use the existing Linux builder with `--with-input`.
No module was installed or tested on the laptop. This is not an established
explanation for the intermittent AFE failure.

## HID candidate

The latest exact-kernel candidate includes the firmware staging cleanup,
GPIO block-boundary and HID write-length fixes below. Module SHA-256:
`c1c2d9f6bb3bf3e3a0ab35cce02088e25c8e0e1fbf836ac6dd14f90ca61642cb`.
The combined eleven-module build passes all sixteen builder checks. Ten other
modules and both USB overlays remain byte-identical to the previous set.
The build retains its existing 63 target-header and pointer-sign warnings.

Firmware startup now releases its CPU staging copy on success and every
error exit. Previously `dchid_get_firmware()` retained that allocation until
device removal, even after `dchid_send_firmware()` had copied the bytes into
a separate coherent DMA buffer. Repeated failed starts accumulated both
copies. The new cleanup frees only the staging allocation. It retains every
coherent buffer, including after a lost command ACK, because firmware may
still use that address. Startup return values and the retry latch are unchanged.

```sh
CC=gcc python3 input-driver/test-firmware-lifetime.py
```

Three ASan/UBSan groups compile the actual lookup, upload and startup
functions with synthetic firmware. They cover early lookup failures, missing
firmware, invalid headers, allocation/GPIO/upload/power failures and success.
Thirty-two failed uploads retain all DMA bytes while releasing every CPU
copy. The original leak and three lifetime/state mutations fail assertions.
The same checks pass with the fragmented receiver applied; its source pin
and hunk offsets were updated without changing receive logic. That optional
module also passes exact-header compilation and module checks. These results
do not establish why AFE startup fails or permit DMA-buffer reuse or teardown.

The shared FIFO now has a packet-level transmit mutex. Previously each HID
interface held only its own command mutex, so another interface could insert
bytes between a packet's header, payload and checksum. A two-thread host test
forces this overlap: the current sender preserves both packets, and removing
the new lock reproduces a corrupted checksum. Every send-error path releases
the lock. It is released before waiting for the command ACK, so GPIO replies
and other interfaces can still transmit while a command awaits its response.
This fixes a source-level race; no evidence yet ties it to the observed AFE
failure. The updated candidate passes the exact-kernel build checks.

Init GPIO requests now validate their own block length. The old parser used
the remaining packet length, so a short GPIO block could borrow bytes from
the following block and configure a bogus GPIO name or ID. The new host test
reproduces that before the fix, then checks all 36 short block lengths,
valid and extended requests, following descriptors and packet truncations.
Restoring the old length check fails the assertion. No recorded boot packet
has shown this malformed input, so it is not a demonstrated AFE startup fix.

GPIO pulse failures now retain the error ACK. The pinned kernel's GPIO setter
returns an errno, which the old code ignored before sending success. Both
pulse edges and the default 10 ms delay are preserved, including the release
attempt after an assertion error. Invalid GPIO IDs and unsupported commands
are rejected before acquiring the GPIO. Host tests cover both edge failures
and preserve the echoed command bytes. This improves failure reporting; the
pulse timing and intermittent AFE failure remain unvalidated on hardware.

Raw HID SET_REPORT now preserves the caller's report type. Feature writes
previously used the output-report flag `0x40`; they now use `0x80`, matching
Apple's SCM FIFO implementation. Output writes still use `0x40`. The host
test covers GET/SET types, buffer boundaries and error returns, and restoring
the old mapping makes it fail. Successful SET_REPORT also returns the number
of submitted bytes, including the report ID, instead of the ACK's payload
length. A four-byte write with a one-byte ACK previously returned one to
hidraw. The expanded check reproduces this before the fix and catches both
type and length regressions. This matches the
[September 25 upstream transport proposal](https://lore.kernel.org/all/20260925-apple-mtp-keyboard-final-v4-8-304c267518f4@gmail.com/),
whose keyboard-only mailbox rewrite is not a replacement for this M5 transport.
The MTP trackpad skips magicmouse's separate
multitouch-enable command, so this is not evidence for its startup failure.

**Do not unload or unbind this transport: its remove path contains BUG_ON(1).**
sysfs unbind is suppressed and the module has no exit, so `rmmod` returns
EBUSY. Unbinding or unloading the MTP helper or the parent DockChannel driver
still reaches the `BUG_ON(1)`.
See [current progress](../PROGRESS.md) rather than assuming the driver is stable.

GPIO requests, events and ACKs are logged (`Acquired GPIO`, `GPIO event:`,
`GPIO ack:`, and the errno when a request fails). Capture an unfiltered
`dmesg` on a failed boot; earlier filters hid every GPIO line.

## start_retry (default off)

Adapted from PR 2 (commit 921db7b). With `dockchannel_hid.start_retry=1`, or
1 written to `/sys/module/dockchannel_hid/parameters/start_retry`, one open
after `start timed out` repeats the interface start: firmware upload plus the
v2 power OFF/ON pair. Without it the interface stays marked starting and later
opens return EINPROGRESS until reboot.

- Hypothesis: the AFE keeps state across the forced reboot, and a failed
  bootload leaves it in a state from which a second start succeeds.
- Expected observation: `AZAHI_START_RETRY iface multi-touch`, then on the
  next open of the trackpad event node another firmware send, two more
  `AZAHI_V2_POWER` lines and `Touch MT ready`. The same AFE failure again
  refutes the hypothesis.
- Risk: each retry keeps one more firmware-sized DMA buffer until reboot. The
  MTP firmware may reject a second upload in one session, which could stall
  the shared comm channel and the keyboard with it.
- Rollback: leave the parameter unset, or write 0 before the next open. A
  reboot without the parameter restores the old behaviour.

## gpio_pulse_50ms (default off, J714s only)

Apple's 26A428 `AppleHIDTransportManagement::externalResourceActionGated`
uses a 50 ms delay between setting and clearing resource action 3. The Linux
handler uses 10 ms. The candidate adds `gpio_pulse_50ms=1` at module load for
an attended comparison. It has no effect on other models. The marker
`AZAHI_GPIO_PULSE_50MS` confirms the selected branch when an event arrives;
changing the option after that event does not repeat the pulse.

- Hypothesis: the shorter pulse contributes to intermittent AFE startup.
- Test: use the candidate with keyboard-independent rollback, enable only
  this timing option, and compare cold boots with `start_retry` still off.
  Record the pulse marker, GPIO errors and whether `Touch MT ready` appears.
- Risk: a longer reset pulse is new hardware behavior and can still fail.
  Host tests establish the default/model guards and both error paths only.
- Rollback: leave the option unset, or reboot with it set to 0. The installed
  module and its pins remain unchanged.

The exact function addresses and packet-layout limitations are recorded in
[the kernel audit](../docs/audit-2026-09-25/kernel.md#input-protocol-follow-up-2026-09-28).
