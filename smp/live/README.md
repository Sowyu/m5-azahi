# Live T6050 secondary-CPU tests from Linux

Research tools, not a fix. No test here brings a core into Linux. Nothing is
installed, and every test module refuses to stay loaded. Read
[the 2026-10-31 results](../../docs/audit-2026-10-31-smp.md) first.

| File | What it does | Writes |
| --- | --- | --- |
| `azahi_smp_ro.c` | Snapshot of CPU_START, cluster controls, CPU/CPM power, reset vectors | None |
| `azahi_smp_t1.c` | Trap over unused loader memory and the sled, release one core, 5 ms status timeline | Loader RAM, CPU_START |
| `azahi_smp_t2.c` | T1 with `+4` and doorbell separated, then IPI and SEV. `mode=2` releases a whole cluster | Loader RAM, CPU_START |
| `azahi_smp_t3.c` | T2 after a cluster-control cycle on an idle cluster. Refuses cluster 0 | Loader RAM, cluster control, CPU_START |
| `azahi_smp_t4.c` | Store-free test: fills with `b .` or `wfi`, verifies both ranges, compares status. **Built, not yet run** | Loader RAM, sled, CPU_START |
| `stub.s` | Source of the trap instructions embedded in T1 to T3 | n/a |
| `kiscap.py` | Read-only capture of a DebugUSB channel on the helper | None |

The modules check for J714s and the expected M core, and refuse a reset vector
that points into System RAM. Each start test leaves a core powered, so run it once
per boot and reset afterwards. Sync the target first.

Do not add `cpm-impl-reg+0x40f8`, `cpu-impl-reg+0x9000` and up, or anything in the
CoreSight blocks to these tools. They are reported or known to fault. These tests
assume recovery from a released core only. Recovery from a CPU0 bus hang is unproven.
