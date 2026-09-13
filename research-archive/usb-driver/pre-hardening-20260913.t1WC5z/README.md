# J714s (M5 Pro / T6050) right-socket USB2 host candidate

Offline-built, offline-verified candidate for bringing up **USB2 host mode on
the right-hand USB-C socket** of the MacBook Pro 14" M5 Pro, so a phone in USB
tethering mode can give native Linux a network connection. Built 2026-09-12 on
the M1 Pro host. **Not yet tested on hardware** — see "Status" below.

Everything here is private bring-up work for this one machine. Nothing is for
upstream. The stock `Image-asahi` kernel is unchanged; all of this is
out-of-tree modules plus a runtime device-tree overlay.

## Status

- Three modules and two device-tree overlays **build clean** against the exact
  Fedora `7.0.13-400.asahi.fc44.aarch64+16k` devel package, with the same
  cross-build recipe already proven on hardware for the input module.
- `test-usb-candidate.py` (11 tests) passes: addresses, IRQs, DART SIDs,
  eUSB2 tunables and PMGR offsets all match the saved real ADT; the overlays
  merge cleanly onto the installed rootguard DTB with `fdtoverlay`; module
  vermagic/`this_module` size/undefined-symbols all check out.
- **No hardware test has run.** There is no established data path into native
  Linux (last interface check showed only `lo`), and the unattended contract
  forbids the reboot/Recovery session that installing these files would need.
  A successful build, matching compatible, or xHCI root hub coming up would
  **not** be success — success is a phone enumerating and outbound HTTPS.

## What it is

The right socket is ADT **instance 2** (`/arm-io/usb-drd2`, `atc-phy2`,
`dart-usb2`), ADT **port-number 3**, PD controller `nub-spmi-a1/hpm2`
(`port-location = "right"`). Do not confuse the instance number (selects the
PMGR `ATC2_*` domains and the register banks) with the port number.

Three pieces, because the stock kernel has no driver that binds this SoC:

1. **`phy-apple-t6050-usb2.ko`** — an eUSB2 host-only PHY provider
   (`compatible = "azahi,t6050-usb2-phy"`). Its power-on sequence is a
   transcription of `AppleT6050TypeCPhy::eusb2phy_init(false, false)` from the
   saved Mac17,9 kernelcache (VA `0xfffffe0009a3b744`), which the XHCI host
   path reaches through `initUSB2(0x40000)`. It differs from the M4 "wallace"
   slice in that the SIG-register bits are not hard-coded: they come from the
   ADT tunables `tunable_USB2PHY_DFLT`/`tunable_USB2PHY_HOST`, applied exactly
   as `AppleT6050TypeCPhy::applyTunables()` does. No register writes at probe.
2. **`dwc3-apple-t6050.ko`** — a fork of the stock `dwc3-apple.c` with a
   distinct compatible (`azahi,t6050-dwc3-usb2`) so the in-tree driver never
   binds, an **optional** reset provider (the loader already leaves the DWC3
   out of reset via the pipehandler), and an `azahi,force-host-mode` property
   that brings the core up in host mode at probe. This is needed because there
   is no SPMI SN201202x Type-C driver in this kernel, so the role-switch cable
   event the stock glue waits on never arrives. See `dwc3-apple-t6050.diff`.
3. **`azahi-usb-overlay.ko`** — applies the device-tree overlay at run time
   with `of_overlay_fdt_apply()`, after a **read-only** preflight that maps and
   prints the ATC2 PMGR power-state registers (always-on, safe to read cold)
   and, only if `ATC2_USB` reads ACTIVE, the PHY/pipehandler/DWC3 banks. It
   embeds two compiled overlays and picks one by module parameter.

## Why a runtime overlay

The enrolled boot DTB (`t6050-j714s-native-rootguard.dtb`) has no USB nodes,
and re-enrolling a new DTB is a boot change that is out of scope right now
(it would risk the working autonomous KDE boot). A runtime overlay adds the
nodes to the live tree without touching the boot image; a reboot returns to
the unchanged system. The loader module keeps itself pinned once an overlay is
applied, because the devices it creates cannot be safely torn down.

## Overlays

- **`t6050-j714s-usb-right-minimal.dtso`** (default): DART ×2 + PHY + DWC3, no
  PMGR nodes, no reset provider. Relies on the m1n1-based loader's
  `usb_phy_bringup(2)` having already powered `ATC2_COMMON` / `ATC2_USB_AON` /
  `ATC2_USB` / `ATC2_PHYMXWRAP` / `dart-usb2` and left the DWC3 out of reset.
  The loader's `kboot_boot()` calls `usb_init()`, so this holds at Linux entry.
- **`t6050-j714s-usb-right-pmgr.dtso`**: same, plus the `ATC2` power-controller
  nodes so `genpd` powers the domains itself. Use only if the loader module's
  preflight reports the domains are **not** active.

Both use numeric `interrupt-parent = <2>` (the AIC's phandle in the installed
DTB; the live tree has no `__symbols__`, so a label can't reach it — the loader
verifies that phandle before applying). Intra-overlay references (iommus, phys,
power-domains) use labels and are resolved through `__local_fixups__`; the build
strips the `__symbols__` node that `dtc -@` emits, which the kernel would
otherwise reject.

DART stream IDs: the ADT mapper uses SID 1, upstream Apple DTs use SID 0 on
dart0 and SID 1 on dart1. The overlay lists both SIDs on both DARTs; unlisted
SIDs only fault, they do not SError, so this is a safe hedge.

## Build

```sh
cd usb-driver && bash build.sh
```

Uses Homebrew `clang`/`ld.lld` + the extracted Fedora headers + the
`input-driver` `modpost` (with `-M`, the flag whose earlier omission broke the
NVMe module). Outputs land in `stage/` with a `SHA256SUMS`. Verify offline:

```sh
python3 test-usb-candidate.py
```

## Test on hardware (ATTENDED, needs a reboot — not done yet)

1. Get `stage/*.ko` and `stage/usb-tether-test.sh` onto the native root
   (Recovery HTTP session, or whatever transport is established then).
2. Plug the phone into the **right** socket with USB tethering enabled.
3. `sh usb-tether-test.sh dry` first — this only prints the PMGR/PHY/DWC3
   state, applies no overlay. Confirm `ATC2_USB ... ACTIVE`.
4. `sh usb-tether-test.sh` — loads the stack and walks root hub → child device
   → interface → address/route/DNS → outbound HTTPS, logging each stage.
5. If the domains were not active, `sh usb-tether-test.sh pmgr`.

The script aborts on the wrong kernel and writes nothing outside its log.

## Known gaps / risks

- **VBUS is the real unknown.** The M4 project got root hubs up but never
  enumerated a child, attributed to VBUS not being sourced because the SPMI PD
  controller was bypassed. Best assessment (from `tipd/core.c` never touching
  regulators, yet host mode working on M1/M2, and m1n1 attaching as a device
  on T6050 after only bringing up the PHYs) is that the TI PD firmware sources
  VBUS autonomously in S0 — but this is unproven on T6050. If the phone does
  not attach, stage two is an SPMI `sn201202x` Type-C driver (the Asahi
  `tipd/spmi.c`, backported), not in this candidate.
- eUSB2 handles **USB2 high-speed only**. No USB3, no DisplayPort, no
  Thunderbolt. Fine for phone tethering.
- The loader leaves the PHY in device-mode init state (SIG `0x01c1000f`); the
  PHY `power_on` runs the shutdown sequence first if it sees the PHY active,
  then the host init. `azahi,sig-clear-mask` drops the loader's device-only
  bits before the tunables run.

## Files

- `phy-apple-t6050-usb2.c`, `dwc3-apple-t6050.c`, `azahi-usb-overlay.c` — sources
- `dwc3-apple-t6050.diff` — the fork's diff against the stock glue
- `dts/*.dtso` — the two overlays
- `vendor/dwc3/` — exact stock dwc3 headers + original glue this was forked from
- `build.sh`, `mk-blob-header.py`, `strip-symbols.py` — build tooling
- `test-usb-candidate.py` — offline verification (11 tests)
- `stage/` — built artifacts + `SHA256SUMS`
- `evidence/` — decoded/raw kernelcache disassembly and the redacted ADT dump
  the register sequence and addresses were derived from
