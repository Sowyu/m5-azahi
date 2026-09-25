# T6050 secondary-CPU startup

Linux on this M5 Pro runs on CPU0 only. All 17 other cores stay offline. This
directory holds the offline diagnosis and a default-off loader diagnostic that
one attended boot can use to tell the two live hypotheses apart.

Full write-up: [../docs/audit-2026-09-25/smp.md](../docs/audit-2026-09-25/smp.md).

## What is here

- The loader diagnostic itself lives with the loader, not here:
  `standalone-loader/m1n1-20260911/src/azahi_smp.c` and `.h`. It is default-off:
  no `azahi.smp=` cmdline token means it does nothing.
- `test-smp-diag.py`: host guards. Compiles the token parser out of the C and
  checks it is word-bounded and default-off, and statically checks that probe
  mode writes no hardware. No target access.

## The short version

The stock m1n1 CPU-start path brings up every secondary on M1 through M4. On
T6050 the same code leaves the secondaries powered but not executing: PMGR
shows the core active (PS_ACTUAL 0x100 to 0x1f0) but the core never runs loader
code. This is the state the upstream initial T6050 support already reported
(AsahiLinux/m1n1 PR #610) and the repo's own V1..V5 checkpoints recorded.

The M4 Pro success does not carry over. The M4 project (damsleth/wallace) starts
all 14 secondaries with the same bare PMGR write, so SPTM being present is not
by itself the blocker. Something specific to the T6050 reset path is.

## Run the host test

```sh
python3 smp/test-smp-diag.py
```

Needs a host C compiler (`cc`) and Python 3. It does not touch hardware and
proves nothing about the target; it only stops the diagnostic from silently
losing its default-off gate or growing a write in probe mode.
