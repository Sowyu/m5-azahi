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

## Status — 2026-09-13

| Component | Evidence so far |
| --- | --- |
| Native Linux / SSD root | Native Fedora KDE from Btrfs SSD root demonstrated |
| Autonomous boot | Aligned v3 worked; corrected v6 is now installed; new cold-boot test pending |
| Corrected v6 | RAM boot reached KDE; Recovery installation and exact readback verified |
| CPU | One core; secondary-core startup unresolved |
| Graphics | Software rendering; no native GPU acceleration |
| Keyboard | Working, with past compositor-related lag |
| Trackpad | Working on some boots; intermittent early AFE startup failure |
| USB tethering | Native DHCP, DNS and certificate-validated HTTPS verified; automatic cold-boot startup pending |
| Remote access | Key-authenticated SSH verified; persistent services installed and live-tested |
| Wi-Fi | N1/Centauri investigation only; no working Linux driver here |
| Shutdown | Can stall at poweroff.target; final power-off unresolved |

Read [PROGRESS.md](PROGRESS.md) and [the handoff](docs/HANDOFF.md) before continuing.
Publication is guarded by [default-deny ignores and index/history checks](docs/PUBLICATION-SAFETY.md).

## Contents

- `input-driver/`: DockChannel interface-power changes and host regression test.
- `nvme-driver/`: ANS/SART experiments, root-write policy and boundary tests.
- `usb-driver/`: USB2 PHY, DWC3 glue, guarded overlay, tethering runner,
  offline tests and RAM-only file courier packaging.
- `standalone-loader/`: custom one-core loader component and bundle validators;
  this is **not** a complete m1n1 checkout.
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

From this repository, with Python 3, Bash and a C compiler available:

```sh
python3 input-driver/test-power-request.py
bash nvme-driver/test-root-write-policy.sh
python3 usb-driver/test-usb-runner.py
python3 usb-driver/test-usb-glue.py
```

These use mocks/temporary host files and do not access target hardware.
Passing tests do not establish hardware safety or functioning tethering.
