# Resume safely

## Immediate state

LATEST: user reports four checksum OK results, cwd is the courier directory.
Next explicit diagnostic-only command (trim output, retain full script log):

```sh
bash usb-tether-test.sh dry 2>&1 | tail -n 20
```

This loads/unloads only the dry diagnostic module and applies no overlay.
Inspect actual output; pipeline completion alone does not establish success.
Do not proceed to `minimal` without evaluating the PMGR result and outstanding
PHY/DART/VBUS audit risks. Dry result is not yet available.

LATEST PHOTO: KDE Konsole shows all five courier files at the correct path.
Delivery succeeded. Next target command (one line):

```sh
cd /run/azahi-usb-20260913 && sha256sum -c SHA256SUMS
```

Wait for four OK checks before considering diagnostic-only preflight. No USB
module load or network success yet. Do not reboot; persistent v4 is unchanged.

NEWEST: the user restarted into proxy, fresh session identity/RAM layout was
verified, and the guarded v6 RAM handoff completed successfully. All old payload
bytes were checked and all replacement bytes read back. Native desktop/courier
confirmation is pending; ask for `ls /run/azahi-usb-20260913` from KDE Konsole.
Proxy access was consumed by handoff. No native network transport is established.
Persistent v4 remains installed; permanent correction is still a separate task.

LATEST: courier v2/v6 built and tested in a no-disk/no-network ARM64 VM with
the actual initrd executables. Old failure reproduced; new courier and five
image checks pass. Target still running KDE from prior RAM boot, no new image
installed. `/run/initramfs` only held `log`, not the courier assets.
Next controlled shutdown/restart should reach existing v4 fallback proxy.
Read fresh identity/base/bootargs, verify old bundle and memory bounds before
any v6 RAM write. Permanent v4 replacement is still outstanding.

NEWEST PHOTO: `initrd-switch-root` journal reports the courier stopped at line11
because `mktemp` is absent. The hook did run. Fix/test the courier's early-boot
tool dependencies before building another candidate. Do not ask the user to
repeat the same log command; no new image or permanent fix has yet been installed.

LATEST: user reports KDE accessible but the courier directory cannot be
accessed from Konsole. Konsole is a valid target terminal. Host image inspection
finds the courier hook and assets present; inspect the current boot journal:

```sh
journalctl -b -u initrd-switch-root --no-pager -n 15
```

Do not treat the older listing request below as a successful result or ask for
a reboot merely to get a text terminal. The actual service output is pending.

A RAM-corrected v5 Linux handoff was sent. The target's current screen and the
presence of `/run/azahi-usb-20260913` are awaiting confirmation. Persistent v4
still fails the loader's initrd-size check. Do not ask for a casual reboot.
No native networking or SSH is established; host commands do not execute on
the target after the USB proxy is consumed by handoff.

Ask for this short target command, one line at a time:

```sh
ls /run/azahi-usb-20260913
```

Expected entries are `SHA256SUMS`, `usb-tether-test.sh`,
`phy-apple-t6050-usb2.ko`, `dwc3-apple-t6050.ko`, and
`azahi-usb-overlay.ko`. If available:

```sh
ls -lh /run/azahi-usb-20260913
```

Do not treat missing files as a reason to repartition or format anything.

## Hard boundaries

- The daily-driving macOS partition is out of bounds: no writes, repair,
  resizing, formatting, boot-policy changes or staging there.
- Public disk identifiers are intentionally invalid. Do not guess replacements
  or enable the historical root-write bounds on another disk.
- No automatic module loading, boot-image installation or firmware replacement.
  Recovery work needs exact target identification, a validated fresh backup,
  appropriate user authentication and verified readback.
- Do not restart the obsolete v4 delivery server or retry its installer.
- Do not unbind/unload DockChannel HID: its remove path contains `BUG_ON(1)`.
- Do not use random MMIO writes, NVMe reset/init, broad register scans or
  speculative power-control changes. Do not relax guards to make a test pass.
- When the user is absent, limit work to safe host-side development and offline
  tests. Persistence does not authorize autonomous power cycles or new risks.
- Webcam previously helped read the target screen, but the latest preference
  was **no webcam**. Use supplied photos; obtain renewed permission for capture.
  Never upload captures or images of the user.
- Prefer short commands and audio prompts when user interaction is needed.
  Never claim an audible prompt was heard merely because playback succeeded.

## Order of work

1. Confirm native boot and RAM courier delivery; verify file hashes.
2. Review/run diagnostic-only USB preflight on the verified private candidate.
3. Resolve hardware audit concerns before a live minimal host overlay test.
4. If the phone enumerates, prove an interface under the right USB controller,
   DHCP and interface-bound certificate-validated HTTPS. A root hub is not enough.
5. Separately replace the bad persistent boot bundle through the guarded private
   workflow. v3 is the known-working fallback; no corrected persistent install
   has yet been verified.
6. Wi-Fi, secondary CPUs and native GPU remain distinct research tasks.

## Public/private split

This repository is for reviewed source and progress, not target-specific
operational secrets. The full private workspace retains recovery receipts,
firmware and boot artifacts. Do not seek or publish the private identifiers in
order to make this reference snapshot immediately executable.
