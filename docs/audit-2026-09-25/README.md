# Offline audit and Wi-Fi groundwork, 2026-09-25

No hardware was available for any of this. Everything is source review,
host tests, cross-compilation against the exact kernel, and static reading of
the public macOS 27.0 (26A428) restore image, which is the same OS build the
target runs. Nothing was installed on the Mac. Every hardware-facing change
is default-off or needs a newly built image, and each report gives an
attended test with rollback.

| Report | Scope |
| --- | --- |
| [kernel.md](kernel.md) | USB PHY, DWC3 glue, overlay, SPMI4/HPM, DockChannel HID, ANS NVMe, SART |
| [tooling-loader.md](tooling-loader.md) | remote access, publication guard, USB/loader tooling, loader C, archived DTs, shutdown |
| [pcie.md](pcie.md) | apcie0 root port, DART and DT for the Apple N1 Wi-Fi functions |

Every finding in the PR #1 audit (`docs/audit/` on that branch) got a
verdict: fixed, confirmed but left open with a reason, or rejected with the
reason. Some PR #1 "fix first" items were wrong: the initrd cache-clean
claim, the rootguard LBA claim and the proposed ACK-mutex fix (which would
deadlock).

## Changes that matter most

1. USB `-110` live-reload failure: the PHY did all hardware init in
   `power_on`, after the DWC3 core soft reset, so any second DWC3 probe reset
   the core without a PHY clock. New `reinit_after_shutdown` parameter,
   default 0, fixes the ordering. Untested on hardware.
2. USB `-71` at SET_CONFIGURATION: no code fix. Ranked hypotheses with safe
   tests are in kernel.md; the first is read-only (USB2 LPM state).
3. NVMe: system sleep on the J714S read-only build stopped the ANS CPU and
   resume would remove the root disk. Sleep is now refused. The installed
   private rootguard build still has the problem until rebuilt; until then
   set `HandleLidSwitch=ignore` on the target.
4. Shutdown hang: there is no power-off handler because the SMC DT node has
   no `apple,smc-reboot` child. `standalone-loader/build-shutdown.py` builds
   a v8 candidate from the pinned v7 image that adds only that node.
5. PCIe for Wi-Fi: `pcie-driver/` plus `azahi_pcie.c` in the loader describe
   and bring up apcie0 port 0. The target of the first session is that Linux
   enumerates the root port, then (with endpoint power) 106b:1901/1902/1903.
   Nodes ship disabled and are enabled only after the loader bring-up
   succeeds.
6. Security and tooling: relay bootstrap expiry and lockout now survive a
   restart, the installer pins the script and unit it installs, 11 builders
   refuse to run under `python -O`, and the publication guard covers more
   secret formats.

## Wi-Fi status, plainly

Native N1 Wi-Fi does not work and is not close. This pass covers the PCIe
path only, which can at best make the chip visible to Linux. There is still
no Linux driver for the N1 functions, and no work on one was done here.
The fastest route to working Wi-Fi on this machine is a USB Wi-Fi adapter on
the existing USB2 port; see [../USB-NETWORK-ADAPTERS.md](../USB-NETWORK-ADAPTERS.md).

## Verification run on 2026-09-25

With `CC=gcc` on an x86_64 Linux host:

| Test | Result |
| --- | --- |
| input-driver/test-power-request.py | 3 groups pass |
| nvme-driver/test-root-write-policy.sh | 525366 checks pass |
| usb-driver/test-usb-glue.py | 5 pass |
| usb-driver/test-usb-runner.py | 19 pass |
| usb-driver/test-native-startup.py | 9 pass |
| usb-driver/pd-backport/test-spmi4.sh | pass |
| remote-access/test-relay.py (pinned deps in a venv) | 7 pass |
| safety/test-publication.py | 14 pass |
| safety/test-assert-guards.py | 2 pass |
| standalone-loader/test-loader-guards.py | 3 pass |
| standalone-loader/test-shutdown.py (needs dtc tools) | 2 pass |
| standalone-loader/test-notch.py | pass |
| pcie-driver/test-pcie-dt.py (with the ADT JSON) | 16 pass |

Every kernel module in the repo builds with zero warnings at `W=1` against
`kernel-7.0.13-400.asahi` configured from `research-archive/kconfig.txt`
(recipe in [../BUILD-AND-TEST.md](../BUILD-AND-TEST.md)). The loader C
fragments compile with `-Wall -Wextra -Werror` against upstream m1n1 headers.

Tests that need private fixtures (real ADT dump, v3 to v6 images, m1n1
Python library, macOS clang) were not run.

## Owner actions

- Delete the three pre-rewrite PR branches (PRs 2, 3 and 4). They still
  publish the old flattened private path in a patch header, and GitHub also
  keeps `refs/pull/N/head`.
- Rebuilt modules and loaders get new hashes. Regenerate the install bundle
  pins before any attended test.
