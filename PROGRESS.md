# Progress — 2026-09-13

This is the public, privacy-reviewed checkpoint. Historical private notes may
contain superseded plans; the state below takes precedence.

## Current boot incident

The known-working **aligned v3** booted native KDE from the SSD without a helper
Mac. The later **USB courier v4** was installed and its bytes read back correctly,
but the packaging was incompatible with the loader. Correct copying did not
mean correct boot behavior.

The loader requires an initrd of exactly **70,698,084 bytes**. Appending the USB
file courier increased v4 to **70,980,667 bytes**. A live proxy check confirmed:

```text
AZAHI_STANDALONE_STOP: bundle bounds/version; no kernel handoff
```

This is a packaging mistake, not a KDE failure or a USB-driver crash. No USB
candidate module had been loaded. The server distributing v4 was stopped.

### Correction and evidence

The **v5-fixed** builder recompresses the original concatenated CPIO bytes with
zstd -19, appends the same courier archive, and zero-pads the initrd to the
loader's exact size. Original CPIO bytes, metadata and ordering are preserved;
loader code, kernel, boot arguments and device tree remain unchanged.

- Original CPIO recompressed size: 67,531,064 bytes.
- Courier frame: 282,583 bytes.
- Final initrd: 70,698,084 bytes.
- Full aligned image: 92,651,520 bytes.
- Four new offline regression tests passed, including compiling the actual
  loader bounds condition: v3/v5 accepted, v4 rejected.

Through the already-running proxy, a guarded **RAM-only** correction verified
the entire old bundle, wrote/read back the corrected initrd in 64 KiB chunks,
published the corrected header last, then called the byte-verified original
loader function. No persistent storage was changed by this test.

Observed markers:

```text
AZAHI_KERNEL_READY
AZAHI_ANS_WARM_READY
AZAHI_STANDALONE_HANDOFF
```

The next-stage kernel/FDT pointers were checked and the handoff sent. **This is
not yet confirmation of a running desktop or successful courier delivery.**
The persistent boot image remains v4. Another reboot may return to proxy until
the fixed image is installed with a fresh validated backup and readback.

## USB candidate

Three exact-kernel modules are built privately for
`7.0.13-400.asahi.fc44.aarch64+16k`:

- eUSB2 host PHY for T6050.
- DWC3 glue with its own compatible, optional reset and forced-host support.
- Runtime DT overlay loader with a read-only power-state preflight.

The target is the **right USB-C socket**, ADT USB instance 2 / port number 3.
The default runner is diagnostic-only. Its live PMGR variant is withheld.
Five power domains must report target and actual ACTIVE; there is no force
bypass. The dry path avoids gated peripheral reads and unloads only its own
diagnostic module. Applied overlays cannot safely be unloaded.

Host validation: 11 artifact/ADT checks, 19 runner mocks and 3 glue/overlay
checks passed in the private workspace. The runner/glue suites are included
and can run without private firmware. Hardware behavior is still unverified.

Outstanding risks: PHY register sequence, DART stream mapping, gated reads,
Type-C role/VBUS sourcing, then actual phone enumeration and network traffic.
No claim of working USB tethering, Internet, or persistent network configuration.

## Earlier milestones and unresolved issues

- Input: board-specific v2 OFF/ON interface-power requests worked under the
  hypervisor and on native boots. Native success logs show `Touch MT ready`.
  Other boots fail AFE attach/boot and time out. Firmware presence was verified;
  replacing it or adding guessed delays is not an established fix.
- Storage: split NVMe/NVMMU mapping and corrected SART exports enabled native
  SSD access. A separate guarded policy restricts writes to the audited Linux
  root range; it does not make experimental DMA/firmware risk disappear.
- KDE: clean per-launch XDG configuration and software-rendering settings
  restored responsiveness and automatic desktop startup. Saved documents remain
  on SSD. Ephemeral configuration is not a RAM-root operating system and is not
  proof that every freeze is a session-restore problem.
- CPU: one core is running. Prior secondary starts did not reach the expected
  entry markers; M4 fixes cannot be assumed to solve this T6050 condition.
- GPU: software rendering only; native acceleration is not implemented here.
- Wi-Fi: host-side metadata identified N1/Centauri control/Alpha/Beta endpoints
  and ACIPC tables. No native scan/association or packet path exists yet.
- Shutdown: reaching poweroff.target with the screen still on was observed.
  That message alone does not prove every filesystem was safely unmounted.

## Next verification

On the target Linux terminal, **without another reboot**:

```sh
ls /run/azahi-usb-20260913
```

If present, list detailed file sizes and then validate the local manifest before
considering a diagnostic-only USB preflight. First obtain the actual result;
do not infer successful delivery from host build tests or handoff markers.
