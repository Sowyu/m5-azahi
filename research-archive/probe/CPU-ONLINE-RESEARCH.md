# CPU startup source review — 2026-09-06

PRIVATE-USER requested online/repository research and permits private reuse, no commits.
No external posts, issues, messages, uploads or upstream submissions were made.
No downloaded scripts were executed or wholesale patches applied.

## Most relevant primary evidence

- [Asahi m1n1 PR610: initial T6050/T6051 support](https://github.com/AsahiLinux/m1n1/pull/610)
  reports M5 Pro secondary cores powering on without entering m1n1, reproduced
  under26.2b2 and27.0b2. This independently matches our stage0/power1f0 result.
  Review discussion agrees the start offset appears correct and suspects
  firmware. That suspicion is NOT a demonstrated root cause or available fix.
  PR merged July10; the report is not proof no later private fix exists.
- [Asahi m1n1 PR657: secondary-read-only memory](https://github.com/AsahiLinux/m1n1/pull/657)
  identifies S3_0_C11_C1_0/LWR, C1_1/UPR, C1_4/CTL. M4/M4Pro tests improved
  Linux SMP reliability by reserving this range and avoiding WFI/WFIT. This
  fixes a post-entry memory problem, not a demonstrated T6050 reset fix.
  UPR denotes the start of the last protected4KiB page: conservatively include
  that page (end=UPR+4096 for aligned values). The displayed patch rounds UPR
  itself and must not be copied blindly when UPR is page-aligned.
- [Asahi Linux7.2 report](https://asahilinux.org/2026/08/progress-report-7-2/)
  describes M4 state-losing WFI, NVMe changes, and later SMP crash fixes.
  It does not demonstrate all-core T6050 startup. Do not conflate baseM5,
  M5Pro/Max and M4 variants.

## Branch audit

- yuyuyureka/m1n1 find-regs-smp781752e775e1bb530e3989de7abe425d6555bd85:
  adds per-core system-register enumeration after the existing SMP start.
  No new start sequence; not run (broad scans unnecessary/risky here).
- smp-debug60cbe066dc7c82b855bf98e3f916f192983c46e3:
  adds smp_start_secondaries after sep_init, before run_actions. No reset fix.
- switch_boot_cpu76acf6fe3c52458821f58f13bbf68afdf1d0841a:
  switches primary toCPU0 after secondaries are alive; our M5Pro already
  bootsCPU0. Not a release mechanism for unstarted cores.
- main940439b9a407fbfc499bea933269219f3f62d4c7 versus local88a9821:
  no smp.c difference in the inspected comparison; no repository update done.

Branch sources: https://github.com/yuyuyureka/m1n1/branches and commit URLs
under https://github.com/yuyuyureka/m1n1/commit/ with the above full hashes.

## Other projects inspected, not treated as drop-in fixes

- [antiapplefox/m5-linux](https://github.com/antiapplefox/m5-linux) explicitly
  reports static analysis and build-only SPTM scaffolding, no hardware bringup.
  Its XNU/SPTM boot path differs from our working raw EL2 boot; not installed.
- [Project Wallace](https://github.com/damsleth/wallace) reports M4Pro/T6040
  multi-core entry and persistent SD-root desktop, with dated evidence and
  separate stability issues. Useful later for input/storage comparison, not
  demonstrated M5Pro/T6050 CPU release code.
- The OFTC public-log endpoint returned access denied. No bypass attempted;
  no claims are based on unseen IRC logs or third-party summaries of them.

## Our resulting test

On clean third boot, EL2 register reads found LWR10005dec000,
UPR10005df7000, CTL0. The48KiB region is outside the resident loader image,
its diagnostic trace, and the established native Linux memory fence.
It therefore does not overlap the earlier secondary marker/stack tests.

Read-only snapshot was ALL WFI instructions. That suggested, but did not prove,
a firmware park area. A guarded RAM-only SEV/B-loop replacement followed by
V5 boundedCPU1 start and one localIPI yielded noevents and noresetmarkers.
No extra executingCPU, no firmwarecontrolwrites or SSD operations. The patch
must remain until physicalcycle. Operational details in CPU-CHECKPOINT.md.

Next CPU work needs a new, evidence-backed reset/handoff hypothesis; do not
repeat the same starts, treat M4 fixes as M5 fixes, or relax power/debug guards.
If implementing general native memory allocation later, read/validate/reserve
the whole reported protected range dynamically rather than hardcoding this
boot's addresses. Our current high-memory fence already excludes it.
