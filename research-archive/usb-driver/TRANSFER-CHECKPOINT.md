# Sep13 USB transfer — v4 BOOT FAILED; RAM correction test in progress

LATEST RAM TEST: session80482 completed successfully with native HANDOFF SENT.
Receipts `logs/usb-fixed-ram-small-20260913.JImYNa/{events.log,prepared.json}`.
Initial4MiB-read attempt(session93175,logs/usb-fixed-ram-20260913.09cFOx) failed
read-only with short transfer3952903/4194304; no RAM writes on that attempt.
Resynced proxy,10 successive64KiB reads matched. Changed chunk size64KiB;
then the entire91819821-byte v4 payload/header matched SHA before mutation.
All70698084 bytes of corrected initrd were written/readback-compared in RAM,
corrected44-byte header published last. Original byte-verified standalone
function returned0; next_stage kernel10800000000/FDT10900000000 verified.
Proxy exit sent. Observed loader logs: AZAHI_KERNEL_READY, one-core startup
skip, warm ANS verified/prepared, AZAHI_STANDALONE_HANDOFF. No extra CPU started.
No SSD/Preboot writes in this test, no live USB candidate loads. Proxy channel
is consumed; native Linux/KDE screen and /run courier still need USER evidence.
NEXT user command once Konsole appears: `ls /run/azahi-usb-20260913`.
Do NOT reboot: persistent selected boot object remains nonbootable v4. Need
fresh reviewed Recovery enrollment of fixed v5 after successful RAM evidence.

CRITICAL NEWEST: v4 enrollment/readback was correct, BUT it cannot autoboot.
User observed Running proxy. Live read-only proxy diagnostic CONFIRMED
`AZAHI_STANDALONE_STOP: bundle bounds/version; no kernel handoff`.
Root cause is our packaging mistake: unchanged private loader hard-codes
INITRD_BYTES=70698084, but v4 header says70980667. Previous packaging tests
missed the actual C loader's acceptance check. This is not KDE or USB-driver
failure: no kernel handoff occurred. Assistant acknowledged responsibility.

Live session readback: base0x100049c4000, bootargs0x1000a960000 revision3,
physbase0x10003af8000, top0x1000a970000, modelMac17,9/J714s, chip6050,
loader prefix and exact v4 bundle header match; no secondaries alive.
Ports reconnected: /dev/cu.usbmodemPRIVATE-SERIAL-REMOVED (control), ...23.
No webcam capture. Do NOT run old boot/chainload scripts with stale base pins.

Bad-v4 enrollment server PID40977/session70147 was stopped intentionally,
so it cannot offer the known-nonbootable image again. Archives/receipts and
working aligned-v3 rollback remain intact. Old download URLs currently down.
No second persistent install yet. Installed Linux boot object remains bad v4.

Correction v5: `../standalone-ssdroot-usb-files-v5-fixed-20260913.bin`,
SHA2562af8a24f94756f38ef7dfe6056c4e6c43d9df4ede993ddcc718932160dc26b75,
92651520B. Loader/kernel/args/DT unchanged. Recompress byte-identical original
cpio with zstd19 (67531064B), append identical courier layer282583B, then zero
pad initrd to EXACT70698084B. Kernel initramfs format allows zero padding.
Every original cpio header/data/order/ownership byte preserved after decoding.
zstd10 was insufficient and safely emitted no image. v3/v4 artifacts preserved.
New builder build-transfer-fixed.py; test-transfer-fixed.py4 checks pass,
including compiled actual-loader size condition: v3/v5 accepted, v4 rejected.

RAM-only recovery/test script proxy-test-fixed.py live session93175, destination
logs/usb-fixed-ram-20260913.09cFOx. No heap initialization/code injection/RVBAR
writes. Rechecks exact observed session, model/ADT/bounds, zero next_stage,
function bytes, all old payload SHA. Writes/readbacks only original initrd
region, then publishes the44-byte corrected bundle header, flushes data cache,
calls byte-verified original azahi_standalone_run at base+0x7454. Only if return0
and expected next_stage kernel/FDT pointers does it exit proxy to native Linux.
No persistent boot-object writes. Handoff/boot result PENDING. Do not assume
disk persistence even if RAM boot succeeds; future Recovery update required.


LATEST: user ran `/tmp/usbi.sh install`; fresh HOST install readback verified.
Installed raw SHA is transfer v4
0ca32c0df14ce714d32029ede06a428722616da0711fc5d0b85a98f1a77d77d0,
92946432B/raw entry2048. New reported coih:
E80103BF9B8BC978CF87D9AF581F3F244F240B8518F611A42D597C88A9BD8E8F0872CCCFE0F6DE50001E45D429FAA854.
Wrapped SHA f1d21a8c8e62c6e164433281aadc4d4d2dce48f9007141a638d792222f84b9dd.
Archive install-after.tar.gz SHA
71e93f6524262873e23c81a1e1ae2aca45fa019f5f9ef78063831812bab37f20,
cksum3305225068 91565941. Receipt VALIDATED install, final Preboot RO;
policy/security fields other than allowed coih/lpnh match baseline.
Only Linux boot object enrollment changed; kernel/loader/DT/args/KDE unchanged.
No native USB load or network success. Cold boot and /run courier still untested.

Next: Recovery `shutdown -h now`, disconnect inter-Mac data cable once off
(keep charger), hold Power for startup options, select Linux (not Options).
User to report KDE/terminal or exact error. Do not auto-load USB candidate on
arrival. Server session70147 remains available for rollback if needed, using
enabled helper `rollback` mode ONLY after reviewing failure. Do not rerun
snapshot or install: both correctly expect selected old-v3 coih and will stop
now that v4 is selected. Old-v3 rollback object preserved/verified on install.


Latest user issue: `/tmp/usb-install.sh: No such file or directory`. Installer
download/execution on target not confirmed. HOST re-fetch verified enabled
helper still available with cksum1939652285 8498 and expected SHA; receipt
directory contains only snapshot, no install readback. Asked to repeat ONLY
download+cksum, this time saving `/tmp/usbi.sh` to reduce manual path errors.
Do not assume install ran; wait for checksum/error before giving its run step.

LATEST: fresh snapshot received and HOST-VERIFIED after user mounted verified
Linux Preboot disk3s4 read-only. Archive `snapshot-after.tar.gz` in live receipt
directory, SHA25619ea80cfb539b58b22dd042aa7bc2c6e75aca19fec5061e4b63de763be603e0d,
cksum853701282 91283401. Raw boot SHA matches aligned v3
397a0e4125087c63b83c09b35cd44fe6bc35508d7d54613bd9a2bf4d9aff46fc;
reported coih remains B422…F1ED. Selected wrapped SHA
d354a1938aa53c7495a8fc87ad37e17a4587963d8fdd3913be5c87365c4a58b1.
No install readback yet. Server's fresh-backup gate is now unlocked.

Enabled helper at `PRIVATE-LAN-ENDPOINT-REMOVED` fetched/syntax-checked
on HOST, verified identical to prior helper except ENABLE_INSTALL=no→yes:
cksum **1939652285 8498**, SHA256
a9c13c7f370bbbe4266982db8b0868a40d28e160a13bc3cb95232baf688871e1.
Next user instruction: download to /tmp/usb-install.sh, check that checksum,
ONLY if it matches run `bash /tmp/usb-install.sh install`, type INSTALL and
owner credentials locally if prompted. Leave Recovery open for host readback
verification. No automatic reboot; stop on any error. Installation pending.

Latest Recovery state: user confirms downloaded `/tmp/usb.sh` checksum matches
1550562757 8497, then ran snapshot. It stopped at `Linux Preboot unmounted or
unexpected mount (disk3s4)`. In this helper that check occurs AFTER verifying
the Linux System/VG/container and disk3s4's Preboot UUID/container, before any
backup upload or enrollment. Next permitted action is `diskutil mount readOnly
disk3s4 && bash /tmp/usb.sh snapshot`. Read-only mount of the verified Linux
Preboot only; no daily macOS mount, no RW fallback. Snapshot/host validation
still pending; installer remains gated. Earlier shutdown/Recovery-entry
pending notes below are historical: user is now executing in Recovery.

Latest attended state: user ran requested shutdown and supplied photo after
reporting a hang. Photo shows tmp.mount unmounted, swaps deactivated,
umount.target/shutdown.target/final.target reached, systemd-poweroff.service
finished, then poweroff.target reached, with display still on. This confirms
the observed late shutdown stall, NOT clean root unmount or completed hardware
poweroff. Prior instruction was `sync && systemctl poweroff`; actual sync
completion was not independently observed. Next conditional instruction: if
unchanged for at least one minute, hold Power until off, release/wait, then
hold for startup Options and enter Linux-paired Recovery. Explain residual
forced-poweroff risk. Force-off/Recovery entry not yet confirmed; no v4 install.

User explicitly agreed to an attended Linux-paired Recovery session after
the FAT staging inventory showed no detected FAT. We prepared the bundle
before requesting shutdown. Current target remains last-seen SSD KDE; no
target writes, mounts, reboot, webcam or live module load performed by agent.

## Candidate and fallback

New `../standalone-ssdroot-usb-files-v4-20260913.bin`:

- bytes 92946432, divisible by 16384; raw entry 2048
- SHA256 `0ca32c0df14ce714d32029ede06a428722616da0711fc5d0b85a98f1a77d77d0`
- POSIX cksum `3362342895 92946432`
- same loader, args, DT, kernel and original initrd bytes as working aligned v3
- only appended compressed cpio files, bundle header lengths/CRCs and padding
  differ. Independent cpio layers are supported by the [kernel format](https://www.kernel.org/doc/html/latest/driver-api/early-userspace/buffer-format.html).
- canonical builder `build-transfer.py`; refuses overwriting outputs; receipt
  next to .bin. `inspect` verifies baseline, exact asset allowlist, no old file
  replacement (only identical-mode parent dirs may overlap), CRCs, padding,
  unchanged components and candidate contents; no repacking old metadata.
- courier `boot-stage.sh`, optional/failure-ignored ExecStartPre drop-in for
  initrd-switch-root.service; no reset of existing ExecStartPre list. Copies
  exactly 5 bundle files to tmpfs `/run/azahi-usb-20260913`, verifying hashes
  before publishing. No SSD writes, driver loads, mounts or KDE config changes.
  Failure leaves temporary RAM directory for diagnosis, boot continues.
- [systemd switch-root code](https://github.com/systemd/systemd/blob/v259/src/shared/switch-root.c)
  transfers /run. File survival on this candidate still needs target evidence.

Rollback is **working autonomous SSD KDE**, NOT V5 proxy:
`../standalone-ssdroot-v3-aligned-20260912.bin`, 92651520 bytes,
SHA256 `397a0e4125087c63b83c09b35cd44fe6bc35508d7d54613bd9a2bf4d9aff46fc`,
cksum `750659463 92651520`. Original file left unchanged.
Saved selected wrapper cksum `1901600601 92654445`;
coih `B422A78B3E396F05C3C08A7AD9ADD7D406EBF641225BAEACCA3D95F5AF24F3FEE89D3A7A87D0B614BF2EAD97C9C5F1ED`.
Validated historical backup chain through original V5 backup, restored V5
receipt, and aligned-v3 installed readback. This does NOT replace a fresh backup.

## Serving / fresh backup gate

Server `transfer-server.py` running in exec session **70147**, bound specifically
to verified host LAN `PRIVATE-LAN-ENDPOINT-REMOVED` (not all interfaces).
Receipts `/PRIVATE-USER/azahi-port/logs/usb-transfer-20260913.edMEZd/`.
Server has immutable copies of both verified images. No uploader code/archive
extraction; exact members, size bounds, duplicate rejection, raw IMG4 layout
and SHA256 validation. Does not validate Apple signatures or derive coih.

Only `PRIVATE-LAN-ENDPOINT-REMOVED` currently available. Its snapshot mode
is read-only and installer enable flag is `no`. Current served helper:
SHA256 `de6839ff302685eb9444b58e3b8b329a81dedfc85b1eeddfa3755e90defb82e2`,
cksum `1550562757 8497`. URL token changes on restart; recheck helper hash then.
Host loopback-via-LAN fetch syntax checked; `/usb-install.sh`, `/candidate.bin`,
`/rollback.bin`, and traversal probe all returned404 before fresh backup.

Recovery helper template `recovery-transfer.sh`: exact Linux System/VG/Preboot/
container UUIDs, 96GB container size/free-space, selected coih, firmware and
paired-Recovery/security pins. No mount in snapshot mode. Requires Linux
System mounted at /Volumes/Linux, Linux Preboot mounted RO. If not, STOP and
resolve exact verified device IDs; don't guess names or mount daily macOS.
Copies only current selected boot wrapper into Recovery /tmp, compares before/
copy/after checksums, uploads for host SHA/layout validation. No openssl need.

After validated fresh snapshot only, server exposes `usb-install.sh` and
images. Install/rollback require typed INSTALL/RESTORE locally, recheck all
pins, remount only verified Linux Preboot, run kmutil targeting /Volumes/Linux,
copy/readback, unmount/remountRO, upload for host raw SHA256 check. Never
auto-reboot, auto-retry or auto-rollback. Owner credentials remain local.
Changed policy/unknown bytes stops; report exact message instead of bypassing.
Old Sep11/Sep12 enrollment helpers must not be run for this update.

`standalone-loader/install-server.py` validator was minimally extended with
snapshot and optional rollback SHA/size; original default V5 behavior retained.
Tests: `test-transfer.py` **16 passed**, including ten real Recovery-shell
mock scenarios and four courier fixtures; existing `test-aligned-install.py`
**12 passed**. Earlier USB artifact/runner/glue33 tests remain separate from
these transfer tests. No hardware/boot test or tethering success claimed.

## Next attended action

Ask user to save work, `sync && systemctl poweroff`, then enter Options/Recovery
when actually off, select/unlock Linux if asked, join same Wi-Fi, Utilities →
Terminal. If shutdown hangs (known issue), ask for current screen rather than
assert clean unmount or blindly force-cut power. No credentials in chat.

Once Recovery Terminal confirmed, fetch **snapshot** helper first, verify
its cksum above before execution, run snapshot; read actual host receipt.
Do not provide the install step until fresh snapshot validated. Mount/policy
checks might require further attended correction; one short command at a time.
After future successful v4 boot, confirm files survived under /run before
copying them to the guarded Linux root or executing even dry module testing.
Remaining USB MMIO/DMA/PHY/PD risks in README still apply; transfer is not
authorization to skip those reviews or immediately load live modules.
