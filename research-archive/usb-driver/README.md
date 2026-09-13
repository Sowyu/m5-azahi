# J714s (M5 Pro / T6050) right-socket USB2 host candidate

**CRITICAL latest:** v4 correctly enrolled but failed loader's fixed initrd
size check. Bad-image server disabled. Fixed-size v5 built; actual C bounds
regression now included. RAM-only correction passed loader and handoff SENT;
KDE/courier pending user evidence. Installed boot remains bad v4; don't reboot
casually. TRANSFER-CHECKPOINT.md top is authoritative over historical notes.

**Latest: transfer-only v4 now INSTALLED and host-readback verified.** Cold
boot and RAM-file courier untested; native USB drivers still not loaded. See
TRANSFER-CHECKPOINT.md for exact new coih, receipts, next boot and KDE rollback.

**Newest Sep13:** user approved attended Recovery transfer. Aligned transfer-
only v4 image built,16 transfer tests +12 existing installer tests passed;
not installed or boot-tested. Read `TRANSFER-CHECKPOINT.md` for current server,
fresh-backup gate, hashes, KDE rollback and next physical steps. No live modules
loaded and no network success. Remaining DMA/PHY/PD review below still applies.

## Sep13 hardening checkpoint (supersedes old test instructions)

User priority: USB tethering first, native N1 Wi-Fi second. Still **no live
USB test or working network**. Host-only rebuild; target boot, KDE, input,
partitions and daily macOS untouched. No commits or webcam capture.

- Canonical runner is now `usb-tether-test.sh` here, copied into stage/deliver
  by `build.sh`. It defaults to **dry**, rejects unknown modes, validates the
  exact four-file manifest, kernel and Linux root UUID, and refuses retries
  with any candidate module already loaded. `run` preserves command and log
  failures; no more successful `tee` hiding failed `insmod`/HTTPS.
- Dry mode loads ONLY the overlay diagnostic, reads PMGR only, then unloads
  that successfully loaded dry module, including when log retrieval fails.
  It never unloads an applied overlay or the input/dockchannel transport.
- Live mode is explicit `minimal`. It matches USB hubs and network interfaces
  by right-controller sysfs ancestry (not usb1 or any non-lo interface), uses
  a temporary NetworkManager profile, requires IPv4, and binds certificate-
  checked HTTPS to that interface with proxies/curl config disabled. DNS may
  use the system resolver; this is not proof DNS packets used USB. No claim
  of persistent networking is made. Temporary profile remains for this boot.
- Overlay requires both target and actual ACTIVE for all five checked power
  states, now including PHYMXWRAP. No force bypass; PMGR live variant withheld
  pending its power/reset audit. Live peripheral mapping/ID failures abort.
  Existing USB, PHY or either DART node is rejected. Read-only MMIO is not a
  general safety guarantee; gating/topology still need hardware validation.
- Fixed-host glue no longer publishes a role switch before forced init.
  If initial core probe succeeds but host init fails, it uses core_remove
  exactly once with no initialized role; it does not dereference host_init's
  failed xHCI allocation or exit the PHY twice. Fixed-host remove likewise
  uses one core_remove. Non-fixed-host legacy path is not this test's scope.
  Reviewed exact saved `linux-7.0.13.tar.xz` core.c/host.c/phy-core.c, not just
  newer upstream. Mock C tests exercise the real init function's control flow,
  not hardware behavior or kernel concurrency.
- Build runs 11 existing artifact checks, 19 runner mocks and 3 glue/overlay
  checks before refreshing `deliver/`. SHA256SUMS describes only three modules
  and the runner, so stage/deliver use the same complete manifest. This is
  offline verification, not a proof of functional USB or complete ABI safety.
- Pre-edit sources and both original artifact directories preserved at
  `pre-hardening-20260913.t1WC5z/`. No original files deleted.

Delivery is still unresolved: native Linux last had only lo; KDE's loader
skips the early proxy window. Do not race proxy or stage through protected
daily macOS. Next user action is a read-only Linux disk listing to identify
whether a Linux-owned FAT staging filesystem exists. No mounting, formatting,
Recovery/boot change or new transfer server has been requested/performed.
No approved live-load command has been given to the user this turn.

NetworkManager temporary-profile semantics:
[official nmcli reference](https://networkmanager.dev/docs/api/latest/nmcli.html).
N1 follow-on evidence: `../probe/N1-WIFI-20260913.md`.

Sep13 rebuilt delivery SHA256 (33 tests passed):
```
c54ffb8d82f966c5a907898e09e0d53fec42904493e42a45999791586f3e0b12  phy-apple-t6050-usb2.ko
24b80b4e23f9a0065547df170ca7e6016e93ac7f17a3b47a2b8757636be045ce  dwc3-apple-t6050.ko
bf9a5c1804f7c37db022d5db46a6f2dd75d4d6490b294e7388271fcd693903b1  azahi-usb-overlay.ko
2d0296c61058fdc252f7192c5eefa0eb3c4121643652078f16b623ad9fd2dd58  usb-tether-test.sh
```
`dwc3-apple-t6050.diff` remains the original fork diff, not the Sep13 update;
the C file and pre-edit backup are the current comparison sources. The old
delivery server's printed Recovery fetch command is not an approved staging
procedure and assumes Linux hashing tools; do not use it unchanged in Recovery.

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
   prints the ATC2 PMGR power-state registers and, only in live mode with all
   five checked domains' target/actual ACTIVE, the PHY/pipehandler/DWC3 banks. It
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
  nodes intended for `genpd`. **Live use withheld** pending power/reset audit;
  inactive domains are not permission to bypass the minimal preflight.

Both use numeric `interrupt-parent = <2>` (the AIC's phandle in the installed
DTB; the live tree has no `__symbols__`, so a label can't reach it — the loader
verifies that phandle before applying). Intra-overlay references (iommus, phys,
power-domains) use labels and are resolved through `__local_fixups__`; the build
strips the `__symbols__` node that `dtc -@` emits, which the kernel would
otherwise reject.

DART stream IDs: the ADT mapper uses SID 1, upstream Apple DTs use SID 0 on
dart0 and SID 1 on dart1. The overlay currently lists both SIDs on both DARTs.
This broader mapping is **not established safe or necessary** on T6050 and
remains an audit item before live loading; offline merge tests do not validate
the actual DMA stream routing. No changes to those DT mappings in this pass.

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

Do not execute live mode yet: delivery and hardware-risk review remain open.

1. Resolve and verify a permitted delivery path, then transfer the four files
   in `deliver/` plus its `SHA256SUMS` into Linux. Do not use daily macOS.
2. Plug the phone into the **right** socket with USB tethering enabled.
3. `bash usb-tether-test.sh dry` — reports PMGR state only, applies no overlay,
   unloads the dry diagnostic. Review all five target/actual states.
4. After risk review, `bash usb-tether-test.sh minimal` is the live experiment.
   It can hang Linux and require an attended cycle. Do not retry/unload the
   applied overlay. PMGR variant and force bypass are disabled.

The runner creates a log and an in-memory NetworkManager profile; ordinary
system daemons may also log/record DHCP state. Boot configuration is unchanged.

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
