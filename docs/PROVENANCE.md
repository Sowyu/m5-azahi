# Source provenance and licensing

This is an independent, AI-assisted experimental project. It does not claim
upstream endorsement or general M5 hardware support.

- Input DockChannel, ANS NVMe, SART, DWC3 glue and DWC3 private headers derive
  from Linux/Asahi sources. Original copyright and SPDX notices are retained.
  NVMe/SART unmodified reference files and original DWC3 glue are under `vendor/`.
- The driver experiments were built against the privately retained Fedora
  Asahi `7.0.13-400.asahi.fc44.aarch64+16k` inputs; source provenance in the
  private build notes records Linux 7.0.13. Exact packages are not distributed.
- The custom standalone component was developed in an isolated m1n1 tree
  based on commit `88a98213d55f2cbd69844762c3171b39c0cd0bf9`. Its SPDX tag is MIT;
  the tree's MIT license is retained alongside the component. The upstream
  checkout and its policies are not replaced or republished here.
- The T6050 PHY source records its derivation from analysis of Apple's
  `AppleT6050TypeCPhy` behavior and ADT tunables. No Apple kernelcache, firmware,
  disassembly dump or extracted proprietary driver is distributed.
- Protocol/build findings are experimental, not a clean-room provenance claim
  or a guarantee of correctness. Preserve these qualifications when reusing them.

Existing licenses apply **per file**. GPL-2.0 text is included under `LICENSES/`.
There is no new blanket license grant over previously unlicensed scripts or
documentation in this initial source publication. Obtain clarification before
assuming those files have the same license as the kernel-derived sources.
