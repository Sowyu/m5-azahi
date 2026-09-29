# Daily driving the J714s Linux install

Settings and checks for the installed v7 system. This does not make the
machine a confirmed daily driver: networking, trackpad reliability, shutdown,
sleep and additional CPU cores remain unresolved on the installed image.
Updated 2026-09-28 offline. None of these changes has run on the machine.

## What you get

| Works | Limit |
| --- | --- |
| KDE from the SSD, full 3024x1964 display, 175% scaling | One CPU core, software rendering: slow for heavy apps |
| Keyboard | Trackpad fails on some boots; reboot usually fixes it |
| Phone USB tethering, at boot and after replug (2026-09-29) | Boot with the right socket empty, or unplug the phone once after boot |
| Reboot | Power-off halts instead; see the shutdown rule |
| | No sleep. Closing the lid does nothing and the battery keeps draining |

## Daily rules

1. Boot with the right USB-C socket empty. MagSafe is fine. Plug USB devices
   in after KDE is up. A device attached during boot causes a clean HPM
   refusal; `azahi-usb` then retries every 10 s for up to 15 minutes, so
   unplugging it for about 15 s is enough. The helper's already-awake path
   does not enforce an empty socket, so follow this order even when it
   reports ready.
2. Shut down with `systemctl poweroff`, then wait for the line
   `Power off not available: System halted instead`. It prints only after
   every device has shut down, so holding the power button after it is as
   safe as a normal power-off. If it never appears within two minutes, note
   what the screen shows before holding power.
3. Don't close the lid to pause. Power off for long breaks, or keep MagSafe
   connected.
4. Don't update the kernel or boot packages. The script adds global DNF
   excludes. Do not assume Discover/PackageKit honors them until checked on
   the target, and do not use options that disable excludes.
5. Never unload the USB, input or storage drivers.

## One-time setup (about 5 minutes)

### Without network: type these as root

```sh
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target
```

This blocks normal systemd sleep requests immediately and persists across
boots. It does not configure package exclusions. Leave system updates alone
until the script below is available. Direct writes to `/sys/power/state`
bypass systemd and remain unsafe.

### With network: use the script

These settings are currently on `audit-2026-09-25`; cloning `main` will not
include this script. In Konsole on the M5, run:

```sh
git clone --branch audit-2026-09-25 --single-branch https://github.com/Sowyu/m5-azahi.git m5-azahi-audit
sudo bash m5-azahi-audit/daily-driver/apply-safe-config.sh           # report only
sudo bash m5-azahi-audit/daily-driver/apply-safe-config.sh --apply   # change, with backups
```

Each line reports `OK`, `CHANGED` or `WOULD-CHANGE`. The script refuses to
run on any other kernel or machine. Run it again in report mode after
applying; each settings line should say `OK`.

The local 2026-09-28 changes preserve separate backups even for two edits in
the same second, as `<file>.azahi-bak-<timestamp>.<random>`. They handle empty,
indented and multiline `excludepkgs` entries in `[main]`, preserve repository
settings, and refuse ambiguous or disabled exclusions before any changes.
These changes have not been published to the branch above yet.

The script also checks DNF5's inherited `disable_excludes` setting. It follows
the documented [drop-in loading order](https://dnf5.readthedocs.io/en/latest/dnf5.conf.5.html#drop-in-configuration-directories),
including matching-filename masks and the final `dnf.conf` override. An
inherited `main` or `*`, even when quoted, refuses all changes. Variable-based
disable settings also need review. Quoted existing exclusions keep their
quotes and package names when the protected names are inserted. Fourteen
host tests pass; the inherited bypass reproduced before the fix.

Fedora 44's inspected PackageKit 1.3.4 and 1.4.0 sources load the same DNF5
configuration and repository exclusions. That supports the intended KDE
update policy, but the target's installed backend and any already-loaded
PackageKit state remain unchecked. Writing the file alone does not prove
that a running graphical updater has reloaded it. Keep graphical updates
paused until an attended check confirms the exclusions in its update list.

The logind settings apply at the next boot. Do not restart systemd-logind
to load them early; that can end the KDE session. The sleep masks already
block normal systemd suspend requests.

This applies settings only. Downloading the source does not update the
installed kernel, drivers or boot image, and does not enable more CPU cores.

## Getting a network

Phone USB tethering works again (2026-09-29, see `docs/HANDOFF.md`). With
`azahi-usb` enabled and the two drop-ins from `usb-driver/azahi-usb.service.d/`
installed, plug the phone into the right socket after KDE is up and enable
USB tethering; NetworkManager's `azahi-usb-tether` profile connects `enu1`.

A USB adapter on the right-hand USB-C socket remains an alternative, through a
USB-C to USB-A adapter if needed. Details and driver list:
[../docs/USB-NETWORK-ADAPTERS.md](../docs/USB-NETWORK-ADAPTERS.md).

1. Boot with sockets empty and wait for KDE.
2. Run `sudo systemctl start azahi-usb`, then inspect
   `sudo journalctl -b -u azahi-usb --no-pager -n 30` for `USB_HOST_READY`
   or `USB_ALREADY_READY`. `systemctl start` itself normally prints nothing.
3. Plug in the adapter.
4. Wired Ethernet (RTL8153 or AX88179) gets DHCP from NetworkManager on its
   own. For a Wi-Fi adapter (MT7921AU is the best-supported chip), run
   `nmcli device wifi connect <ssid> --ask`.
5. Check with `nmcli device` and a real HTTPS request, for example
   `curl -sI https://fedoraproject.org | head -n 1`.

Once this works reliably, start USB at every boot:
`systemctl enable azahi-usb`, or run the script with `--usb-at-boot --apply`.
Keep booting with the sockets empty.

The phone tethering path is still broken (see `docs/HANDOFF.md`). An adapter
avoids the phone's USB function switching, which every recorded failure
involved.

An Android phone also offers a proposed
[ADB cable fallback](../remote-access/PHONE-CABLE.md). It can carry phone SSH
and, with a foreground Termux proxy, laptop HTTP/HTTPS without a tether
network interface. A private offline laptop bundle is ready, but the real
phone and USB data path remain untested. The phone needs its own internet
connection for web access.

## Quick health check

The local `check-health.py` gives a compact report without serials, UUIDs,
network addresses or raw logs. It reads existing state, does not contact
the network, and refuses another model or kernel:

```sh
python3 daily-driver/check-health.py
python3 daily-driver/check-health.py --json
```

`NETWORK_CONFIGURED_NOT_TESTED` means an IPv4 address and a default route
exist on the right-port USB network path. It is not an internet test. The CPU
count reports online CPUs only, without claiming a load test. Exit 0 means
the report was collected, not that the laptop is healthy. This new report
has not been published to GitHub yet.

The health report checks USB network interfaces, not ADB proxy traffic.
`PHONE_NON_NETWORK_FUNCTION` can therefore coexist with a usable proxy.
Use the cable guide's verified HTTPS request to test that separate path.

The report also distinguishes USB service enablement from its current state,
and reports the system's NTP synchronization flag. A running USB service does
not prove networking. `usb2_lpm_policy` is the kernel's allowed/disabled policy,
not evidence that the controller entered L1 or that LPM caused a disconnect.

Checks available without that script:

```sh
uname -r                                  # 7.0.13-400.asahi.fc44.aarch64+16k
findmnt -n -o SOURCE,FSTYPE /             # the SSD Btrfs root
systemctl is-enabled suspend.target       # masked; nonzero exit is normal
systemctl is-enabled azahi-usb            # enabled once you opt in
nmcli -t device                           # your adapter, connected
systemctl --failed                        # nothing
```

## Next improvements (each needs an attended session)

- **Real power-off.** Install the v8 image from
  `standalone-loader/build-shutdown.py` through Recovery, keeping v7 as
  rollback. Test plan: `docs/audit-2026-09-25/tooling-loader.md`.
- **More CPU cores.** Not usable yet. A read-only loader probe
  (`azahi.smp=probe`, see `docs/audit-2026-09-25/smp.md`) records reset state.
  It cannot establish why the other cores fail to enter the loader.
- **Trackpad retry and the input driver fixes.** These need the rebuilt
  input module and a boot test with a rollback that doesn't depend on the
  keyboard, such as SSH over the USB adapter.
- **Sleep.** Needs the rebuilt NVMe module and real suspend support; the
  masks above stay until both exist.
