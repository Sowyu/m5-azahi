# Tooling audit: m5-azahi Python and shell (fresh clone)

**Severity counts: 0 critical, 15 high, 56 medium, 56 low, 1 informational
(128 findings).**

High-severity index, in order of how much I would fix first:

1. USB-46 `proxy-test-v6.py:103` — device-RAM write bounds are `assert`, gone under `-O`.
2. USB-25 `install-native-startup.py:44` — the two root-executed boot artifacts are the only unpinned ones.
3. USB-5 `boot-stage.conf:3` — unverified root script at boot, failures discarded.
4. RA-1 `relay.py:56` — bootstrap password expiry resets on every relay restart.
5. RA-3 `relay.py:26-48` — nothing prints the relay fingerprint the README says to compare.
6. SF-2 — hooks are `--no-verify`-skippable and there is no server-side or CI check.
7. SF-1 `docs/PUBLICATION-SAFETY.md:47` — says hooks are installed in this clone; they are not.
8. RA-13 `persist.py:65-96` — persistent units unhardened, SSH tunnel runs as root.
9. USB-10 `start-native-usb.sh:39` — one missing optional module aborts boot USB with no retry.
10. USB-24 `install-native-startup.py:41` — reads three of four modules from a hard-coded private path.
11. USB-1 `azahi-usb.service:7` — no sandboxing on a root module-loading unit.
12. RA-2 `relay.py:57` — five-attempt lockout resets with the process.
13. BT-1 / ID-1 / NV-4 — two of the four README-promised tests fail on a gcc-only host.

Scope: Python and shell tooling only. C sources, device trees and vendor
copies were read only where a script's claim depends on them. Audited at
commit `843d290`.

## Test execution summary

Run on Linux (Python 3.13.5, gcc present, no clang, no network, no m1n1
library, no private `.bin`/`.dtb`/headers fixtures).

| Test | Result | Cause |
|---|---|---|
| `usb-driver/test-usb-runner.py` | PASS (19 tests) | |
| `usb-driver/test-usb-glue.py` | PASS (3 tests) | |
| `usb-driver/test-native-startup.py` | PASS (8 tests) | |
| `safety/test-publication.py` | PASS (14 tests) | |
| `safety/check-publication.py --staged` | PASS (385 versions) | |
| `safety/check-publication.py --history` | PASS (461 versions) | |
| `usb-driver/pd-backport/test-spmi4.sh` | PASS only with `CC=gcc` | default `clang` not found |
| `input-driver/test-power-request.py` | FAIL | `FileNotFoundError: 'clang'` (line 59) |
| `nvme-driver/test-root-write-policy.sh` | FAIL | `clang: command not found` (line 6) |
| `usb-driver/pd-backport/test-proxy-hpm.py` | ERROR in `setUpClass` | `build_bridge()` needs `clang -dynamiclib` |
| `usb-driver/test-usb-candidate.py` | ERROR at import | `ModuleNotFoundError: m1n1` (line 19) |
| `usb-driver/test-transfer-fixed.py` | ERROR (0 tests) | missing `standalone-ssdroot-usb-files-v5-fixed-20260913.bin` |
| `usb-driver/test-transfer-v6.py` | ERROR (0 tests) | missing `...v6-courier-20260913.bin` |
| `usb-driver/test-courier-vm.py` | ERROR | missing v5 image (also needs QEMU, zstd) |
| `remote-access/test-relay.py` | ERROR at import | `ModuleNotFoundError: asyncssh` (no network to install) |

`docs/BUILD-AND-TEST.md` promises four tests runnable "with Python 3, Bash and
a C compiler available". Two of the four fail on a gcc-only host. See
BT-1.

---

## remote-access/relay.py

**RA-1 (high) — `relay.py:56` the 20-minute bootstrap expiry resets on every
relay restart.**
`self.deadline = time.monotonic() + 1200` is computed in `State.__init__`, so
each `serve` invocation grants a fresh 20-minute window. Only the one-use flag
survives (`bootstrap-delivered` file, line 58). `README.md:17` states
"Bootstrap password expires after 20 minutes and one successful transfer" and
`relay.py:5` repeats it; neither is true across a restart, crash-loop or
supervisor respawn. A relay left running under `systemd`/`Restart=` keeps the
password live indefinitely.
Fix: persist an absolute expiry into `config.json` at `initialize()` time
(`expires_at = time.time() + 1200`) and compare against wall clock in
`password_auth_supported`.

**RA-2 (high) — `relay.py:57` the five-attempt lockout is per-process, so a
restart resets `failures` to 0.**
`self.failures = 0` in `State.__init__`. Combined with RA-1 an attacker who can
cause the relay to restart (or who simply waits for one) gets unlimited
password attempts in unlimited 20-minute windows against a 64-bit secret that
unlocks the target's tunnel private key.
Fix: persist the counter to a file next to `config.json`, incremented before
the comparison.

**RA-3 (high) — no code path ever prints the relay host-key fingerprint, but
the documented security model requires the operator to compare it.**
`README.md:21` says "The user must independently compare the relay's SSH
fingerprint before accepting it." `initialize()` (`relay.py:26-48`) prints only
"Created private task keys/config"; `serve()` (`relay.py:156`) prints only
"RELAY_LISTENING". Nothing runs `ssh-keygen -lf relay_key.pub`. The operator
who cannot obtain the fingerprint will accept the key blind on first connect,
and that first connection carries both the bootstrap password and the target's
`tunnel_key` private key (embedded in the delivered `bootstrap.py`, see
`relay.py:45-46`). This is the practical host-key-pinning bypass in this design.
Fix: print `subprocess.check_output(['ssh-keygen','-lf',folder/'relay_key.pub'])`
at the end of `initialize()` and again on every `serve()` startup.

**RA-4 (medium) — `relay.py:45-47` the private key is written world-readable
for one syscall before `chmod`.**
`(folder / 'bootstrap.py').write_text(...)` uses the ambient umask (typically
0022), and `os.chmod(..., 0o600)` only lands on the next line. `config.json`
two lines above (line 41) correctly uses `os.open(..., 0o600)`. The parent directory is
0700 so the practical exposure is same-user only, but the asymmetry is a bug.
Fix: use the same `os.open(..., os.O_CREAT|os.O_EXCL, 0o600)` pattern, or call
`os.umask(0o077)` at the top of `initialize()`.

**RA-5 (medium) — `relay.py:110-114` the one-use bootstrap is marked delivered
before the transfer completes, with no integrity confirmation.**
The `bootstrap-delivered` sentinel is created (line 111), then `state.used`
is set, then the file contents are written to stdout. A client that drops the
connection mid-write leaves the password permanently disabled and the operator
holding a truncated `bootstrap.py`. Nothing checksums the delivered body.
This is not a race between concurrent connections (asyncio does not preempt
between the check and the `open('x')`), but it is a durability bug.
Fix: write the sentinel only after `proc.stdout.write` returns and the channel
drains, and append a `# sha256:<digest>` trailer the operator can verify.

**RA-6 (medium) — `relay.py:65` `State.__init__` crashes at relay startup if
`registration.json` exists but `native_known_hosts` was removed.**
`(folder / 'native_known_hosts').read_text()` is unguarded, so a partially
deleted state directory turns into an unhandled `FileNotFoundError` and the
relay never starts, with no diagnostic.
Fix: catch `OSError` and raise the existing `ValueError('Invalid saved
registration')`.

**RA-7 (low) — `relay.py:28` the root-UUID validator accepts non-UUIDs.**
`re.fullmatch('[0-9a-f-]{36}', root_uuid)` accepts `'-' * 36`. The value is
later compared literally against `findmnt` output so this cannot mis-target,
but it defeats the stated intent of `ValueError('Expected private Linux root
UUID')`.
Fix: `re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', root_uuid)`.

**RA-8 (low) — `relay.py:36` port 8022 is hard-coded in `initialize()` with no
CLI override**, while the value is stored in `config.json` as if it were
configurable and duplicated as a literal in `persist.py:89`.
Fix: add `--port` to the `init` subcommand.

## remote-access/bootstrap.py

**RA-9 (medium) — `bootstrap.py:37-42` the "refuse a competing listener" check
is a TOCTOU probe whose failure surfaces as a raw traceback.**
The socket is bound and immediately closed; `sshd` is not started until line
90, roughly ten operations later. Anything binding 127.0.0.1:2222 in that
window wins, and the daemon then fails inside `systemd-run` with a much less
clear error. The `OSError` from `bind` is not caught, so the intended message
never appears.
Fix: wrap the bind in `try/except OSError` and raise
`RuntimeError('Port 2222 already in use; refusing')`; keep the socket open
until immediately before `systemd-run` if the race matters.

**RA-10 (medium) — `bootstrap.py:90-98` the two transient units get no
sandboxing properties.**
`systemd-run` is called with only `Restart=` and `RestartSec=`. The persistent
equivalents in `persist.py` are equally bare. Both units run as root with the
full capability set; the tunnel unit is a plain outbound `ssh` client that
needs neither root nor any capability beyond reading its key.
Fix: add `--property=NoNewPrivileges=yes --property=ProtectSystem=strict
--property=ProtectHome=yes --property=PrivateTmp=yes
--property=CapabilityBoundingSet=` to the tunnel unit at minimum.

**RA-11 (low) — `bootstrap.py:93` `systemctl is-active` is polled once with no
settle delay**, so a `Type=simple` unit that dies instantly can still report
`active` on the first probe.
Fix: `systemctl is-active --wait` is not appropriate here; use a short
`ExecStartPost` health check or poll `is-active` for two seconds.

**RA-12 (low) — `bootstrap.py:107` `setup(CONFIG)` references a name that only
exists after `relay.initialize()` prepends it**, so running the tracked file
directly is a bare `NameError`. The docstring says CONFIG is injected but
nothing guards the direct-invocation case.
Fix: `setup(globals()['CONFIG'])` behind a
`if 'CONFIG' not in globals(): sys.exit('This file is a template; ...')`.

## remote-access/persist.py

**RA-13 (high) — `persist.py:65-96` the two generated persistent units contain
no systemd hardening and run the SSH tunnel as root.**
`azahi-native-tunnel.service` executes `/usr/bin/ssh -NT ... -R` as root
forever. It needs only its key file. `azahi-native-sshd.service` legitimately
needs privilege, but neither unit sets `NoNewPrivileges`, `ProtectSystem`,
`ProtectHome`, `PrivateTmp`, `RestrictAddressFamilies`, `ProtectKernelModules`
or a `CapabilityBoundingSet`. `README.md:55-62` describes this installer as the
hardened, reviewed path.
Fix: give the tunnel unit `DynamicUser=yes` (or a dedicated system user owning
`tunnel_key`), `NoNewPrivileges=yes`, `ProtectSystem=strict`,
`RestrictAddressFamilies=AF_INET AF_UNIX`, `CapabilityBoundingSet=`. Give the
sshd unit `ProtectHome=read-only`, `NoNewPrivileges` cannot be set for sshd but
`ProtectSystem=full` and `ReadWritePaths=/var/lib/azahi-remote` can.

**RA-14 (medium) — `persist.py:82` the tunnel unit is ordered after
NetworkManager but never after `network-online.target`.**
`After=NetworkManager.service` is satisfied when the daemon starts, not when a
route exists. On the documented topology the route arrives only once
`azahi-usb.service` has loaded the USB drivers and the `azahi-usb-tether`
profile has autoconnected. The unit therefore reliably fails its first attempts
and depends on `Restart=on-failure`/`RestartSec=15` to converge.
Fix: add `After=network-online.target` and `Wants=network-online.target`, and
`After=azahi-usb.service` to mirror the `Before=` already declared in
`usb-driver/azahi-usb.service:4`.

**RA-15 (medium) — `persist.py:102-105` hard-codes the interface name `enu1`.**
The NetworkManager profile binds to `ifname enu1`. Nothing in the repo
guarantees that name: `usb-tether-test.sh:43-56` deliberately discovers the
interface by walking sysfs from the right-port hub because the name is not
predictable. `README.md:60` does not mention the hard-coded name.
Fix: take the interface as an argument, or omit `ifname` and match on the
device path/MAC.

**RA-16 (medium) — `persist.py:54-57` the "backup" is a directory of empty
`.absent` marker files; nothing is actually recoverable.**
The name `azahi-access-before-` and `install-receipt.json`'s `"backup"` field
imply a rollback point. If `nmcli` (line 102), `daemon-reload` (106) or
`enable` (107) fails, the function raises with `/var/lib/azahi-remote` and both
unit files already created, and nothing removes them. A retry then hits
`RuntimeError('Dedicated persistent state already exists; no overwrite')` at
line 44 and the operator must clean up by hand with no script to do it.
Fix: wrap lines 58-107 in `try/except BaseException` that removes the units and
`dest` before re-raising, or ship an `--uninstall` mode.

**RA-17 (low) — `persist.py:25` `runtime, expected_uuid, host = sys.argv[1:]`
raises a bare `ValueError: not enough values to unpack` on wrong arity**, with
no usage message, in a script that must be invoked correctly as root.
Fix: use `argparse`.

**RA-18 (low) — `persist.py:63` rewrites the sshd config by naive string
replacement** (`.replace(runtime, str(dest))`). Correct today because `runtime`
matches `/run/azahi-remote-[A-Za-z0-9_]+` and cannot be a substring of anything
else in the file, but it silently produces a broken config if the path pattern
ever changes.
Fix: regenerate the config from the same template `bootstrap.py:53` uses.

## remote-access/test-relay.py

Could not execute here (`asyncssh` unavailable, no network). Reviewed
statically. The four tests are genuine loopback integration tests, not mocks;
`test_tunnel_register_pin_and_exact_forward` pushes real bytes through the
reverse forward. The gaps below are coverage, not fakery.

**RA-19 (medium) — nothing tests the two expiry controls the README sells.**
There is no test for the 20-minute deadline (`relay.py:56`) and none for the
five-failure lockout (`relay.py:57`). Both are the defects RA-1/RA-2; a test
asserting the documented behaviour would have caught the restart reset, because
it would have to construct a second `State`.
Fix: add a test that monkeypatches `time.monotonic`, and one that loops six bad
passwords then asserts the sixth is refused even with the correct password.

**RA-20 (low) — `test-relay.py:64` the `compile()` assertion is close to
tautological.**
`compile(result.stdout, '<bootstrap>', 'exec')` only proves the delivered blob
parses as Python. It does not check that `CONFIG = {...}` was prepended, that
`tunnel_private` is present, or that the body matches the tracked
`bootstrap.py`. A relay bug that delivered the un-prepended template would pass
this test and then fail on the target with `NameError` (RA-12).
Fix: `self.assertTrue(result.stdout.startswith('CONFIG = {'))` and
`self.assertIn(self.state.config['tunnel_private'], result.stdout)`.

**RA-21 (low) — `test-relay.py:20,40` mutate the module global
`relay.FORWARD_PORT`**, and the `assertEqual(relay.FORWARD_PORT, 22022)` at
line 20 is self-fulfilling after `asyncTearDown` restores it. A crashed test
leaves the module patched for any test that follows in the same process.
Fix: make `FORWARD_PORT` a `State` attribute, or use
`unittest.mock.patch.object`.

**RA-22 (low) — `relay.initialize()` is never tested for its own guards**
(non-empty directory, non-IPv4 host, malformed UUID). `asyncSetUp` calls it
only on the happy path.

## remote-access/README.md and requirements.txt

**RA-23 (medium) — README claims contradicted by the code**, collected:
- line 17 "expires after 20 minutes" — false across restart (RA-1).
- line 21 "compare the relay's SSH fingerprint" — impossible, nothing prints it
  (RA-3).
- line 60 "adds the dedicated `azahi-usb-tether` NetworkManager autoconnect
  profile" omits that it is pinned to the hard-coded interface `enu1` (RA-15).
- line 55 describes `persist.py` as safe and reviewed without mentioning that a
  mid-install failure leaves unremovable state (RA-16).

**RA-24 (low) — `requirements.txt:4` pins `pycparser==3.0`, which does not
exist** on PyPI (latest is 2.x). The file is described as a pinned dedicated
environment, so `pip install -r requirements.txt` fails outright. Could not
verify against the index from this sandbox (no network), but the version is
implausible; the same list pins `cryptography==50.0.1` and `cffi==2.1.1` which
are also far ahead of anything shipped.
Fix: regenerate with `pip freeze` from the actual working environment.

---

## safety/check-publication.py

Note first: `.git/privacy-guard` does **not** exist in this checkout and
`core.hooksPath` is unset. The guard is currently inert here.

**SF-1 (high) — `docs/PUBLICATION-SAFETY.md:47` states "Hooks are installed in
this public clone"; they are not.**
`git config --local core.hooksPath` returns nothing and `.git/privacy-guard` is
absent in a fresh clone. Every protection described in that document is
currently off for this working copy. The next sentence ("Git does not
automatically install them in new clones") partially covers this, but the
preceding claim is simply wrong for the artifact a reader is holding.
Fix: change the sentence to "Hooks must be installed in every clone; run
`bash safety/install-hooks.sh`", and have the installer print the current
`core.hooksPath` so an operator can verify.

**SF-2 (high) — the hook layer is bypassable with `--no-verify` and there is no
server-side or CI check.**
`safety/pre-commit` and `safety/pre-push` are client-side Git hooks. Both are
skipped by `git commit --no-verify` / `git push --no-verify`, and
`git config --unset core.hooksPath` disables them permanently. `install-hooks.sh:15-16`
`chmod 500`/`400` the installed copies, but the same user owns them so the
permissions are advisory. There is no `.github/workflows` directory and no
other automated check anywhere in the tree.
Fix: add a GitHub Actions workflow (or a push-time repository ruleset) that
runs `python3 safety/check-publication.py --history` on every ref update. That
is the only layer an operator cannot skip from the client.

**SF-3 (medium) — `check-publication.py:33` the `private-lan` rule misses every
private-address form except RFC1918 IPv4.**
Verified empirically against `content_issues`: `fd12:3456:789a::1` (IPv6 ULA),
`100.101.102.103` (CGNAT/Tailscale), `169.254.10.5` (link-local) and a public
helper IPv4 all pass clean. `remote-access/relay.py` takes an arbitrary helper
IPv4; on a Tailscale or IPv6 deployment the address is publishable today.
Fix: extend to `fd[0-9a-f]{2}:`, `fe80::`, `169\.254\.`, `100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.`.

**SF-4 (medium) — `check-publication.py:25` the `private-key` rule misses PGP
key blocks.**
`-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----` does not match
`-----BEGIN PGP PRIVATE KEY BLOCK-----` (verified: no issues reported). It also
misses a bare base64 OpenSSH key body pasted without armour
(`b3BlbnNzaC1rZXktdjEA...`, verified clean).
Fix: add `rb'-----BEGIN [A-Z0-9 ]*PRIVATE KEY( BLOCK)?-----'` and a rule for
the `b3BlbnNzaC1rZXktdjEA` base64 prefix.

**SF-5 (medium) — `check-publication.py:39` the `literal-secret` rule only
matches a whole-line shell assignment.**
The `(?m)^\s*...\s*$` anchoring means all of these pass clean (verified):
`{"password": "0123456789abcdef"}`, `password: hunter2hunter2`,
`PASSWORD="s3cretvalue" # relay`. The relay writes its bootstrap password into
`config.json` in exactly the first form, so the guard's own project's highest
value secret is in a shape the content rules do not see. The `path-not-reviewed`
default-deny is what actually stops it.
Fix: add a JSON/YAML variant:
`rb'''(?i)["']?(password|passwd|secret|token|api_key)["']?\s*[:=]\s*["'][^"'\r\n]{8,}["']'''`.

**SF-6 (medium) — `check-publication.py:36` the `mac-address` rule only matches
the colon form.** `a4-83-e7-11-22-33` and `a483.e711.2233` pass clean
(verified).
Fix: `rb'\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b|\b(?:[0-9a-f]{4}\.){2}[0-9a-f]{4}\b'`.

**SF-7 (medium) — `check-publication.py:19-21` `BAD_SUFFIX` omits several
archive and credential extensions.** Verified clean: `.bz2`, `.iso`, `.crt`,
and `.netrc` (which also escapes `BAD_COMPONENTS`). `.p8`, `.der`, `.jks`,
`.kdbx`, `.ovpn`, `.mobileconfig`, `.rar`, `.bak` are likewise absent.
Fix: extend the alternation; add `.netrc` and `.npmrc` to a filename blocklist
next to `BAD_COMPONENTS`.

**SF-8 (medium) — `check-publication.py:136` the `--staged` flag is parsed and
then discarded.**
`main()` calls `scan(history=args.history)`; `args.staged` is never read.
`scan(history=False)` reads the whole index via `git ls-files --stage`, so the
behaviour is fail-closed and matches the documented "checks the index" claim,
but a reader (and `docs/PUBLICATION-SAFETY.md:14`) reasonably believes the flag
selects a mode. `check-publication.py --history --staged` silently ignores
`--staged`.
Fix: either drop the flag or make it the explicit default with
`parser.add_mutually_exclusive_group()`.

**SF-9 (low) — `check-publication.py:69` applies `re.I` to every rule
unconditionally**, which weakens the intent of the case-sensitive patterns
(`AKIA`, `gh[pousr]_`, `eyJ`) into case-insensitive ones. This produces false
positives, not misses, so it is fail-closed, but the `test_forbidden_extensions_case_insensitive`
test name suggests case handling was meant to be per-rule.

**SF-10 (low) — `check-publication.py:107` re-shells `git cat-file -s` once per
blob per commit.** With `MAX_COMMITS = 2000` and ~385 paths that is up to
770,000 subprocess spawns in the worst case. On this 20-commit repo `--history`
took under a second; a pre-push on a large history would hang.
Fix: one `git cat-file --batch-check --batch-all-objects` call.

## safety/allowed-paths.txt

**SF-11 (positive, no action) — the allowlist is exact and current.**
Verified: 385 entries, 385 tracked files, zero tracked-but-unlisted, zero
listed-but-untracked, zero duplicates. There are no globs or directory
prefixes, so the "too broad allowlist entry" failure mode does not exist here.

**SF-12 (medium) — the allowlist approves research prose whose only content
protection is the regex set, and the regexes have the gaps in SF-3 to SF-7.**
Entries such as `research-archive/probe/N1-WIFI-20260913.md`,
`research-archive/probe/NETWORK-CHECKPOINT.md` and
`research-archive/CLAUDE.md` are free-form notes about network hardware and
sessions. An SSID, an IPv6 ULA, a `.local` hostname or a Wi-Fi passphrase in
any of those files publishes cleanly today (`wpa_passphrase=CorrectHorseBattery`
and `anika-mbp.local` both verified clean).
Fix: fixing SF-3/SF-5 covers most of it; add an SSID/`.local`-hostname rule and
require a second human review specifically for `*CHECKPOINT.md` edits.

**SF-13 (low) — `check-publication.py:91` `set(...splitlines())` silently drops
entries with trailing whitespace into never-matching keys.** Fail-closed, but a
paste with a trailing space produces a confusing `path-not-reviewed` on a file
the operator believes is approved.
Fix: `{line.strip() for line in ... if line.strip()}` plus an explicit reject on
lines that differ from their stripped form.

## safety/pre-commit, pre-push, install-hooks.sh

**SF-14 (medium) — `pre-push:3-6` matches the destination against two exact
strings, so legitimate equivalents are refused and the check gives a false
sense of coverage.**
`https://github.com/Sowyu/m5-azahi` (no `.git`), `ssh://git@github.com/...`, or
a configured remote using a `insteadOf` rewrite all hit the refusal branch.
Fail-closed, so not a hole, but the hook also never inspects the refs being
pushed (it ignores stdin entirely and scans `rev-list --all`), so a push to a
correct URL but a wrong branch is indistinguishable.
Fix: normalise the URL (strip trailing `.git`, accept both schemes) and log the
refs read from stdin into the receipt.

**SF-15 (low) — `install-hooks.sh` has no uninstall path and refuses to
re-enrol.** Line 7 aborts if `$guard` exists. Adding a reviewed path (which
`docs/PUBLICATION-SAFETY.md:44-52` says happens routinely) requires manual
`rm -rf .git/privacy-guard` first, which is exactly the state where a commit
slips through unguarded.
Fix: add an `--update` mode that diffs the tracked allowlist against the
installed one, prints the added paths, and requires a typed confirmation.

**SF-16 (low) — `install-hooks.sh:17` does not verify that `core.hooksPath` was
actually set**, nor that Git is new enough to honour it (`core.hooksPath`
requires Git 2.9). It prints success unconditionally.
Fix: `git config --local --get core.hooksPath` readback before the success line.

## safety/test-publication.py

**SF-17 (medium) — `test-publication.py:88-90` runs the scanner against the
*production* `allowed-paths.txt`, not a fixture.**
`check()` invokes `HERE/'check-publication.py'` with `cwd=self.root`, and
`POLICY` resolves relative to the script, so `GitTests` depends on the real
allowlist containing `README.md` and *not* containing `unknown.md`. Adding
`unknown.md` to the allowlist would silently turn
`test_force_added_unreviewed_file` (line 112) green while testing nothing.
Fix: add a `--policy PATH` flag to the scanner and point the tests at a
temporary fixture allowlist.

**SF-18 (low) — no test covers the regex gaps found in SF-3 to SF-7.**
`test_fake_secret_rules` (line 54) is a positive-only table: every sample is
constructed to match its rule. There are no negative-control cases proving the
rules catch realistic variants (`.bz2`, PGP armour, JSON password, dash MAC,
IPv6). A one-line variant per rule would have caught all five gaps.

---

## usb-driver/azahi-usb.service

**USB-1 (high) — no service hardening on a unit that runs a root shell script
that loads kernel modules.**
The `[Service]` block (lines 7-12) sets only `Type`, `ExecStart`,
`RemainAfterExit` and `TimeoutStartSec`. No `NoNewPrivileges`, no
`ProtectHome`, no `PrivateTmp`, no `ProtectSystem`, no `CapabilityBoundingSet`,
no `SystemCallFilter`, no `ProtectProc`. The script genuinely needs
`CAP_SYS_MODULE` and read access to `/opt/azahi-usb`, and nothing else.
Fix: `NoNewPrivileges=yes`, `ProtectHome=yes`, `PrivateTmp=yes`,
`ProtectSystem=strict`, `ReadOnlyPaths=/opt/azahi-usb`,
`CapabilityBoundingSet=CAP_SYS_MODULE CAP_SYS_ADMIN CAP_DAC_READ_SEARCH`,
`RestrictAddressFamilies=`, `SystemCallArchitectures=native`.

**USB-2 (medium) — `azahi-usb.service:3-4` the ordering does not express what
the unit actually gates.**
`Before=azahi-native-tunnel.service` covers exactly one consumer. Nothing
orders this unit before `network-online.target`, so anything else that waits
for network readiness runs before the USB NIC exists. `After=NetworkManager.service`
has no matching `Wants=`, so on a host where NM is not enabled the ordering
silently evaporates.
Fix: add `Before=network-online.target network.target`,
`Wants=NetworkManager.service`, and drop the single-consumer `Before=` or keep
both.

**USB-3 (medium) — no `ConditionKernelVersion` / no integrity condition,
despite the script hard-failing on both.**
`start-native-usb.sh:4` refuses a wrong kernel and line 9 verifies
`SHA256SUMS`; on failure systemd records a unit failure rather than a skipped
unit, which is noisier and, given `RemainAfterExit=yes` with no `Restart=`,
non-recoverable without manual intervention.
Fix: `ConditionKernelVersion=7.0.13-400.asahi.fc44.aarch64+16k` and
`ConditionPathExists=/opt/azahi-usb/SHA256SUMS` alongside the existing
`ConditionPathExists=/etc/azahi-usb-root`.

**USB-4 (low) — `azahi-usb.service` is not mentioned in
`usb-driver/README.md`.** The README (lines 17-21) documents only the initrd
courier and the transfer builders. The newest and by far most privileged
component in the directory, a root oneshot enabled at boot that insmods three
out-of-tree modules, has no entry.

## usb-driver/boot-stage.conf

**USB-5 (high) — `boot-stage.conf:3` executes an unverified root script at boot
and swallows its failure.**
`ExecStartPre=-/bin/bash /azahi-usb-stage.sh`. The leading `-` is deliberate
(line 2 explains it), but the target script itself is never integrity-checked;
only the payload it copies is (`boot-stage-v2.sh:18` verifies `SHA256SUMS`).
Anything that can write `/azahi-usb-stage.sh` into the initrd gets root
execution during `initrd-switch-root` with all errors discarded.
Fix: the drop-in should invoke a fixed absolute path under a verified directory
and the parent builder should record the script's own digest in the receipt.
`build-transfer-v6.py:97` already computes `receipt['assets']` for it, so the
digest exists but nothing checks it at runtime.

**USB-6 (medium) — the drop-in has no `[Unit]` header and no comment naming the
unit it patches.**
The file is three lines of `[Service]`. Only `build-transfer.py:72` reveals the
destination
(`etc/systemd/system/initrd-switch-root.service.d/usb-files.conf`). A drop-in
`ExecStartPre=` without a preceding empty `ExecStartPre=` appends to the
original unit's list, so this runs *after* whatever `initrd-switch-root.service`
already declares; that ordering is load-bearing and undocumented.
Fix: add a comment naming the unit and the append semantics.

## usb-driver/boot-stage.sh (v1) and boot-stage-v2.sh

Both have `set -euo pipefail`, both quote their variable expansions correctly.

**USB-7 (medium) — `boot-stage.sh` is a known-broken script still tracked,
still allowlisted, and still shipped inside the v4 and v5 images.**
It calls `findmnt` (line 6) and `mktemp` (line 11) through `PATH`, and the
initrd has neither, which is precisely the exit-127 failure that
`courier-vm-init.sh:15-20` reproduces on purpose. `build-transfer-fixed.py:72`
reuses v4's asset archive verbatim (`extra = v4parts['initrd'][INITRD_BYTES:]`),
so v5 also contains the broken v1 courier; only `build-transfer-v6.py:26`
substitutes v2. Nothing in `boot-stage.sh` itself says it is superseded.
Fix: add a first-line comment `# SUPERSEDED by boot-stage-v2.sh; retained only
to document the v4/v5 regression. Do not ship.`

**USB-8 (medium) — neither courier verifies the provenance of `SHA256SUMS`,
only that the payload matches it.**
`boot-stage-v2.sh:18` runs `sha256sum -c SHA256SUMS` where `SHA256SUMS` was
itself copied from the same untrusted `$source_dir` two lines earlier (line 16).
That detects bit rot and detects the corruption case the VM test exercises, but
it cannot detect a coherent substitution of both the payload and the manifest.
The same pattern recurs at `start-native-usb.sh:8` and
`install-native-startup.py:59`, and `PROGRESS.md` describes these as "checksum
verified".
Fix: embed the expected `SHA256SUMS` digest as a literal in the script (the
builder already knows it) and compare before using the file.

**USB-9 (low) — neither courier cleans up its staging directory on failure.**
`temporary=$(mktemp -d /run/azahi-usb-staging.XXXXXX)` at `boot-stage.sh:11` /
`boot-stage-v2.sh:13`; every `exit 1` after that point leaks the directory in
tmpfs, and `mv -T -n` failing (line 17 / line 19) leaves it populated with the module
payload.
Fix: `trap 'rm -rf "$temporary"' EXIT` immediately after the `mktemp`.

## usb-driver/start-native-usb.sh

Has `set -euo pipefail`. Variable expansions are quoted or inside `[[ ]]`.

**USB-10 (high) — `start-native-usb.sh:39-41` a `modprobe` loop under `set -e`
aborts the whole startup if any one stock module is absent.**
```
for module in apple-dart dwc3 xhci-plat-hcd usbnet cdc_ncm cdc_ether rndis_host; do
    modprobe "$module"
done
```
`rndis_host` and `cdc_ether` are commonly not built on hardened or trimmed
kernel configs. A single missing module aborts before any `insmod`, leaving the
machine with no USB host and, per `azahi-usb.service` having no `Restart=`, no
retry. The equivalent loop in `usb-tether-test.sh:128` has the same problem.
Fix: `modprobe -q "$module" || echo "optional module $module unavailable"`, and
hard-fail only on `apple-dart`, `dwc3` and `xhci-plat-hcd`.

**USB-11 (medium) — `start-native-usb.sh:33` insmods `./azahi_hpm_once.ko`
(underscores) while every other insmod uses the hyphenated build output.**
Lines 42-44 load `./phy-apple-t6050-usb2.ko`, `./azahi-usb-overlay.ko`,
`./dwc3-apple-t6050.ko`. `install-native-startup.py:20` also pins
`azahi_hpm_once.ko` with underscores, and `build.sh` never produces that file
at all (see USB-19). The naming inconsistency means nothing in the repo
demonstrates the file exists under that name.
Fix: settle on one convention and have `build.sh` emit it.

**USB-12 (medium) — `start-native-usb.sh` takes no lock, so two concurrent
invocations can double-insmod.**
`RemainAfterExit=yes` prevents systemd from re-running it, but a manual
`bash /opt/azahi-usb/start-native-usb.sh` alongside the unit races the
`count=0`/`count=3` module census at lines 11-13.
Fix: `exec {lock}>/run/azahi-usb.lock; flock -n $lock || exit 0` at the top.

**USB-13 (low) — `start-native-usb.sh:5` reads `/etc/azahi-usb-root` without
validating it is a UUID.** Safe because the value is compared to `findmnt`
output, but an empty file makes the comparison succeed against an empty
`findmnt` result on an unusual mount setup.
Fix: `[[ $expected_uuid =~ ^[0-9a-f-]{36}$ ]] || exit 1`.

**USB-14 (low) — `start-native-usb.sh:4` is a bare compound test with no
message.** Under `set -e` a wrong kernel exits 1 silently; every other guard in
the file prints a reason.

## usb-driver/usb-tether-test.sh

**USB-15 (medium) — the script has no `set -e` or `set -o pipefail` at file
scope; only `set -u` inside `main()` (line 83).**
Error handling is entirely manual `|| return N`, and several commands are
unchecked: `dmesg -w >> "$LOG" 2>&1 &` (line 126) and the `local profile=...`
assignment (line 148). The file-scope functions (`say`, `run`, `verify_bundle`,
`candidate_hub`) run with no `set -u` when sourced, which is exactly how
`test-usb-runner.py` exercises them, so the tests run under laxer settings than
production.
Fix: `set -uo pipefail` at the top of the file so sourced use matches, keeping
the explicit `|| return` style instead of `set -e`.

**USB-16 (medium) — `usb-tether-test.sh:89` the published script can never
run, and offers no supported way to supply the missing value.**
`[[ $(findmnt -n -o UUID /) = PRIVATE-LINUX-FSUUID-NOT-CONFIGURED ]]`. The
redaction is deliberate and `usb-driver/README.md:12` says so, but unlike
`start-native-usb.sh:5`, which reads the UUID from `/etc/azahi-usb-root`, there
is no file or environment override. A downstream user must edit the tracked
source, which invalidates the `SHA256SUMS` entry for `usb-tether-test.sh` and
so fails `verify_bundle` at line 102.
Fix: read the expected UUID from `${AZAHI_ROOT_UUID:?}` or `/etc/azahi-usb-root`
so the file itself stays unmodified and manifest-clean.

**USB-17 (low) — `usb-tether-test.sh:148` the "unique" temporary profile name
does not include the random suffix it was meant to.**
`local profile="azahi-usb-${LOG##*.}-$BASHPID"`. `LOG` is
`/root/usb-test.XXXXXX.log`, so `${LOG##*.}` strips everything up to the last
dot and yields the literal string `log`. Every run produces
`azahi-usb-log-<pid>`. Uniqueness survives only by PID reuse being unlikely.
Fix: `${LOG%.log}` then `##*.`, or capture the suffix separately from `mktemp`.

**USB-18 (low) — `usb-tether-test.sh:95` writes its log to `/root` while the
script's own banner (line 125) says "Only logs and a temporary NetworkManager
profile are intended".** Consistent, but `/root/usb-test.*.log` files
accumulate with no rotation or cleanup and contain full `dmesg -w` output.

## usb-driver/build.sh

**USB-19 (medium) — `build.sh` does not build `azahi_hpm_once.ko`, which
`install-native-startup.py:20` pins and `start-native-usb.sh:30` loads.**
The `mods` array (lines 56-60) covers three modules; `hpm-once.c` lives under
`pd-backport/` and no script in the tree compiles it. There is no single build
entry point that produces the full set the installer requires.
Fix: add the fourth module to `build.sh`, or document the two-step build in
`docs/BUILD-AND-TEST.md`.

**USB-20 (medium) — hard-coded macOS Homebrew toolchain paths with no override.**
`build.sh:11-12` `cc=/opt/homebrew/opt/llvm/bin/clang`,
`ld=/opt/homebrew/opt/lld/bin/ld.lld`. Same in `input-driver/build-module.sh:6-7`,
`nvme-driver/build-modules.sh:13-14` and `nvme-driver/build-modules.sh:51`
(`/opt/homebrew/opt/llvm/bin/llvm-nm`), and `usb-driver/test-usb-candidate.py:24`
(`LLVM = Path("/opt/homebrew/opt/llvm/bin")`).
`docs/BUILD-AND-TEST.md:5` does disclose "Homebrew LLVM/LLD", so this is
documented, not hidden. It is still an unnecessary hard dependency.
Fix: `cc=${CC:-/opt/homebrew/opt/llvm/bin/clang}` throughout.

**USB-21 (medium) — `build.sh:88` and the other builders use `shasum -a 256`
while every runtime script uses `sha256sum`.**
`shasum` is a Perl script present by default on macOS and absent on many Linux
images; `sha256sum` is coreutils and absent on stock macOS. Splitting them by
host is defensible, but `test-usb-runner.py:58` then has to inject a
`sha256sum() { shasum -a 256 "$@"; }` shim to test the runtime script, which
makes the test itself macOS-dependent.
Fix: pick one and provide the shim in one place.

**USB-22 (low) — `build.sh` never cleans `stage/` or `deliver/`.** A module
removed from the `mods` array leaves a stale `.ko` in `stage/`; only files named
in the `shasum` list at line 88 are covered, so the stale file ships silently
if it is later added back to a copy list.

**USB-23 (low) — `build.sh` does not check for `dtc`, `fdtdump`, `zstd`, or
`shasum` before starting**, unlike `usb-tether-test.sh:120`, which explicitly
checks its tools before touching hardware.

## usb-driver/install-native-startup.py

**USB-24 (high) — `install-native-startup.py:41,54` reads three of four modules
from a hard-coded `/root/usb-candidate`, contradicting its own documented
`STAGING_DIRECTORY` argument.**
```python
path = stage / name if name == 'azahi_hpm_once.ko' else Path('/root/usb-candidate') / name
```
The docstring (line 4) says `Usage: python3 script.py STAGING_DIRECTORY
EXPECTED_ROOT_UUID`. In fact the staging directory supplies exactly one module
plus two text files; the other three come from a private absolute path that
exists on one machine. An operator who assembles a complete staging directory
gets an opaque `RuntimeError('Module checksum failed: ...')` from a path they
never named.
Fix: read all four from `stage`, and pass `/root/usb-candidate` as the argument.

**USB-25 (high) — the two artifacts actually executed as root at boot are the
only ones not pinned.**
`PINS` (lines 16-21) covers the four `.ko` files. `start-native-usb.sh` and
`azahi-usb.service` get only `is_symlink()`/`is_file()` checks (lines 44-47)
and a `bash -n` syntax check (line 48). The kernel modules, which cannot be
loaded without the script, are verified; the script that loads them is not.
`SHA256SUMS` is then generated *from whatever was copied* (line 59), so
`start-native-usb.sh:9`'s runtime `sha256sum -c` cannot detect a substitution
made at install time.
Fix: add both files to `PINS`.

**USB-26 (medium) — hard-coded module digests make the installer unusable by
anyone who rebuilds.**
`docs/BUILD-AND-TEST.md:44` acknowledges "private artifact hashes will not
match locally rebuilt public scripts/modules", but this script has no
`--pins-from FILE` or `--accept-manifest` path, so there is no supported route
from a local build to an install. Combined with USB-24 the script is
single-machine-only.
Fix: accept a signed or operator-confirmed manifest path.

**USB-27 (medium) — no rollback on partial install.**
Lines 52-69 create `/opt/azahi-usb`, write the unit, write `/etc/azahi-usb-root`
and run three `systemctl` calls with `check=True`. A failure at `systemd-analyze
verify` (line 64) or `enable` (line 66) leaves all three destinations present,
and line 38's `Installation already exists; no overwrite` then blocks every
retry. The `backup` directory (line 50) records only that the destinations were
absent.
Fix: `try/except BaseException` that unlinks the three destinations before
re-raising.

**USB-28 (low) — `install-native-startup.py:25` indexes `sys.argv` directly**,
producing `IndexError` instead of a usage message for a root-only tool.

## usb-driver/test-native-startup.py

Passes (8 tests). It runs the real production script with path rewriting, which
is a good design. Two mocks defeat the checks they appear to cover.

**USB-29 (medium) — `test-native-startup.py:46` the `readlink` mock hard-codes
the very string the script is matching on, so every right-port test is
tautological.**
```
readlink() { [[ -e "$2" ]] && echo /fake/382280000.usb/xhci/usb1; }
```
`start-native-usb.sh:16,47` test `[[ $(readlink -f "$hub") != */382280000.usb/* ]]`.
The mock returns a path containing `382280000.usb` for *any* existing node, so
`test_preserve_live` (line 74) and `test_fresh_success_order` (line 86) prove
only that the mock's own output matches the pattern the mock was written to
match. If the driver were ever bound to a different controller address, or the
glob in the script were wrong, both tests would still pass.
Fix: make the mock echo a path derived from `$2` and build the fixture so the
right-port and wrong-port hubs differ; add a case where `readlink` returns
`/fake/382180000.usb/...` and assert the script refuses.

**USB-30 (medium) — `test-native-startup.py:44` stubs `grep` to unconditionally
return 0, so the model guard is never exercised.**
`grep() { return 0; }` disables `start-native-usb.sh:5`
(`grep -zFxq 'apple,j714s' /proc/device-tree/compatible`). No test asserts the
script refuses a wrong model, even though a wrong-root test exists.
Fix: write a real `proc/device-tree/compatible` fixture in the temp root and
drop the `grep` mock; add a `wrong_model=True` case.

**USB-31 (low) — `test-native-startup.py:45` the `sha256sum` mock returns
`$HASH_BAD` and logs a token**, so `test_identity_hash_guards` only proves that
a nonzero exit from `sha256sum` aborts the script under `set -e`. The manifest's
format, its file list, and the real `sha256sum -c` behaviour are untested.

## usb-driver/test-usb-runner.py

Passes (19 tests), and the sysfs fixture tests (lines 96-117) are genuinely
substantive.

**USB-32 (medium) — `test-usb-runner.py:145` the `findmnt` mock returns the
redaction placeholder, coupling every `dry_mocks` test to the fact that the
script is redacted.**
```
findmnt() { echo PRIVATE-LINUX-FSUUID-NOT-CONFIGURED; }
```
`usb-tether-test.sh:89` compares against the same literal. The moment an
operator substitutes a real UUID (which USB-16 forces them to do by editing the
file), five tests break for reasons unrelated to any behaviour change.
Fix: after implementing USB-16, set the env var in the mock preamble instead.

**USB-33 (low) — `test-usb-runner.py:44` `test_https_success` is tautological.**
```python
self.assertEqual(self.shell('NEWIF=usb0; curl() { return 0; }; https_test').returncode, 0)
```
`https_test` is a single `run curl ...`. Mocking `curl` to return 0 and
asserting 0 asserts nothing about the function. The adjacent
`test_https_failure_and_binding` (line 37) is the useful one because it checks
the argument vector.
Fix: delete it, or assert the success path also appends to `$LOG`.

**USB-34 (low) — `test-usb-runner.py:58` requires `shasum`**, which is not
present on minimal Linux images. See USB-21.

## usb-driver/test-usb-glue.py

Passes (3 tests). Compiles the real `dwc3_apple_init` body against a mock
harness, which is a real control-flow check.

**USB-35 (low) — `test-usb-glue.py:107` `assertNotIn('module_param(force', source)`
is trivially evaded.** `module_param_named(force, ...)`, `module_param(force_host, ...)`
with different spacing, or a rename all pass. The intent (no force override
parameter) deserves a parse, not a substring.

**USB-36 (low) — `test-usb-glue.py:14-22` `function()` walks braces with no
bound**, so an unbalanced source raises `IndexError` at an opaque offset
instead of reporting the malformed function. Same helper is reused in
`input-driver/test-power-request.py` in spirit.

**USB-37 (low) — hard-coded `/usr/bin/cc`** at `test-usb-glue.py:89` and
`test-transfer-fixed.py:54`. Works on this host; fails where `cc` is at
`/bin/cc` or only `gcc` exists. Note the inconsistency: these two use `cc`,
while `input-driver/test-power-request.py` and
`nvme-driver/test-root-write-policy.sh` hard-code `clang` and consequently fail
here.

## usb-driver/test-usb-candidate.py

**USB-38 (medium) — cannot run from a clone; fails at import, not with a skip.**
Line 19 `from m1n1.adt import load_adt` after inserting `ROOT/pylib` and
`ROOT/proxy-kit/proxyclient` into `sys.path`; neither directory exists in the
repository. Even past that it needs `adt-real-t6050.bin` (line 52),
`t6050-j714s-native-rootguard.dtb` (line 22), the devel headers under the
gitignored `input-driver/build/` (line 21), the built `stage/*.dtbo` (line 58)
and Homebrew `llvm-readelf`/`llvm-nm` (line 24).
`docs/BUILD-AND-TEST.md:38` lists it under "requiring private inputs", so this
is disclosed. The defect is the failure mode: a bare `ModuleNotFoundError`
rather than `raise unittest.SkipTest('requires private fixtures: ...')`.
Fix: guard the imports and raise `SkipTest` naming each missing artifact.

**USB-39 (medium) — `build.sh:90` makes the private-fixture test a hard build
dependency.** `python3 test-usb-candidate.py` runs inside `build.sh`, so the
build cannot complete anywhere the private fixtures are absent, even to produce
the modules that would populate `stage/`.

**USB-40 (low) — bare `assert` in `setUpClass` (lines 53, 61)** for the ADT
model and the base DTB digest. `python3 -O` removes both, and this is the only
check that the baseline DTB is the intended one.

## usb-driver builders: build-transfer.py / -fixed / -v6

These are a chain, not duplicates: `-v6` loads `-fixed` (line 12) which loads
`build-transfer.py` (line 18), each reusing the previous one's helpers. The
duplication concern is narrower than "three copies".

**USB-41 (medium) — `build-transfer.py` remains directly runnable and will
happily write the known-bad v4 image.**
`docs/BUILD-AND-TEST.md:46-48` and `usb-driver/README.md:20` both say "Never
install v4", but `if __name__ == '__main__'` (lines 134-141) has no guard: the
only precondition is that the output does not already exist. The regression it
documents (initrd length != the loader's `INITRD_BYTES`) is caught by
`build-transfer-fixed.py:38`, not by `build-transfer.py` itself.
Fix: add `sys.exit('v4 is a documented regression; use build-transfer-v6.py')`
to the `__main__` block, keeping the module importable for its helpers.

**USB-42 (medium) — module-level `runpy.run_path` couples import to disk
fixtures and to running arbitrary builder code.**
`build-transfer.py:31-33` executes three other scripts at import; `-fixed:18`
and `-v6:13` chain further. Any test that imports the top of the chain
transitively executes five files. Today all five guard their side effects
behind `if __name__ == '__main__'`, so nothing is written, but this is an
invariant no test asserts, in scripts that write multi-megabyte boot images.
Fix: replace `runpy.run_path` with `importlib.util.spec_from_file_location`,
which is what `test-relay.py:8` and `test-proxy-hpm.py:9` already use.

**USB-43 (medium) — the v4/v5/v6 tests error out with `FileNotFoundError`
rather than skipping.**
`test-transfer-v6.py` and `test-transfer-fixed.py` both fail in `setUpClass`
with "Ran 0 tests"; `test-courier-vm.py` fails in `main()`. All three need
gitignored `.bin` fixtures. Disclosed in `docs/BUILD-AND-TEST.md:29`, but the
output does not tell the reader which fixture is missing or that it is
expected.
Fix: `raise unittest.SkipTest(f'requires private fixture {V["OUTPUT"]}')`.

**USB-44 (low) — `build-transfer-fixed.py:32` parses `INITRD_BYTES` out of C
source with a regex** (`^#define INITRD_BYTES (\d+)U$`). Fragile against a
whitespace change or a hex literal, and `[1]` on a `None` match gives
`TypeError` instead of a diagnosis.

**USB-45 (low) — hard-coded dated output filenames** (`build-transfer.py:20`,
`-fixed:20`, `-v6:16`) with an `assert not OUTPUT.exists()` precondition, so a
rebuild requires deleting the file by hand. No `--output` flag anywhere.

## usb-driver/proxy-test-v6.py

**USB-46 (high) — safety bounds guarding writes into live device RAM are plain
`assert` statements, removed by `python3 -O`.**
```python
assert BASE + initrd_offset <= address < address + len(chunk) <= BASE + initrd_offset + F['INITRD_BYTES']
interface.writemem(address, chunk)
```
(lines 103-104). The same applies to the identity checks at lines 74-89
(chip ID, base address, bootargs revision, ADT model, "no other CPU is alive"),
the payload pre-verification at line 98, and the input validation at line 40.
Under `-O` every one of those disappears and the script writes 70 MB into an
unverified physical address on an attached Mac.
Fix: convert every precondition on this path to
`if not cond: raise RuntimeError(...)`. This applies equally to
`build-native-ssdroot.py`, `mk-blob-header.py`, `strip-symbols.py` and the
builder `inspect()` functions, but it is severe here because the consequence is
a hardware write.

**USB-47 (medium) — `proxy-test-v6.py:30` hard-codes a redacted serial device
with no override.** `PORT = '/dev/cu.usbmodemPRIVATE'`, macOS-only naming, and
`--run` has no `--device` flag (unlike `proxy-hpm.py:308`, which does). The
script cannot be run even by someone with the right hardware without editing
it.
Fix: add `--device` mirroring `proxy-hpm.py`.

**USB-48 (low) — `proxy-test-v6.py:57` inserts `ROOT/pylib` and
`ROOT/proxy-kit/proxyclient`**; neither exists in the repository.

## usb-driver/courier-vm-init.sh and test-courier-vm.py

**USB-49 (medium) — `courier-vm-init.sh:19` asserts an exact exit status of
127, so any other missing-binary failure passes for the wrong reason.**
`[[ $old_status == 127 && ! -e /run/azahi-usb-20260913 ]]`. The VM is
deliberately built without `mktemp` (line 15 asserts its absence), but `findmnt`
missing, `cp` missing or a bash startup failure all yield 127 too. Line 14
sha256sums `findmnt` to show it exists, which mitigates but does not close it.
Fix: grep `/run/old-courier.log` for the specific `mktemp: command not found`.

**USB-50 (low) — `courier-vm-init.sh:40` mounts ramfs over `/run`, hiding
`/run/saved-good`** from the earlier preservation check, and the script never
verifies that the preserved copy survived the whole run.

**USB-51 (low) — `test-courier-vm.py:27` leaves its work directory behind
permanently.** `tempfile.mkdtemp` with no cleanup; the docstring says this is
deliberate ("retained for inspection"), but each run leaks a kernel image plus a
70 MB initrd into `/tmp`.

**USB-52 (low) — `test-courier-vm.py` uses bare `assert` throughout** (lines 24,
29, 55, 56), including the pinned kernel digest. `-O` makes the whole test a
no-op that exits 0.

## usb-driver/mk-blob-header.py, strip-symbols.py

**USB-53 (low) — both rely exclusively on `assert` for their correctness
checks.** `mk-blob-header.py:12` validates the FDT magic and total length;
`strip-symbols.py:14-16` validates that exactly one `__symbols__` node was
removed and `__local_fixups__` survived. Under `-O` `strip-symbols.py` becomes
`cat` and `mk-blob-header.py` embeds arbitrary bytes as a device-tree overlay.
Fix: `if magic != 0xd00dfeed: raise SystemExit(...)`.

**USB-54 (low) — `strip-symbols.py:13` matches a literal one-tab indentation**
(`\n\t__symbols__ \{\n.*?\n\t\};\n`). A `dtc` version that indents differently
turns the tool into a silent no-op, caught only by the assert above it (and not
at all under `-O`).

---

## usb-driver/pd-backport/proxy-hpm.py

The transport poisoning design (lines 61-119) and the register allowlist
(line 123) are solid; the two-write SSPS path is tightly bounded. Findings are
portability and hygiene.

**PD-1 (medium) — `proxy-hpm.py:47-49` hard-codes `clang` and `-dynamiclib`,
making the module macOS-only and unimportable elsewhere.**
`build_bridge()` runs `clang ... -dynamiclib -o bridge.dylib`. On Linux both the
binary and the flag are wrong. This is what makes `test-proxy-hpm.py` error out
in `setUpClass` here (`FileNotFoundError: 'clang'`), even though every test in
that file except one is pure host logic that would otherwise run.
Fix: `os.environ.get('CC', 'cc')` and pick `-dynamiclib`/`-shared` plus
`.dylib`/`.so` from `sys.platform`.

**PD-2 (medium) — `proxy-hpm.py:45` writes build output inside the source tree
and never cleans it up.**
`tempfile.mkdtemp(prefix='host-bridge.', dir=HERE / 'build')`. Every run and
every `test-proxy-hpm.py` invocation leaks a directory into
`usb-driver/pd-backport/build/`. Gitignored, so it will not be published, but a
test that permanently grows the checkout is a scope violation for a repository
whose stated policy is that nothing new appears without review. I reproduced
this with `test-spmi4.sh` and removed the resulting directory.
Fix: `tempfile.TemporaryDirectory()` under the system temp dir, loaded and then
released after `CDLL`.

**PD-3 (medium) — `proxy-hpm.py:314` requires the device path to start with
`/dev/cu.usbmodem`**, a macOS-only naming convention. A Linux operator with
correct hardware is refused with "Explicit proxy serial device and fresh
private receipt required".
Fix: accept `/dev/tty*` and `/dev/cu.*` and validate with
`os.path.exists` plus a character-device check.

**PD-4 (low) — `proxy-hpm.py:396` writes the receipt inside `finally`**, so
an `OSError` there (missing parent directory, existing file created by a
concurrent run) replaces the original exception and hides the real failure of a
hardware diagnostic.
Fix: wrap the receipt write in its own `try/except` that prints the failure and
re-raises the original.

## usb-driver/pd-backport/test-proxy-hpm.py

The `FakeHPM` tests are the strongest in the repository: they assert exact
transaction sequences and, crucially, assert the *absence* of any `op == 0`
write on every refusal path (lines 132, 152, 166, 175, 211, 248).
`test_disconnected_s0_refuses_every_changed_precondition` sweeps all 32 status
bits. No tautologies found.

**PD-5 (medium) — the whole file is gated on `build_bridge()` in `setUpClass`
(line 99), so a missing clang skips 15 pure-logic tests.**
Only three tests (`test_ffi_*`) actually need the compiled bridge. On this host
all 18 error out.
Fix: move `build_bridge()` into a separate `TestCase` class, or lazily build it
inside the three FFI tests with `SkipTest` on failure.

**PD-6 (low) — `test-proxy-hpm.py:220` needs `pylib`/`proxy-kit/proxyclient`
and `adt-real-t6050.bin`**, none of which exist in a clone, and imports them
mid-test rather than skipping.

## usb-driver/pd-backport/test-spmi4.sh

**PD-7 (medium) — `test-spmi4.sh:7` defaults to `clang` and
`usb-driver/pd-backport/README.md:110` documents it as "Clang with
AddressSanitizer", but it builds and passes cleanly with `CC=gcc`.**
Verified: `CC=gcc sh test-spmi4.sh` passes all checks. The default therefore
excludes gcc-only hosts for no technical reason.
Fix: `"${CC:-cc}"`.

**PD-8 (low) — `test-spmi4.sh:6` leaks a build directory into the source tree
on every run** (`mktemp -d "$PWD/build/host-transport.XXXXXX"`), retained
deliberately per line 11 but never garbage-collected. Same class as PD-2.

**PD-9 (low) — `test-spmi4.sh:3` sets `-eu` without `pipefail`.** No pipes
today, so inert; noted only because the sibling shell scripts do set it.

---

## ramroot/mkcpio.py

**RR-1 (medium) — `mkcpio.py:103` splits manifest lines on whitespace, so any
path or symlink target containing a space is silently mis-parsed.**
`t = ln.split()`. A `file /etc/my config.txt src 0644` line becomes a five-field
entry and writes the wrong mode; `slink /a/b /target with space` silently
truncates the target to `/target`. There is no quoting mechanism and no arity
check, so a short line raises a bare `IndexError` naming no line number.
Fix: `shlex.split(ln)` plus an explicit arity check per kind that reports the
offending line.

**RR-2 (medium) — `mkcpio.py:41,72` use `assert` for the two invariants that
prevent a corrupt archive.**
Line 41 enforces the newc 4 GiB per-file limit; line 72 catches a short read.
Under `python3 -O` a 4 GiB+ file produces a nine-hex-digit size field that
shifts every subsequent header by one byte, and a truncated source produces an
archive whose declared sizes exceed its contents. Both failures are silent and
only manifest at boot. `probe/build-native-ssdroot.py:82` imports this Writer
to build a real boot image.
Fix: `raise ValueError` in both places.

**RR-3 (low) — `mkcpio.py:106` the `dir` branch calls
`ensure_parents(w, t[1] + "/x", seen)`** with a fake `/x` leaf to reuse the
parent logic. It works, but the key-space agreement between `ensure_parents`
and the `dir` branch is maintained only by the comment at line 89.

**RR-4 (low) — no hardlink support and `nlink` is a constant** (2 for
directories, 1 for files). Harmless for the kernel's newc reader; would corrupt
a round-trip through `cpio -i`.

## probe/build-native-ssdroot.py

**PB-1 (medium) — `build-native-ssdroot.py:181` bakes a redaction placeholder
into the kernel command line with no override.**
`bootargs.replace('root=/dev/loop0', 'root=PARTUUID=PRIVATE-LINUX-PARTUUID-NOT-CONFIGURED')`.
The published builder therefore produces an unbootable image by construction,
and there is no argument or environment variable to supply the real PARTUUID.
Disclosed in `docs/BUILD-AND-TEST.md:51-53`, but as with USB-16 the only route is
to edit the tracked file.
Fix: `os.environ['AZAHI_ROOT_PARTUUID']` with a clear error when unset.

**PB-2 (medium) — every integrity pin in the file is a bare `assert`.**
Lines 55 (source image digest), 66 (stock initrd match), 80 (DTB digest), 109
(busybox digest), 111 (ELF magic and machine type), 172 (size bound), 176 and
179 (no forced-root config leaked into the image). `python3 -O` removes all of
them and the script writes an unverified boot image anyway.
Fix: a `check(cond, message)` helper that raises.

**PB-3 (low) — hard-coded dated output name and a `assert not OUTPUT.exists()`
precondition** (lines 18, 53), so any rebuild needs a manual `rm`. No CLI at all
(`main()` takes no arguments).

**PB-4 (low) — hard-coded private artifact paths** at lines 54, 56, 57, 79, 108:
`native-input-v2-20260906.bin`, `initramfs-asahi.img`,
`ramroot/work/ramroot.cpio.zst`, `t6050-j714s-native-rootguard.dtb`,
`probe/vendor/ssdboot/bin/busybox.static`. None are in the repository and the
first failure is a `FileNotFoundError` with no explanation.

---

## input-driver/test-power-request.py

**ID-1 (high) — `test-power-request.py:59` hard-codes `clang`, so one of the
four tests `README.md:75` promises "with Python 3, Bash and a C compiler
available" fails on any host without clang.**
Confirmed: `FileNotFoundError: [Errno 2] No such file or directory: 'clang'`.
The test's own harness is portable C11; `test-usb-glue.py:268` compiles an
equivalent harness with `/usr/bin/cc` and passes here.
Fix: `os.environ.get('CC', 'cc')`.

**ID-2 (low) — the file has no `if __name__ == '__main__'` guard**; importing
it compiles and executes a binary as a side effect.

**ID-3 (low) — `test-power-request.py:8-9` locates the function by substring
index** and raises `ValueError: substring not found` if `dchid_reset_interface`
is renamed, with no indication that the test file needs updating.

## input-driver/build-module.sh

Has `set -euo pipefail`, quoted expansions.

**ID-4 (low) — writes to `build/` without `mkdir -p`** (line 26 onward), unlike
`usb-driver/build.sh:16` which does. A fresh checkout fails on the first
`-o build/dockchannel-hid.o`.

**ID-5 (low) — depends on `build/modpost` (line 27) with no existence check**,
unlike `usb-driver/build.sh:13` which has `test -x "$modpost"`.

## nvme-driver/build-modules.sh

Has `set -euo pipefail`, quoted expansions, and a proper usage branch.

**NV-1 (medium) — `build-modules.sh:51-52` requires `rg` (ripgrep) for the
export-table verification**, an optional third-party tool not mentioned in
`docs/BUILD-AND-TEST.md`. `grep -q` would do the same job.
Fix: replace both `rg -q` calls with `grep -q`.

**NV-2 (medium) — `build-modules.sh:19` hard-codes `$PWD/build/...` in the
include path even when building the `rootguard` variant into
`build-rootguard`.**
```
-I "$PWD/build/linux-7.0.13/drivers/nvme/host"
```
`$output` is `build-rootguard` in that mode, but the header include still points
at `build`. If the two trees ever diverge the rootguard build silently compiles
against the readonly variant's headers.
Fix: use `$output` or a separate explicit `sources=` variable.

**NV-3 (low) — hard-coded Homebrew `llvm-nm`** at line 51 (see USB-20), and
`shasum` at line 46 (see USB-21).

## nvme-driver/test-root-write-policy.sh

**NV-4 (high) — `test-root-write-policy.sh:6` hard-codes `clang`, so the second
of the four README-promised tests fails on a gcc-only host.**
Confirmed: `clang: command not found`. The C file compiles with gcc's
`-fsanitize=undefined,address` equally well; the sibling `test-spmi4.sh` already
parameterises this as `"${CC:-clang}"`.
Fix: `"${CC:-cc}"`.

**NV-5 (low) — the test binary is retained in `$TMPDIR` forever** (line 4-8,
`mktemp -d`, no trap). Deliberate per line 9, but every invocation leaves an
ASan-instrumented executable behind.

---

## Cross-cutting

**BT-1 (high) — `docs/BUILD-AND-TEST.md:9-14` and `README.md:75-82` promise
four host-runnable tests; two of the four fail on a host that has gcc but not
clang.**
`input-driver/test-power-request.py` (ID-1) and
`nvme-driver/test-root-write-policy.sh` (NV-4) both hard-code `clang`, while
`test-usb-runner.py` and `test-usb-glue.py` pass. The docs say "a C compiler",
not "clang". `docs/BUILD-AND-TEST.md:33` further reports that all four passed in
"the sanitized public clone" on 2026-09-13, which is true only on a macOS or
clang-equipped host.
Fix: change both to `${CC:-cc}` (one-line change each), or amend the docs to
say clang is required.

**CC-1 (medium) — pervasive use of `assert` for validation across the Python
tooling.**
Affected: `proxy-test-v6.py` (hardware write bounds, USB-46),
`build-native-ssdroot.py` (all integrity pins, PB-2), `mkcpio.py` (archive
invariants, RR-2), `mk-blob-header.py`, `strip-symbols.py`,
`test-courier-vm.py`, and all three `build-transfer*.py` `inspect()` functions.
`python3 -O` turns each of these into a no-op. In several cases the assert is
the *only* check standing between the script and a corrupt boot image or a
device-memory write.
Fix: keep `assert` for internal invariants only; use `raise` for anything that
validates external input or gates a destructive action.

**CC-2 (medium) — tests error out rather than skip when private fixtures are
absent.**
`test-usb-candidate.py`, `test-transfer-fixed.py`, `test-transfer-v6.py`,
`test-courier-vm.py`, `test-proxy-hpm.py` and `test-relay.py` all produce
`ModuleNotFoundError` / `FileNotFoundError` tracebacks. `docs/BUILD-AND-TEST.md`
correctly says they need private inputs, but a reader running the suite cannot
distinguish "expected, needs fixture X" from "broken".
Fix: a shared `require(path_or_module, reason)` helper raising
`unittest.SkipTest`.

**CC-3 (low) — inconsistent compiler invocation across seven scripts.**
`/usr/bin/cc` (`test-usb-glue.py`, `test-transfer-fixed.py`), bare `clang`
(`test-power-request.py`, `test-root-write-policy.sh`, `proxy-hpm.py`),
`${CC:-clang}` (`test-spmi4.sh`), `/opt/homebrew/opt/llvm/bin/clang`
(`build.sh`, `build-module.sh`, `build-modules.sh`). Three conventions for the
same job.
Fix: standardise on `${CC:-cc}` for host tests and a single overridable
`$CROSS_CC` for kernel module builds.

**CC-4 (low) — no script anywhere writes outside its stated scope.**
Checked every root-running script for out-of-scope writes. `persist.py` writes
`/var/lib/azahi-remote`, two unit files and one NM profile as documented;
`install-native-startup.py` writes `/opt/azahi-usb`, one unit and
`/etc/azahi-usb-root` as documented; `bootstrap.py` writes only under `/run`;
both couriers write only under `/run`. The only stray writes are into the
source tree from host tests (PD-2, PD-8) and log/temp accumulation in `/root`
and `$TMPDIR` (USB-18, NV-5). Recorded here as a negative result.
