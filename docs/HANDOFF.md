# Resume safely

## Immediate state

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
