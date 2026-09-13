# Verified input + read-only SSD checkpoint, 2026-09-06

Hardware: J714s / T6050, Mac17,9. Host is the M1 Pro.

## Result and limits

Both built-in inputs physically verified on the v2-power baseline. The
combined SSD image also initializes both. NVMe discovery plus 8,192 direct
reads now pass; two 16 MiB extents were read four times each with identical
SHA256 per extent. This is 128 MiB / 128 nominal 64-entry I/O queue wraps.
No SSD writes, filesystem mounts, fsck, formatting, or GPT changes.
No claim of writable-storage safety or untethered boot readiness.

- Namespace prefix: `0831f0559b5954235f96f43f6c75c41b70ee45ab153063ccba95a02baa820339`
- Partition 3 prefix: `a5c325dc0f058ba496143d3553f9cb9832c7a0e875cb83846d5698d96f7b014c`
- Controller remained `live`; systemd `running`; DART fault count 0.
- Namespace stats after first test: 4,245 completed reads, **0 writes**.
- Logs: `logs/input-ssd-limit-boot-20260906/console.log`,
  `logs/input-ssd-limit-launch-20260906.log`.

The previous boot with the same image/DT and no limit adjustment crashed at
CQ head 63; firmware reported 65-entry queues. One host-side MMIO hook now
substitutes 63 for 64 in both pending-command limit fields, matching the
[m1n1 driver convention](https://github.com/AsahiLinux/m1n1/blob/main/src/nvme.c).
Stock Linux CreateCQ/CreateSQ already use depth minus one.

## Reproduce (physical reset required before a new session)

Do not interrupt the healthy guest unnecessarily. On a fresh proxy boot,
use the bounded NOP check and chainload the existing
`/PRIVATE-USER/azahi/m1n1-vmtmrfix.bin`, then:

```sh
python3 -u probe/boot-input.py /PRIVATE-USER/azahi/guest-hv-input-ssd-ro.bin NEW_LOG_DIRECTORY --prepare-mtp --trace-input --prepare-ans --activate-ans-link --ans-zero-based-limit --share /PRIVATE-USER/azahi-port/ramroot/work-kde
```

Use a new log directory. Never run two proxy clients. Guest commands go only
through `probe/guest-command.py`, which sends to the second CDC port.
Mount the `inputfiles` 9p share read-only, then run
`bringup-20260906/probe-ssd-readonly.py`. It masks automounters/repartitioning,
pauses udev, explicitly probes NVMe, sets every namespace read-only, resumes
udev, and reports identities. NVMe is blacklisted from automatic loading.

Run `verify-ssd-reads.py /dev/nvme0n1` and then `/dev/nvme0n1p3` for bounded
direct-read checks. `inspect-apfs-labels.py` is a narrow read-only metadata
reader pinned to partition 3's APFS UUID; it resolves volume OIDs from the
latest checksum-valid container checkpoint. It does not mount filesystems.

Local tests: `python3 probe/test-prepare-ans.py` covers exact ADT addresses,
PMGR shadows/no writes, one gated-link activation, the limit transform and
callback address/width/value rejection.

## Disk identities: do not infer authorization to change these

GPT disk UUID: `PRIVATE-UUID-REMOVED`.
Logical sectors are **4096 bytes**, not 512.

| Partition | Start LBA | Sectors | APFS purpose / identity |
| --- | ---: | ---: | --- |
| nvme0n1p1 | 6 | 140800 | iBootSystemContainer; PARTUUID PRIVATE-UUID-REMOVED |
| nvme0n1p2 | 140806 | 180324745 | Separate main APFS container; PARTUUID PRIVATE-UUID-REMOVED |
| nvme0n1p3 | 180465551 | 62500000 | 250 GB Linux-named APFS container; PARTUUID PRIVATE-UUID-REMOVED |
| nvme0n1p4 | 242965551 | 1310709 | RecoveryOSContainer; PARTUUID PRIVATE-UUID-REMOVED |

Partition 3 container UUID: `PRIVATE-UUID-REMOVED`.
Current checkpoint volume names/UUIDs from checksum-verified APFS metadata:

- Linux: `PRIVATE-UUID-REMOVED`, role 0x1.
- Linux - Data: `PRIVATE-UUID-REMOVED`, role 0x40.
- Preboot: `PRIVATE-UUID-REMOVED`, role 0x10.
- Recovery: `PRIVATE-UUID-REMOVED`, role 0x4.
- VM: `PRIVATE-UUID-REMOVED`, role 0x8.
- Update: `PRIVATE-UUID-REMOVED`, role 0xc0.

The name Linux does not mean this is a Linux root filesystem. Formatting
partition 3 would destroy these volumes, including boot infrastructure.
The existing no-repartition constraint prevents creating conventional Linux
root space without a new explicit user decision. Do not change partition 2,
the boot/recovery containers, or Linux's boot files. Leave the current guest
healthy and all namespaces read-only while awaiting that decision.
