# J714s shutdown and restart

The early standalone device tree has no SMC reboot child and no PMU bus.
Consequently the stock SMC reboot driver refuses to bind, leaving no kernel
power-off handler and only a watchdog restart path. Loading its module alone
does not fix that.

This board driver supplies the missing lifecycle on the pinned Fedora
`7.0.13-400.asahi.fc44.aarch64+16k` build. It follows the Asahi SMC reboot
driver's `rest`/`offw`, clean-boot-stage and shutdown-bit semantics, then sends
`phra` or `off1`. It retains the installed SMC core and its locking. The final
four-byte write uses one 32-bit SRAM access and bounded atomic mailbox TX;
it does not enter the stock unbounded receive-poll loop. A one-second wait
leaves the existing watchdog restart handler available as fallback.

The PMU transport is restricted to the J714s primary Abbey controller and
three legacy boot-state bytes. It preserves unrelated shutdown-byte bits,
verifies writes by readback, and quarantines ambiguous FIFO states without
retry, reset or flush. Controller ownership includes a reversible hold on
its automatic clock gate; the parent AHB must already be active. The fixed
addresses/SID and scratchpad base were checked against this board's private
hardware description. Raw descriptions and firmware are not distributed.

`enable=0` is the module default: it validates the PMU and SMC without
registering power handlers or writing PMU boot state. The service explicitly
enables the validated path. It keeps handlers registered through shutdown;
stopping the service does not unload the module. It refuses an existing
power-off handler or a different board. No boot image, APFS object or boot
policy is changed by the service.

## Evidence

The target build passes `W=1` (optional pahole/BTF tooling is absent).
ASan/UBSan checks cover byte framing, every shutdown-byte value, preservation
of unrelated bits, failed replies/readbacks, bounded waits, SMC message IDs,
single 32-bit writes, and the actual lifecycle callbacks with injected faults.
Read-only PMU/SMC validation passed on hardware. Two normal restarts returned
to Fedora. The first also verified native Wi-Fi and SSH; between them, normal
power-off turned the machine fully off without holding the power button.
Normal power-on restored Fedora, automatic input recovery and native HTTPS.
The user confirmed pointer/clicks after the final restart.

The late SMC callback runs after persistent journaling stops. These observations
establish the tested outcomes, not whether every restart used SMC rather than
its watchdog fallback. They are not a claim of universal power-management
support or suspend/resume reliability.

## Build and host checks

```sh
make -C /usr/src/kernels/$(uname -r) M="$PWD" W=1 modules
clang -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined test-pmu.c -o /tmp/test-pmu
/tmp/test-pmu
clang -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined test-smc.c -o /tmp/test-smc
/tmp/test-smc
python3 test-lifecycle.py
```

`azahi_pmu_probe` is a separate diagnostic, not a dependency of the power
driver. Its default only checks controller state; `hold_clock=1 read_scratch=1`
reads the three boot-state bytes without PMU writes. Never load both modules
together. Failed ambiguous transactions retain module/resource ownership until
the next boot. Do not force-unload them.

The tested local layout places `azahi_power.ko` and executable `start-power.sh`
under `/opt/azahi-power/current`, with `azahi-power.service` installed and enabled.
The module must be built for the exact running kernel. To stop future loading,
disable that service. That does not remove handlers already registered in the
current boot. This remains an experimental board-specific implementation.

Protocol references: Asahi's
[SMC reboot driver](https://github.com/AsahiLinux/linux/blob/236788cd2602a24c703fe7bdaddaf73ef77d2027/drivers/power/reset/macsmc-reboot.c),
[SPMI controller](https://github.com/AsahiLinux/linux/blob/236788cd2602a24c703fe7bdaddaf73ef77d2027/drivers/spmi/spmi-apple-controller.c)
and [generation-4 register definitions](https://github.com/AsahiLinux/m1n1/blob/5d6df45b2b7f9f1f925e469304122cfdd65694ba/proxyclient/m1n1/hw/spmi4.py).
