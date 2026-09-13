# Documentation audit: m5-azahi

Scope: README.md, PROGRESS.md, docs/*.md, docs/research-archive-manifest.json,
per-component READMEs, research-archive/*.md, .gitignore, LICENSES/, plus
`git log -p --all` (23 commits, 109,027 diff lines) and a fresh-clone test run.

**Severity counts: critical 3, high 15, medium 22, low 13 (53 findings).**

> Tooling note for anyone re-running these greps: `grep` on this host is ugrep,
> which honours the repo's default-deny `.gitignore` when the search root is `.`
> and silently returns nothing. Every scan below used `--no-ignore-files`.
> Any prior audit that ran plain `grep -r ... .` here produced false negatives.

---

## 1. Claims the code does not support / mutually contradictory claims

### CRITICAL-1 — `usb-driver/README.md:3` flatly contradicts the root status table
`usb-driver/README.md:3` says "**Offline-tested experimental source; live USB
tethering not yet demonstrated.**" `README.md:41` says "DHCP/DNS/HTTPS worked on
the prior boot", `docs/HANDOFF.md:34` says "USB tethering is verified by direct
native SSH", and commit `2d213d4` is titled "Record working native USB tethering".
Why it matters: the component README is the first thing a reader of `usb-driver/`
sees, and it understates a result the rest of the repo treats as established.
Fix: rewrite `usb-driver/README.md:3` to "live tethering worked on one boot;
cold-boot USB startup currently fails", matching `README.md:41`.

### CRITICAL-2 — `usb-driver/README.md:20` and `standalone-loader/README.md:7-9` are two generations stale
`usb-driver/README.md:20`: "The corrected v5 RAM handoff awaits target confirmation."
`standalone-loader/README.md:7-9`: describes v4 as installed and v5 as "still
pending". Both were superseded by v6: `PROGRESS.md:3` / `docs/HANDOFF.md:3`
("v6 cold boot reaches KDE"), `README.md:35-36`, commits `ba3c984` and `843d290`.
Why it matters: a reader following `standalone-loader/README.md` would build and
install v5 over a working v6. Fix: replace both paragraphs with the v6 state and
add a one-line "current status lives in README.md, not here" pointer.

### HIGH-1 — `README.md:75` promises "a C compiler"; two of the four listed tests hardcode `clang`
Verified on a fresh `git clone` of this repo with gcc 14 and no clang:
- `python3 input-driver/test-power-request.py` → `FileNotFoundError: 'clang'`
  (`input-driver/test-power-request.py:59` hardcodes `["clang", ...]`).
- `bash nvme-driver/test-root-write-policy.sh` → `line 6: clang: command not found`,
  exit 127 (`nvme-driver/test-root-write-policy.sh:6`).
- `python3 usb-driver/test-usb-runner.py` → OK, 19 tests.
- `python3 usb-driver/test-usb-glue.py` → OK, 3 tests.
So 2 of 4 documented commands fail from a fresh clone on the stated prerequisites.
Same list is repeated at `docs/BUILD-AND-TEST.md:10-15` with the same gap.
Fix: either change `README.md:75` to "clang (gcc is not sufficient: the tests
invoke `clang` by name)", or honour `$CC`/fall back to `cc` in both test files.
`usb-driver/pd-backport/test-spmi4.sh:7` already does this correctly with
`"${CC:-clang}"` — copy that pattern.

### HIGH-2 — `docs/BUILD-AND-TEST.md:33-36` states unverifiable test counts as fact
"Publication validation on 2026-09-13 reran all four host commands above in the
sanitized public clone: ... **525,366 storage policy checks passed**, and
**19 runner + 3 glue/overlay tests passed**." The 19 and 3 reproduce exactly; the
525,366 figure cannot be reproduced from a fresh clone at all (HIGH-1), and no
output artifact is in the repo. Fix: state the toolchain the run used
(Homebrew clang on macOS), or drop the precise number.

### HIGH-3 — `docs/HANDOFF.md:61-65` asserts a state its own document already refuted
Line 61: "CRITICAL remaining issue: installed boot object is still bad v4, which
stops in proxy. ... Do not claim standalone cold-boot success." Lines 3-6 of the
same file: "v6 cold boot reaches KDE ... the first reported cold boot of installed
v6." The stale paragraph carries a CRITICAL label and imperative wording, so it
reads as current guidance. Same text at `PROGRESS.md:61-65`.
Fix: prefix every superseded section with "SUPERSEDED <date> — historical" or move
them below a single `## History` divider.

### HIGH-4 — `docs/HANDOFF.md:25-30` gives stale imperative next steps
"Cold boot is NOT yet tested. Next: orderly Recovery shutdown, unplug phone and
helper data cables ... Do not send a proxy payload." Superseded by lines 3-15.
A reader who skims to the first "Next:" executes the wrong test. Same at
`PROGRESS.md:25-30`. Fix: as HIGH-3.

### HIGH-5 — `PROGRESS.md:319-322` presents a completed step as pending
"Next: preserve the checked courier directory from /run to a fresh directory under
/root ... Copy outcome is pending." Commits `4db3146` and `8b109e5` record the
courier files reaching native KDE with checksums verified. Fix: delete or mark
superseded.

### HIGH-6 — `remote-access/README.md:44-45` vs `README.md:42`
`remote-access/README.md:44-45`: "Native key-authenticated access and a live switch
to the persisted services have now been verified, followed by certificate-validated
HTTPS GET success." `README.md:42`: remote access "currently unavailable while
cold-boot USB is diagnosed"; `docs/HANDOFF.md:10`: "Native SSH is currently
unreachable". Fix: add "(prior boot; unreachable since the v6 cold boot)" to the
component README, or drop the status sentence and link to `README.md`.

### HIGH-7 — `remote-access/README.md:64` vs `README.md:35`
"These services are installed and live-tested on the research machine, but cold
boot remains untested" contradicts `README.md:35` ("Installed v6 cold boot reached
KDE") and `docs/HANDOFF.md:3-10`, where the cold boot happened and the tunnel did
*not* come back. Fix: record the actual cold-boot outcome (services did not
restore connectivity).

### MEDIUM-1 — `README.md:59` says 284 archive files; the directory holds 285
`docs/research-archive-manifest.json` declares 284 and lists 284 (verified: names,
byte counts and all 284 SHA256s match the working tree exactly, `source_bytes`
2,754,265 matches). The 285th file, `research-archive/README-PUBLIC-ARCHIVE.md`,
is not in the manifest and is not declared as an exception. Fix: add a
`"self_documenting_files"` note to the JSON, or say "284 snapshots plus this README".

### MEDIUM-2 — `usb-driver/README.md:10` publishes DART bases no shipped code uses
`0x382f00000`/`0x382f80000` appear nowhere in the tracked source (the DWC3 and PHY
bases at `README.md:9` do appear, in `usb-driver/azahi-usb-overlay.c:50-53` and
`usb-driver/phy-apple-t6050-usb2.c:33,52`). Unsupported hardware constants in a
README invite copy-paste into someone else's overlay. Fix: drop them or cite the
private ADT node they came from.

### MEDIUM-3 — `nvme-driver/root-write-policy.h:3` redaction ate a space
"GPT root UUIDPRIVATE-LINUX-PARTUUID-NOT-CONFIGURED" — the sanitizer substituted
without preserving the separator. Cosmetic, but it shows the redaction pass edits
by blind string replace, which is worth knowing before trusting it elsewhere.
Fix: "GPT root UUID `PRIVATE-LINUX-PARTUUID-NOT-CONFIGURED`".

### LOW-1 — `README.md:73-82` omits three runnable host test suites
`python3 safety/test-publication.py` (14 tests, verified passing here),
`python3 remote-access/test-relay.py`, `python3 usb-driver/test-native-startup.py`
and the `pd-backport` checks all run offline but appear only in
`docs/PUBLICATION-SAFETY.md:30` or nowhere. Fix: list them, or say the README list
is illustrative.

### LOW-2 — `README.md:57` lumps `probe/` and `ramroot/` together as directories of tooling
Each contains exactly one file (`probe/build-native-ssdroot.py`,
`ramroot/mkcpio.py`). Fix: name the two files instead of implying directories.

---

## 2. Broken links and path references

Every backticked path and markdown link in all tracked `.md` files was resolved
against the doc's directory, the repo root, and (for archive docs) the archive root.

### MEDIUM-4 — 230 distinct dangling paths in `research-archive/` docs, 161 of them under `logs/`
The archive's notes are written as if the evidence sits beside them. It does not:
`logs/` is excluded by `.gitignore:47` and by the manifest's `exclusions` list.
Representative hits:
- `research-archive/probe/CPU-CHECKPOINT.md:350-358` — six `logs/cpu-diag-v4-*.log`
- `research-archive/standalone-loader/README.md:290` — `logs/standalone-v3-coldboot-kde-20260912.jpg`
- `research-archive/CURRENT-STATE.md:806-810` — `logs/recovery-root-install-20260906.cILw73`,
  `logs/recovery-backup-20260906.eTn0av`
- `research-archive/input-driver/README.md:94` — `logs/input-v2power-boot-20260906/console.log`
- `research-archive/probe/HANDOFF-20260912-USB.md:229` — `probe/firmware-analysis/kernelcache.mac17j.macho`
- `research-archive/BRINGUP.md:302,547` — `m1n1/build/m1n1.bin`, `scratchpad/m1n1-pristine/build/m1n1.elf`
- `research-archive/CURRENT-STATE.md:6` and `research-archive/PROGRESS.md:8` — `publication/export-public.sh`
  (the tool that produced this publication is itself unpublished and excluded).
Why it matters: every "verified" statement in the archive cites a file the reader
cannot open, so none of it is independently checkable (see section 5).
Fix: one banner at the top of `research-archive/README-PUBLIC-ARCHIVE.md`:
"All `logs/`, `evidence/`, `build*/`, `m1n1/`, `probe/firmware-analysis/` and
`publication/` paths cited below were excluded from publication and are absent."

### MEDIUM-5 — `usb-driver/pd-backport/audit-spmi4.py` cannot run from any clone
`audit-spmi4.py:19` prepends `ROOT/'pylib'` and `ROOT/'proxy-kit/proxyclient'` to
`sys.path` and imports `m1n1.adt`; `:26` opens `probe/firmware-analysis/kernelcache.mac17j.macho`;
`:27` opens `adt-real-t6050.bin`; `:37` runs `probe/inspect-kernelcache.py`; `:40`
reads `build/exact/linux-7.0.13/...`. None of those five paths exist in the repo
and all are in the manifest `exclusions`. `docs/BUILD-AND-TEST.md:38-42` lists
which tests need private inputs but does **not** list `audit-spmi4.py`.
Fix: add it (and `usb-driver/pd-backport/check-build.sh`, which hardcodes
`/opt/homebrew/opt/llvm/bin/clang` at line 15) to the private-inputs list.

### LOW-3 — Ambiguous `vendor/` reference
`docs/PROVENANCE.md:8` says the reference files "are under `vendor/`". There is no
top-level `vendor/`; they are at `nvme-driver/vendor/` and `usb-driver/vendor/dwc3/`
(and `usb-driver/pd-backport/vendor/tipd/`). Fix: name all three.

### LOW-4 — Public docs are otherwise link-clean
No broken reference found in `README.md`, `docs/*.md` or the component READMEs
beyond LOW-3. Recording this so a future pass does not redo the sweep.

---

## 3. Licensing and provenance

### HIGH-8 — `usb-driver/phy-apple-t6050-usb2.c:5-9` states it is a transcription of Apple's kernelcache; `docs/PROVENANCE.md:16-18` softens this to "analysis of behavior"
The file header:
```
 * The register sequence is a transcription of the saved Mac17,9 kernelcache
 * (probe/firmware-analysis/kernelcache.mac17j.macho):
 *   AppleT6050TypeCPhy::eusb2phy_init(bool primary, bool secondary)  VA 0xfffffe0009a3b744
 *   AppleT6050TypeCPhy::eusb2phy_shutdown()                          VA 0xfffffe0009a3ce54
 *   AppleT6050TypeCPhy::initUSB2(unsigned)                           VA 0xfffffe0009a76e98
```
`docs/PROVENANCE.md:16-18`: "The T6050 PHY source records its derivation from
analysis of Apple's `AppleT6050TypeCPhy` behavior and ADT tunables. No Apple
kernelcache, firmware, disassembly dump or extracted proprietary driver is
distributed." The second sentence is true (no dump ships) but is placed so it reads
as a rebuttal of the first. "Transcription of" a named C++ symbol at a named virtual
address is a derivative-work claim, not behavioural analysis, and it is the
opposite of clean-room. `docs/PROVENANCE.md:19-20` explicitly disclaims a
clean-room provenance claim, so the repo is internally aware of this and still
lets `PROVENANCE.md:16-18` read as reassurance.
Why it matters: this is the single highest-risk statement in the repo for anyone
who redistributes it, and it is also the file most likely to be copied out.
Fix: quote the header verbatim in `PROVENANCE.md` rather than paraphrasing, and
state plainly that the register sequence is transcribed from a disassembly of
Apple's driver and that redistributors should get their own legal read.

### HIGH-9 — SPDX tags on transcribed code assert a grant the author may not hold
`usb-driver/phy-apple-t6050-usb2.c:1` is tagged `GPL-2.0 OR BSD-2-Clause`.
The same file (lines 5-9) says its register sequence was transcribed from Apple's
proprietary binary. Dual-licensing content derived from a third party's
copyrighted work is not something the transcriber can unilaterally do.
Fix: keep the tag if the sequence is defensible as unprotectable
register/value facts, but say so in one line in the header; otherwise drop
BSD-2-Clause and note the derivation constraint.

### HIGH-10 — `docs/PROVENANCE.md:13-15` says the upstream m1n1 checkout is not republished; `research-archive/` republishes seven of its sources
"The upstream checkout and its policies are not replaced or republished here."
But present and manifest-listed:
`research-archive/standalone-loader/m1n1-20260911/src/{main,payload,smp,kboot,nvme,cpufreq}.c`
and `Makefile` — upstream m1n1 files, not the custom component. The manifest's own
`exclusions` array even lists `"standalone-loader/m1n1-20260911/**"`, yet ten paths
under exactly that prefix appear in `files`. So the manifest contradicts itself and
contradicts `PROVENANCE.md`.
Fix: either remove those seven upstream files from the archive, or amend
`PROVENANCE.md:13-15` and the manifest `exclusions` entry to say only the modified
subset of the upstream tree is republished under its MIT license.

### MEDIUM-6 — `README.md:56` and `standalone-loader/README.md:3-4` say "not a complete m1n1 checkout"; the archive weakens that
True for `standalone-loader/` (2 files), misleading once
`research-archive/standalone-loader/m1n1-20260911/` adds seven upstream sources.
Fix: state the archive's larger m1n1 subset in `README.md:59-61`.

### MEDIUM-7 — `LICENSES/` holds only `GPL-2.0.txt`, but four licenses are claimed in SPDX tags
Tags in tracked files: `GPL-2.0`, `GPL-2.0-only OR MIT`, `GPL-2.0 OR MIT`,
`GPL-2.0 OR BSD-2-Clause` (`usb-driver/phy-apple-t6050-usb2.c:1`), `GPL-2.0+`
(`usb-driver/pd-backport/vendor/tipd/tps6598x.h:1`, `trace.h:1`), `MIT`
(`standalone-loader/m1n1-20260911/src/azahi_standalone.{c,h}:1`).
`docs/PROVENANCE.md:22` says only "GPL-2.0 text is included under `LICENSES/`".
MIT text does exist, but only at `standalone-loader/m1n1-20260911/LICENSE`;
BSD-2-Clause text is nowhere in the repo.
Fix: add `LICENSES/BSD-2-Clause.txt` and `LICENSES/MIT.txt`, and update
`PROVENANCE.md:22` to point at them.

### MEDIUM-8 — 42 of the ~78 tracked non-archive scripts carry no SPDX header, under a stated "no blanket license" policy
`docs/PROVENANCE.md:22-25`: "Existing licenses apply **per file** ... There is no
new blanket license grant over previously unlicensed scripts or documentation."
So per-file tags are load-bearing, and every untagged file is legally unusable by
design. Untagged files include everything a reader is told to run:
`input-driver/test-power-request.py`, `nvme-driver/test-root-write-policy.{c,sh}`,
`usb-driver/test-usb-runner.py`, `usb-driver/test-usb-glue.py`,
`safety/{check,test}-publication.py`, `safety/install-hooks.sh`,
`remote-access/{relay,bootstrap,persist,test-relay}.py`,
`standalone-loader/build-{bundle,aligned}.py`, `probe/build-native-ssdroot.py`,
`ramroot/mkcpio.py`, all `usb-driver/build-transfer*.py`, all `.dtso` files.
Why it matters: "run these four commands" plus "these files carry no license"
is a contradiction between `README.md:73-82` and `PROVENANCE.md:24`.
Fix: add one SPDX line to the author's own scripts. `MIT` or `GPL-2.0-only`
resolves the whole class in one commit and costs nothing.

### MEDIUM-9 — The Asahi LLM-policy acknowledgement in `README.md:8-23` is consistent, but `PROVENANCE.md` never repeats the AI-assistance disclosure next to the derivation claim
`README.md:5,13` and `docs/PROVENANCE.md:3` both disclose AI assistance, and
`README.md:15-16` correctly says publishing does not imply eligibility for upstream
contribution. No internal contradiction found here. The gap: the PHY file
(HIGH-8) is the one artifact where AI assistance plus binary-derived content
compound, and neither its header nor `PROVENANCE.md:16-18` mentions AI involvement
in the transcription. Fix: one sentence in the PHY header.

### LOW-5 — `usb-driver/phy-apple-t6050-usb2.c:18` says "Not for upstream submission"; `README.md:18-19` floats a future public installer
Not a contradiction (an installer is not upstreaming), but the two lines will be
read together. Fix: none required; noting so it is not re-flagged.

---

## 4. Privacy: what the publication guard let through

Scanned: full working tree and `git log -p --all` for RFC-4122 UUIDs, MAC
addresses, IPv4 (all ranges), `/Users/`+`/home/` paths, ECIDs, Apple serial
patterns, emails, `/dev/cu.*` serial identities, hostnames, PIDs, `claude-<uid>`
session dirs, `/var/folders`, and 64-hex hashes.

**Clean:** no UUID, no MAC, no IPv4, no ECID, no Apple serial, no personal email
anywhere in the tree or in history. Placeholders (`PRIVATE-LINUX-*-NOT-CONFIGURED`,
`PRIVATE-USER`, `PRIVATE-UUID-REMOVED`, `PRIVATE-SERIAL-REMOVED`,
`PRIVATE-LAN-ENDPOINT-REMOVED`) are applied consistently. The `safety/allowed-paths.txt`
allowlist matches `git ls-files` exactly (385 = 385, no drift either direction),
and `python3 safety/test-publication.py` passes 14/14.

### HIGH-11 — `research-archive/m1n1-vmtmr-ro.patch:2` leaks the private directory tree and the macOS UID
```
+++ PRIVATE-PATH-REMOVED private folder names>/PRIVATE-UUID-REMOVED/scratchpad/m1n1-fix/src/hv_exc.c	<timestamp>
```
The redactor replaced the username and a UUID but left everything else in a
path-mangled string it evidently did not recognise as a path:
- `claude-<UID>` (the literal numeric UID is in the patch) identifies the primary macOS account.
- Four private folder names under `Documents` (see the patch header) form a
  home directory layout, including a distinctive (and misspelled) folder chain
  that is effectively a unique fingerprint for this person's machine.
- A wall-clock timestamp with no timezone stripping.
This is the only genuine leak found, and it is exactly the class
`docs/PUBLICATION.md:34` promises to exclude ("personal absolute paths") and
`docs/PUBLICATION-SAFETY.md:23-24` claims to detect ("personal home paths").
Why the guard missed it: the scanner looks for `/Users/<name>` and `/home/<name>`;
this string is PRIVATE-PATH-REMOVED because macOS had already flattened the
path into a temp-directory name. Cause and fix are both one line.
Fix: rewrite the patch's `---`/`+++` headers to `a/src/hv_exc.c` / `b/src/hv_exc.c`
(standard practice anyway), and add `-Users-` / `-home-` / `claude-[0-9]+` to the
content rules in `safety/check-publication.py`. Then re-scan history.

### MEDIUM-10 — `docs/research-archive-manifest.json` publishes exact byte sizes for 41 private images
`omitted_root_artifacts` lists every withheld artifact with its exact length, e.g.
`guest-hv-input-ssd-base.bin` 1,027,610,916; `guest-hv-input-ssd.bin` 1,027,611,015;
`native-rootguard-v1-20260906.bin` 1,027,838,716; `fedora-44-kde.zip` 4,442,691,640;
`Image-asahi` 77,398,016. Byte-exact sizes of images built from the operator's
private rootfs are a fingerprint: anyone holding a candidate copy can confirm a
match, and the size deltas between the `guest-hv-input-*` variants disclose the
exact size of each change. The stated purpose (documenting what was withheld) is
served by the filename and the reason alone.
Fix: drop the `bytes` field from `omitted_root_artifacts`, or bucket it
("~1.0 GB"). Keep `bytes` for the 284 published files, where it is verifiable.

### MEDIUM-11 — Exact private-image sizes and hashes are repeated in tracked source and public docs
- `standalone-loader/README.md:8` — "exact **70,698,084-byte** initrd requirement"
  (also `PROGRESS.md:394,416,481,500`; `standalone-loader/m1n1-20260911/src/azahi_standalone.c:20`;
  `usb-driver/build-transfer-fixed.py:23`; `standalone-loader/build-bundle.py:34`).
- `docs/HANDOFF.md:21` / `PROGRESS.md:21` — "92651520-byte size" plus a matching SHA256.
- `PROGRESS.md:435` and `usb-driver/proxy-test-v6.py:29` — SHA256
  `324822de...96ee` of the private v6 boot object.
- `usb-driver/build-transfer.py:18-29` — the private filename
  `standalone-ssdroot-v3-aligned-20260912.bin` plus its SHA256 and four module hashes.
- `usb-driver/install-native-startup.py:17-20` — SHA256 of four private `.ko` builds.
- `usb-driver/test-courier-vm.py:29` / `standalone-loader/build-bundle.py:49` —
  SHA256 of the private kernel image.
`docs/BUILD-AND-TEST.md:44` acknowledges these hashes will not match public
rebuilds, so their only remaining function is verification against private copies.
Fix: this is arguably intentional (pins guard against installing the wrong image)
— but say so once in `BUILD-AND-TEST.md` and note that the hashes and sizes
identify private artifacts, so the "images are intentionally absent" line at
`README.md:64-65` is not the whole story.

### MEDIUM-12 — `usb-driver/pd-backport/audit-spmi4.py:28-31` publishes SHA256 of the machine's ADT dump and of Apple's kernelcache
`26ddfbe9...5093` (kernelcache.mac17j.macho) and `5a87c2ee...7a24`
(`adt-real-t6050.bin`). The ADT is a per-device dump: its hash is a machine
identifier in the same sense a serial hash is. `docs/PUBLICATION.md:30,33` excludes
"raw ADTs and device dumps" and "receipts containing identifiers";
`docs/PUBLICATION-SAFETY.md:70-71` defends the file as containing "fixture hashes,
not the private fixtures", which concedes the point rather than answering it.
Fix: drop the ADT hash assertion (the script cannot run publicly anyway, MEDIUM-5),
or state in `PUBLICATION-SAFETY.md` that a per-device dump hash was accepted and why.

### LOW-6 — `disk3s1/s3/s4`, `disk0s3`, `disk0s6` appear as real BSD device names
`research-archive/CURRENT-STATE.md:36,547`; `research-archive/usb-driver/TRANSFER-CHECKPOINT.md:90,109-112`;
`research-archive/PROGRESS.md:435-436`; `research-archive/standalone-loader/README.md:474,634`;
`research-archive/probe/validate-recovery-storage.py:125`;
`research-archive/probe/test-recovery-partitions-mocks.sh:22,25`.
Not secrets (BSD names are enumeration-order artifacts), but combined with the
partition table at `research-archive/CURRENT-STATE.md:771` (start LBA 204034123,
38764544 blocks), the exact `addPartition ... 158913789952` at
`test-recovery-partitions-mocks.sh:25`, and `nvme-driver/root-write-policy.h:16-17`
(`AZAHI_ROOT_FIRST_LBA 204034123`, `AZAHI_ROOT_END_LBA 242798667`), the repo fully
describes one specific disk's geometry. `README.md:28` already warns never to reuse
it, so this is disclosed, not hidden. Fix: none required; noted for completeness.

### LOW-7 — mktemp session suffixes published in directory names and doc text
`research-archive/usb-driver/pre-hardening-20260913.t1WC5z/` (a directory in the
tree), `research-archive/standalone-loader/README.md:429`
(`/private/tmp/azahi-boot-disasm-20260912.4F58aQ`), plus ~12 cited log directories
carrying suffixes (`.eTn0av`, `.Zrp24U`, `.n8zyi1`, `.AO0gTd`, `.T0uKOR`,
`.GJsJmU`, `.4XhuGj`, `.yS45qc`, `.cILw73`, `.4VxUyx`, `.8rrzgj`).
Random suffixes carry no information, but they make session artifacts correlatable
across documents. Fix: rename the tracked directory to `pre-hardening-20260913/`.

### LOW-8 — Autologin-as-root configs shipped without a warning
`research-archive/ramroot/work-kde/sysroot-overlay/etc/systemd/system/getty@tty1.service.d/autologin.conf`
and the `serial-getty@ttySAC0` equivalent both set
`agetty --autologin root --noclear`. No credential leak, and it is correct for a
bring-up ramdisk. Fix: one comment line in `research-archive/README-PUBLIC-ARCHIVE.md`
so nobody lifts these into a real system.

---

## 5. Documentation structure

### CRITICAL-3 — `PROGRESS.md` and `docs/HANDOFF.md` are byte-identical for their first 323 lines
`diff <(sed -n '3,323p' PROGRESS.md) <(sed -n '3,323p' docs/HANDOFF.md)` is empty:
321 identical lines, 15 identical `##` headings in the same order. The files then
diverge — `PROGRESS.md:324-577` (Current boot incident, USB candidate, Earlier
milestones, Next verification) versus `docs/HANDOFF.md:324-477` (Immediate state,
Hard boundaries, Order of work, Public/private split).
Why it matters: `README.md:46` tells the reader to read both. 56% of `PROGRESS.md`
and 68% of `docs/HANDOFF.md` is the same text, and any future correction must land
in two places or the two files silently disagree — which is already how HIGH-3 and
HIGH-4 got frozen into both.
Fix: keep the shared session log in `PROGRESS.md` only. Reduce `docs/HANDOFF.md`
to its four unique sections plus a link to `PROGRESS.md`. One-line change to
`README.md:46` to explain the split.

*(Re-classified as critical rather than a structure nit because it is the
mechanism that keeps the stale-guidance findings alive in both files.)*

### HIGH-12 — Seven sections are titled "## Latest:" in each of `PROGRESS.md` and `docs/HANDOFF.md`
`PROGRESS.md:3,215,234,255,281,301,327` (and the identical set in `HANDOFF.md`),
alongside nine "## Earlier:" sections at `:17,32,75,101,121,145,171,196` and
`:546`. Six of the seven "Latest" headings are not latest. A reader jumping to any
`## Latest` heading with ctrl-F lands on stale state — and the sections at `:215`
through `:301` describe *older* work than the "Earlier:" sections above them, so
the reverse-chronological order is not even internally consistent.
Fix: retitle to `## 2026-09-13 — v6 cold boot ...` etc. Dates sort, "Latest" does not.

### MEDIUM-13 — `PROGRESS.md:325` says "the state below takes precedence" in a reverse-chronological file
"Historical private notes may contain superseded plans; the state below takes
precedence." Everything below line 325 is *older* than everything above it. The
sentence tells the reader to trust the stale half.
Fix: "the state at the top of this file takes precedence".

### MEDIUM-14 — Three-way overlap between `PROGRESS.md`, `docs/HANDOFF.md` and `research-archive/CURRENT-STATE.md`
`research-archive/CURRENT-STATE.md` (56,630 bytes) is a third running state
document covering the same period, with its own "latest" claims
(e.g. `:36` disk3s4 mounted RO, `:51` "Sep13 latest disk photo", `:631` v3 SSD
root table). Nothing marks it as historical, and `README.md:59-61` describes the
archive only as "snapshots", not as containing a competing current-state file.
Fix: add "SUPERSEDED — see /PROGRESS.md" as line 1 of
`research-archive/CURRENT-STATE.md`, `research-archive/PROGRESS.md` (78,126 bytes)
and `research-archive/BRINGUP.md` (78,127 bytes).

### MEDIUM-15 — No "verified" claim in the repo is checkable from the repo
`README.md:32` heads its table "Evidence so far", and the entries lean on words
like "demonstrated", "verified", "user-reported". The supporting evidence is
uniformly a `logs/*.log` or `logs/*.jpg` path that is excluded (MEDIUM-4: 161 such
paths), or a user photograph. Specific unfalsifiable claims:
- `README.md:34` "Native Fedora KDE from Btrfs SSD root demonstrated" —
  evidence is `logs/standalone-v3-coldboot-kde-20260912.jpg` (absent).
- `README.md:36` "Recovery installation and exact readback verified" —
  `docs/HANDOFF.md:21` cites a SHA256 and byte count; no receipt in repo.
- `input-driver/README.md:10` "The installed trackpad firmware was verified
  privately; it is not distributed."
- `docs/BUILD-AND-TEST.md:35` "525,366 storage policy checks passed" (HIGH-2).
This is defensible for a personal project — `README.md:63` already says it is a
snapshot, not a reproducible distribution — but the word "verified" is doing work
the repo cannot back.
Fix: add one line under the `README.md:32` table: "Evidence for these rows is
photographs and logs held privately; nothing in this repository reproduces them."
Then the table is honest and the wording can stay.

---

## 6. Additional findings from the deep read of the long-form logs

These come from a full read of `PROGRESS.md`, `docs/HANDOFF.md`,
`research-archive/{PROGRESS,CURRENT-STATE,BRINGUP,CLAUDE}.md` and
`research-archive/README-PUBLIC-ARCHIVE.md`. All line numbers spot-verified.

### HIGH-13 — `PROGRESS.md` states four mutually exclusive USB-tethering results
- `:7-8` "the phone does not charge and USB tethering is unavailable"
- `:34` "USB tethering **is verified** by direct native SSH"
- `:121` heading "native USB tethering works"
- `:184` "USB tethering is NOT working or verified."
- `:232` "USB tethering remains unverified; no user network interface/DHCP/HTTPS result."
All five in one 577-line file, none marked superseded, all in present tense.
Duplicated verbatim into `docs/HANDOFF.md` at the same line numbers (CRITICAL-3).
Fix: same as HIGH-3 — date the sections; the ordering problem is what makes this
unreadable, not the individual statements.

### HIGH-14 — `docs/HANDOFF.md:419-421` and `:467-469` sit inside "Immediate state" and "Order of work" while contradicting the top of the file
`:419-421` "still fails the loader's initrd-size check … No native networking or
SSH is established; host commands do not execute on the target."
`:467-469` "v3 is the known-working fallback; no corrected persistent install has
yet been verified."
Both contradict `:17-23` (v6 installed, readback verified) and `:34-38` (SSH
verified). Unlike the `## Earlier:` blocks these carry no chronological marker at
all — `## Immediate state` (`:324`) and `## Order of work` (`:460`) read as the
document's standing instructions.
Fix: rewrite these two sections from the current state, or delete them and let the
dated log stand alone.

### HIGH-15 — `research-archive/CURRENT-STATE.md:601-603` publishes a self-validation that is false in the published copy
"Documentation validation: all 14 local Markdown links resolve; the five artifact
hashes in the table were recomputed and match".
In the published tree neither holds: the receipt links at `:663-667` all point into
the absent `logs/` directory, and the five hashed artifacts at `:648-654`
(`native-ssdroot-v3-20260906.bin`, `native-loader-prefix-20260906.bin`,
`nvme-driver/build-rootguard/nvme-apple.ko`, `nvme-driver/build/apple-sart.ko`,
`t6050-j714s-native-rootguard.dtb`) are all excluded.
Why it matters: it is the only explicit "I checked the docs" claim in the repo, and
it is the one claim a reader can falsify in thirty seconds. It was true in the
private workspace and became false at publication, which is exactly the failure
mode the archive banner should cover.
Fix: append "(validated in the private workspace; the cited artifacts and logs are
excluded from this publication)".

### MEDIUM-16 — `research-archive/CURRENT-STATE.md:636` summary table contradicts its own log three times over
Table row: "Trackpad | … Sep12 native KDE has no visible pointer/trackpad response
by user report; diagnosis pending." Log entries above it: `:79` "user reports
working trackpad", `:87-88` "Trackpad working after reboot per user", `:356` "User
reports trackpad now works". The at-a-glance table was never refreshed from the
log it summarises. Same file, `:633` "One core is enabled/proven. Other 17 remain
unresolved" is consistent with `PROGRESS.md:559`; `:638` "No working native remote
shell/input transport is established" is not.
Fix: regenerate the tables at `:631-638` or delete them.

### MEDIUM-17 — Three different answers to "does it cold boot on its own"
- `research-archive/CURRENT-STATE.md:605-611` "**Yes: one successful autonomous
  cold boot on September 12**" (aligned v3)
- `research-archive/CURRENT-STATE.md:19-25` "enrolled USB-files v4 FAILED boot,
  now in proxy"
- `PROGRESS.md:3` v6 cold boot reaches KDE
Three images, three verdicts, no cross-reference. `README.md:35` picks the third
and labels it "(user-reported)", which is the honest framing; the archive does not.
Fix: the archive banner (MEDIUM-14) covers this.

### MEDIUM-18 — `PROGRESS.md:98` undercounts the enrolled remote-access files
"Only the five reviewed remote-access source files were enrolled in both
publication allowlists." `safety/allowed-paths.txt:373-378` enrolls six
(`README.md`, `bootstrap.py`, `relay.py`, `requirements.txt`, `test-relay.py`,
`persist.py`), and `remote-access/` contains six files.
Why it matters: `docs/PUBLICATION-SAFETY.md:50-57` and `:61-72` make precise
enrolment counts the audit trail for what was reviewed. A count that is off by one
makes the trail useless. Duplicated at `docs/HANDOFF.md:98`.
Fix: change to six, and recheck the other counts in `PUBLICATION-SAFETY.md`
("exactly five source paths" at `:50`, "ten source/provenance paths" at `:61`)
against `safety/allowed-paths.txt`.

### MEDIUM-19 — Document dates disagree with document contents
- `research-archive/CURRENT-STATE.md:1` "# M5 Pro Linux handoff — 2026-09-06",
  newest entry `:3` is Sep 13.
- `research-archive/BRINGUP.md:5` "Date: 2026-08-15.", newest sections are
  2026-09-06.
- `docs/HANDOFF.md:1` "# Resume safely" carries no date at all, while being 321
  lines identical to `PROGRESS.md`, which is dated 2026-09-13 at `:1`.
Fix: date `docs/HANDOFF.md`; change the two archive headers to a range
("2026-08-15 to 2026-09-13").

### MEDIUM-20 — Conflicting standing instruction about webcam use
`research-archive/CURRENT-STATE.md:99-100` "webcam screen observation is important
and explicitly authorised without asking again" vs `docs/HANDOFF.md:454-455` "the
latest preference was **no webcam**". Both are operator-consent records; the
archive one is stale and phrased as a blanket standing authorisation.
Why it matters: this is the only consent-scoped instruction pair in the repo, and
a reader resuming from the archive would act on the revoked one.
Fix: strike `CURRENT-STATE.md:99-100` or mark it superseded explicitly by date.

### MEDIUM-21 — Archive docs use bare relative paths that collide with real top-level directories
`research-archive/CURRENT-STATE.md:17,25,33,40,49` cite `usb-driver/TRANSFER-CHECKPOINT.md`.
That resolves inside the archive (`research-archive/usb-driver/TRANSFER-CHECKPOINT.md`,
present) but the repo also has a real top-level `usb-driver/`, which has no such
file. Same collision for `probe/NETWORK-CHECKPOINT.md`, `probe/N1-WIFI-20260913.md`,
`probe/HANDOFF-20260912-USB.md`, `probe/native-kde-regression-20260912.md`
(`CURRENT-STATE.md:56,73,97,109`), `probe/{SSDROOT-BOOT,NATIVE-SSD,ROOTGUARD,CPU,NATIVE}-CHECKPOINT.md`
(`:756,878-882`), and `probe/{test-ssdroot,test-native-rootguard,boot-native}.py`
(`:834-837`). Top-level `probe/` contains exactly one file.
Why it matters: a reader who opens `CURRENT-STATE.md` from a file browser at the
repo root follows these into the wrong directory or a 404, and the file reads as a
top-level handoff (its H1 is "M5 Pro Linux handoff").
Fix: prefix them `research-archive/…`, or add one line to
`research-archive/README-PUBLIC-ARCHIVE.md` stating that all relative paths in the
archive resolve against `research-archive/`, not the repo root.

### MEDIUM-22 — `research-archive/CURRENT-STATE.md:661-667` is the milestone's only evidence block and every link in it dangles
Headed "Successful-run receipts:", five bullets, all into `logs/`. Adjacent
unverifiable claims: `:830-831` "23 SSD-root tests, 11 mocked rootguard tests,
525,366 shared C write-policy checks… all passed" (no output file; and
`README-PUBLIC-ARCHIVE.md:18-20` warns redaction may have made these scripts
unrunnable), and `:841-842` "a bounded native 16 KiB write/flush/read/restore at
root-relative 32 GiB passed… including before/after metadata checks" — a storage
safety claim with no log at all.
Fix: covered by the archive banner (MEDIUM-4), but the 16 KiB write claim at
`:841-842` deserves its own note since it is the one asserting the SSD was written
to safely.

### LOW-9 — `PROGRESS.md:567-577` puts the oldest instruction in the most authoritative position
The file's final section, `## Next verification`, says "On the target Linux
terminal, **without another reboot**: `ls /run/azahi-usb-20260913`" — a step
already completed and reported at `:281-285` and `:374-383`. Readers who scroll to
the bottom for "what do I do now" get the stalest answer in the document.
The same `ls /run/azahi-usb-20260913` command appears four times:
`PROGRESS.md:401-403`, `PROGRESS.md:571-573`, `docs/HANDOFF.md:425-427`, and in
prose at `PROGRESS.md:385`/`docs/HANDOFF.md:389`.
Fix: delete `## Next verification` and put the current next action directly under
the `## Latest` heading at `:3`.

### LOW-10 — Full inventory of stale imperative "Next:" blocks
For whoever does the cleanup, these are every superseded present-tense instruction
found, beyond HIGH-3/HIGH-4/HIGH-5:
`PROGRESS.md` (mirrored at the same lines in `docs/HANDOFF.md`): `:93-96`,
`:112-119`, `:136-140`, `:229-232`, `:298-299`, `:385-387`, `:399-403`,
`:437-439`, `:461-467`, `:567-577`.
`docs/HANDOFF.md` only: `:326-334`, `:338-350`, `:364-374`, `:376-384`,
`:406-415`, `:423-437`, `:448`, `:462-469`.
`research-archive/CURRENT-STATE.md`: `:9` ("Do not reboot."), `:17`, `:30-33`,
`:47-48`, `:65-68`, `:562-566`, and the whole numbered "Exact tested boot
procedure" at `:674-733`, which uses host paths that no longer exist.
`research-archive/README-PUBLIC-ARCHIVE.md:16-18` does warn "Do not run these
scripts or follow old next-step instructions" — but that warning is scoped to
`research-archive/`, and `PROGRESS.md` / `docs/HANDOFF.md` have the same problem
with no equivalent warning.
Fix: one `> SUPERSEDED` blockquote per stale block is cheaper than rewriting, and
survives future appends.

### LOW-11 — `research-archive/CURRENT-STATE.md` and `research-archive/PROGRESS.md` bury their structure under 500+ lines of prepended log
`CURRENT-STATE.md`: 66 bolded log entries at `:3-596`, of which 50 lead with
LATEST/Latest/NEWEST/CURRENT/IMMEDIATE (nine in capitals). Its first `##` heading
is at `:605`; the pointer explaining the layout is at `:597-599`, after 596 lines.
`research-archive/PROGRESS.md`: 517 lines of prepended log before its first
heading (`:520` "## The short version"), then a second nested log under `:536`
with its own Latest/Current/Earlier `###` headings at `:538,626,701,728,764,825,899`.
Fix: move the real headings to the top and let the log follow. No content change.

### LOW-12 — `research-archive/BRINGUP.md` uses eight H1s at the same nesting level as its H2s
`#` at `:579,637,758,873,927,1113,1246,1309`; equally-ranked sections use `##` at
`:73,99,145,347,439,505`. Breaks any table-of-contents generator and outline view.
Fix: demote the eight `#` to `##`.

### LOW-13 — `research-archive/CLAUDE.md` and `research-archive/BRINGUP.md` cite ~90 workspace paths that were never published
`BRINGUP.md` alone references 13 `src/*.c` files, 5 `proxyclient/` modules, 11
loose `*.py` tools, 5 `*.sh` runners and every `*.bin` image. `CLAUDE.md` cites
`m1n1/CLAUDE.md:240`, `GUARD.S:224`, three `logs/*` files, and all `~/azahi/*`
artifacts at `:171-181`. Only `deploy.sh` (`CLAUDE.md:126`) resolves.
These are agent-instruction files for a workspace that does not exist here.
Fix: the archive banner covers it; alternatively drop `CLAUDE.md` from the
publication, since it is operating instructions for a private tree.

---

## Suggested order of repair

1. `research-archive/m1n1-vmtmr-ro.patch:2` — the only real leak (HIGH-11). One line.
2. Fix the two clang-dependent tests or the README prerequisite (HIGH-1). Two lines.
3. Deduplicate `PROGRESS.md` / `docs/HANDOFF.md` (CRITICAL-3), then date every
   heading (HIGH-12). This alone retires HIGH-3, HIGH-4, HIGH-5, HIGH-13, HIGH-14,
   MEDIUM-13 and LOW-9/LOW-10, because they are all artifacts of the same layout.
4. Refresh the three stale component READMEs (CRITICAL-1, CRITICAL-2, HIGH-6, HIGH-7).
5. Reconcile `docs/PROVENANCE.md:16-18` with the PHY header (HIGH-8, HIGH-9) and
   with the republished m1n1 sources (HIGH-10).
6. Add the archive banner (MEDIUM-4, MEDIUM-14, MEDIUM-21) — one paragraph in
   `research-archive/README-PUBLIC-ARCHIVE.md` retires roughly 240 dangling
   references and most of the unverifiable-evidence findings.
7. Everything else.
