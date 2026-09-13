# DockChannel input experiment

J714s uses a two-phase v2 interface-power request. The patch sends nine-byte
requests for the will/has phases and keeps the older board path unchanged.
The host test checks both OFF/ON encodings, ordering and error propagation.

Native keyboard and trackpad operation have been observed, but some boots
still fail early AFE attach/boot and time out. A successful boot logs
`Touch MT ready`; accepted power requests alone do not prove touch readiness.
The installed trackpad firmware was verified privately; it is not distributed.

**Do not unload or unbind this transport: its remove path contains BUG_ON(1).**
See [current progress](../PROGRESS.md) rather than assuming the driver is stable.
