# USB network adapters as a stopgap (2026-09-25)

This is not native Wi-Fi. Native N1 Wi-Fi still needs the PCIe and driver
work tracked in `docs/audit-2026-09-25/`. A USB Wi-Fi or Ethernet adapter on
the existing right-socket USB2 host stack is the shortest route to a working
network on this machine, and it would also give future sessions SSH access
without a phone.

## Why it may behave better than phone tethering

Every recorded USB failure so far involves the Android phone: `-71` at
SET_CONFIGURATION, then the phone presenting ADB or Imaging instead of a
network function while its UI claims tethering (see `docs/HANDOFF.md`).
A USB Wi-Fi or Ethernet adapter has one fixed function and no role or
function switching. That removes the phone side from the problem. It does
not fix a host-side cause if one exists, so treat the first attempt as a
diagnostic, not a promise.

## Drivers already in the target kernel

The target config (`research-archive/kconfig.txt`, exact
7.0.13-400.asahi.fc44 build) has these as modules:

| Chipset family | Module | Firmware package on Fedora |
| --- | --- | --- |
| MediaTek MT7921AU (Wi-Fi 6) | `mt7921u` | `mt7xxx-firmware` |
| MediaTek MT7925U (Wi-Fi 7) | `mt7925u` | `mt7xxx-firmware` |
| Realtek RTL8821CU / 8822BU / 8822CU | `rtw88_8821cu`, `rtw88_8822bu`, `rtw88_8822cu` | `realtek-firmware` |
| Atheros AR9271 (2.4 GHz, open firmware) | `ath9k_htc` | `atheros-firmware` |
| Realtek RTL8153 Ethernet | `r8152` | none needed for basic use |
| ASIX AX88179 Ethernet | `ax88179_178a` | none |
| CDC NCM / ECM Ethernet | `cdc_ncm`, `cdc_ether` | none |

MT7921AU has the most mature in-kernel support of the Wi-Fi options.
Wired Ethernet (RTL8153 or AX88179) is the simplest test of the USB host
stack itself, because it needs no firmware and no radio setup.

Whether the firmware packages are installed on the target is not recorded.
Check before relying on a Wi-Fi adapter: `ls /lib/firmware/mediatek` (or
`rtw88`, `ath9k_htc`). Without network access the package cannot be
installed from the target itself.

## Attended test

Same power-up order that worked for the phone: boot with every USB-C socket
empty, wait for KDE, then plug the adapter (through a USB-C to USB-A adapter
if needed) into the right socket. Automatic USB startup is currently
disabled (see `docs/HANDOFF.md`), so start it the documented way first.

1. `lsusb -t`: the adapter should appear at 480M with a driver bound.
2. `dmesg | tail -n 40`: look for `-71`, disconnects or firmware load errors.
3. `nmcli device`: a `wlan0`/`wlx...` or `enx...` device should exist.
4. Wi-Fi: `nmcli device wifi list`, then
   `nmcli device wifi connect <ssid> --ask`.
5. Verify as for tethering: default route, DNS, synchronized time, and
   certificate-validated HTTPS through that interface.

Stop and capture logs if step 1 shows `-71` with a fixed-function adapter.
That would point at the host side (PHY, controller or power) rather than
the phone, which is useful evidence either way.

Hotplug after startup and cold-boot-with-adapter are separate, untested
cases. The HPM guard refuses a connected state at boot by design; do not
remove that guard to make boot-with-adapter work.
