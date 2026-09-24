# Daily driving the J714s Linux install

This is the shortest path to using the installed v7 system day to day with
what exists now. It changes settings only: no rebuilt module, no new boot
image, no reboot needed to apply. Written 2026-09-25, offline; nothing here
has been run on the machine yet.

## What you get

| Works | Limit |
| --- | --- |
| KDE from the SSD, full 3024x1964 display, 175% scaling | One CPU core, software rendering: slow for heavy apps |
| Keyboard | Trackpad fails on some boots; reboot usually fixes it |
| Wired or Wi-Fi networking through a USB adapter (see below) | No built-in Wi-Fi |
| Reboot | Power-off halts instead; see the shutdown rule |
| | No sleep. Closing the lid does nothing and the battery keeps draining |

## Daily rules

1. Boot with every USB-C socket empty. MagSafe is fine. Plug USB devices in
   after KDE is up. A cable at boot makes the USB startup refuse, by design.
2. Shut down with `systemctl poweroff`, then wait for the line
   `Power off not available: System halted instead`. It prints only after
   every device has shut down, so holding the power button after it is as
   safe as a normal power-off. If it never appears within two minutes, note
   what the screen shows before holding power.
3. Don't close the lid to pause. Power off for long breaks, or keep MagSafe
   connected.
4. Don't update the kernel or boot packages. The setup below blocks them in
   dnf, which also covers Discover.
5. Never unload the USB, input or storage drivers.

## One-time setup (about 5 minutes)

### Without network: type these as root

```sh
mkdir -p /etc/systemd/logind.conf.d
printf '[Login]\nHandleLidSwitch=ignore\nHandleLidSwitchExternalPower=ignore\nHandleLidSwitchDocked=ignore\nHandleSuspendKey=ignore\nHandleHibernateKey=ignore\n' > /etc/systemd/logind.conf.d/90-azahi-no-sleep.conf
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target
grep -q '^excludepkgs' /etc/dnf/dnf.conf || sed -i '/^\[main\]/a excludepkgs=kernel*,m1n1*,uboot-images*,update-m1n1' /etc/dnf/dnf.conf
grep '^excludepkgs' /etc/dnf/dnf.conf
```

The last command must print the `excludepkgs=` line. If an `excludepkgs`
line already existed, the `sed` did nothing: add the four patterns to that
line by hand.

The mask takes effect at once and makes every suspend request fail,
including KDE's lid and idle actions. The logind file applies at next boot.
Don't restart systemd-logind to load it early; that can end the KDE session.

### With network: use the script

```sh
git clone https://github.com/Sowyu/m5-azahi
bash m5-azahi/daily-driver/apply-safe-config.sh           # report only
bash m5-azahi/daily-driver/apply-safe-config.sh --apply   # change, with backups
```

Each line reports `OK`, `CHANGED` or `WOULD-CHANGE`. After the typed steps
above, every line should already say `OK`. The script refuses to run on any
other kernel or machine. Edited files are backed up as
`<file>.azahi-bak-<timestamp>`.

## Getting a network

The fastest route is a USB adapter on the right-hand USB-C socket, through a
USB-C to USB-A adapter if needed. Details and driver list:
[../docs/USB-NETWORK-ADAPTERS.md](../docs/USB-NETWORK-ADAPTERS.md).

1. Boot with sockets empty and wait for KDE.
2. Run `systemctl start azahi-usb`. It should print `USB_HOST_READY`, or
   `USB_ALREADY_READY` if it already ran.
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

## Quick health check

```sh
uname -r                                  # 7.0.13-400.asahi.fc44.aarch64+16k
findmnt -n -o SOURCE,FSTYPE /             # the SSD Btrfs root
systemctl is-masked suspend.target        # masked
systemctl is-enabled azahi-usb            # enabled once you opt in
nmcli -t device                           # your adapter, connected
systemctl --failed                        # nothing
```

## Next improvements (each needs an attended session)

- **Real power-off.** Install the v8 image from
  `standalone-loader/build-shutdown.py` through Recovery, keeping v7 as
  rollback. Test plan: `docs/audit-2026-09-25/tooling-loader.md`.
- **More CPU cores.** Under investigation offline; not usable yet.
- **Trackpad retry and the input driver fixes.** These need the rebuilt
  input module and a boot test with a rollback that doesn't depend on the
  keyboard, such as SSH over the USB adapter.
- **Sleep.** Needs the rebuilt NVMe module and real suspend support; the
  masks above stay until both exist.
