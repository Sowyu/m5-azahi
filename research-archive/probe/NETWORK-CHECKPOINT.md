# J714s native networking — 2026-09-12

## Sep13 CURRENT: USB first, hardened candidate still untested on target

Update: user approved attended Recovery. Proposed file-transfer bundle below
is now built and offline-tested, NOT installed. Fresh-backup-gated server is
running onPRIVATE-LAN-ENDPOINT-REMOVED Current exact procedure, hashes and
KDE rollback: `usb-driver/TRANSFER-CHECKPOINT.md`. No target changes yet.

Latest user photo of requested lsblk confirms nvme0n1p5 Btrfs `fedora`,
PARTUUID PRIVATE-UUID-REMOVED mounted at `/`: native SSD
root verified again. p4 PARTUUID PRIVATE-UUID-REMOVED has
blank FSTYPE/mountpoint; no FAT filesystem is shown anywhere in the listing.
Blank lsblk FSTYPE is not proof p4 contains no data or permission to format it.
p2 protected APFS identity matches prior inventory; p3/p7 APFS, p6 no detected
filesystem. No mounts/writes performed. FAT staging route is unestablished.

Proposed alternate delivery: build a separately named, verified Linux boot
bundle carrying the candidate files in its initramfs, retaining kernel/DT/
rootguard and installing no driver automatically. Transfer/enroll only through
Linux-paired Recovery after a fresh verified backup and explicit attended
approval. This is a proposal, NOT a built/tested package or a completed boot
change. Need review early-to-SSD file handoff and alignment/receipt tests first.
Do not run old enrollment scripts unchanged or enter Recovery before ready.

User explicitly prioritised USB tethering before native Wi-Fi. Host-only
implementation/rebuild completed with 33 passing offline checks. New canonical
usb-driver/usb-tether-test.sh; stage/deliver refreshed and verified. See
usb-driver/README.md top for behavior changes, source/lifecycle audit and
remaining live risks. No target network/USB success, no target modifications,
no webcam, no reboot or transfer server started. Next read-only user inventory:
`lsblk -o NAME,FSTYPE,LABEL,PARTUUID,MOUNTPOINTS`. It is for choosing a verified
Linux-owned staging path, not permission to format/mount or touch daily macOS.

## Sep13 native N1 driver/ACIPC sources located, no networking yet

User asked for built-in Wi-Fi after recovering KDE/trackpad. New host-only
investigation found AppleCentauriAlpha/Control/Beta DriverKit personalities
matching saved106b:1902/1901/1903; Alpha publishes AppleWLANDriver. Full code
lives in HOST DriverKit shared cache, not the tiny dext executables or just
the saved kernelcache manager. Apple-shipped AirshipDK t2026 plists describe
ACIPC firmware-loader registers, control/data rings, interrupts and errata.
See **probe/N1-WIFI-20260913.md** for exact paths/hashes/maps and remaining
implementation. Eight saved-hardware audit tests pass; Asahi wip7.2 still same
pin, no matching Linux N1 driver found. No target access, reboot, webcam,
module load, boot/storage change or commit. Working Linux session preserved.
This is an RE foothold, not a driver/network success or quick-fix promise.

USB candidate below is NOT cleared for live testing: earlier code review
found test-script exit-code masking/false HTTPS success, dry-run module left
loaded blocking subsequent apply, and missing role-switch cleanup on forced
host probe failure. Those are unpatched; delivery isn't the only blocker.

## Latest: right-socket USB2 host candidate BUILT and offline-verified (not tested)

Unattended session built a full USB2-host candidate for phone tethering in
`usb-driver/` (see `usb-driver/README.md`). Host-only work: no target
connection, no MMIO, no driver load, no boot-image edit, no reboot. Webcam
confirms the target is still on the unchanged native KDE desktop
(`logs/usb-offline-build-check-20260912-1510.jpg`).

**Built and cross-checked against the exact `7.0.13-400.asahi.fc44.aarch64+16k`
devel package:**

- `phy-apple-t6050-usb2.ko` — eUSB2 host PHY, sequence transcribed from the
  saved kernelcache `AppleT6050TypeCPhy::eusb2phy_init(false,false)`
  (VA 0xfffffe0009a3b744); SIG bits driven by the ADT `tunable_USB2PHY_DFLT`
  (+0x8 mask 0x7003 → 0x0003, +0x18 mask 0x703 → 0x103) then
  `tunable_USB2PHY_HOST` (+0x8 → 0x7003). No writes at probe.
  SHA256 `c54ffb8d82f966c5a907898e09e0d53fec42904493e42a45999791586f3e0b12`.
- `dwc3-apple-t6050.ko` — fork of stock `dwc3-apple.c`, distinct compatible
  `azahi,t6050-dwc3-usb2`, optional reset, `azahi,force-host-mode` at probe.
  SHA256 `703c8c5ddda01c8ecd911e6bf33df95da3614f6c1d1787fed6bb2b2ef4d59826`.
- `azahi-usb-overlay.ko` — runtime `of_overlay_fdt_apply` loader with read-only
  PMGR/PHY/DWC3 preflight; embeds both overlays.
  SHA256 `2b45bf4924176220066c5a3098b22bde784aef9efb587b95cb4c69f8d380166e`.
- Overlays `t6050-j714s-usb-right-{minimal,pmgr}.dtbo`, merge cleanly onto the
  installed rootguard DTB with `fdtoverlay`.
- `usb-driver/test-usb-candidate.py`: **11 tests pass** (addresses/IRQs/DART
  SIDs/tunables/PMGR offsets vs the saved ADT, overlay merge, module ABI).

**Key facts nailed down** (all were mis-assumed at least once, now guarded by
the test): the right socket is ADT **instance 2 / port-number 3**, so its PMGR
domains are `ATC2_*` (COMMON @0x280600000+0x238, USB_AON/USB/PHYMXWRAP
@0x288300000+0x178/0x180/0x188), **not** `atc3_*`. `PHY_TYPE_USB2` is 3 in this
kernel. The loader's `usb_init()` in `kboot_boot()` already powers every ATC
instance and leaves the pipehandler at DWC3_RESET_N, so the minimal overlay
needs no PMGR nodes or reset provider.

**Remaining live-test prerequisite (blocker for completion):** no data path
into native Linux exists (only `lo`), and installing/testing needs an attended
Recovery/HTTP session + a reboot, both forbidden this unattended run. The
biggest engineering unknown is VBUS — the M4 project reached root hubs but no
child enumerated; best assessment is the TI PD firmware sources VBUS
autonomously in S0, unproven on T6050. Stage two if it does not is an SPMI
`sn201202x` PD driver (not in this candidate). See `usb-driver/README.md`.

## Previous: unattended long-running task requested for receiving agent

User updated the handoff: work while they are shopping/watching movies today;
no questions, no reboot/power cycles, keep going toward working native Linux
networking (Nothing Phone tether priority). Read the execution contract at the
top of `probe/HANDOFF-20260912-USB.md`. Preserve working KDE/boot and macOS;
continue all useful offline work if live access is unavailable. Do not call
builds or root hubs networking success. Document a genuine exhausted-access
blocker without asking for intervention or claiming completion. This is a
handoff directive, not evidence that a background run has been launched.

## Previous stop/document checkpoint (superseded by contract above)

User approved Nothing Phone (3a) Pro USB tethering as immediate priority,
then asked to stop and document everything. That pause was subsequently
replaced by the unattended receiving-agent instructions above. Read
`probe/HANDOFF-20260912-USB.md` first: exact target
baseline, safety/rollback, local changes, source pins, M5 PHY symbol addresses,
and uncompleted work. No USB candidate built, installed or tested; target
KDE/boot/macOS unchanged. No power cycle requested. New host-only change:
`inspect-kernelcache.py --entry` supports exact fileset selection; symbols-only
lookup succeeded with Capstone5.0.9 in `/tmp/azahi-usb-disasm.G380qX`.
M5 eusb2phy_init located at fffffe0009a3b744, not yet disassembled/reviewed.
New PD source is tipd/spmi.c, not sn201202x.c. Full details in handoff.
Older preference/next-action paragraphs below are historical; tether priority
is agreed and fixture identity is known.

## Latest: built-in Wi-Fi preference; Apple N1 PCI IDs confirmed

User has a **Nothing Phone (3a) Pro**, but strongly prefers ordinary built-in
Wi-Fi. Treat that as the requested destination; phone is a fallback, not an
already working connection. No phone tether/USB enumeration test performed.

Saved ioreg plist contains populated endpoint identities missing from the
raw preboot ADT. The updated offline audit extracts ONLY allowlisted identity
fields and passes **8 tests**, including wrong vendor/missing endpoint and
private-field exclusion. Saved ioreg SHA256:
`82f39f12aac5806de5f60daa0c17007223ca8c7e2672ba9f7275e6e7c631a836`.

| Saved endpoint | PCI vendor:device | Class |
| --- | --- | --- |
| centauri-control | 106b:1901 | ff0000 |
| centauri-alpha | 106b:1902 | 0d2000 |
| centauri-beta | 106b:1903 | 0d1100 |

[Apple's exact 14-inch M5 Pro/Max specs](https://support.apple.com/en-au/126318)
identify the wireless chip as Apple N1. These are Apple-vendor endpoints, not
the M4 BCM4388 PCI device. Do not force-bind brcmfmac or apply M4 Wi-Fi firmware
or RF/calibration data to them.

Exact local Fedora linux-7.0.13.tar.xz wireless source scan: 2,135 C/header/Rust
files checked for Centauri, PCI_VENDOR_ID_APPLE and 0x1901/2/3. Fourteen lines
matched, all unrelated legacy Broadcom board-vendor quirks, PHY tables,
Qualcomm WMI event IDs or Prism EEPROM tags. No matching N1 driver established.
Asahi asahi-wip-7.2 drivers/net/wireless directory has no Apple vendor subtree;
current-tree path search and focused repository searches established no
compatible N1 driver either. Search absence is not proof that no unpublished
driver exists; scope of conclusion is the checked sources.

Saved kernelcache.mac17j.macho has
`com.apple.driver.AppleCentauriManager` at VA 0xfffffe0007332760,
fileset offset 0x32e760. Defined symbols include probe/start, powerOn,
powerOnOffSequence, apcieErrorHandler, UserClient and USBController methods.
This is a useful offline RE starting point, NOT a Linux driver or proof of
the full Wi-Fi protocol. No firmware executed or new target access performed.
GitHub linux issue479 search hit is an unrelated M1 Thunderbolt report;
do not adopt its Centauri-as-TB or security-wall speculation for this N1 task.

Assessment: built-in Wi-Fi currently requires PCIe/controller bringup AND a
new compatible wireless driver/firmware interface. Merely enabling PCIe or
installing wpa_supplicant cannot make these endpoints usable. No honest
before-trip completion promise. Need agree whether to spend remaining travel
time on phone/USB fallback or pursue longer-term N1 development. USB fallback
also requires the M5 USB work described below; it is NOT plug-and-play yet.
Working KDE/boot/macOS untouched. No reboot requested.

## Current state and scope

KDE now auto-starts from SSD following the clean-config repair. Preserve that
baseline. User approved networking next to enable target-local development.
No native network interface beyond lo at last photographed check. No native
USB controller nodes in enrolled minimal DT. Nothing was installed, loaded,
rebooted, or written to hardware in this networking turn. No commits or daily
macOS writes. Shutdown still hangs at poweroff.target, per user.

The fixture question is now answered above. Do not assume any dongle can work before
the M5 host controller/PHY/Type-C path is operational. Physical socket mapping
is not independently verified. No additional power cycle requested.

## Verified offline inventory

Run `python3 probe/network-hardware-audit.py`. Eight identity/linkage/privacy
tests pass with `python3 probe/test-network-hardware-audit.py`. These scripts
only parse saved files; no proxy, device opening, MMIO, or network access.

- Saved real ADT: Mac17,9, J714sAP;
  SHA256 `5a87c2ee23c945694303a4396fbbf197918220f87441a41505838a3c37277a24`.
- Current rootguard DTB SHA256
  `ddd855503c88b8b3b0afe64b4f3862dee2ec328c347b6c7eca5664bdf1fee5f8`.
- Local kernel config SHA256
  `997a0fb73eb02e81a364cc3a29d81a3c6cc8c17b1980f3b9d6bb65795ace23b3`.
- USB core/glue, xHCI platform, Apple ATC/DART/SPMI and common USB NIC drivers
  are configured (mostly modules). Module presence in config alone does not
  prove the target rootfs contains every .ko or that hardware can bind.
- `PHY_APPLE_T6040_USB2` and `TYPEC_SN201202X` absent/unset in current config.
- PCIe bridge0 children are **centauri-control, centauri-alpha, centauri-beta**,
  unlike the Broadcom BCM4388 setup in the M4 reference. Do not apply its Wi-Fi
  firmware/power recipe blindly. No centauri Linux driver was established by
  this search; exact PCI IDs are not in these saved ADT endpoint properties.

| ADT port | USB core | PHY bank0 / bank1 | USB DART0 / DART1 | Core IRQ list |
| --- | --- | --- | --- | --- |
| 1 | 0x2a2280000 | 0x2a2a90000 / 0x2a2800000 | 0x2a2f00000 / 0x2a2f80000 | 1419,1420,1421,1422 |
| 2 | 0x2aa280000 | 0x2aaa90000 / 0x2aa800000 | 0x2aaf00000 / 0x2aaf80000 | 1451,1452,1453,1454,846 |
| 3 | 0x382280000 | 0x382a90000 / 0x382800000 | 0x382f00000 / 0x382f80000 | 1483,1484,1485,1486,856 |

These are translated ADT resources, **not an approved register scan/write map**.
Each USB core is 0x11800 bytes. PHY candidate banks each 0x4000. DART banks
each 0xc000; remaining ADT DART resources are shared protection/other blocks,
not permission to manipulate them. All three mapper-usb nodes use SID1;
vm-base 0x10000004000, vm-size 0xffff0000. Core -> PHY and core -> mapper
phandles verified by audit. Do not confuse this with MTP's independently
verified SID0, or assume both USB DART instances accept identical handling.

USB ADT compatible: usb-drd,t6050 + usb-drd,t8142.
PHY ADT compatible: atc-phy,t6050 + atc-phy,t6040.
All USB2 host tunables: `080000200370000003700000` (raw, not executed).
Port3 clock-gate IDs: USB267; PHY586,61,268,246,247,248,249.
HPM nodes use `usbc,sn201202x,spmi`; hpm2 at nub-spmi-a1, hpm0/1/5 at
nub-spmi-a0. No SPMI/PD command was issued.

## Source comparison and remaining engineering

Exact Fedora source inspected from saved linux-7.0.13.tar.xz:
drivers/usb/dwc3/dwc3-apple.c registers apple,t8103-dwc3, requests reset
controller, leaves state PROBE_PENDING until a role-switch cable event.
Simply adding a compatible node or modprobing USB Ethernet does not supply
the missing PHY/Type-C role event path.

Closest experimental M4 source, wallace main observed at
`2d0753bff8f02e89add2800b1a2019d0555100c8`:

- [USB2 v2 host test](https://github.com/damsleth/wallace/blob/2d0753bff8f02e89add2800b1a2019d0555100c8/evidence/2026-08-19-t6040-usb2-v2phy-rerun-root-hubs-restored.md):
  root hubs came up, no child enumeration; VBUS/fixture state unresolved.
  It is NOT an end-to-end USB networking success.
- [Host-only PHY slice](https://github.com/damsleth/wallace/blob/2d0753bff8f02e89add2800b1a2019d0555100c8/patches/0001-phy-apple-add-experimental-T6040-USB2-only-slice.patch):
  239-line M4 provider, default host mode fixes early DWC3 power-on -EINVAL.
  Volatile register writes at power_on; no inverse power_off sequence. ADT
  M4-compatible fallback makes this worth evaluating, not automatically safe.
- [Forced-host glue patch](https://github.com/damsleth/wallace/blob/2d0753bff8f02e89add2800b1a2019d0555100c8/patches/t6040-dwc3-apple-force-host.patch):
  depends on a prior force-device fork not present in our stock glue. Cannot
  apply this small patch alone and assume the dependency stack is complete.
- [M4 Wi-Fi evidence](https://github.com/damsleth/wallace/blob/2d0753bff8f02e89add2800b1a2019d0555100c8/evidence/2026-07-29-t6040-WIFI-AND-BLUETOOTH-WORKING.md):
  BCM4388 endpoint, unlike this saved M5 Centauri topology.

Asahi asahi-wip-7.2 observed at
`236788cd2602a24c703fe7bdaddaf73ef77d2027`:

- [SN201202x binding](https://github.com/AsahiLinux/linux/blob/236788cd2602a24c703fe7bdaddaf73ef77d2027/Documentation/devicetree/bindings/usb/apple%2Csn201202x.yaml)
  and [Type-C Kconfig](https://github.com/AsahiLinux/linux/blob/236788cd2602a24c703fe7bdaddaf73ef77d2027/drivers/usb/typec/tipd/Kconfig)
  provide newer SPMI PD-controller support absent from our current config.
- PHY atc.c match table still t8103/t8122 only; no t6040/t6050 match.
  DWC3 Apple glue still matches t8103. No drop-in M5 USB stack established.

Next: get available fixture identity, choose host vs gadget route, review
M5 PHY sequence + power/role + DART dependencies, stage isolated module/DT
candidate and transfer/rollback plan. Native testing requires a real data
path for delivering code (currently none), likely a single batched Recovery
or separate diagnostic boot after build validation. Do not replace the working
enrolled image with an unreviewed USB experiment. No candidate module/DT or
new enrolled image has been built yet; the completed artifact is the offline
audit and tested board mapping.
