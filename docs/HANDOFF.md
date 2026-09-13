# Resume safely

## Latest: live test timed out before phone networking

The next user photo shows the runner's failure: no unique right-port USB
network interface. Kernel messages at about 590.5 seconds show PHY host init
completion, xHCI USB2/USB3 root hubs (Linux IDs 1d6b:0002 and 1d6b:0003),
one port on each, and "host mode up (state 2)". These are controller root hubs,
not the phone. No child-device attach or descriptor error appears in the
displayed tail. The shell prompt returned; no kernel hang is shown.

The user previously reported no phone charging and grey tethering. Whether
the requested reconnect was performed is not separately confirmed. VBUS /
Type-C role handling remains a hypothesis, not an electrical measurement;
cable and PHY issues remain possible. No networking, DHCP or HTTPS success.
Do not rerun or unload the applied overlay. Persistent boot remains bad v4;
this session used the v6 RAM correction. No reboot requested.

Next: preserve the checked courier directory from /run to a fresh directory
under /root on the already verified Linux SSD root, then verify its manifest.
Do not overwrite an existing destination or touch daily macOS. Copy outcome
is pending. Subsequent engineering should audit the missing SN201202x SPMI
transport/PD integration, especially actual target IRQ mapping; upstream probe
issues a wake command and is not a read-only diagnostic.

## Immediate state

LATEST LIVE PHOTO: the runner reached the right-controller root hub
`/sys/devices/platform/soc/382280000.usb/xhci-hcd.0.auto/usb1` after loading
dependencies and all three candidate modules. User says phone is not charging
and tethering remains grey. No phone/interface/Internet proof yet. Photo shows
the script still waiting; final exit result pending.

Do NOT rerun or unload. Allow its bounded wait to finish, unplug/replug the
phone once, then request `dmesg | tail -n 30`. VBUS/role negotiation is suspected,
not confirmed. A powered hub or PD changes must not be assumed to solve it.
Remember the files remain under /run: preserve a verified copy on the guarded
Linux root before a future reboot if needed, never on the macOS partition.

LATEST: phone connected, tethering grey (controller not enabled yet). First
attended `minimal` test is being requested after save-work/hang warning:

```sh
sync && bash usb-tether-test.sh minimal
```

User should enable tethering as soon as available during the script's wait.
Allow up to about three minutes for host/interface/DHCP/HTTPS stages. Request
the output if it fails or stays grey; do not rerun/unload manually. This is an
explicit experimental hardware test under the user's ongoing USB bring-up
authorization, not proof that remaining physical SID/PHY/VBUS risks are solved.
No result has yet been received. Persistent v4 remains unchanged.

LATEST PHOTO: dry preflight PASSED, all five PMGR target/actual states ACTIVE;
diagnostic unloaded, no overlay applied. User is being asked to disconnect
the inter-Mac USB cable and connect an unlocked phone to the target's RIGHT
USB-C socket. No live/minimal command issued yet. Allow the phone tethering
toggle to remain grey until enumeration; do not interpret it alone as failure.

Exact-kernel source supports combining SID bits per DART (so the four overlay
references do not consume four DART slots), but physical SID routing, PHY
clear-mask behaviour and PD/VBUS remain experimental. Do not equate dry success
with full hardware validation. Save user work before a later live test, warn of
possible hang/power-cycle, and do not auto-retry/unload an applied overlay.

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
