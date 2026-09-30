# Apple N1 bring-up on J714s

**2026-09-30 checkpoint: native N1 now securely associates to a WPA2-PSK/CCMP
access point and receives ordinary network packets under Linux.** The firmware
reports association success, four-way handshake status zero/stage seven, and
connection completion status zero. The corrected receive queue has accepted
hundreds of frames and wrapped its descriptors without stopping.

**Native Wi-Fi is not yet usable by applications.** Transmission, DHCP/IP
connectivity, full cfg80211/NetworkManager integration, reconnects and boot-time
startup are unfinished. USB tethering remains the working network. The packet
frontend has built successfully but has not yet been loaded at this checkpoint.

The source-only checkpoint now includes the current experiments in
[`experiments`](experiments). Firmware images,
signature tickets, keys, credentials, device identifiers, raw packet captures,
logs and disassembly remain private. The source is an experimental progression,
not an installable production driver; numbered recovery modules have exact
state guards and must not be loaded as a batch.

What changed:

- Fresh control transport S41 completed twenty queries across ring wrap,
  station configuration/start and native passive scanning.
- The running firmware requires a 14-byte global connection TLV; the local
  older host encoder used 12 bytes. Matching the firmware parser removed
  status 347 (TLV parsing failure).
- Restoring the firmware's five connection timeout defaults removed an
  immediate four-way timeout. Secure association succeeded twice.
- RX completions use kind 3 for DMA plus metadata. The first receiver rejected
  this, leaving all 127 buffers consumed; the firmware later aborted. S50
  accepts the validated descriptor format and continuously reposts buffers.
- Alpha-only function reset initially failed when reusing the modified working
  image. S54 restores the boot-populated memswap image with bus mastering off,
  then republishes it. Firmware recovery and subsequent reconnection succeeded
  while Linux, tethering and SSH stayed up.
- S51 opened the default station TX queues. S55 provides a bounded, process-
  context packet frontend for the next TX/DHCP test; it is compile-checked only.

Current ownership: S19 retains control firmware, Alpha working memory and MSI;
S49 owns the active Alpha control transport; S50/S51 own active RX/TX DMA.
S53 is the host-only connection caller. Earlier S41/S44/S46 and both reset
markers remain pinned. Published DMA must not be force-unloaded or recycled.
The old BAR4 crash-window reader remains quarantined and was not used. There
was no new Linux kernel panic in this checkpoint's tests. Exact live state and
private evidence are recorded in the private workspace's `wifi/RESULTS.md`.

The following sections record the **earlier first-ROM experiment**.

## First ROM transfer result — 2026-09-29

The N1 ROM accepted a production signed boot image under Linux and advanced
to **preboot, execution stage 4**. This is a firmware-loading milestone,
not working Wi-Fi. Only the ROM PCI identity `106b:1900` is enumerated;
there is no WLAN interface, scan, association or packet transport yet.

The previous pause on the firmware format is superseded by this result.
The supplied production IM4M has no ECID/BNCH values in its manifest policy.
Those names occur in certificate constraints, which must not be mistaken
for a device-bound ticket. All 38 component SHA-384 digests in that ticket
match their FTAB payloads. This offline check does **not** authenticate the
certificate chain; the ROM's success response is separate hardware evidence.

| Step | Observed result |
| --- | --- |
| GP port power and link | Already brought up by the private runtime modules; Gen1 x1 |
| Linux PCI enumeration | `0000:01:00.0`, Apple `106b:1900`, BAR0 64 KiB, single-device DMA IOMMU group |
| ROM register survey | Stage 0, chip/board register `0x20260841`, image response/address/size zero |
| Prepare without doorbell | Image and descriptor DMA mappings verified, then released; PCI command restored to zero |
| ROM image transfer | Response 1 after about 40 ms, first MSI |
| Firmware progress | Stage 4 after about 130 ms, second MSI |
| Next stage | Stayed at preboot for the observation window; no re-enumeration attempted |
| Host after test | Linux and phone tethering responsive; no new DART/AER error observed |

The original live test waited approximately 16.6 seconds, then disabled PCI
bus mastering and retained the image, descriptor, IRQ and module until
reboot. Its final response register was zero because the stage transition
cleared it; the earlier response 1 must not be lost when interpreting the
result. PCI command after the test was `0x0402` (memory decode enabled,
bus mastering disabled, legacy INTx disabled).

The current source stops at preboot explicitly and reports the previously
observed acceptance response. This reporting/cleanup revision has been
compile-checked but has **not** been reloaded into the current live session.
The original tested source and module are preserved in the private workspace
as `wifi/s3-tested-20260929` and on the target as
`/root/azahi-20260929/s3-tested-20260929`.

## Files and scope

- `n1_fw.py`: offline FTAB/IM4M inspector and manifest-first packager. It
  retains all component bytes and the complete signed ticket. It rejects
  incorrect chip/board/security policy, device-bound tickets, digest
  mismatches, duplicate/overlapping/out-of-range records, unsupported flags
  and replacing an existing embedded manifest. It never accesses hardware.
- `test_n1_fw.py`: synthetic format, truncation and corruption cases; no
  firmware fixtures or Apple code are included.
- `n1-rom-survey.c`: one-shot guarded ROM register reader. It temporarily
  enables PCI memory decoding and restores the original command word; no
  DMA or firmware operation.
- `n1-rom-boot.c`: a single reviewed ROM transfer, restricted to J714s,
  the expected BDF/device, chip/board, BAR size, initial register state,
  exclusive DMA IOMMU group and exact image digest. Default `launch=0`
  prepares and frees mappings without ringing a doorbell. `launch=1` pins
  resources and performs the transfer. It has no next-stage or RF operation.
- `Kbuild`: builds the two experiments against the running kernel.

These experiments are not a reusable or hotplug-safe Wi-Fi driver. In the
launched state, do not force-unload the module, remove the PCI device,
unbind/reset the host controller or recycle its DMA mappings. The module
does not implement a removal/re-enumeration lifecycle. Reboot is its
documented resource-release boundary. No module autoload or boot service
was installed, and earlier PCIe power/link bring-up also remains runtime-only.

## Reproduce the offline checks

Keep firmware, tickets, raw disassembly and hardware logs in the private
workspace. Do not copy them into this source directory.

```sh
cd wifi-driver
python3 -m unittest -v test_n1_fw.py
python3 n1_fw.py /private/path/ftab.bin /private/path/centauri.j714sap.im4m
# Optional packaging; the destination must not already exist:
python3 n1_fw.py /private/path/ftab.bin /private/path/centauri.j714sap.im4m \
  --output /private/path/n1-boot-candidate.bin
```

Thirteen synthetic tests pass. The candidate reconstructed from the private
production inputs matches the digest below. The modules build with `W=1`
against `7.0.13-400.asahi.fc44.aarch64+16k` using the target's matching GCC
16.1.1. Missing `pahole`/`vmlinux` prevents optional BTF generation; it does
not prevent building either module.

```sh
make -C /lib/modules/$(uname -r)/build M="$PWD" W=1 modules
```

Building on the helper Mac is not supported by this command. Loading on a
fresh target boot additionally requires the independently reviewed private
GP power/link sequence, N1-only PCI host fork and runtime overlay. This
directory is not a complete boot-time installation recipe.

## Image construction and protocol findings

Inputs came from the production `UniversalMac_27.0_26A428` IPSW:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `Firmware/t2026macG1/Release/ftab.bin` | 31,109,444 | `9d0c83b9641c90c012956c90c099f8cd3a03ebb1e5e4580468a10132587d7ba2` |
| Production `centauri.j714sap.im4m` | 7,772 | `5e0d4efe4273f357c87ae943c9d8ccbab3b738945cdfa866abebbe426e88134b` |
| Prepared candidate before runtime nonce copy | 31,117,312 | `755379aa14e9884f3fdd9cfe2ec144815252cdfca0d5d1767365f782c7455937` |

The FTAB has a 48-byte header, 83 16-byte records and `rkosftab` at offset
32. The unchanged IM4M is placed at `0x560`, immediately after the packed
record table. Payload offsets shift by the ticket's 4-byte-aligned length.
The result is zero-padded to 4096 bytes. All 83 original payloads and the
ticket are checked for byte-for-byte preservation. Only 38 payloads have
individual hashes in this ticket; the inspector lists the other entries.

At runtime the module copies the device's current 64-bit boot nonce from
BAR0+`0x8034` into FTAB+8, without logging it. The production policy is kept
intact. The image descriptor is 32 bytes: 64-bit DMA address, 32-bit image
length, 32-bit zero, then a zero 16-byte terminator. Both mappings use the
Linux DMA API under the N1's IOMMU, with a 40-bit DMA mask.

The transfer writes normal boot mode 0 at `0x803c`, host platform
`0x00086050` at `0x807c` (host board 8, T6050), descriptor address at
`0x8044/0x8048`, descriptor length 32 at `0x804c`, then doorbell 1 at
`0x9000` with a DMA write barrier. Stage is read at `0x8000`, response at
`0x8040`. MSI reception was observed twice in the live test.

Derived from local macOS 26.6.2 DriverKit/userspace code and the local
26A428 kernelcache, with raw artifacts retained privately:

- `AirshipDK`: `direct_boot::send_image`, boot register write operation,
  and `pci_transport::handle_mem_read32`. The latter passes bank and offset
  directly to `IOPCIDevice::MemoryRead32`; bank 0 was verified live as BAR0.
- `CentauriBooter`: `CentauriFirmware::create`,
  `CentauriTransport::sendImage`, `CentauriPlatform::getPlatformIdentifier`.
- `AppleConvergedFirmwareUpdater`: `RTKitFirmware::setManifest`,
  `ACFUFTABFile::setManifestToTopOnData`, `ACFUFTABFile::setBootNonce`.
- The `t2026-CentauriControl.plist` stage and register definitions.

The public [Apple PCI read API](https://developer.apple.com/documentation/pcidriverkit/iopcidevice/memoryread32-60hg9)
and [Linux PCI driver documentation](https://docs.kernel.org/PCI/pci.html)
describe the host APIs, not the proprietary N1 protocol.

## Next: preboot re-enumeration

The static path explains the live stopping point:

1. `CentauriControl::ExecStageChanged(4)` calls `TriggerReenumeration`.
2. This requests `AppleCentauriManager::DoReenumeration`.
3. `doReenumerationOnWorkloop` waits for driver termination, calls
   `portEnable(false, true, true)`, waits (100 ms in the normal host path),
   then calls `portEnable(true, true, true)`.
4. `portEnable` invokes the `function-pcie_port_control` object:
   `APCIEPortControl::enable(bool)`, then the embedded PCIe port's
   enable/disable machinery. It is not just a Linux bus rescan.

The low-level T6050 port path includes root-port reset, lane/PHY operations
and controller state restoration. A private port-0-only experiment now
cross-builds, but remains untested because target access dropped. The SSD
uses the same fabric: do not substitute
a whole-controller reset or general PCIe reinitialization. N1 power should
not be conflated with the port-control operation.

Before the next live attempt, implement IRQ/DMA/device teardown and
re-enumeration in the host/endpoint drivers, including restoring the N1
port's MSI and RID-to-SID mappings. Establish a fresh recoverable target
session; phone tethering after reboot can require an unplug/replug as
described in `docs/HANDOFF.md`. Then validate the new PCI identity and next
execution stage. Do not assume `1901`/`1902`/`1903` have appeared until
measured. Later work remains: next-stage boot/calibration, running-firmware
IPC, and the Linux WLAN control/data path.

## Second-stage preparation (offline only)

The loader sends the primary signed image again after reopening the boot
channel at stage 1. Before that transfer it expands the primary `2ftb`
component into a separate, zero-filled host allocation. The 592-byte header
describes 34 regions extending to 11,418,624 bytes. The header is preserved;
it is not a second signed firmware image. `n1_fw.py` now validates and
optionally creates this allocation with `--secondary-output /private/path`.
The primary boot candidate remains byte-for-byte unchanged.

| Subsystem | Tag | Offset | Bytes |
| --- | --- | ---: | ---: |
| Control | `mswc` | 3,670,912 | 3,145,728 |
| Wi-Fi | `msww` | 640 | 2,097,152 |
| Bluetooth | `mswb` | 2,097,920 | 1,572,864 |

The zero-filled candidate's SHA-256 is
`7b98e7d7f7fa79b17b52861c9486ba65c1e131852b24170a5103e4d9058a43f9`.
Validation rejects incomplete headers, missing memswap regions, overlap,
duplicate tags, unsupported flags, manifest ranges and allocations over
32 MiB. The ordinary FTAB parser still requires actual payload bytes.

The local driver trace shows `AllocateSecondaryMemory` mapping one 40-bit
DMA segment, then `ConfigureEndpointForMemSwap` writing its low address,
high address and byte length to PCI configuration offsets `0xf88`, `0xf8c`
and `0xf90`. These are PCI configuration offsets, not BAR0 offsets. The
boot-stage image doorbell is BAR0+`0x9070`. This sequence and subsequent
memswap handoff have not been tested under Linux; it must not be described
as successful second-stage boot.

A private `wifi/s6` transfer experiment now cross-builds, with exact image
hashes, N1-only IOMMU checks and a non-launching default. It is not included
here and has not run on the target. A live survey must confirm the new PCI
identity, register state and nonce behavior before trying it.

Only these six reviewed source/documentation paths are excepted from
`.gitignore`. The independent publication guard remains unchanged; adding
them to its exact allowlist requires a separate publication review. No
firmware, logs, binaries, commits or pushes are part of this checkpoint.
