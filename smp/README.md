# T6050 secondary-CPU startup

All-core startup remains unresolved. The last hardware result is CPU0 online,
with the other 17 cores powered on by experiments but never observed entering
the loader. Everything below was prepared offline. Nothing is installed.

## Prepared changes

`t6050-start-guards.patch` applies to the archived standalone loader baseline
and can be reviewed for the complete private loader tree. It keeps
`AZAHI_ONE_CORE` and fixes these startup faults:

- T6050 CPU_START and CPU_STOP masks use six cores per cluster. CPU6 uses bit
  6, CPU12 uses bit 12, and CPU17 uses bit 17. Other chips retain their existing
  mapping. The ADT `function-enable_core` arguments confirm all 18 masks.
- A locked reset vector that differs from the loader entry now returns before
  allocating a stack or writing registers. The old code printed a failure but
  continued the start attempt. T6050 compares address bits 41:11, matching
  iBoot's writer. The old mask missed a differing bit 11.
- A T6050 start timeout keeps `target_cpu` and both reset stacks intact and
  parks the boot CPU permanently. A late arrival cannot resume startup or
  Linux handoff. This path deliberately avoids `panic()`, which reboots.
- Invalid die/core combinations and a failed stack allocation return before
  CPU-start writes. J714s accepts only die 0 and the matching linear CPU ID.

These changes do not explain CPU1's failure. Corrected-mask starts for CPU6
and CPU12 also failed in the historical experiments. This is prerequisite
work, not a demonstrated SMP fix.

The patch also adds `azahi_smp.o` to the private build. Copy the current
`azahi_smp.c`, `azahi_smp.h`, and `azahi_standalone.c` from
`standalone-loader/m1n1-20260911/src/` when integrating it. The public tree is
incomplete and cannot produce a working image by itself.

## Read-only diagnostic

`azahi.smp=probe` now runs from the standalone entry before DT preparation.
No token means no action. It validates J714s board identity, the PMGR range,
and each of the 18 die-0 CPU addresses before reading their reset registers.
Other dies are skipped. Malformed and duplicate tokens are refused.

`azahi.smp=start` is now refused, with no CPU-start writes. The previous mode
called a loop that resets the shared stack pointer and advances `target_cpu`
after a timeout. The patch now prevents that on T6050. Calling it from
`kboot_boot` was also too late, because DT preparation had already removed
offline CPU nodes. A future start experiment still needs a separate entry
and a new reset-release hypothesis. Do not remove the one-core guard to run
the old instructions.

Matching reset vectors alone do not establish who controls reset entry. A
read-only MMIO probe can still fault on real hardware.

## Verify offline

```sh
python3 smp/test-smp-diag.py
```

Needs Python 3, a host C compiler with UndefinedBehaviorSanitizer, `patch`,
and `trash-put`. Eight tests cover the actual diagnostic and patched
start/stop functions against register mocks, plus build refusals. They cover all 18 masks, legacy
mapping, register-write order, reset-vector refusal including bit 11,
allocation failure, delayed arrival during timeout quarantine, default-off
behavior, malformed tokens, register-layout checks and build refusals.
Temporary files go to Trash.

To cross-compile against a complete local m1n1 header tree:

```sh
python3 smp/build-offline.py --m1n1 /path/to/m1n1 --output /path/to/new-build
```

Pass `--cc /path/to/aarch64-linux-gcc` for a nonstandard toolchain. This applies
the patches without fuzz and produces `smp.o`, `azahi_smp.o`, `pmgr.o`,
`azahi_standalone.o` and a combined `loader-components.o`. It checks that the
custom entry, diagnostic and PMGR lookup symbols resolve. `manifest.json`
records commands and hashes. The PMGR base sources must match the pinned
hashes from m1n1 commit `4184923ffb2dff079b384d6a32cc02142aa14572`; see
[the lookup dependency](../standalone-loader/README.md#read-only-pmgr-lookup-dependency).
It refuses an existing output directory, a host compiler or changed PMGR
inputs and retains failed builds. All four objects compiled with AArch64 GCC
16.1 and `-Werror`. The combined object still has ordinary m1n1 dependencies;
it is not a boot image and nothing is installed.

The [complete link check](../standalone-loader/README.md#complete-offline-link-check)
also combines the archived main/payload integration with these sources and
a pinned upstream tree. Both complete ELF files link without undefined
symbols. That result does not supply the private payload or establish CPU
startup on hardware.

The [optional shared-state backport](../standalone-loader/README.md#optional-smp-shared-state-backport)
now integrates the seven upstream SMP commits into that complete build.
It preserves the T6050 guards while adding static stacks, shared-memory
mappings and MPIDR-based re-entry. Four host groups and both ELF links pass;
secondary startup remains disabled and hardware validation is still absent.

[The investigation](../docs/audit-2026-09-25/smp.md) records the remaining reset
question and the iBoot/SPTM findings. Hardware validation still requires
observing each core enter the loader, then all 18 CPUs executing Linux work.

For offline firmware analysis, `decode-ibootdata.py` reads an already extracted
T6050 iBootData 1.0 payload and reports its sequence records. It has no hardware
access or execution mode. Use `--all-records` to retain surrounding guards;
filtering by sequence can hide guards carrying a different name.
`python3 smp/test-ibootdata.py` runs four in-memory format/bounds and CLI tests.
The investigation documents its supported layout and
the distinction between reset-vector restoration and a new CPU startup fix.

## Linux execution check prepared offline

`check-linux-cpus.py` defaults to reporting readiness. On the pinned J714s
kernel, after all 18 CPUs are online and available to the process, explicitly
run the short execution check:

```sh
python3 smp/check-linux-cpus.py --run
```

It starts one process per CPU, pins each process, repeatedly checks the actual
executing CPU with `sched_getcpu`, and hashes 16 MiB per CPU against a fixed
known result. A missing worker, wrong CPU, bad hash, changed online state or
timeout prevents `ALL_18_CPUS_EXECUTED`. This is a short per-core execution
check, not an endurance, thermal, concurrency or sleep certification. It does
not start offline CPUs, alter boot arguments or bypass the one-core guard.

`python3 smp/test-linux-cpus.py` checks the refusal/aggregation paths and one
actual worker on the host. Those host tests are not M5 hardware results.
