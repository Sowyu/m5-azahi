# Publication safeguards

The private workspace and public clone now use default-deny `.gitignore`
policies. Existing tracked files are unaffected; no new file is automatically
eligible for publication. This is the first layer, not a security boundary.

## Active local enforcement

`safety/install-hooks.sh` installs independent copies of the scanner and exact
path allowlist under `.git/privacy-guard`. Installed hooks use those copies,
not whichever scanner happens to be checked out in the working tree.
The installer refuses to overwrite an existing installed policy.

- Pre-commit checks the **index**, not the working tree.
- Pre-push checks the index and **every local reachable commit**, including
  deleted historical secrets, before sending data.
- Only the intended GitHub repository is accepted as the push destination.
- Unknown paths fail closed, even after `git add -f`.
- Images, archives, device dumps, firmware, keys, logs and database formats
  are blocked by path/type rules. Symlinks and submodules are rejected.
- Files must be UTF-8 text without binary control bytes, at most 2 MiB each;
  source trees are capped at 12 MiB and history at 2,000 commits per scan.
- Content checks reject common credentials, device UUIDs/ECIDs, personal home
  paths, LAN addresses, serial-port identities and upload capabilities.
- Diagnostics identify the rule and path, never the matched secret value.

Run the synthetic regression suite with:

```sh
python3 safety/test-publication.py
```

For read-only audits:

```sh
python3 safety/check-publication.py --staged
python3 safety/check-publication.py --history
```

## Adding source later

Do not automatically regenerate the installed allowlist from untracked files.
Review every new path and its content, update the tracked policy, then explicitly
review/re-enroll the independent local policy. Ordinary source edits to already
approved paths still undergo content checks. No blanket exceptions for archives.

Hooks are installed in this public clone; Git does not automatically install
them in new clones. New clones require explicit setup after code review.

The courier-v6 update explicitly reviewed and added exactly five source paths:
`boot-stage-v2.sh`, `build-transfer-v6.py`, `courier-vm-init.sh`,
`test-courier-vm.py`, and `test-transfer-v6.py` under `usb-driver/`.
The prior installed policy was preserved locally before enrolling only those
paths. Hooks stayed enabled and continue to scan their contents and history.
The subsequent RAM handoff also explicitly enrolled `usb-driver/proxy-test-v6.py`
after redacting its serial-port identity. The prior policy was preserved first;
no log, boot image or identity receipt was added.

## Limits

The subsequent PD feasibility audit explicitly enrolled ten source/provenance
paths under `usb-driver/pd-backport`: README, host-only compile checker, source
checksum manifest, and seven verbatim files from a pinned public Asahi commit.
The independent installed allowlist was backed up before adding only those
paths. No objects, loadable modules, raw diagnostics or hardware dumps were
enrolled. Existing content and complete-history checks remain enabled.

The generation-4 follow-up separately reviewed and enrolled only
`usb-driver/pd-backport/audit-spmi4.py` and `no-tbt-switch.patch`, again preserving
the previous installed allowlist first. The audit contains derived constants
and fixture hashes, not the private fixtures, images or raw disassembly. The
patch is against already-public GPL driver sources and is compile-only.

These controls make accidental publication much harder, not impossible.
A user with control of Git can disable hooks or use another upload route;
GitHub web/API uploads are outside local hooks. Pattern scanners cannot detect
every secret, encoded value or private sentence. Human review remains required.
The safeguards do not retract anything already published and are not a claim
that GitHub account-level push protection has been enabled.
