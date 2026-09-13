# Native SSD bring-up — 2026-09-06

**Current-state override:** v3 has now booted KDE from the internal SSD root.
The RAM-only/not-mounted statements below are historical. Standalone startup
is still unfinished. See [current handoff](../CURRENT-STATE.md) and
[successful boot checkpoint](SSDROOT-BOOT-CHECKPOINT.md). Do not repeat installers.

## NEWEST — native rootguard hardware test PASSED

M5 has left Recovery and is now running native RAM Linux. Rootguardv1 completed
the16KiB bounded padding write/flush/read/restore successfully, then disarmed
and reset all namespacesRO. Before/after metadata and root-prefix checks pass.
Evidence `logs/rootguard-v1-boot-screen2-20260906.jpg`, boot/preflight logs and
exact next state in `probe/ROOTGUARD-CHECKPOINT.md`. KDE SSD filesystem NOT yet
mounted/booted; only one CPU. Do not rerun installers or power-cycle yet.

## LIVE OVERRIDE — root installation COMPLETE and independently verified

User said done. Transfer complete:425/425 chunks,14248030208B. Receiver
PID54038/session57931 was subsequently stopped normally after webcam
confirmed completion and shell prompt. Server log explicitly records
`FULL_SSD_READBACK_SHA256_VERIFIED` with source SHA256
`bc33421d52f06288c53cba128ccc79b13c077fb90f957fea048a5048cd955f7b`,
followed by `VALIDATED_ROOT_INSTALL after`. After archive is6111B,
POSIXcksum1157201623, SHA256
`e98e09c7d47757379a0456020b6bcdf106e1d9b47ae95459a58d5417906dd9a1`.
Evidence: `logs/recovery-root-install-20260906.cILw73/progress.json` and
`after/{backup.tar.gz,receipt.txt,validation.json}`; receiver log
`logs/recovery-root-install-server-20260906.log`.
All protected original GPT entries remain unchanged by UUID; this metadata
check is NOT a whole-volume hash of daily macOS. No daily filesystem writes
were targets of the installer. New root now contains Btrfs UUID
PRIVATE-UUID-REMOVED, still14.25GB (partition158.78GB).
DO NOT rerun installer. M5 remains in Recovery. The next RAM-root write-test
candidate is now built/offline validated; see `ROOTGUARD-CHECKPOINT.md` for
new artifacts, limitations and required physical boot into Linux proxy.
One CPU proven; all-core work still unresolved. Native write behavior is
UNTESTED; disk-root initrd/standalone loader remain unfinished.
Older entries below are historical and superseded by this live override.

## CURRENT — KDE root transfer ready, awaiting user execution (NO COPY YET)

**Running server:** PID54038, exec session57931:
`python3 -u probe/recovery-root-server.py --bind PRIVATE-LAN-ENDPOINT-REMOVED --destination
/PRIVATE-USER/azahi-port/logs/recovery-root-install-20260906.cILw73`.
Log `logs/recovery-root-install-server-20260906.log`.
Only public GET `/install-root.sh`; scoped per-run transfer endpoints for
preflight/prefix/manifest/chunk-N/verify-N/complete/after. DO NOT restart or
change server during transfer: ordered SHA256 state is in memory; progress
file is NOT sufficient for automatic resume. No target request at handoff.
Served script12414B, SHA256
`f4645e77725345199511d69532ef3ee9b28b5e90ee6b8843ee8a4fa92629fc4a`;
GET verified exactly against saved `served-script.sh` mode0600 in destination.
Saved script contains scoped LAN capability; don't print it/token in chat.

User handoff single command:
`curl -q --noproxy '*' --proto '=http' -f PRIVATE-LAN-ENDPOINT-REMOVED -o /tmp/install-root.sh && bash /tmp/install-root.sh install-kde-root`
Tell keep charger connected, Recovery open, don't interrupt/reboot or rerun
on errors.425 chunk progress;14.25GB download AND full read-back upload.
No macOS-side root mount/format is required. This DOES write the new ROOT
partition; it does not touch EFI or original APFS/Recovery volumes.

**Source:** unchanged `ramroot/work-kde/root.img`14248030208B,
SHA256 `bc33421d52f06288c53cba128ccc79b13c077fb90f957fea048a5048cd955f7b`.
Btrfs UUIDPRIVATE-UUID-REMOVED,4096 sector,16384 node,
5.66GB used. Corresponds to `fedora-44-kde.zip` root.img entry size and CRC32
359c8a1b; manifest build computes and matches full source SHA and ZIP CRC.
Existing source was used read-only for earlier KDE boot; no root.img edits.
`probe/build-root-transfer-manifest.py` generated
`probe/kde-root-transfer-20260906.json` (SHA256
769d948fdb9928cfec5e33e6da42c60e3c9e5f0e7f59fddf59d282b69d2f5492),425
chunks up to32MiB, index/offset/bytes/POSIXcksum/SHA256. Logs
`logs/kde-root-transfer-manifest-build-20260906.log`.

**Installer design:** generated from pinned read-only collector function
region of recovery-create-partitions.sh (no action tail/addPartition), plus
`probe/recovery-install-root-tail.sh`. Fixed PATH/model/explicit action,
minimum128MiB Recovery scratch. Collect current GPT/plists and host validates
ALL original/new entries against reviewed real partition report. Resolve root
by UUID, require Linux type, raw root extent835723767808..994503340031bytes,
158779572224B,4096-sector,not mounted,never disk0s2/3. Recheck identity/extent
and mount state before EVERY chunk. Test dd fullblock/fsync support in RAM
before disk writes. Back up first69632B of new root to host; require first4KiB
zero and no Btrfs magic at primary superblock (refuses existing/partial image).
Download checksum-pinned manifest, verify index/offset/length/4K alignment/
14.25GB total bounds. Download one32MiB chunk to RAM, check size+cksum before
write. dd writes only bounded new root raw partition with1MiB blocks,
conv=notrunc,oflag=fsync. Bounded raw read-back to RAM, cksum then host uploads
and verifies SHA256, tracks whole readback hash. Source chunks SHA-checked
before serving and source inode/size/mtime/ctime unchanged. At425 chunks
requires full-image SHA256, then fresh metadata host validation again.
Success marker `KDE_ROOT_IMAGE_INSTALLED_AND_VERIFIED` only after all checks.
No native Linux writes/driver changes in this installer; Apple's Recovery
storage driver performs these media writes.

**Receiver files:** preflight/after each backup.tar.gz,receipt.txt,validation.json;
root-header-before.bin; progress.json (`verified_chunks`,`verified_bytes`);
server log `SSD_VERIFIED N/425`. Read-back payloads are hashed and discarded,
not saved as another14GB file. Transfer does not auto-resume after failures.
GET/PUT sequence guarded; corrupt readback doesn't advance progress; duplicate
just-completed verification is idempotent. Reports bounded1MiB, prefix69632B,
data uploads exactly corresponding <=32MiB. No execution of uploads.

**Verification:**8 tests pass in `probe/test-root-install.py` plus mocks:
rendered Bash syntax/model rejection, scaled4KiB mocked successful write/
readback/after checks, wrong root UUID/preflight/corrupt download refusal
before writes, bad local readback or host SHA stops afterward, actual local
HTTP32MiB download and valid/corrupt/duplicate verification/order tests.
No target SSD accessed by tests. Log
`logs/kde-root-install-offline-tests-20260906.log`.

IMPORTANT NEXT: installing source image does NOT enable autonomous boot.
Need native NVMe write firewall restricted to the root LBA range, input+
module/config overlay for actual disk root, boot initramfs without RAM root,
and persistent loader ANS/DAPF handoff. Native existingv3 is RO and cannot
mount this disk root writable. EFI is still unformatted. Extra cores/GPU
remain unresolved. Stay in Recovery until copy verified; don't boot blindly.

## CURRENT — partitions CREATED; HTTP422 diagnosed, full reviewed validation PASS

User reported one error. Webcam `logs/recovery-partitions-error-20260906.jpg`
shows both diskutil adds finished, then curl HTTP422 and Recovery prompt.
Host received before/esp/root reports; initial root rejected solely at
`Unexpected Linux root extent` BEFORE the remaining final checks. M5's
4096-sector Recovery allocated the128MiB helper INSIDE requested148GiB;
host512-sector test had allocated it outside. Exact delta134217728B.
No correction to disk needed. Do not rerun creation or restore any old GPT.

Validator now has explicit `root_allocation='includes-helper'` (default stays
exact-root, preserving initial guard). This mode requires root exactly
ROOT_BYTES-BOOTER_BYTES, and the exact128MiB Apple_Boot immediately after it;
all original-byte, bounds, UUID, CRC, APFS and plist checks remain intact.
All stages revalidated, real root now PASS, saved separately as
`logs/recovery-partitions-20260906.Zrp24U/root/validation-reviewed.json`.
Original failure log/receipts retained, no forged successful upload receipt.
New tests include actual target archive, default refusal, explicit mode
success and rejection when helper missing.15 tests pass; log
`logs/recovery-partitions-reviewed-tests-20260906.log`.

Reports in `logs/recovery-partitions-20260906.Zrp24U/`:
before5256B SHA256 d1689df40ba0184ca827c47ccef48378a5f51d3b2eccdc3fe2fad9b09ade3c2f
esp5559B SHA256 02e8d504893eb0c058c9c7da620428f94cc339a926ed81d173a2b16aa3fb8cd8
root6108B SHA256 041661789158251d1420f38c8ed549f47e44f45f811a95eb047ee5063c78c585

**New target partitions (CURRENT Recovery live BSD names, change on reboot):**
- EFI UUID `PRIVATE-UUID-REMOVED`, type EFI,
  GPT slot4, live **disk0s6**, LBA203903051..204034122,131072 sectors,
  536870912B, blank/no filesystem.
- ROOT UUID `PRIVATE-UUID-REMOVED`, Linux Filesystem,
  GPT slot5, live **disk0s5**, LBA204034123..242798666,38764544 sectors,
  **158779572224B**, blank/no filesystem.
- NEW HELPER UUID `PRIVATE-UUID-REMOVED`, Apple_Boot,
  GPT slot6, live **disk0s8**, LBA242798667..242831434,32768 sectors,
  134217728B. Do not confuse with existing Recovery.
- Remaining gap LBA242831435..242965550,134116 sectors,549339136B.
- ORIGINAL Recovery UUIDPRIVATE-UUID-REMOVED is now GPTslot7,
  same original extent242965551..244276259. ALL original GPT entry bytes
  match post-resize baseline by UUID, including p1/daily p2/Linux APFS p3.
  New slices MUST be resolved by UUID on every next boot, never inferred.

Stopped consumed partition receiverPID48049 normally after review, no target
process/power changes. Port8765 free for next helper; old URLs now unavailable.
Recovery stays open. NO new image install/format/native write test yet.
Next implement root-image transfer/install bounded to new ROOT UUID/extent,
then native driver write firewall confined to that partition, then standalone
boot. Existing native SSD v3 still READ-ONLY and old four-partition identity
guards are intentionally stale; must not reuse unchanged after partitioning.
No commits, extra cores or GPU acceleration. Daily macOS volume untouched by
task mutation commands. Full data backup was not made (metadata only).

## Current — partition creation helper ready, waiting for user execution

M5 still Recovery after validated96GB Linux APFS shrink. No target partitions
created yet as of this handoff. No webcam/powercycle needed.

**RUNNING SERVER:** PID48049, exec session63777. Command:
`python3 -u probe/recovery-resize-server.py --partitioning --bind PRIVATE-LAN-ENDPOINT-REMOVED
--destination /PRIVATE-USER/azahi-port/logs/recovery-partitions-20260906.Zrp24U
--baseline /PRIVATE-USER/azahi-port/logs/recovery-resize-20260906.yS45qc/after/backup.tar.gz`
Log `logs/recovery-partitions-server-20260906.log`. Replaces completed resize
serverPID44040, terminated normally. Per-run upload capability must remain
unchanged while user has downloaded helper. No uploads received yet.
Only GET `/partitions.sh` and token PUT before/esp/root, one per stage,
strict stage ordering. Archives/receipts/validation.json go into corresponding
stage subdirectories. Refuses duplicate reports, preserves invalid reports,
never executes upload contents. No old check.sh/resize.sh endpoint now.

User command:
`curl -q --noproxy '*' --proto '=http' -f PRIVATE-LAN-ENDPOINT-REMOVED -o /tmp/partitions.sh && bash /tmp/partitions.sh create-linux-partitions`
Keep charger connected/Recovery open; do not rerun after partial completion.
This DOES create partitions but not filesystems or KDE installation.

`probe/recovery-create-partitions.sh` local SHA256
`396cfc7c9e67f96db978860bfa41cf2ed528edb7fc4ed6944cb7f225be878501`,
served8098B normalized against local source byte-for-byte. Bash syntax and
M1 model rejection pass. Model/pinned96GB Linux store/System/VG/container,
all original UUID/extents/sector sizes, bounded partition inventory guards.
Backs up GPTs+Linux superblock and metadata before and after each mutation.
Host validation receipts REQUIRED before proceeding. Re-reads GPTs immediately
before each add and checks same cksum/size as validated copies. New EFI device
resolved from fresh metadata; numeric slice never guessed. Explicit EFI UUID
rechecked immediately before adding root. Only mutating commands:
1) `diskutil addPartition disk0s3 %PRIVATE-UUID-REMOVED% %noformat% 536870912`
2) `diskutil addPartition RESOLVED_ESP %PRIVATE-UUID-REMOVED% %noformat% 158913789952`
The command's %noformat% wipes only newly allocated partition space; it does
not run a filesystem formatter. No whole-disk partitionDisk, eraseVolume,
GPT raw writes, existing volume mounts/writes, or boot policy changes.

`probe/validate-recovery-partitions.py`: loads/validates pinned post-resize
baseline via earlier validator. Strict bounded regular-file archive allowlist;
valid GPT headers/table CRCs/both copies; compares ALL original entry bytes
by UUID, allowing slot renumber only; PMBR exact. Verifies all metadata
plists agree with GPT/device list, original Linux96GB APFS checksum/volumes.
Before requires no new partitions; esp requires one512MiB EFI starting at
LBA203903051; root requires unchanged EFI plus148GiB Linux immediately after.
Allows optional128MiB Apple_Boot immediately following root, only inside
approved gap ending beforeLBA242965551. Rejects any extra/overlap/out-of-gap
entry. Final leftover415121408B if helper,549339136B otherwise. New UUIDs and
live devices recorded in root/validation.json for subsequent write guards.
Success marker `LINUX_PARTITIONS_VERIFIED` only after final host validation.
Failure stops; read error/report first, no blind rerun or GPT restore.

Tests: `probe/test-recovery-partitions.py` + mocks12 pass; original11 resize
tests pass after optional --partitioning server mode added. Log
`logs/recovery-partitions-offline-tests-20260906.log`. Synthetic tests exercise
Recovery renumber/live noncontiguous slices, helper/no helper, unchanged
original bytes, out-of-gap helper, rerun refusal, failed before/esp receipts,
changed GPT just before mutation, and actual localhost staged receiver.
No real target device accessed in tests. Original test fixture image was
reattached, identity confirmed Disk Image/Virtual/not Internal/4GiB; removed
only blank synthetic Linux partition (and its automatic helper), then tested
explicit1GiB root size. diskutil keeps exact root size and adds128MiB helper
AFTER it. Image normally detached and preserved. Additional result
`logs/partition-layout-test-20260906.8rrzgj/after-explicit-root.plist`.

Next after user done: check server log + root validation report first;
independently validate all stages. Do not guess new disk numbers. Then prepare
root image install with exact newly-created UUID and write-range guards.
Native write-capable driver, persistent bootloader and SSD KDE remain undone.
Daily macOS p2 is never a filesystem/volume mutation target. No commits.

## Current — resize COMPLETED, validated after report received

**Next-step experiment (HOST image only, not M5):** Created new4GiB sparse
image under `logs/partition-layout-test-20260906.8rrzgj/layout.sparseimage`.
Before partition writes verified hdiutil maps that exact image to hostdisk4,
diskutil identifies Disk Image/Virtual/Internalfalse/4GiB. Set up dummy
partitions and middle free space; tested addPartition explicit EFI GUID,
%noformat%,536870912 then explicit Linux Filesystem GUID,%noformat%,0.
Both succeeded, but Linux (>1GiB) automatically acquired a134217728B
Apple_Boot helper. GPT is reordered physically, so old trailing Recovery
entry moved from slot5 to8 even though its live BSD name stayed disk4s5.
New EFI live slice was disk4s7, new rootdisk4s6, helperdisk4s9: NEVER guess
new slice from partition order. All five original test UUIDs/types/sizes
matched saved before/after plists. Actual target is4096-sector; this image
uses512-sector, so test informs guards but does not prove exact M5 behavior.
Image detached normally after testing and preserved locally, not deleted.
Saved before.plist/after-esp.plist/after-root.plist/after-root-gpt.txt.
This DOES NOT create target partitions. Next helper must compare original
GPT entry bytes BY UUID (permit Recovery slot renumber only), bound every
new extent to current160GB gap, allow/record a new128MiB Apple_Boot only
inside that gap if diskutil creates it, and resolve all live device IDs
from refreshed plists. Prefer512MiB ESP +148GiB root with spare gap so an
auxiliary partition fits. Do not reuse old four-entry validator unchanged.
No next target partition helper ready yet; M5 remains unchanged after resize.

Both stages received fromPRIVATE-LAN-ENDPOINT-REMOVED at19:44. No webcam needed.
`logs/recovery-resize-20260906.yS45qc/before/backup.tar.gz`5331B,
cksum1638206163, SHA256
`6c7342c234d410b14034bc652bc5254f9760b0c027e25bc397eecdf83e429024`.
`logs/recovery-resize-20260906.yS45qc/after/backup.tar.gz`5334B,
cksum3378359546, SHA256
`7d181ae3651f5ce11e5f6e8947aec20340efb1cafaee51d0b3c0a0158cacbcc0`.
Both folders have receipt.txt and validation.json. After report independently
revalidated using `validate-recovery-storage.py --linux-bytes 96000000000
--require-unlocked`: PASS. Protected GPT/MBR fingerprint unchanged from
original baseline, header/table CRCs valid, primary/backup tables agree,
all original partition identities/extents as expected, six Linux APFS
volume UUIDs/roles preserved, all unlocked/no encryption migration.
APFS first-superblock SHA256
`16853be314dd8689c34cfdfc963948d02a681f03d24f15e8dd3e3d3ce2cc97ea`.

**Current physical map, 4096-byte LBAs:**
p1 start6,count140800 unchanged.
p2 DAILY MACOS start140806,count180324745 unchanged, never filesystem target.
p3 LINUX APFS start180465551,count23437500 =96000000000 bytes, sameUUID.
FREE start203903051,count39062500 =160000000000 bytes.
p4 RECOVERY start242965551,count1310709 unchanged.
Disk total244276265 sectors. Linux containerdisk3, daily containerdisk4.
After preferred min75872023347; hard min65134605107; max256000000000.

No Linux root or ESP partitions created yet; no formats/root-image installs.
M5 stays in Recovery. Resize serverPID44040/session78893 still listening but
both upload slots consumed; never rerun resize helper or restore old GPT.
Next: design/test free-space-only addPartition step. Local diskutil manual
supports addPartition after a partition using %GUID% %noformat% size, but
warns of gaps/auxiliary booters. Testing on a NEW temporary host disk image
before preparing target mutation. Upstream asahi-installer diskutil.py uses
addPartition and then resolves the resulting partition in refreshed layout;
do not assume new slice numbering without validation. Native writable NVMe
and standalone loader/rootfs work remain unfinished. No CPU/GPU advance.

## Newest — guarded resize helper ready, awaiting user execution

User reports `diskutil apfs unlockVolume disk3s1 -nomount` succeeded; fresh
script will independently require all six Linux APFS volumes unlocked and
no encryption migration. No webcam needed; no power cycle requested.

**Running server:** PID44040, exec session78893,
`probe/recovery-resize-server.py --bind PRIVATE-LAN-ENDPOINT-REMOVED --destination
/PRIVATE-USER/azahi-port/logs/recovery-resize-20260906.yS45qc --baseline
/PRIVATE-USER/azahi-port/logs/recovery-storage-20260906.4VxUyx/backup.tar.gz`.
Log `logs/recovery-resize-server-20260906.log`. Old report serverPID42246
terminated after completed upload. Current server only serves `/resize.sh`
and two token-protected bounded uploads, before/after, to separate folders.
Do NOT restart server or change its token while target script may be active.
No target upload yet at handoff. Served8291B helper normalized to local
reviewed script exactly; SHA256 local
`7330c3cc6251e5f96e5dd54768dff290a9acd28877743813c90a609b173f57e7`.

User handoff one line:
`curl -q --noproxy '*' --proto '=http' -f PRIVATE-LAN-ENDPOINT-REMOVED -o /tmp/resize.sh && bash /tmp/resize.sh resize-linux-96gb`
Tell user charger connected, don't interrupt/reboot, leave Recovery open.
This IS a resize, not read-only report. No formatting/deletion/new partition.

`probe/recovery-resize-linux.sh` is Bash3 compatible, fixed PATH, model
Mac17,9, explicit resize-linux-96gb arg, exact Linux System/VG/store UUIDs,
all four old GPT partition UUID/offset/size/sector guards, exact disk size,
six unique allowlisted volume UUIDs/unlock/migration checks and fresh limits.
Copies primary+backup GPT and Linux APFS first superblock before/after.
Before the **only mutating command** `diskutil apfs resizeContainer disk0s3
96000000000`, it requires upload checksum/size receipt AND host validation
marker, then repeats identities/partition/unlock/limits checks immediately.
No use of raw GPT writes, formats, mount/unmount, policy changes, or daily p2
filesystem access. Refuses rerun after p3 changed. Resize error stops, leaves
Recovery log path, instructs no retry/GPT restore. Post-collect expects p3
exact96GB and every other original partition unchanged. Success marker:
`LINUX_RESIZE_VERIFIED` only after host also validates after report.

Host validator checks archive bounds/allowlist/regular files, checksum-valid
GPTs and APFS superblock, exact sizes/identities/volume roles, plus compares
protective MBR and ALL GPT entry bytes except p3 end-LBA to original baseline.
Protected fingerprint `2b1feb9db283085b4eacc5b440293ba0fa02c6ca346a2ec3f8dfd2ce1629d62d`.
Both stages saved as before|after/backup.tar.gz, receipt.txt, validation.json.
422 means validation failed and archive is preserved; do not rerun blindly.
The host never executes uploaded bytes. One upload per stage, after requires
valid before. Metadata backups are NOT full filesystem backups.

`probe/test-recovery-resize.py` + `test-recovery-resize-mocks.sh`: 11 tests
pass. Real baseline parse, locked rejection, synthetic resized GPT/APFS
checksums/protected bytes, corruption/path rejection, mocked shell success
and no rerun, locked/wrong-p2/minimum/bad-receipt refusal, localhost receiver
exact download and before/after ordering/duplicate refusal. No target devices
accessed by tests. Log `logs/recovery-resize-offline-tests-20260906.log`.
Host execution of real helper correctly rejects M1 model immediately.
No hardware resize completed yet; next check server receipts/log first.

## Current — read-only report received and validated, awaiting local unlock

Archive `logs/recovery-storage-20260906.4VxUyx/backup.tar.gz`, 5329 bytes,
cksum4115333838, SHA256
`34bff2a70ad89d4d6675a32839a4d43a598148fab864be80cf4cb6d8e2449c74`.
`probe/validate-recovery-storage.py` validates receipt SHA, exact archive
member allowlist/regular-file/size bounds (without extraction), both GPT
header/table CRCs, identical tables, four exact partition UUIDs/extents,
disk geometry, Linux APFS first-superblock checksum/UUID/size, limits target.
Validation passed. This is metadata backup, NOT a full filesystem backup.
Never restore old GPT alone after resizing/changing filesystems.

Recovery report currently resolves Linux container to **disk3** (older
Recovery disk4 is stale), Data **disk3s1**, System **disk3s3**. Same pinned
volume and container UUIDs. Data and System report locked; System is mounted
read-only at /Volumes/Linux, Recovery volume disk3s5 supplies current Recovery.
No webcam needed this turn: received structured report directly from
PRIVATE-LAN-ENDPOINT-REMOVED. No power cycle. Native session ended previously.

CurrentSize/MaximumSize 256000000000; MinimumSizeNoGuard 65178645299;
MinimumSizePreferred **75916063539**. Used 56115122176, free199884877824.
Candidate retain96000000000 APFS, free160000000000 for future Linux storage;
no exact new partition layout committed, no shrink helper executed/prepared.
Daily p2 remains completely excluded from filesystem/volume mutations.
Local diskutil manual requires all APFS volumes unlocked before shrink.
Next user command (only while this same Recovery session persists):
`diskutil apfs unlockVolume disk3s1 -nomount`, password entered locally only.
This unlock is NOT decryptVolume and does not disable FileVault.
After user response confirm state; build guarded Linux-only shrink procedure
with fresh identity/limits guards and post-operation protected extent checks.
Do not hand out an unguarded numeric disk resize command. Native write and
persistent boot work remain unfinished; historical read hash mismatch is
not resolved by this Recovery metadata validation.

Existing serverPID42246/session34989 still running but upload slot consumed;
do not rerun old report helper (PUT would409). Subsequent report needs fresh
destination/capability and explicit new download. HTTP, not HTTPS; working
download used curl -q --noproxy '*' --proto '=http'. Old server logging has a
malformed-request AttributeError (self.path absent); valid HTTP still works.

The entries below are historical and superseded by this current section.

**Current — Recovery Terminal ready:** Webcam
`logs/recovery-storage-ready-20260906.jpg` confirms the M5 Recovery terminal.
Native v3 session has ended. Read-only report receiver running at
PRIVATE-LAN-ENDPOINT-REMOVED, exec session34989, log
`logs/recovery-storage-server-20260906.log`, destination
`logs/recovery-storage-20260906.4VxUyx`. GET /check.sh verified byte-for-byte
against reviewed recovery-storage-check.sh after substituting the per-run
upload capability. It serves only the helper and accepts one bounded report;
it never executes uploads. No report received yet. User next two commands:
curl -f PRIVATE-LAN-ENDPOINT-REMOVED -o /tmp/check.sh
bash /tmp/check.sh
Do not restart receiver with a new capability while the downloaded script is
in use. No resize/format/mount/boot changes are part of this helper.

## Current next step: Recovery read-only space report

Webcam `logs/native-ssd-ro-v3-health-20260906.jpg` shows controller state
`live` and blkid identifies p3 as APFS. Full UUID output is crowded; do not
claim an independently exact optical UUID comparison. Native reads remain
consistent, main namespace write counters zero, all namespaces RO.

User asked whether the agent can type. Read-only checks confirm no target
/dev/cu.usbmodem* devices, no enabled USB/network controller in this native
DT, old Recovery IPPRIVATE-LAN-ENDPOINT-REMOVED absent from ARP and TCP22 not reachable. Old
guest-command.py needs two CDC ports; uinject needs an existing guest shell
transport and cannot create one. Do not pretend host keyboard automation
can reach this separate physical laptop. No unrelated Bluetooth ports used.

Prepared `probe/recovery-storage-check.sh` for one-shot Recovery inventory,
Linux-only APFS resize LIMITS query, GPT primary/backup copies, and Linux
superblock copy. NO resize, format, mount/unmount, policy or boot writes.
Pins M5 model, Linux volume/VG/store, all four partition UUIDs/offsets/sizes,
4096-sector geometry and APFS container UUID before raw reads. Writes only
Recovery /tmp and uploads a bounded archive to our private LAN host. Shell
syntax passes and executing on this M1 host exits 'Not the M5 target'.
Script SHA256 fe1ad182fdff4a01d987c70eb110dacc4fed8067b183eaa1b62a5aaf1d3275c1.
Limits query matches diskutil's local manual and upstream asahi-installer
src/diskutil.py get_resize_limits. No numeric resize size is present.

Existing backup server now accepts --script; default old behavior unchanged.
Server is NOT running. Host en0 IPPRIVATE-LAN-ENDPOINT-REMOVED, TCP8765 free. When Recovery is
ready, create a new mktemp directory under logs and start:
python3 -u probe/recovery-backup-server.py --bind PRIVATE-LAN-ENDPOINT-REMOVED --destination NEW_DIR --script probe/recovery-storage-check.sh
Then user runs curl -f PRIVATE-LAN-ENDPOINT-REMOVED -o /tmp/check.sh and
bash /tmp/check.sh. Inspect report/validate GPT+APFS checksums on host before
considering any Linux-side storage changes. Daily p2 remains excluded.

Current laptop still native v3 shell. Asked for shutdown, hold power,
Options/Recovery and Utilities > Terminal; select Linux if OS choice appears.
This is a read-only inventory stage, not authorization to touch daily macOS.
No target writes or proxy actions this turn. Handoff cue requested every turn.

**Latest read-only checks:** User ran lsblk -o NAME,RO,PARTUUID and
cat /sys/block/nvme0n1/stat. Webcam
`logs/native-ssd-ro-v3-identities-20260906.jpg` shows all three NVMe namespaces
RO=1, and main namespace write-count field 5 and sectors-written field 7 both
zero. Partition UUID rows are present and appear consistent with the recorded
layout, but do not treat blurred full UUID transcription as an exact check.
Next short checks: `cat /sys/class/nvme/nvme0/state` and
`blkid -p /dev/nvme0n1p3` (expect live, APFS UUID
PRIVATE-UUID-REMOVED). No reboot or additional probing requested.
Read consistency is verified; historical hash difference remains unresolved.

## Latest hardware result: native discovery + repeat reads, stale-baseline check stops

V3 handoff completed, proxy disappeared, and the test ran automatically.
Webcam `logs/native-ssd-ro-v3-screen1-20260906.jpg` shows NVMe namespaces and
partitions with RO=1; both /dev/nvme0n1 and p3 completed four 16MiB direct-read
passes and SSD_DIRECT_READ_VERIFY_DONE. The per-region repeated digests match
within this native boot. Native NVMe discovery and 128MiB consistent reads
are observed; the previous missing-export failure is resolved.

The service then stopped with AssertionError: Read digest differs from
verified HV baseline. The historical hashes predate the Recovery/V5 bootloader
installation, which can change p1 and p3 boot metadata, but that explanation
is not yet verified. Do NOT remove the mismatch check or claim unchanged
SSD content. Full current hashes are not reliably transcribed from photo.
The final zero-write-counter/controller-live assertions occur AFTER the
failed hash check and have not run. Next obtain read-only lsblk partition
identities and namespace stats from the shell; inspect APFS identity as needed.

Firmware emits many NVICLOG-not-yet-written/ERR_ABSENT oslog messages, but
the reads completed. No panic visible. Current native shell/test session is
left running, no proxy client, all observed NVMe namespaces read-only. Do
not restart the test (its probe refuses preexisting devices). No power cycle
requested. No installation or writable-storage success is claimed.

**Live override — v3 loading:** User cycled into Linux proxy. Fresh V5 at
0x10005118000 verified original vectors/unused SMP and original WFI range
0x10005924000..0x10005930000. Unchanged native prefix then chainloaded in RAM.
v3 native transfer underway; exact ANS link activation and RUN=0x10 passed.
Logs `native-ssd-ro-v3-{preflight,chainload,boot}-20260906.log`. No media or
partition writes. Installed V5/backup unchanged. Do not run another proxy
client during transfer; do not use CPU diagnostic helpers after chainload.

## Newest result: v2 load failure fixed locally; cycle required for v3

Webcam `logs/native-ssd-ro-service-failure-20260906.jpg` clearly shows the
manual service ran, then modprobe nvme_apple failed with unknown symbols:
devm_apple_sart_get, apple_sart_add_allowed_region,
apple_sart_remove_allowed_region (err -2). NVMe module did not load/probe;
no native SSD access has been established. Both input device names and
trackpad firmware-ready logs are visible; physical keyboard shell use is
confirmed, physical native trackpad motion remains untested.

Cause is the local build's missing modpost `-M` flag: .export_symbol records
in apple-sart.o were omitted from the final module's export table. Fixed
build now asserts all three __ksymtab symbols and generated symvers entries.
NVMe module SHA unchanged (94755503...); corrected SART SHA256
58ba58e4a6dd0b4574751d224772d9bfe447fa3f4e8bdba8cfa9e7c52b80305d.
Preserved old modules in nvme-driver/vendor/. No target changes this turn.

Candidate `native-ssd-ro-v3-20260906.bin`: 1027836304 bytes, SHA256
373a0954c8d84a7e98a79dd7eeb69c650a0fe1bf9c27e36b4cfd253988310493.
Offline runner validation passes; DT/kernel/initramfs baseline unchanged.
Adds RAM shell-profile fallback to request the test once if normal startup
skipped it, and creates the RAM log before early commands. Test not yet run.
`boot-native.py --ssd-readonly` now rejects the broken v2 module identity.

Current target is still the v2 native root shell; USB proxy absent, no client.
Asked for physical shutdown, hold power for startup options, select Linux
until Running proxy. Do not choose daily macOS or Options/Recovery. Then
verify fresh V5, chainload unchanged native prefix, transfer v3 as before
using NEW log paths. No SSD data writes/partition changes/commits.

Older state notes below are chronological, not current instructions.

**Newest:** User reports `native-ssd-ro-check` is inactive. Appended image
archive was parsed locally: script, service and correct wants symlink are
present. Missing RAM log plus inactive state does not establish why startup
was skipped. Next user command: `systemctl start native-ssd-ro-check` to run
the guarded read-only diagnostic. Its probe refuses existing NVMe devices;
do not bypass that guard. No reboot requested. User asks for no name usage
and an audible cue at every handoff/end of turn.

**Latest user report:** The user's name is PRIVATE-USER, not PRIVATE-USER (earlier notes
incorrectly inferred it from the host account name). Native keyboard/shell
respond, but `tail -25 /run/native-ssd-ro.log` reports no such file. No SSD
test success can be inferred. Check `systemctl status native-ssd-ro-check
--no-pager` next to distinguish absent/skipped service from an early failure
before log creation. Do not blindly reprobe; retain the running native shell.

PRIVATE-USER approved moving one-core SSD boot ahead of CPU research. **Daily-driving
macOS partition 2 is out of scope. No commits.** Preserve p1 boot and p4 Recovery.
Linux-named p3 is APFS containing boot infrastructure, not disposable root space.
No partition or filesystem modifications have been made during this test.

## Current live state

The fourth clean V5 boot passed fresh read-only preflight, then the unchanged
native loader prefix was chainloaded into RAM at 0x100043a4000. Installed V5 on
SSD and its verified original backup remain unchanged. V5 no longer describes
the currently running RAM loader; do not use CPU diagnostic helpers now.

Native SSD v2 RAM payload transfer and native handoff completed; USB proxy
disappeared as expected. First webcam view shows early Linux console text.
The panel test result is still pending. The only new ANS hardware
control change is the exact verified APCIE_SYS_ST0 activation at 0x280900150;
all three parents were ACTIVE and ANS coprocessor RUN read 0x10. No NVMe/media
commands were sent by the preparation helper. One proxy client only.

- Image `native-ssd-ro-v2-20260906.bin`, 1027835983 bytes,
  SHA256 `689311b3178f9f22337704ecf867b86a516ef8ef013e618863118350d7c3fdf2`.
- DTB SHA256 `35bcfe35db7fb450524b02c4b9b1dd45a5c8339a9db36492f5c21aa0e280a7b5`.
- Exact native kernel/prefix and RAM fences unchanged; see NATIVE-CHECKPOINT.md.
- Modules/provenance/read-only command filtering: `nvme-driver/README.md`.
- Logs `native-ssd-ro-{preflight,chainload,boot}-20260906.log`.
- Build log `native-ssd-ro-v2-build-20260906.log`.

Expected panel result: NATIVE_SSD_READS_PASS with both prior 16MiB extent
hashes matched four times each, live controller, zero completed media writes.
Three webcam captures `logs/native-ssd-ro-screen{1,2,3}-20260906.jpg` show
console text, but it is too small/blurred to read; whole-frame Vision OCR
returned no text. Do not infer success, panic or a definite shell prompt.
Asked PRIVATE-USER to bring the screen closer or report the last two lines. No power
cycle requested; no proxy/guest client remains. Native session left intact.
Once a shell is confirmed, inspect `/run/native-ssd-ro.log` and
`systemctl status native-ssd-ro-check --no-pager`, then the kernel log; do not
blindly reprobe an already initialized controller. Built-in physical input
also remains unverified natively.

PRIVATE-USER reports the last messages mention macsmc_power being blacklisted and
an unknown oslog message. Both also occurred in the successful HV input/SSD
session (console.log lines 2901 onward, 3382 and 3906); they do not identify
a fatal failure. Fourth webcam capture shows an additional console line,
still unreadable. PRIVATE-USER then confirmed pressing Enter on the built-in keyboard
produced the root shell prompt: native shell and physical keyboard response
are now user-verified. This is not a trackpad or SSD success claim. Next read
`/run/native-ssd-ro.log` from that shell. Do not remove the SMC blacklist
or request a cycle based only on these messages.

This result is **not yet observed**. No native SSD, writable storage, persistent
boot or additional CPU success is claimed. Root is still RAM for this test.
