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
outputs are consumed; the eight host test groups pass with GCC and ASan/UBSan.
No updated input module is installed, and intermittent AFE startup remains
unresolved.

The latest exact-kernel candidate includes both the GPIO block-boundary and
HID write-length fixes below. Module SHA-256:
`891efe20097cbdd779932ebdc8b1400fffc2443eddecf836fe5ceef6e7636990`.
The normal nine-module build and optional NVMe-pair ten-module build produce
the same input bytes. The paired build passes all fourteen builder checks;
other modules and overlays retain their prior hashes.

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
