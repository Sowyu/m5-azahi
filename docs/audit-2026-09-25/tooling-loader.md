# Tooling, loader and device-tree audit, 2026-09-25

Scope: remote-access/, safety/, probe/, ramroot/, standalone-loader/, the USB
Python/shell/unit files, the pd-backport Python, and the archived device
trees. Every finding in the PR #1 reports `tooling.md` and `loader-dt.md` was
checked against the current tree. Those reports were written at 843d290,
which is not an ancestor of the rewritten main. There was no hardware access,
so every change is source only. Nothing was installed or run on the Mac.

## Summary

- 178 findings checked, including 4 new ones. Every verdict that led to a
  code change was re-checked directly.
- 17 confirmed defects fixed. Each fix has a test that fails on the old code.
- PR #1 "fix first" items in this area: the initrd cache-clean claim (C1) is
  rejected; the rootguard LBA claim (C2/D5) is rejected; the ANS
  power-controller base (D1) is wrong, but only in an archived DT that no
  current builder uses; the flattened home path is fixed on main but still
  published on three old PR branches.
- Shutdown: cause found, host-only candidate builder and test added, attended
  test plan with rollback below.

## Fixes in this pass

| Finding | File | Change | Test (fails on old code) |
| --- | --- | --- | --- |
| USB-46, PB-2, RR-2, USB-53, CC-1 | proxy-test-v6.py, build-transfer{,-fixed,-v6}.py, mk-blob-header.py, strip-symbols.py, probe/build-native-ssdroot.py, ramroot/mkcpio.py, build-bundle.py, build-aligned.py, build-notch.py | One line after the imports: `if not __debug__: raise SystemExit(...)`. Under `-O` or `PYTHONOPTIMIZE` these scripts now refuse to start instead of running with every assert stripped. | New `safety/test-assert-guards.py` runs every tracked non-test script that contains an assert under `-O` and requires the refusal and no output file. Old proxy-test-v6.py died with FileNotFoundError; old mkcpio.py exited 0. |
| RA-1, RA-2, RA-19 | remote-access/relay.py | The 20-minute window (from the first `serve`) and the failure count are persisted as `bootstrap-expires` and `bootstrap-failures`, so a restart cannot reopen an expired or locked-out password. Wall clock replaces monotonic because the value must survive a restart. | `test_restart_keeps_expiry_and_lockout` |
| RA-3, RA-23 | relay.py, README.md | `init` and `serve` print `RELAY_HOST_KEY SHA256:...`, the same form the OpenSSH client shows. README describes the persisted limits. | `test_init_prints_openssh_fingerprint` compares with `ssh-keygen -lf`. |
| RA-10, RA-13 (tunnel only) | persist.py, bootstrap.py | Outbound tunnel units get an empty `CapabilityBoundingSet=`, `ProtectSystem=strict`, `ProtectHome=yes`, `PrivateTmp=yes`. | `test_tunnel_units_drop_privileges` (structural) |
| RA-20 | test-relay.py | Delivered bootstrap must start with `CONFIG = {` and contain the tunnel key. | Same test |
| USB-24, USB-25 | usb-driver/install-native-startup.py | All pinned files come from the staging argument, not `/root/usb-candidate`. `start-native-usb.sh` and `azahi-usb.service` are now pinned in `SOURCE_PINS`. Each file is read once and those verified bytes are installed, closing the hash-then-copy gap. | test-native-startup.py `Installer`: pins must equal the repo files and the private path must be gone. |
| New (EXTRA-1-tooling) | usb-driver/build.sh:32 | `! fdtdump \| grep -q __symbols__` could never abort, because `set -e` ignores negated commands. Now an explicit `if ...; then exit 1; fi`. | `test_no_negated_guard_under_errexit` rejects any `! cmd` line in tracked shell scripts. |
| SF-3, SF-4, SF-5, SF-6 | safety/check-publication.py | New `private-net` rule (IPv4 link-local and carrier-grade NAT ranges, IPv6 unique-local and link-local). New `quoted-secret` rule for JSON/YAML (the relay config.json form). `literal-secret` allows a trailing comment. `private-key` also catches PGP key blocks and the bare OpenSSH base64 prefix. `mac-address` catches dash and dotted forms. Zero hits in the current tree. | test-publication.py sample table extended with one variant per gap. |
| New (EXTRA-1-loader) | azahi_standalone.c:136 | `kboot_set_chosen()` returns the slot index, so the loader stopped if any other chosen parameter came first. Check is now `< 0`. The working v7 path set bootargs first (index 0), so behaviour there is unchanged. | New `standalone-loader/test-loader-guards.py` compiles the real function and call-site condition. |
| New (EXTRA-2-loader) | kboot.c dt_set_memory | The T6050 clamp replaced the RAM range with the safe window, which advertises RAM that does not exist on machines under about 61 GiB. It now intersects. Result for the recorded 64 GB J714s is unchanged. A stale comment about 0x10200000000 is annotated. | test-loader-guards.py runs the real block with the recorded 64 GB values and a 24 GB case. |
| X1 (partial) | none | Guard against hand-typed addresses drifting apart. | `test_shared_addresses_agree`: INITRD_ADDR must equal the kboot_set_initrd copy target; kernel/FDT/initrd windows must not overlap. |
| Shutdown | new standalone-loader/build-shutdown.py | Builds a v8 candidate on the host: pinned v7 image plus one DT node. | New standalone-loader/test-shutdown.py on a synthetic bundle. |

The loader C cannot be compile-checked as part of m1n1 because the repo holds
only kboot.c and azahi_standalone.c. The changed fragments are compiled and
run on the host with `cc -Wall -Wextra -Werror`. They take effect only when
the private loader is rebuilt; the installed v7 loader is unchanged.

Considered and not changed:

- `azahi-usb.service` hardening (USB-1). The unit must hold CAP_SYS_MODULE,
  which already means arbitrary kernel code. `ProtectKernelModules` blocks
  insmod; `ProtectKernelTunables` makes /sys read-only and breaks the
  handoff's sysfs diagnostics; `NoNewPrivileges` and the seccomp options can
  have the kmod exec transition refused on SELinux-enforcing Fedora.
- sshd unit. Its settings apply to every admin session it spawns;
  `ProtectSystem`/`ProtectHome` would stop the remote root shell editing
  /etc, /usr or /root. It is the only remote path.
- Tunnel `NoNewPrivileges`, `RestrictAddressFamilies`, `SystemCallFilter`:
  without CAP_SYS_ADMIN the seccomp options imply NoNewPrivileges, with the
  same SELinux concern.
- D1 archive file: not edited. It is manifest-pinned history and not built.

## Priority items

| Item | Verdict | Evidence |
| --- | --- | --- |
| proxy-hpm.py bare asserts on the 70 MB write | REJECTED for proxy-hpm.py; CONFIRMED and fixed in proxy-test-v6.py | proxy-hpm.py has no asserts; every check is an explicit raise. The 70 MB RAM write is in proxy-test-v6.py:100-105 (USB-46). |
| relay expiry/lockout in memory; no fingerprint | CONFIRMED, fixed | relay.py:56-57 at HEAD |
| installer pins only .ko files, reads a hard-coded path | CONFIRMED, fixed | install-native-startup.py:41,44-48,54 |
| systemd hardening | Partly CONFIRMED | Tunnel units hardened; USB and sshd units deliberately left (reasons above). |
| C1 initrd cache clean | REJECTED | kboot.c:2711-2716 copies the initrd to 0x10A00000000 on T6050/T6051 and hands that copy to the kernel; azahi_standalone.c:135 cleans exactly that range. test-loader-guards.py now fails if the two addresses diverge. |
| C2/D5 rootguard LBAs without a GPT match | REJECTED | Four fail-closed layers: root-write-policy.h `#error` blocks a public rootguard build; probe requires the PARTUUID string and both LBAs to equal compiled constants, else -ENODEV (apple.c:1599-1611), and public placeholders differ; writes stay disarmed until userspace arms them (apple.c:44-66); ssdroot-prepare.sh:63-101 checks root start/size and hashes both GPT copies and the filesystem UUID before arming. |
| D1 ANS power-controller base | CONFIRMED-NOT-FIXED (archive only) | Labels live in `&pmgr1` at 0x280900000, not 0x280600000 (hv-nvme.dts:128,137,141). The loader uses the correct 0x2809001{28,38,40,50}. Only the archived build-guest-ramroot.sh reads this file; the boot chain deletes pmgr0 to pmgr5. PCIe/Wi-Fi work must use apcie_st0 = 0x280900128 and apcie_sys_st0 = 0x280900150, never this file. |
| Flattened home path | CONFIRMED-FIXED on main; still public elsewhere | Patch header uses a/ and b/; check-publication.py has a rule with a test. Remote branches for PRs 2 to 4 still carry the old header, which is why `check-publication.py --history` refuses. Removing them needs the owner; GitHub also keeps `refs/pull/N/head`. |

## Verdicts

`fixed` means fixed in this pass. `NOT-FIXED` is short for
CONFIRMED-NOT-FIXED.

### Remote access

| ID | Verdict | Location | Reason |
| --- | --- | --- | --- |
| RA-1 | fixed | relay.py:56 | Deadline was per process; now persisted. |
| RA-2 | fixed | relay.py:57 | Per-process count, now persisted. |
| RA-3 | fixed | relay.py:26-48,156 | Fingerprint printed. |
| RA-4 | NOT-FIXED | relay.py:45-47 | Directory is already 0700. Hygiene. |
| RA-5 | REJECTED | relay.py:110-114 | Marking delivery before sending is the deliberate fail-closed order. |
| RA-6 | NOT-FIXED | relay.py:65 | Traceback, relay does not start. Fails closed. |
| RA-7 | NOT-FIXED | relay.py:28 | Loose regex; value is compared literally with findmnt. |
| RA-8 | REJECTED | relay.py:36 | Feature request. |
| RA-9 | REJECTED | bootstrap.py:37-42 | A foreign listener fails the pinned host key. |
| RA-10 | fixed (tunnel) | bootstrap.py:90-98 | Transient sshd left as is. |
| RA-11 | NOT-FIXED | bootstrap.py:93,98 | Single `is-active` probe. Hygiene. |
| RA-12 | NOT-FIXED | bootstrap.py:107 | NameError is itself a refusal. |
| RA-13 | partly fixed | persist.py:65-96 | Tunnel hardened; sshd deliberately not. |
| RA-14 | REJECTED | persist.py:82 | The NIC appears only when tethering is enabled; restart loop intended. |
| RA-15 | NOT-FIXED | persist.py:102-105 | `enu1` comes from the only supported port. Doc gap. |
| RA-16 | NOT-FIXED | persist.py:54-107 | No rollback; retry fails closed. |
| RA-17 | NOT-FIXED | persist.py:25 | ValueError on wrong arity. Fails closed. |
| RA-18 | REJECTED | persist.py:63 | Regex-constrained path, exact replace, `sshd -t` validates. |
| RA-19 | fixed | test-relay.py | Restart test added. |
| RA-20 | fixed | test-relay.py:64 | Content asserted. |
| RA-21 | NOT-FIXED | test-relay.py:20,40 | Global restored in tearDown. Test hygiene. |
| RA-22 | NOT-FIXED | test-relay.py | Refusal paths untested. |
| RA-23 | partly fixed | README.md | Expiry and fingerprint text fixed; `enu1` and rollback gaps remain. |
| RA-24 | REJECTED | requirements.txt | All pins install, including pycparser 3.0. |

### Safety

| ID | Verdict | Location | Reason |
| --- | --- | --- | --- |
| SF-1 | NOT-FIXED | docs/PUBLICATION-SAFETY.md:47 | Hooks were not installed in this clone. Doc mismatch. |
| SF-2 | NOT-FIXED | pre-commit, pre-push | Client-side hooks only, a documented limit. |
| SF-3 | fixed | check-publication.py:34 | private-net rule |
| SF-4 | fixed | :25 | PGP block and bare base64 key |
| SF-5 | fixed | :40 | quoted-secret rule; trailing comment |
| SF-6 | fixed | :37 | Dash and dotted MAC forms |
| SF-7 | NOT-FIXED | :19-21 | Binary files still fail other checks. |
| SF-8 | NOT-FIXED | :134-137 | `--staged` matches the default. Fails closed. |
| SF-9 | NOT-FIXED | :70 | Global re.I adds only false positives. |
| SF-10 | REJECTED | :107-108 | Sizes are cached per oid. |
| SF-11 | REJECTED | allowed-paths.txt:7-11 | Allowlist is not exact: five docs/audit/*.md entries point at files that exist only on the PR #1 branch. |
| SF-12 | partly fixed | :24-41 | IPv6 and JSON covered; SSID and .local not. |
| SF-13 | NOT-FIXED | :92-93 | Trailing-space entries never match. Fails closed. |
| SF-14 | REJECTED | pre-push:3-6 | Deliberately strict. |
| SF-15 | REJECTED | install-hooks.sh:7-10 | Deliberate and documented. |
| SF-16 | REJECTED | install-hooks.sh | `set -e` stops before the success line. |
| SF-17 | REJECTED | test-publication.py:89-116 | The coupling fails loudly (verified by mutation). |
| SF-18 | partly fixed | test-publication.py:54-74 | Variants added. |

### USB tooling

| ID | Verdict | Location | Reason |
| --- | --- | --- | --- |
| USB-1 | REJECTED | azahi-usb.service:7-12 | CAP_SYS_MODULE equals kernel code execution. |
| USB-2 | REJECTED | :3-4 | Normal idiom; the NIC appears later anyway. |
| USB-3 | REJECTED | :5 | Fails loudly and closed. |
| USB-4 | NOT-FIXED | usb-driver/README.md:4-5 | Unit undocumented. |
| USB-5 | REJECTED | boot-stage.conf:3 | Inside the enrolled, pinned initrd; `-` prefix deliberate. |
| USB-6 | REJECTED | boot-stage.conf | Stock unit has no ExecStartPre. |
| USB-7 | REJECTED | boot-stage.sh | Byte-compared by the v4 to v6 chain. |
| USB-8 | REJECTED | boot-stage-v2.sh:16-18 | An integrity check, as claimed. |
| USB-9 | NOT-FIXED | boot-stage-v2.sh:13-20 | Leaks the staging dir until reboot. Fails closed. |
| USB-10 | REJECTED | start-native-usb.sh:39-41 | All modules are =m for the pinned kernel. |
| USB-11 | REJECTED | :33 | check-build.sh builds the underscore name. |
| USB-12 | REJECTED | :10-44 | EEXIST plus `set -e`. |
| USB-13 | NOT-FIXED | :5-6 | Only a contrived newline-only file passes. |
| USB-14 | NOT-FIXED | :4,7 | Silent exit 1. |
| USB-15 | NOT-FIXED | usb-tether-test.sh | `set -u` applies only inside main. |
| USB-16 | REJECTED | :89 | Deliberate redaction. |
| USB-17 | NOT-FIXED | :95,148 | `${LOG##*.}` yields "log". Low. |
| USB-18 | REJECTED | :95,125 | Consistent with the script's banner. |
| USB-19 | REJECTED | build.sh | check-build.sh hpm-once builds the module. |
| USB-20 | REJECTED | build.sh:11-12 | Documented macOS host. |
| USB-21 | NOT-FIXED | build.sh:88 | shasum vs sha256sum split. |
| USB-22 | REJECTED | build.sh | Explicit names everywhere. |
| USB-23 | REJECTED | build.sh | `set -e`; zstd unused. |
| USB-24 | fixed | install-native-startup.py:41,54 | All files read from staging. |
| USB-25 | fixed | :16-21,40-59 | Script and unit pinned; read once. |
| USB-26 | REJECTED | :16-21 | Deliberate pins. |
| USB-27 | NOT-FIXED | :38-66 | No rollback. Fails closed. |
| USB-28 | NOT-FIXED | :25 | IndexError on bad arguments. |
| USB-29 | NOT-FIXED | test-native-startup.py:46 | No wrong-port case. |
| USB-30 | NOT-FIXED | :44 | Model guard untested. |
| USB-31 | NOT-FIXED | :45 | Manifest content untested. |
| USB-32 | REJECTED | test-usb-runner.py:145 | Breaks loudly. |
| USB-33 | REJECTED | :44 | Positive control. |
| USB-34 | NOT-FIXED | :57 | Needs Perl shasum. |
| USB-35 | NOT-FIXED | test-usb-glue.py:152 | Substring check. |
| USB-36 | NOT-FIXED | :14-22 | IndexError still fails the test. |
| USB-37 | NOT-FIXED | :68,134 | /usr/bin/cc hard-coded. |
| USB-38 | NOT-FIXED | test-usb-candidate.py:18 | Errors instead of skipping. |
| USB-39 | REJECTED | build.sh:82-90 | stage/ is filled before the gate. |
| USB-40 | NOT-FIXED | test-usb-candidate.py:53,61 | Test asserts under -O. |
| USB-41 | NOT-FIXED | build-transfer.py:134-141 | Can still write v4 on the host; installs nothing. |
| USB-42 | REJECTED | :31-33 | The proposed change does nothing. |
| USB-43 | NOT-FIXED | test-transfer-*.py | Error, not skip; names the missing file. |
| USB-44 | NOT-FIXED | build-transfer-fixed.py:30 | TypeError aborts. |
| USB-45 | REJECTED | builders | Exclusive outputs by design. |
| USB-46 | fixed | proxy-test-v6.py:40-120 | `-O` refused. |
| USB-47 | REJECTED | :30 | Redaction. |
| USB-48 | REJECTED | :57 | Documented private dependency. |
| USB-49 | REJECTED | courier-vm-init.sh:14-19 | Exit 127 can only come from mktemp. |
| USB-50 | REJECTED | :25-40 | Check completes before the mount. |
| USB-51 | NOT-FIXED | test-courier-vm.py:27 | About 70 MB kept per run. |
| USB-52 | NOT-FIXED | :24-59 | Test asserts under -O. |
| USB-53 | fixed | strip-symbols.py, mk-blob-header.py | `-O` refused. |
| USB-54 | REJECTED | strip-symbols.py:13 | Fails loudly. |

### pd-backport tooling

| ID | Verdict | Location | Reason |
| --- | --- | --- | --- |
| PD-1 | REJECTED | proxy-hpm.py:43-49 | Built only when called; macOS by design. |
| PD-2 | NOT-FIXED | proxy-hpm.py:44-45 | Leaks gitignored build dirs. |
| PD-3 | REJECTED | proxy-hpm.py:314 | Deliberate device guard. |
| PD-4 | NOT-FIXED | proxy-hpm.py:316,389-397 | Receipt lost when its parent directory is missing. |
| PD-5 | NOT-FIXED | test-proxy-hpm.py:97-99 | 15 logic tests blocked by the clang bridge. |
| PD-6 | NOT-FIXED | test-proxy-hpm.py:220 | Errors instead of skipping. |
| PD-7 | REJECTED | test-spmi4.sh:7 | `${CC:-clang}` already allows an override. |
| PD-8 | NOT-FIXED | test-spmi4.sh:5-11 | Build dirs kept. |
| PD-9 | REJECTED | test-spmi4.sh:3 | No pipelines. |

### ramroot and probe

| ID | Verdict | Location | Reason |
| --- | --- | --- | --- |
| RR-1 | NOT-FIXED | mkcpio.py:103 | Manifest parser unused by current callers. |
| RR-2 | fixed | mkcpio.py:41,72 | `-O` refused; under -O the short-read check looped forever. |
| RR-3 | NOT-FIXED | mkcpio.py:106 | Harmless. |
| RR-4 | REJECTED | mkcpio.py:43,50 | Valid newc. |
| PB-1 | REJECTED | build-native-ssdroot.py:181 | Must match the loader's placeholder. |
| PB-2 | fixed | build-native-ssdroot.py:36-179 | `-O` refused. |
| PB-3 | REJECTED | build-native-ssdroot.py:18,53 | Deliberate exclusive output. |
| PB-4 | NOT-FIXED | build-native-ssdroot.py:54-108 | Error message quality only. |

### Input and NVMe tooling (verdicts only)

| ID | Verdict | Location | Reason |
| --- | --- | --- | --- |
| ID-1 | CONFIRMED-FIXED | test-power-request.py:61 | Uses `$CC` or cc. |
| ID-2 | NOT-FIXED | test-power-request.py | No `__main__` guard; nobody imports it. |
| ID-3 | REJECTED | test-power-request.py:10-11 | Loud failure on rename is correct. |
| ID-4 | REJECTED | build-module.sh:5-26 | Stops at line 8 first. |
| ID-5 | REJECTED | build-module.sh:27 | `set -e` already aborts. |
| NV-1 | NOT-FIXED | build-modules.sh:51-52 | Needs ripgrep, undocumented. |
| NV-2 | REJECTED | build-modules.sh:19 | Shared header directory. |
| NV-3 | REJECTED | build-modules.sh | Documented host pin. |
| NV-4 | fixed (orchestrator) | test-root-write-policy.sh:6 | Now `"${CC:-clang}"`; passes with gcc (525366 checks). |
| NV-5 | REJECTED | test-root-write-policy.sh | Documented retention. |
| BT-1 | fixed with NV-4 | README.md:84-88 | The listed host tests now run with any C compiler via `CC`. |
| CC-1 | fixed | 11 builders | Enforced by test. |
| CC-2 | NOT-FIXED | six tests | Error instead of skip. |
| CC-3 | NOT-FIXED | host tests | Three compiler conventions. |
| CC-4 | CONFIRMED | root scripts | Informational: writes stay in documented scope. |

### Loader

| ID | Verdict | Location | Reason |
| --- | --- | --- | --- |
| C1 | REJECTED | azahi_standalone.c:134-135 | See priority table. |
| C2 | REJECTED | azahi_standalone.c:121-122 | See priority table. |
| C3 | REJECTED | :97-117 | Lengths bounded before `end` is computed; CRCs catch any reslice. |
| C4 | REJECTED | :90-91 | Same as stock m1n1. |
| C5 | REJECTED | :57-68 | 0x419600044 is ANS ASC CPU_CONTROL; its domain and parent are checked ACTIVE first. |
| C6 | NOT-FIXED | :20,99 | Deliberate exact pin. Fails closed. |
| C7 | REJECTED | :16,107 | Needs mem_size >= 0xf47008000; target has 0xfc7008000. |
| C8 | NOT-FIXED (partial) | :118-120; build-bundle.py:45 | inspect() lacks the root= check. |
| C9 | REJECTED | :94,142 | Exact-target gate. |
| C10 | REJECTED | :101-126 | Windows are disjoint. |
| C11 | NOT-FIXED | :60-68 | Readability only. |
| B1 | REJECTED | build-bundle.py:56-65 | SHA-pinned input. |
| B2 | REJECTED | :73 | Checks the link layout, as intended. |
| B3 | REJECTED | :69 | Host pin. |
| B4 | REJECTED | :75 | Superset check. |
| B5 | NOT-FIXED | :33-48 | Duplicated constants. |
| A1 | REJECTED | build-aligned.py:39 | Length rounding proven on hardware. |
| A2 | NOT-FIXED | :2,22-28 | Docstring says 16 KiB; code adds 170 bytes. |

### Archived DTs and archive tools

| ID | Verdict | Location | Reason |
| --- | --- | --- | --- |
| D1 | NOT-FIXED (archive) | hv-nvme.dts:128-141 | See priority table. |
| D2 | NOT-FIXED (archive) | hv-nvme.dts:262 | Not in the chain. |
| D3 | REJECTED | native-ssd-ro.dts:20-22 | ADT reg[3] is 0x60010 long; driver touches only NVMMU registers. |
| D4 | REJECTED | native-ssd-ro.dts:7 | Project SART v4 module; proposed fallback would misprogram hardware. |
| D5 | REJECTED | rootguard.dts:6-8 | See priority table. |
| D6 | REJECTED | rootguard.dts:7-8 | Read with of_property_read_u64 and matched exactly. |
| D7 | NOT-FIXED (no effect) | pmgr-refs.dtsi | pmgr nodes are deleted in the chain. |
| D8 | REJECTED | t6050.dtsi:310-321 | ADT confirms 12 M-cluster plus 6 P-cluster cores. |
| D9 | REJECTED | t6050-min.dtsi:67-73 | No bus DMA limit; 64-bit mask. |
| D10 | NOT-FIXED (archive) | t6050-min.dtsi | Fork of t6050.dtsi. |
| D11 | NOT-FIXED (no effect) | t6050-min.dtsi:118 | Node disabled. |
| D12 | REJECTED | board DTs | DT bootargs are overwritten by the bundle. |
| D13 | REJECTED | native-input.dts:7 | Overwritten; real bootargs have loglevel=3. |
| D14 | NOT-FIXED (cosmetic) | hv.dts:25-27 | Alias to a disabled node. |
| P1 | REJECTED | plist2adt.py:22 | No consumer. |
| P2-P4 | NOT-FIXED (archive) | plist2adt.py | No consumer. |
| S1, S2 | NOT-FIXED (archive) | deploy.sh | Retired host. |
| S3 | REJECTED | deploy.sh:6 | A key filename is not key material. |
| M1, M2 | NOT-FIXED (archive) | vmtmr patch | Hypervisor flow unused. |
| M3 | CONFIRMED-FIXED | vmtmr patch:1-2 | a/ and b/ paths. |
| K1, K2 | REJECTED | kconfig.txt | Stock config; K2 documented. |
| X1 | partly fixed | several | Shared-address test added. |
| X2 | partly fixed | several | Only non-private residue remains. |

### New findings

| ID | Verdict | Location | Reason |
| --- | --- | --- | --- |
| EXTRA-1-tooling | fixed | build.sh:32 | Negated guard under `set -e`. |
| EXTRA-2-tooling | NOT-FIXED (owner action) | `--history` over `rev-list --all` | Three pre-rewrite PR branches fail the guard, including the flattened path. The new rules also flag synthetic samples in docs/audit/tooling.md on the PR #1 branch; importing that file into main needs its samples split first. |
| EXTRA-1-loader | fixed | azahi_standalone.c:136 | Return-value check. |
| EXTRA-2-loader | fixed | kboot.c:433-441 | RAM clamp intersects instead of replacing. |

## Shutdown hang

### Cause

After "Reached target poweroff.target" the panel stays on. With no sys-off
handler registered, `reboot(POWER_OFF)` falls back to HALT
(kernel/reboot.c:759-762). It prints `Power off not available: System halted
instead` at emergency level, visible even with loglevel=3, then spins in
`machine_halt()` (arch/arm64/kernel/process.c:101-106).

There is no power-off handler on this machine:

- No PSCI.
- `apple_wdt` handles restart only; its node is present (t6050-min.dtsi:88-94,
  matching the ADT wdt at 0x28836c000).
- The only power-off driver is macsmc-reboot. Its probe returns -ENODEV
  without an OF node (drivers/power/reset/macsmc-reboot.c:213-214).
- The MFD attaches an of_node only to an SMC child whose compatible is
  `apple,smc-reboot` (drivers/mfd/macsmc.c:53, mfd-core.c:194-223).
- The boot DT's SMC node (research-archive/t6050-j714s-hv-input.dts:14-24)
  has only a `gpio` child.

PR 3's modules-load.d approach therefore binds nothing, which confirms the
earlier handoff review.

### What T6050 needs

Required: `/soc/smc@28c600000/reboot { compatible = "apple,smc-reboot"; }`.
Node name and reg do not matter; the MFD matches on compatible.
`status = "disabled"` would suppress the device.

Wanted, not available yet: the nvmem cells. Upstream T6030 uses PMIC nvmem
cells at 0xf801 (boot_stage), 0xf802 bits 0-3 (boot_error_count), 0xf802
bits 4-7 (panic_count) and 0xf80f bit 3 (shutdown_flag)
(arch/arm64/boot/dts/apple/t6030.dtsi:786-873).

- On J714s the main PMU is `/arm-io/nub-spmi0/spmi-abbeyL1`: SPMI slave
  0x0e, controller generation 4, `info-leg_scrpad = 0xf800` (same base as
  T6030), `info-has_phra = 1`.
- The 7.0.13 spmi-apple-controller uses the older FIFO layout
  (0x0/0x4/0x8). Generation 4 uses 0x200/0x210/0x220
  (pd-backport/audit-spmi4.py). No driver can reach the PMU today, and the
  repo's generation-4 transport is HPM-only and default-off.
- Providing the cells would mean PMU scratchpad writes over an unvalidated
  transport. The reboot driver writes boot_stage at every probe and clears
  the error counts, so that is not safe yet.
- The binding lists the cells as required, but the driver treats them as
  optional ("Missing NVMEM cell", non-fatal; `of_nvmem_cell_get` returns
  -ENOENT, not -EPROBE_DEFER).

### Evidence from macOS 27.0 (26A428, Mac17,9 kernelcache)

- AppleSMC writes key MBSE (4 bytes) with 'offw' (0xfffffe0009a9a254 to
  a9a294) and 'slpw' (0xfffffe0009a9a0b8), and logs "MBSE result", "NTAP
  result" and "kPanicBegin MBSE failed". The key names Linux uses exist on
  this generation.
- The ADT points the PMU at the same key: abbeyL1 has
  `function-external_standby = <smc-pmu, 'keyW', 'MBSE'>`.
- AppleDialogSPMIPMU shutdown path: reads PMU boot-key offset 0xf, applies
  `and #0x27; orr #0x8` and writes it back (0xfffffe0009ad5000 to ad506c),
  which sets bit 3 of 0xf800+0xf, the upstream shutdown_flag. It then stores
  'off1' (0xfffffe0009ad9c88), calls keyW, waits 1 s and panics with "SMCFW
  failed to handle shutdown request". Restart uses 'phra'
  (0xfffffe0009ad9b18); suspend uses 'susp'. macOS also clears bits 4, 6 and
  7; the Linux cell only sets bit 3.

### Expected behaviour with only the node

On poweroff the reboot notifier writes MBSE=offw (500 ms timeout), enters
atomic mode (NTAP=0), then writes MBSE=off1. Without shutdown_flag, the
driver's own comment says the machine may restart instead of powering off.
Either outcome comes after filesystems are unmounted. A restart boots the
default OS; Linux is chosen at the startup picker. With no cells, probe
writes nothing to the SMC, so boot-time risk is low.

Regression risk: macsmc-reboot also takes over restart at
SYS_OFF_PRIO_HIGH, above apple_wdt. If the SMC accepts phra, the machine
restarts. If the write fails with an error, apple_wdt still runs. But
`apple_smc_write_atomic()` polls with no timeout, so a silent SMC would hang
restart where the watchdog works today.

### Candidate

`standalone-loader/build-shutdown.py`:

- Input is the installed v7 image pinned by SHA-256 (2eaea0bc...). Output is
  `standalone-ssdroot-shutdown-v8-20260925.bin` plus a JSON receipt. It
  refuses to overwrite either.
- It locates the one header whose four section CRCs validate, skipping the
  magic literal inside the loader.
- It refuses unless `/soc/smc@28c600000` has compatible apple,t8103-smc and
  exactly one child, `gpio`.
- It adds the node with fdtput, then proves that removing the node gives the
  canonical-identical original DT.
- It enforces the loader's DT bounds (40 to 65536 bytes, magic, totalsize
  equal to the length).
- Loader, bootargs, kernel and initrd stay byte-identical; CRCs and 16 KiB
  padding are recomputed and the result is re-decoded. DT offset and
  alignment are unchanged. v7's own DT growth booted, so shifting gzip and
  initrd is known to work.

### Attended test plan

About 15 minutes on the host, about 45 minutes attended.

1. Zero-change confirmation on v7. At the next poweroff hang, read the last
   screen line; `Power off not available: System halted instead` confirms
   the cause. On the next boot, `ls -l
   /sys/bus/platform/devices/macsmc-reboot/`: expect no `of_node` and no
   `driver` link. Then `dmesg | grep "Failed to locate of_node"`. Also run
   `systemctl reboot` once to confirm the apple_wdt restart works today.
2. Build on the host: `python3 standalone-loader/build-shutdown.py` next to
   the private v7 image. Check the receipt's args/gzip/initrd hashes equal
   v7's.
3. Install with the same private Recovery procedure as v7, keeping v7 as the
   rollback. Prefer a RAM-only proxy load if available.
4. Boot v8 with every USB-C socket empty. Expect `Missing NVMEM cell
   shutdown_flag (-2)` (and the other three), `Handling reboot and poweroff
   requests via SMC`, and `/sys/bus/platform/drivers/macsmc-reboot/macsmc-reboot`.
   Stop on any SError.
5. `systemctl reboot`. Expect `Issuing restart (phra)`, then a restart. A hang
   of more than 30 s after that line means the atomic path is broken:
   long-press power and roll back.
6. `systemctl poweroff`. Record the outcome:
   - Powers off: success.
   - Restarts: shutdown_flag is needed (future nvmem work).
   - `Unable to power off system` WARN, then an init-exit panic: the SMC
     accepted the write but nothing happened.
   - `Failed to issue MBSE = off1`: the SMC rejected the write.
   - Hang after `Issuing power off`: the atomic poll never completed.

Rollback: hold power for startup options, boot macOS or Recovery, and
reinstall the pinned v7 image 2eaea0bc.... No macOS volume, partition or
boot-policy change is involved.

## Tests

| Test | Before | After |
| --- | --- | --- |
| usb-driver/test-usb-runner.py | 19 pass | 19 pass |
| usb-driver/test-native-startup.py | 8 pass | 9 pass |
| usb-driver/test-usb-glue.py | 4 pass | 5 pass (fifth added in the kernel pass) |
| safety/test-publication.py | 14 pass | 14 pass (extended sample table) |
| standalone-loader/test-notch.py | PASS | PASS |
| remote-access/test-relay.py (pinned deps in a private venv) | 4 pass | 7 pass |
| safety/test-assert-guards.py (new) | n/a | 2 pass |
| standalone-loader/test-loader-guards.py (new) | n/a | 3 pass; 2 fail on the old C |
| standalone-loader/test-shutdown.py (new; needs dtc/fdtput/fdtget, skips otherwise) | n/a | 2 pass |
| `check-publication.py --staged` | pass | pass |
| `check-publication.py --history` | refused (PR branches) | refused (PR branches, plus synthetic samples on the audit branch) |

Not runnable here: test-usb-candidate.py (m1n1 pylib, real ADT),
test-transfer-fixed.py and test-transfer-v6.py (v3 to v6 images),
test-courier-vm.py (v5 image, QEMU), audit-spmi4.py (m1n1, ADT, image), and
test-proxy-hpm.py (needs clang `-dynamiclib`).

## Open risks

- The v8 shutdown candidate is unproven on hardware. Restart may hang if the
  SMC atomic poll never completes, and poweroff may become a restart without
  shutdown_flag.
- The three pre-rewrite PR branches still publish the flattened private path
  until the owner removes them.
- Any edit to start-native-usb.sh or azahi-usb.service now needs its pin
  updated in install-native-startup.py (for example if PR 4's diagnostics are
  applied).
- Tunnel hardening is untested on the SELinux target. The new units apply
  only to a future install; persist.py refuses to overwrite installed ones.
- New publication rules can false-positive on dotted groups of four hex
  digits (the Cisco MAC notation). This fails closed.
