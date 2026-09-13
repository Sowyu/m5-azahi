# Full code audit, 2026-09-13

I read the whole public tree at commit `843d290` and wrote up everything I
found wrong. This directory is the result. Four reports, one per area, each
with file:line, defect, impact and a suggested fix, ranked by severity.

| Report | Scope | Critical | High | Medium | Low |
| --- | --- | --- | --- | --- | --- |
| [kernel-c.md](kernel-c.md) | USB PHY, DWC3 glue, overlay, SPMI4/HPM, DockChannel HID, ANS NVMe, SART | 1 | 4 | 29 | 34 |
| [loader-dt.md](loader-dt.md) | standalone loader, bundle builders, device trees, plist2adt, kconfig | 4 | 10 | 21 | 11 |
| [tooling.md](tooling.md) | remote-access, safety hooks, USB scripts and builders, systemd units, host tests | 0 | 15 | 56 | 56 |
| [docs.md](docs.md) | README, PROGRESS, HANDOFF, provenance, privacy, manifest | 3 | 15 | 22 | 13 |
| Total | | 8 | 44 | 128 | 120 |

Nothing in this PR changes code. Agents picking up work from this repo: treat
the list below as the queue, top to bottom, and fix one item per commit with
the finding ID in the commit message.

## Fix first (hardware or data risk)

1. `input-driver/dockchannel-hid.c:1079`: the `hdr.iface >= MAX_INTERFACES`
   check logs and falls through. Upstream has `goto done` there. A byte from
   the coprocessor indexes past `ifaces[16]` into `pkt_buf`, and the resulting
   pointer is written through. Restore the `goto`. (kernel-c C1)
2. `research-archive/t6050-j714s-hv-nvme.dts:137,141`: ANS power controllers
   are declared at PMGR base `0x280600000`. They live at `0x280900000`, as the
   loader, the pmgr dtsi and the sibling input-ssd DT all say. The wrong base
   lands on fabric domains and `resets = <&ps_ans>` asserts a reset on one of
   them. (loader-dt D1)
3. `standalone-loader/.../azahi_standalone.c:134-135`: the initrd is handed to
   the kernel in place inside the bundle, but the D-cache clean targets
   `INITRD_ADDR`, which was never written. Clean the range actually passed to
   `kboot_set_initrd`. (loader-dt C1)
4. `research-archive/t6050-j714s-native-rootguard.dts:6-8`: redaction replaced
   the PARTUUID with a placeholder but kept the real LBA window. The guard can
   no longer verify the disk before authorizing writes. Refuse to arm without a
   GPT match. (loader-dt C2, D5)
5. `usb-driver/pd-backport/hpm-once.c`: reaches the PD controller directly with
   no `allow_*` gate, and `mode=probe` also writes to the bus. Either route it
   through the gated SPMI4 controller or give it the same default-off params.
   (kernel-c H3)

## Fix next (security)

6. `usb-driver/pd-backport/proxy-hpm.py:298-328`: every precondition on the
   path that writes 70 MB into live device RAM is a bare `assert`. `python3 -O`
   removes all of them. Convert to explicit raises. (tooling USB-46)
7. `remote-access/relay.py:35,73`: bootstrap expiry and the five-attempt
   lockout are in-process state, so a restart resets both. Nothing ever prints
   the relay host-key fingerprint the README says the operator must compare.
   (tooling RA-1, RA-2, RA-3)
8. `input-driver/dockchannel-hid.c:1005`: the ACK handler writes into
   `resp_buf` with no lock against the 1 s timeout path in `dchid_cmd()`. A
   late ACK memcpys device bytes into a returned caller's stack frame.
   (kernel-c H1)
9. `usb-driver/install-native-startup.py:16-21,41-47`: the four `.ko` files are
   pinned by digest; the shell script and unit that load them as root are not.
   Three of four modules are also read from a hard-coded `/root/usb-candidate`
   rather than the staging argument. (tooling USB-24, USB-25)
10. `usb-driver/azahi-usb.service`, `remote-access/persist.py:65-96`: no
    hardening on units that run root shell scripts and a root ssh tunnel.
    (tooling USB-1, RA-13)

## Privacy

- `research-archive/m1n1-vmtmr-ro.patch:2` still contains the operator's
  macOS UID and a four-folder private directory chain. The scanner looks for
  `/Users/<name>` and missed the flattened `-Users-<name>-` form. Rewrite the
  patch header to `a/` and `b/` and add the flattened form to
  `safety/check-publication.py`. (docs HIGH-11, loader-dt M3)
- `docs/research-archive-manifest.json` publishes byte-exact sizes of 41
  withheld private images. (docs MEDIUM-10)
- The publication guard is client-side only. No CI. `--no-verify` skips it.
  (tooling SF-2)

## Docs

- `PROGRESS.md` and `docs/HANDOFF.md` are byte-identical for their first 323
  lines and each has seven sections titled "Latest". PROGRESS states four
  mutually exclusive USB tethering outcomes. Deduplicate, then date every
  heading. (docs CRITICAL-3, HIGH-12, HIGH-13)
- Two of the four host tests the README lists hard-code `clang`; the README
  promises "a C compiler". (docs HIGH-1)
- `usb-driver/README.md` and `standalone-loader/README.md` describe v4/v5 as
  current; the root README reports v6 cold-booting. (docs CRITICAL-1, -2)
- `usb-driver/phy-apple-t6050-usb2.c` says it transcribes three named
  kernelcache functions at listed VAs and ships `GPL-2.0 OR BSD-2-Clause`.
  `docs/PROVENANCE.md` softens that to "analysis of behavior". Pick one story.
  (docs HIGH-8, HIGH-9)

## What was checked and is fine

- `docs/research-archive-manifest.json`: 284 declared, 284 present, all
  names, sizes and SHA256s match.
- `safety/allowed-paths.txt` matches `git ls-files` exactly.
- No UUIDs, MACs, IPs, ECIDs, serials or emails anywhere in the tree or in
  `git log -p --all`, beyond the one patch header above.
- Bundle header struct packing matches between the C loader and
  `build-bundle.py`.
- No root-running script writes outside its documented scope.

## Method

Each area was read in full by a separate reviewer. The three forked kernel
files with a vendored original (`dwc3-apple-t6050.c`, `apple.c`, `sart.c`)
were diffed against it. `dockchannel-hid.c` has no vendored original in the
tree, which is how item 1 got in. Tests that can run from a fresh clone were
run: `test-usb-runner.py` (19 pass), `test-usb-glue.py` (3 pass), `test-native-startup.py` (8 pass),
`safety/test-publication.py` (14 pass); the two `clang`-only tests fail on a
gcc host. One tooling note: `grep` on the audit host was ugrep, which honours
the default-deny `.gitignore`; scans used `--no-ignore-files`.
