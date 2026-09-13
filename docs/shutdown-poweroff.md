# Shutdown hang at poweroff.target

Status 2026-09-13: cause identified from source, fix prepared, nothing tested
on hardware yet.

## Symptom

`systemctl poweroff` prints "Reached target poweroff.target", the panel stays
lit, the machine never powers off, and the user long-presses the power button
(PROGRESS.md:564, research-archive/CURRENT-STATE.md:143-146).

## Root cause

Nothing in the running kernel registers a power-off handler, so the final
`reboot(2)` syscall ends in the arm64 `machine_power_off()` idle loop with
the framebuffer untouched. That is exactly the observed picture: unmount and
service teardown complete, then silence with the screen on.

Why no handler exists, in order:

1. On Apple silicon the only power-off path is the SMC driver's reboot child,
   `macsmc-reboot` (`CONFIG_POWER_RESET_MACSMC=m`,
   research-archive/kconfig.txt:5564). It writes SMC key `MBSE` = `off1`
   from a `SYS_OFF_MODE_POWER_OFF` handler. There is no PSCI firmware on this
   machine and no `psci` node in any DT here, so `CONFIG_ARM_PSCI_FW=y`
   (kconfig.txt:2634) contributes nothing. None of the other
   `CONFIG_POWER_RESET_*` entries (kconfig.txt:5558-5576) match a node in
   the boot DT.
2. The SMC core does come up. The boot DTB is compiled from
   `t6050-j714s-native-rootguard.dts`, whose include chain is
   rootguard -> native-ssd-ro -> native-input -> hv-input-sid0 -> hv-input
   -> hv -> t6050-min.dtsi. The SMC node lives in
   research-archive/t6050-j714s-hv-input.dts:14-24 and its RTKit handshake
   was seen working (research-archive/PROGRESS.md:926-927, :1017).
3. That SMC node has exactly one child, `gpio` (`apple,smc-low-gpio`). It has
   no `reboot { compatible = "apple,smc-reboot"; }` child. Compare the M3 Pro
   reference DT research-archive/t6030-j514s.dts:2539-2543, which has one.
4. The Asahi SMC MFD driver (`drivers/mfd/macsmc.c`, `CONFIG_MFD_MACSMC=m`,
   kconfig.txt:6129) adds its children with `devm_mfd_add_devices()` from a
   fixed cell list that includes `macsmc-reboot` with
   `of_compatible = "apple,smc-reboot"`. When no child node matches,
   `mfd_add_device()` logs `macsmc-reboot: Failed to locate of_node` and
   still registers the platform device, just without an `of_node`.
5. `macsmc-reboot.ko` carries only an OF modalias
   (`MODULE_DEVICE_TABLE(of, ...)`, no `MODULE_ALIAS("platform:...")`). A
   platform device without an `of_node` has modalias `platform:macsmc-reboot`,
   which matches nothing, so udev never loads the module. The driver would
   bind by name (`platform_match()` name fallback) if it were loaded, but
   nothing loads it. The GPIO driver shows the same mechanism working the
   other way: `macsmc-gpio` also has no node, yet it registered, because the
   `apple,smc-low-gpio` node pulled the module in and the driver then bound
   both devices by name (research-archive/PROGRESS.md:1017-1018).
6. The kernel command line blacklists `macsmc_power,macsmc_input,
   macsmc_hwmon,rtc_macsmc` (probe/build-native-ssdroot.py:190). It does not
   blacklist `macsmc_reboot`, so the blacklist is not the cause and must stay
   (research-archive/CURRENT-STATE.md:889-891).

Confidence: about 85 percent that the missing handler is the cause of the
hang, from source alone. The remaining doubt is whether the SMC on this
loader accepts the `MBSE` write at all; that is only answerable on hardware.

## Hypotheses considered and refuted

- SMC node absent or disabled in the boot DT. Refuted: present and probed
  (t6050-j714s-hv-input.dts:14, PROGRESS.md:926).
- SMC blacklist removes the reboot driver. Refuted: `macsmc_reboot` is not in
  the list (probe/build-native-ssdroot.py:190).
- Watchdog missing from the DT. Refuted: `watchdog@28836c000` is in
  research-archive/t6050-min.dtsi:88-94 with `apple,t8103-wdt`, so
  `apple_wdt` autoloads through its OF alias and registers a restart handler.
  The loader disables the watchdog at start (research-archive/standalone-
  loader/m1n1-20260911/src/main.c:173, `wdt_disable()`) and never re-arms it,
  so a Linux-side hang is not a watchdog issue either. The wdt only covers
  `reboot`, never `poweroff`.
- NVMe driver blocking shutdown. Refuted: `apple_nvme_shutdown()`
  (nvme-driver/apple.c:1818-1826) only disables the controller and stops
  RTKit; the "J714S_RO refuses runtime reset" path (apple.c:1159-1163) is in
  the reset worker, which shutdown does not call. Shutdown reached
  poweroff.target, so device shutdown callbacks completed.
- DockChannel HID `remove` `BUG_ON` (input-driver/dockchannel-hid.c:1214-
  1216). Refuted: the driver has no `.shutdown` callback and the kernel does
  not call `.remove` at power-off.
- One CPU / no PSCI. Not a factor for power-off: `smp_send_stop()` has no
  secondaries to stop, and the SMC path does not need PSCI.
- Missing nvmem cells (shutdown_flag, boot_stage, ...) making the reboot
  driver fail probe. Refuted: the driver treats a missing cell as a warning
  and continues; only `-EPROBE_DEFER` is propagated.

## Fix shipped

`shutdown/macsmc-reboot.conf`, a one-line `modules-load.d` file. Install on
the Linux SSD root while it is mounted read-write:

```sh
sudo install -D -m 644 shutdown/macsmc-reboot.conf /etc/modules-load.d/macsmc-reboot.conf
sudo modprobe macsmc_reboot
ls /sys/bus/platform/drivers/macsmc-reboot/
```

The `ls` should list `macsmc-reboot` (the bound device). If it does, the
next `systemctl poweroff` has a handler. No DTB rebuild, no Recovery
reinstall, no bundle hash change. The blacklist is untouched.

Why not the preferred DT change first: it is the correct shape (see upgrade
below) but the boot DTB is hash-pinned in probe/build-native-ssdroot.py:80,
so it needs a rebuilt DTB, a rebuilt bundle and a Recovery reinstall. The
module-load file gets the same driver bound with one file write.

Trade-offs of the shipped fix:

- The reboot driver's probe touches no SMC key. Power-off writes `MBSE off1`
  through the atomic mailbox path, not the SRAM read path that SError'd in
  `macsmc_power_probe` (research-archive/PROGRESS.md:683-686). Lower risk,
  not zero.
- Once loaded, `macsmc_reboot` also takes over `reboot` (`MBSE phra`,
  `SYS_OFF_PRIO_HIGH`, above `apple_wdt`). Either handler resets the SoC
  into iBoot and the installed loader, which boots Linux again.
- The four nvmem cells are absent (no SPMI/PMU node in the T6050 DTs), so
  the kernel logs "Missing NVMEM cell" warnings and the SMC's boot-stage and
  shutdown-flag bookkeeping is skipped. Harmless for power-off.

## Upgrade path (DT)

Add to the SMC node in the private copy of `t6050-j714s-hv-input.dts`:

```
reboot {
	compatible = "apple,smc-reboot";
};
```

Then rebuild the DTB, update the pinned hash in
probe/build-native-ssdroot.py:80, rebuild the bundle, reinstall, and delete
the modules-load.d file. The archived DTS files were left unchanged because
the archive is historical and its manifest pins their hashes.

## What to look for on the next attempt

Before shutting down, after installing the file:

```sh
lsmod | grep macsmc
ls /sys/bus/platform/devices | grep -i smc
cat /sys/bus/platform/devices/macsmc-reboot/modalias
ls /sys/bus/platform/drivers/macsmc-reboot/
cat /sys/kernel/reboot/*
dmesg | grep -iE 'smc|wdt|watchdog|psci|reboot|poweroff|rtkit'
```

Expected: `macsmc_reboot` in lsmod; `macsmc-reboot` among the devices;
modalias `platform:macsmc-reboot` (confirms the missing of_node); the driver
directory listing the device; `dmesg` shows the `Failed to locate of_node`
warning and, if nvmem is absent, `Missing NVMEM cell` warnings and no
`Failed to write MBSE` line.

After the attempt, on the following boot:

```sh
journalctl -b -1 | tail -n 40
journalctl -b -1 | grep -iE 'macsmc|MBSE|reboot:|Power down'
```

Confirmed if the machine actually powered off. If it still hung, `reboot:
Power down` with no `macsmc` write error means the SMC ignored `MBSE`; a
`Failed to write MBSE` line means the mailbox path itself failed. Either way
the next step is a hardware question, not a config one.

If the module never loads: `modprobe macsmc_reboot` by hand and read the
error. `Module not found` means the SSD root lacks the Fedora module set for
this kernel release.

## Manual fallback if the fix does not work

- `echo o > /proc/sysrq-trigger` will not help: it calls the same
  power-off path and has no handler either.
- `systemctl reboot` should work through `apple_wdt` (or through the SMC
  once the module is loaded). Filesystems unmount first, then the SoC resets
  into the loader. Hold the power button once the loader or startup picker
  is on screen, not while Linux is running. Untested; an orderly reboot is
  still a cleaner exit than a long-press with Btrfs mounted.
- If both hang, wait for the panel to show the final kernel messages before
  the long-press. Once poweroff.target is reached the root filesystem has
  been remounted read-only or unmounted, so the disk is not at risk at that
  point; the kernel simply has nowhere to go.
