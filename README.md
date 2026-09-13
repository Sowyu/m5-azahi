# M5 Azahi bring-up

Experimental Linux bring-up on **Apple M5 Pro / T6050 / J714s / Mac17,9**.
Independent research project, not an official Asahi Linux release or installer.
Development has used AI assistance; upstream attribution is retained.

**Not ready for general installation. Do not run these drivers or boot tools on
a daily-use machine. Never use the reference disk geometry on another SSD.**

## Status — 2026-09-13

| Component | Evidence so far |
| --- | --- |
| Native Linux / SSD root | Native Fedora KDE from Btrfs SSD root demonstrated |
| Autonomous boot | Aligned v3 worked; currently installed v4 has a known packaging regression |
| Corrected v5 | Offline verified; RAM handoff sent; user reports KDE accessible but courier directory missing |
| CPU | One core; secondary-core startup unresolved |
| Graphics | Software rendering; no native GPU acceleration |
| Keyboard | Working, with past compositor-related lag |
| Trackpad | Working on some boots; intermittent early AFE startup failure |
| USB tethering | Right-port USB2 candidate built and offline tested; no live enumeration/network proof |
| Wi-Fi | N1/Centauri investigation only; no working Linux driver here |
| Shutdown | Can stall at poweroff.target; final power-off unresolved |

Read [PROGRESS.md](PROGRESS.md) and [the handoff](docs/HANDOFF.md) before continuing.

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
