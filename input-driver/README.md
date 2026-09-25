# DockChannel input experiment

J714s uses a two-phase v2 interface-power request. The patch sends nine-byte
requests for the will/has phases and keeps the older board path unchanged.
The host test checks both OFF/ON encodings, ordering and error propagation.

Native keyboard and trackpad operation have been observed, but some boots
still fail early AFE attach/boot and time out. A successful boot logs
`Touch MT ready`; accepted power requests alone do not prove touch readiness.
The installed trackpad firmware was verified privately; it is not distributed.

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
