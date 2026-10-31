# Bounded trackpad startup recovery

The installed input transport can leave multi-touch permanently marked
`starting` after an AFE boot failure (`No HINT_L`) and missing READY event.
Later opens return EINPROGRESS. A plain firmware/power retry reproduced the
same failure. Pulsing the device-tree-declared AFE reset for 50 ms, releasing
it, allowing another 50 ms to settle, and then retrying startup succeeded.
Firmware reported `Touch MT ready`; opening the event device succeeded in
2.408 seconds, and the user confirmed pointer movement and clicks.

This is a bridge for the exact installed input module. Its removal path
cannot safely run and its manually built functions have no ftrace entries.
The kernel's supported livepatch mechanism instead changes `hid_hw_open`,
preserving its locking, open counts, errors and callbacks. Recovery is selected
only for the exact transport parent, SPI mouse type and original open callback.
All other devices retain the original path. The original transport still owns
startup, firmware DMA and event reception; no DMA memory is freed or reused.

The patch validates the installed module's open/start/close symbol offsets
before activation and holds its device/module references. It uses the original
startup helper. This is intentionally incompatible with other driver builds;
it must not be generalized by removing those checks. A normal replacement
input module should eventually incorporate the fix directly.

Only one failed-start recovery is allowed per patch load. An already-ready
trackpad is untouched. A late READY is given another bounded wait before any
reset. Command, GPIO or second READY failures return an error rather than
looping. Both reset edges report errors; release is attempted even when
assertion fails. `afe_reset` defaults off; the tested service enables it.
The keyboard reset line is never used.

The service runs before the display manager, waits for livepatch transition
completion without forcing it, opens the trackpad once, and emits an input
add event so an already-running desktop can discover the recovered device.
It does not unload or unbind the transport or its parent. On the next cold
boot, the initial AFE failure recovered automatically at about ten seconds.
The following warm restart repeated that automatic recovery. The user confirmed
working input after both boots, and final service/network checks passed.

## Checks

```sh
make -C /usr/src/kernels/$(uname -r) M="$PWD" W=1 modules
clang -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined test-recovery.c -o /tmp/test-recovery
/tmp/test-recovery
python3 test-hid-core.py
python3 test-reset.py
```

These exercise the actual open/recovery/reset functions with simulated
completion and GPIO behavior. Target `W=1` compilation passed. The livepatch
completed normally (`enabled=1`, `transition=0`); no forced transition was used.

The tested local layout places the module and executable startup script under
`/opt/azahi-input/current` and enables `azahi-input-recovery.service`. Disable
the service to prevent future boot loading. Reverting a running patch uses
its standard livepatch `enabled` control, followed by waiting for unpatching
to finish; never force a transition or unload the shared input transport.

See [kernel livepatch documentation](https://docs.kernel.org/livepatch/livepatch.html)
and the [input investigation](../README.md) for the underlying driver and
native reset-timing evidence. This does not establish suspend/resume support
or eliminate every possible input failure.
