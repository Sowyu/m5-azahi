# M5 Azahi bring-up

Experimental Linux bring-up on **Apple M5 Pro / T6050 / J714s / Mac17,9**.
Independent research project, not an official Asahi Linux release or installer.
Development has used AI assistance; upstream attribution is retained.

```text
🚨 PERSONAL PROJECT / AI-ASSISTED DEVELOPMENT NOTICE 🚨

I acknowledge Asahi Linux's Generative AI (LLM) Policy, which broadly
forbids generative AI tooling for material contributions to Asahi Linux.

This is only my personal, independent, AI-assisted research project.
It is not an official Asahi Linux project, release, or endorsed installer.
Publishing this repository does not make its work eligible for upstream
contribution or imply compliance with Asahi Linux's contribution policy.

If I make enough progress, I may release a separate installer for others
in the future. No public installer is available now, and this experimental
code is not ready for general installation.

🚨 Please do not treat this repository as official Asahi Linux support. 🚨
```

Policy: [Asahi Linux — Generative AI (LLM) Policy](https://asahilinux.org/llm-policy/).

**Not ready for general installation. Do not run these drivers or boot tools on
a daily-use machine. Never use the reference disk geometry on another SSD.**

## Status, 2026-09-25 (hardware state last observed 2026-09-13)

| Component | Evidence so far |
| --- | --- |
| Native Linux / SSD root | Native Fedora KDE from Btrfs SSD root demonstrated. Lid-close sleep can drop the root disk on the installed build: set `HandleLidSwitch=ignore` |
| Autonomous boot | v7 SSD KDE cold boot verified; does not establish reliable USB networking |
| Corrected v6 | RAM boot reached KDE; Recovery installation and exact readback verified |
| CPU | One core; secondary-core startup unresolved. Two ranked hypotheses and a default-off read-only probe exist, untested |
| Graphics | Software rendering; no native GPU acceleration |
| Keyboard | Working, with past compositor-related lag |
| Trackpad | Working on some boots; intermittent early AFE startup failure |
| Display/settings | Full 3024x1964 display and persisted 175% scaling verified on v7 |
| USB tethering | Worked on earlier boots; CURRENTLY FAILED; automatic USB startup temporarily disabled. Likely `-110` reload cause fixed in source (default-off, untested); `-71` unresolved |
| Remote access | Saved SSH/tunnel setup exists; currently unreachable without USB networking |
| Wi-Fi | Not working. Default-off PCIe root-port groundwork (untested) aims only at making the N1 visible; no N1 driver exists. USB Wi-Fi adapter is the documented stopgap |
| Shutdown | Stalls at poweroff.target: no power-off handler (missing `apple,smc-reboot` DT node). v8 candidate builder exists, not installed |

Read [PROGRESS.md](PROGRESS.md) and [the handoff](docs/HANDOFF.md) before continuing.
The 2026-09-25 offline audit, fixes and Wi-Fi PCIe groundwork are summarised in
[docs/audit-2026-09-25](docs/audit-2026-09-25/README.md). None of it is installed.
To use the installed system day to day, follow [daily-driver/](daily-driver/README.md).
Publication is guarded by [default-deny ignores and index/history checks](docs/PUBLICATION-SAFETY.md).

**Current departure state:** KDE is running, but the phone has not exposed a
working network interface. USB automatic startup was deliberately disabled
for a delayed-start experiment and has not been restored. Both automatic and
delayed manual startup have subsequently failed to provide reliable internet.
No more reboot/proxy tests are requested while the user is away. Read the
handoff before changing anything; older successful tests are not a current
working recipe. Live USB-controller reload is unsafe and previously failed.

## Contents

- `daily-driver/`: runbook and settings script for day-to-day use of the
  installed system (no sleep, pinned boot packages, USB adapter networking).
- `input-driver/`: DockChannel interface-power changes and host regression test.
- `nvme-driver/`: ANS/SART experiments, root-write policy and boundary tests.
- `usb-driver/`: USB2 PHY, DWC3 glue, guarded overlay, tethering runner,
  offline tests and RAM-only file courier packaging.
- `standalone-loader/`: custom one-core loader component and bundle validators;
  this is **not** a complete m1n1 checkout.
- `pcie-driver/`: default-off apcie0 port-0 description and driver fork for the
  Apple N1 Wi-Fi functions; untested on hardware.
- `smp/`: secondary-CPU startup diagnosis notes and host guard for the
  default-off loader probe.
- `probe/`, `ramroot/`: selected SSD-root packaging and CPIO tooling.
- `docs/`: current findings, safety constraints, test instructions and publication scope.
- [`research-archive/`](research-archive/README-PUBLIC-ARCHIVE.md): 284 additional
  source/configuration/history snapshots, including earlier CPU probes,
  device trees, Recovery tooling and isolated loader integration changes.

This is a **reviewed source snapshot, not a complete reproducible distribution**.
Private firmware, original device trees, exact kernel build inputs, installed
images, machine identifiers and recovery credentials are intentionally absent.
Public copies replace private disk identities with invalid placeholders;
rootguard kernel compilation is explicitly blocked. Some historical packaging
tests require excluded fixtures and cannot run from a fresh clone.

No compiled drivers, firmware or flashable release is provided. Existing SPDX
and copyright notices apply per file; see [provenance](docs/PROVENANCE.md).

## Host-only tests

From this repository, with Python 3, Bash and a C compiler available (set
`CC=gcc` if `clang` is not installed):

```sh
python3 input-driver/test-power-request.py
bash nvme-driver/test-root-write-policy.sh
python3 usb-driver/test-usb-runner.py
python3 usb-driver/test-usb-glue.py
python3 usb-driver/test-native-startup.py
bash usb-driver/pd-backport/test-spmi4.sh
python3 safety/test-publication.py
python3 safety/test-assert-guards.py
python3 standalone-loader/test-loader-guards.py
python3 standalone-loader/test-notch.py
python3 standalone-loader/test-shutdown.py   # needs dtc/fdtget/fdtput, else skips
python3 pcie-driver/test-pcie-dt.py          # full run needs AZAHI_ADT_JSON
```

`remote-access/test-relay.py` needs the pinned packages in
`remote-access/requirements.txt`; install them in a virtualenv.

These use mocks/temporary host files and do not access target hardware.
Passing tests do not establish hardware safety or functioning tethering.
