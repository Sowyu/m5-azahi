# Audit: standalone loader + research-archive device trees

**46 findings: 4 critical, 10 high, 21 medium, 11 low.**

Scope: `standalone-loader/` (azahi_standalone.c/.h, build-bundle.py, build-aligned.py,
README.md) and `research-archive/` device trees plus plist2adt.py, deploy.sh,
m1n1-vmtmr-ro.patch, kconfig.txt. All files read in full.

Read these four first: **D1** (ANS power-controllers at the wrong PMGR base, will write
always-on fabric registers), **C1** (initrd cache flush targets an address nothing was
written to), **C2/D5** (root write-guard trusts hard-coded LBAs next to a redacted PARTUUID),
**D7** (the PMGR file that is actually included has 67 parent power-domain links stripped out).

One structural cause runs under most of the rest: the same addresses and lengths are typed
by hand into C, two Python builders, and six device trees, with no generator and no shared
source. See **X1**.

## standalone-loader/m1n1-20260911/src/azahi_standalone.c

### C1 (critical) — cache maintenance is done on the wrong initrd address
`azahi_standalone.c:134-135`. `kboot_set_initrd((void *)initrd, ...)` registers the initrd
*in place inside the bundle*, then line 135 cleans the D-cache for `INITRD_ADDR`
(`0x10a00000000`), an address this function never wrote and never copied to.
Why it matters: the 67 MB of initrd bytes that the kernel will actually read (at `initrd`,
inside the bundle) are left dirty in L1/L2 while a wholly unrelated 67 MB window gets
cleaned. If the kernel or a later stage reads the initrd with MMU/caches configured
differently, it sees stale data, and the failure is a silent initramfs corruption, not a
clean stop. The two constants also disagree with `build-bundle.py:84`, which records
`initrd_address=0x10a00000000` in the receipt as if a copy happened.
Fix: clean the range actually handed to `kboot_set_initrd`:
`dc_cvau_range((void *)initrd, h->initrd_len);` — or copy the initrd to `INITRD_ADDR`
first and pass that pointer to `kboot_set_initrd`. Pick one and delete the other constant.

### C2 (critical) — DT-declared root partition LBAs are trusted with no runtime check
`azahi_standalone.c:121-122` accepts any DT whose root compatible is `apple,j714s`, and
`build-bundle.py:46` only asserts the string `azahi,j714s-nvme-rootguard` appears somewhere
in the DT blob. The rootguard DT
(`research-archive/t6050-j714s-native-rootguard.dts:6-8`) carries
`azahi,root-partuuid = "PRIVATE-UUID-REMOVED"` next to real
`azahi,root-first-lba = <204034123>` / `azahi,root-end-lba = <242798667>`.
Why it matters: the PARTUUID that would let the guard verify the window is a redacted
placeholder that can never match, so the only thing gating writes is a hard-coded LBA pair.
If the partition table shifts (resize, restore, different machine), those LBAs point into a
macOS volume and the "root-only write" guard authorizes writes onto it. Data loss, not a
boot failure.
Fix: refuse to arm the guard unless the PARTUUID read from the on-disk GPT at
`root-first-lba` matches `azahi,root-partuuid`; drop the LBA properties and derive them from
the matched GPT entry.

### C3 (high) — CRC32 is treated as an integrity gate, and the header itself is uncovered
`azahi_standalone.c:113-117`. The four `tinf_crc32` comparisons cover the payload sections
only. `magic`, `version`, the four lengths and the four CRC words (`azahi_standalone.h`
struct at `.c:22-26`) are covered by nothing.
Why it matters: CRC32 is not a tamper check — anyone who can write the boot image can
recompute all four values. And a single flipped bit in `args_len`/`dt_len`/`gzip_len` inside
the accepted ranges reslices every following section; the loader then CRCs the *shifted*
data against the *stored* CRCs, and while that normally fails, the failure mode is a wrong
`end` computed at line 101 from corrupt lengths before any CRC runs, so the RAM-bounds check
at 105-108 is performed on attacker-chosen numbers.
Fix: add a CRC (or better, a SHA-256/signature) over the 44-byte header itself and verify it
before line 101 uses any length field; keep the section CRCs as a corruption check only and
stop describing them as validation.

### C4 (high) — the header is dereferenced before any address is validated
`azahi_standalone.c:90-91`. `h = (void *)_payload_start` is read (`memcmp` of 8 bytes, then
nine `u32` loads at 97-99) before the checks at 102-108 establish that the payload lies
inside tested RAM.
Why it matters: if the image was loaded somewhere unexpected, the loader faults reading its
own header instead of printing `AZAHI_STANDALONE_STOP`. The whole point of the stop path is
to fail loudly.
Fix: validate `_payload_start` and `_payload_start + sizeof(*h)` against
`cur_boot_args.top_of_kernel_data` before the first dereference.

### C5 (high) — ANS MMIO is read before the PCIe link it lives behind is brought up
`azahi_standalone.c:65`. `read32(0x419600044)` ("check warm firmware") runs *before* the
`APCIE_SYS_ST0` link bring-up at lines 68-83.
Why it matters: 0x419600000 is the ANS BAR reached through APCIe ST0. In the one case the
code explicitly anticipates (`states[3] == 0x1000030f`, link nibble not 15), the link is by
the code's own admission not up yet, so this read targets a device behind a down link. That
is exactly the SError class the DT comments elsewhere in this repo complain about, and it is
unrecoverable.
Fix: move the `running = read32(0x419600044)` check to after the link-ready loop
(after line 83), keeping the `0xabad1dea` guard.

### C6 (high) — `INITRD_BYTES` is an exact-equality gate on a 70 MB artifact
`azahi_standalone.c:20` and `:99` (`h->initrd_len != INITRD_BYTES`), duplicated at
`build-bundle.py:34` and `:48`, and again in prose at `standalone-loader/README.md:8`.
Why it matters: the README already documents this biting — "Installed courier v4 fails the
loader's exact 70,698,084-byte initrd requirement". Every initramfs regeneration is a loader
source change plus a rebuild. Nothing about correctness needs the *exact* length; the CRC
already pins the content.
Fix: replace with a range check (`h->initrd_len >= 1<<20 && initrd end <= top_of_kernel_data`)
and let `initrd_crc` pin identity. Same for `KERNEL_BYTES` at `:19`/`:129`: the check that
matters is `((struct kernel_header *)kernel)->image_size == dest_len`, which is
self-consistent and needs no constant.

### C7 (high) — `SAFE_HIGH` silently requires a 64 GiB machine
`azahi_standalone.c:16`, enforced at `:107`
(`phys_base + mem_size < SAFE_HIGH` → stop). `SAFE_HIGH - 0x10000000000 = 0xf4ab00000`
≈ 61.2 GiB of RAM above the DT memory base.
Why it matters: an otherwise identical J714s with 24/36/48 GB stops with
"payload or RAM outside tested layout", a message that names neither RAM size nor the
threshold. The DT (`t6050-j714s.dts:53`) hardcodes a matching `0x10 0` = 64 GiB.
Fix: derive the required top from `KERNEL_ADDR + KERNEL_BYTES` and the initrd extent rather
than a machine-specific constant, and print the observed vs required values in `stop()`.

### C8 (medium) — the builder never produces the bootargs the loader demands
`azahi_standalone.c:118-120` requires all three of `azahi.ssd_root=1`, `maxcpus=1` and the
literal `root=PARTUUID=PRIVATE-LINUX-PARTUUID-NOT-CONFIGURED`.
`build-bundle.py:57-60` lifts bootargs verbatim out of the source image and appends only
` azahi.standalone=1 drm.panic_screen=qr_code`; `inspect()` at `:45` checks only
`maxcpus=1` and `azahi.ssd_root=1`.
Why it matters: two directions of breakage. A bundle can pass every host-side assert and
then stop at boot on the missing PARTUUID string. And the string the loader insists on is a
"NOT-CONFIGURED" placeholder, so a bundle that *does* satisfy the loader hands the kernel a
root device that cannot exist — it is a boot-arg check that guarantees the kernel cannot
mount root.
Fix: assert the full required set (including the PARTUUID token) in `inspect()`, and change
the loader to require a well-formed `root=PARTUUID=<uuid>` rather than the placeholder
literal.

### C9 (medium) — hard-coded CPU count, board id and DART index
`azahi_standalone.c:94` (`board_id != 8`), `:142` (`for i in 1..18`), `:145`
(`dapf_init("/arm-io/dart-mtp", 1)`).
Why it matters: the "18" is a third copy of the core count that already exists in the ADT and
in `t6050.dtsi`'s cpu-map. If m1n1's `MAX_CPUS`/actual topology differs, the loop silently
checks the wrong range and the "secondary unexpectedly alive" guard becomes decorative.
Fix: iterate to the ADT/`smp` core count instead of a literal.

### C10 (medium) — decompression destination is never checked against the bundle
`azahi_standalone.c:124-126`. `tinf_gzip_uncompress` writes `KERNEL_BYTES` to `KERNEL_ADDR`
with no assertion that `[KERNEL_ADDR, KERNEL_ADDR+KERNEL_BYTES)` is disjoint from the loader
image, the bundle, or the initrd it is about to hand off.
Why it matters: today it happens to be disjoint because of the `low_bundle`/`high_test`
conditions at 102-104, but that is an unstated coupling between four constants in three
places. Change any one and the kernel overwrites its own compressed source mid-decompression.
Fix: one explicit overlap assertion against `_base`, `end`, and `INITRD_ADDR` before the call.

### C11 (low) — `prepare_ans` state predicate is unreachable in one branch
`azahi_standalone.c:60-61` already rejects every `states[3]` except those with link nibble 15
or the exact value `0x1000030f`. The bring-up branch at `:68` therefore only ever runs for
`0x1000030f`.
Why it matters: the code reads as if it handles a general "link down" case; it handles one
magic value. Anyone extending the accepted state set at line 61 will not notice they also
changed what line 68 does.
Fix: hoist the `0x1000030f` special case into a named predicate used by both sites.

## standalone-loader/build-bundle.py

### B1 (high) — source image is parsed by scanning for ASCII markers with no format check
`build-bundle.py:57-65`. `source.index(b'chosen.bootargs=')`, then `dt_len` is read from
`source[dt_start+4:+8]` as big-endian with no check that `source[dt_start:dt_start+4] ==
d00dfeed`, then `source.index(b'm1n1_initramfs', gz_start)` searches for a marker *inside the
gzip byte range*.
Why it matters: a false-positive `m1n1_initramfs` hit inside compressed kernel data truncates
the kernel and shifts the initrd; a bootargs line not followed by an FDT yields a garbage
`dt_len` and silently wrong slices. The only backstop is the kernel SHA at `:49`, which is
itself a hard-coded constant for one specific kernel — regenerate the kernel and the backstop
is gone.
Fix: assert the FDT magic at `dt_start`, assert `40 <= dt_len <= 65536` before slicing, and
search for the initramfs marker from `gz_start + gz_len` derived from the gzip trailer rather
than by scanning the compressed region.

### B2 (medium) — `_base == 0` assertion checks a link-time value, not the load address
`build-bundle.py:73`. The loader's runtime logic (`azahi_standalone.c:102-104`) branches on
`(u64)_base` being either below `SAFE_LOW` or exactly `0x10400000000`. The builder asserts
the ELF symbol is 0.
Why it matters: it reads as a guard on the layout the loader tests, and it is not one. The
builder cannot in fact verify the runtime base, so the assert gives false confidence.
Fix: drop the assert or replace it with a comment stating the base is decided at load time.

### B3 (medium) — hard-coded macOS toolchain path
`build-bundle.py:69`: `/opt/homebrew/opt/llvm/bin/llvm-nm`.
Why it matters: the build is unreproducible anywhere but one Apple-silicon host with Homebrew
LLVM, and the failure is a `FileNotFoundError` rather than a useful message. The rest of the
script is portable.
Fix: `os.environ.get('NM', 'llvm-nm')` and resolve via `shutil.which`, erroring with the name
that was searched for.

### B4 (medium) — negative-symbol assertions are substring matches on the whole nm output
`build-bundle.py:75`: `'t6050_smp_trace' not in symbols`.
Why it matters: this is checking a safety property (no tracing/reset-marking code in the
shipped loader) with a check that any similarly named symbol, or a symbol in a comment-like
string, defeats or falsely trips. It also does not cover the parsed symbol table it just built.
Fix: check membership in `parsed`, not substring in the raw text.

### B5 (low) — `inspect()` duplicates every constant the C loader already hard-codes
`build-bundle.py:33-34,48` repeat `4096`, `65536`, `32<<20`, `70698084`, `77398016` from
`azahi_standalone.c:19-20,97-99`.
Why it matters: five constants in two languages with no shared source. C6 above is the
already-realised cost.
Fix: emit the limits into a generated header consumed by both, or at minimum a single
`constants.py` the C build reads.

## standalone-loader/build-aligned.py

### A1 (medium) — trailing padding cannot achieve the alignment the docstring claims
`build-aligned.py:3` ("exact RAM-tested v2 plus 16 KiB zero padding", "Alignment is supported
by T6040 cold-boot evidence") and `:39` (`source + bytes((-len(source)) % PAGE)`).
Why it matters: appending 170 zero bytes to the *end* of the image changes the total size to a
multiple of 16 KiB. It does not change the alignment of the loader, the header, the kernel
gzip, or the initrd *within* the image, and it cannot change where the image is loaded. If the
cold-boot problem was an alignment problem, this build does not fix it; if it was a
size-multiple problem, the docstring names the wrong mechanism.
Fix: state which object needs 16 KiB alignment and pad *before* it, or drop the file and
record that the size rounding is what Recovery wanted.

### A2 (medium) — `16 KiB padding` is actually 170 bytes, hard-coded in the validator
`build-aligned.py:22-28`: `size = 92651350`, `len(data) == 92651520`,
`receipt['padding_bytes'] == 170`.
Why it matters: the docstring says 16 KiB, the code appends 170 bytes, and both the input size
and the padding length are frozen literals. Any change to the v2 bundle (see C6 — the initrd
length is expected to change) makes all three asserts fire at once with no indication which
constant is stale.
Fix: compute `size = len(source)` from the file, keep only the SHA assert as the identity
check, and drop the two derived literals.

## research-archive/t6050-j714s-hv-nvme.dts

### D1 (critical) — the four ANS power-controllers are placed at the wrong PMGR base
`t6050-j714s-hv-nvme.dts:137,141` declares `pmgr_nvme: power-management@280600000` with
`reg = <0x2 0x80600000 0 0x4000>`, and the comment at `:128` states "all four live in pmgr0
at 0x280600000". They do not. In `t6050-pmgr-refs.dtsi` the four labels sit inside `&pmgr1`
(block at `:787-1397`), whose base is `0x280900000` (`t6050-pmgr-nodes.dtsi:9,14`):

| label | refs line | real address | what `hv-nvme.dts` actually points at |
|---|---|---|---|
| `ps_apcie_st0` @0x128 | 821 | 0x280900128 | 0x280600128 = `ps_pmp` (always-on) |
| `ps_fab6_soc` @0x138 | 837 | 0x280900138 | 0x280600138 = `ps_pmgr_soc_ocla` |
| `ps_ans` @0x140 | 847 | 0x280900140 | 0x280600140 = `ps_b2b_ctrl_nogate` (always-on) |
| `ps_apcie_sys_st0` @0x150 | 865 | 0x280900150 | 0x280600150 = `ps_fab0_acc_1` (always-on) |

The loader agrees with `pmgr1`, not with this file: `azahi_standalone.c:46` hard-codes
`{0x280900138, 0x280900128, 0x280900140, 0x280900150}`, and the sibling DT
`t6050-j714s-hv-input-ssd.dts:7,11` uses `0x280900000` correctly.
Why it matters: this file's own comment (`:96-99`) records that one unexpected
`apple-pmgr-pwrstate` probe write SErrored the machine. Booting this DTB makes the driver
issue its probe-time ACTIVE+AUTO_ENABLE flush against three always-on fabric/PMP domains,
and worse, `nvme` declares `resets = <&ps_ans>` at `:272`, so the NVMe driver will assert a
PMGR reset on `b2b_ctrl_nogate` — a fabric control domain, not ANS. Three of the four are
`apple,always-on` in the generated tree and are not marked so here (`:143-176` marks only
`fab6_soc`), which removes the one guard that would have blocked the writes.
Fix: change `:137` to `power-management@280900000` and `:141` to
`reg = <0x2 0x80900000 0 0x4000>`, and correct the comment at `:128`. Then add a build check
that every hand-written `power-controller@<off>` matches the label/offset/parent recorded in
`t6050-pmgr-refs.dtsi`.

### D2 (medium) — NVMe compatible disagrees with the sibling variant
`t6050-j714s-hv-nvme.dts:262` uses `"apple,t6050-nvme-ans3", "apple,t8103-nvme-ans2"`;
`t6050-j714s-hv-input-ssd.dts:61` describes the same controller as
`"apple,t6050-nvme-ans2", "apple,t8103-nvme-ans2"`, and its comment at `:60` calls it "ANS2
ABI". The reference DTB for the previous generation, `t6030-j514s.dts:2679`, uses
`"apple,t6030-nvme-ans3"`.
Why it matters: the leading string is what a future in-tree driver will match on. Two files in
one directory disagree about the ANS generation of the same silicon, and one of them
contradicts the M3-Pro reference sitting beside it. Whichever is wrong will be copied forward.
Fix: pick `-ans3` (matching the t6030 reference and the M4+ split described at `:240-259`),
apply it to both files, and delete the "ANS2 ABI" comment.

## research-archive/t6050-j714s-native-ssd-ro.dts

### D3 (high) — maps 0x60000 of a region a sibling file documents as bus-erroring
`t6050-j714s-native-ssd-ro.dts:20-22` gives `nvme` three reg entries, the third being
`<0x4 0x1dcc0000 0 0x60000>` named `"nvmmu"`.
`t6050-j714s-hv-nvme.dts:244-247` states the opposite for that exact address: "ans reg[3] =
0x41dcc0000 holds ONLY the NVMMU (+0x28100..+0x28120). Every AP access to reg[3] beyond the
base page bus-errors (L2C_ERR 0x82; 189 guest SErrors all latched 0x41dce4908)".
Why it matters: `0x41dce4908` is inside the 0x60000 window this file declares. Any driver that
ioremaps and touches the named region past the first page takes the documented SError. The
two files were written from the same hardware sessions and disagree.
Fix: shrink the `nvmmu` entry to the one page that is known good
(`<0x4 0x1dcc0000 0 0x4000>`), or drop the third entry as `hv-nvme.dts:263-264` does.

### D4 (medium) — SART described with three different compatibles for one MMIO block
`t6050-j714s-native-ssd-ro.dts:7` says `"azahi,j714s-sart-v4"`;
`t6050-j714s-hv-input-ssd.dts:46` and `t6050-j714s-hv-nvme.dts:203` say
`"apple,t6050-sart", "apple,t6000-sart"`; `t6030-j514s.dts:2672` (the reference) says
`"apple,t6030-sart", "apple,t6000-sart"`. `hv-input-ssd.dts:45` comments "Existing live-kit
SARTv4 translation supplies this v3 guest ABI", while `hv-nvme.dts:182-183` says "ADT says
sart-version = 4 ... which is what apple,t6000-sart drives".
Why it matters: `CONFIG_APPLE_SART=m` (`kconfig.txt:` in-tree driver) matches only the
`apple,*` strings. The `azahi,j714s-sart-v4` variant silently needs an out-of-tree module that
is not named anywhere in the DT, so this DTB boots with no SART and the NVMe DMA filter is
never programmed.
Fix: use one compatible list across all three files, with the `apple,t6000-sart` fallback
present in every one so the in-tree driver always binds.

## research-archive/t6050-j714s-native-rootguard.dts

### D5 (critical) — redaction removed the identity check but left the write window
`t6050-j714s-native-rootguard.dts:6-8`. See C2 above. `azahi,root-partuuid` is the string
`"PRIVATE-UUID-REMOVED"` while `azahi,root-first-lba = <204034123>` and
`azahi,root-end-lba = <242798667>` are real LBAs for one specific disk.
Why it matters: the redaction pass removed the only value that could validate the window and
kept the window itself. Anyone building from this archive gets a write-enable range for a
partition layout that is not theirs.
Fix: redact the LBAs too, or drop all three properties and require the guard to locate its
partition by GPT PARTUUID at runtime.

### D6 (low) — 64-bit LBAs written as 32-bit-representable literals with `/bits/ 64`
`t6050-j714s-native-rootguard.dts:7-8` uses `/bits/ 64 <204034123>`. Correct, but the
sibling properties in the same tree use the two-cell convention.
Why it matters: a consumer that reads these with `of_property_read_u32` gets the high half
(zero) and authorises LBA 0 through 0. Silent, and the failure direction is "guard blocks
everything" rather than data loss, so it will look like a driver bug.
Fix: keep `/bits/ 64` and make the driver use `of_property_read_u64`; add a probe-time
`WARN` if either value reads back as 0.

## research-archive/t6050-pmgr-refs.dtsi vs t6050-pmgr.dtsi

### D7 (high) — the included PMGR file has 67 parent power-domain links stripped out
`t6050.dtsi:475` and `t6050-min.dtsi:238` include `t6050-pmgr-refs.dtsi`, never
`t6050-pmgr.dtsi`. The two files are otherwise identical (`diff` = the six node definitions
plus 67 removed `power-domains` lines and 5 added `apple,always-on`). Each removal left the
blank line behind, so the artifact is greppable: 67 hits for a lone indented empty line before
`};`. Examples: `t6050-pmgr-refs.dtsi:177` (`ps_aic`, lost
`power-domains = <&ps_pms>;` — cf. `t6050-pmgr.dtsi:225`) and
`t6050-pmgr-refs.dtsi:844` (`ps_fab6_soc`, lost `power-domains = <&ps_fab0_piogw>;` — cf.
`t6050-pmgr.dtsi:892`).
Why it matters: with the parents gone, genpd treats 67 domains as roots. Powering on a leaf
no longer powers on the fabric block it sits behind, so the first MMIO access hits a gated
block and SErrors. That is precisely the failure the DT comments in this directory keep
describing and working around with `pd_ignore_unused`, `/delete-node/ &pmgrN` and
`status = "disabled"`. No comment anywhere records that the links were removed on purpose or
why.
Fix: either include `t6050-pmgr.dtsi` (the complete tree) and delete the refs copy, or add a
header comment to `t6050-pmgr-refs.dtsi` naming the reason and listing the 67 dropped
parents. Two near-identical 2700-line generated files with no generator checked in is the
underlying problem.

## research-archive/t6050.dtsi

### D8 (medium) — PMU affinity assigns 12 cores to the E PMU and 6 to the P PMU
`t6050.dtsi:310-321`. Twelve `apple,sotra-m` cores (cluster0 + cluster1) get
`AIC_CPU_PMU_E`; six `apple,sotra-p` cores get `AIC_CPU_PMU_P`. L2 sizes at `:256,263,270`
follow the same split: 8 MiB, 8 MiB, 16 MiB.
Why it matters: the M3 Pro reference in this same directory (`t6030-j514s.dts:16-68,71-249`)
is 6 `apple,sawtooth` E-cores with a 4 MiB L2 and 6 `apple,everest` P-cores with a 16 MiB L2.
No shipped Apple Pro die has more E-cores than P-cores, so an 18-core part is far more likely
6 E + 12 P than 12 E + 6 P. If the m/p labelling is inverted, every perf event on twelve
P-cores is routed to the wrong AIC FIQ index and `perf` returns silence or wrong counts.
Fix: re-derive the cluster roles from the ADT `cpu-type`/`cluster-type` properties rather than
from the modelled-on-t8132 template, and record the ADT values in the file header.

### D9 (medium) — `soc` has no `dma-ranges`
`t6050.dtsi:291-297` (and the identical `t6050-min.dtsi:67-73`) declares `soc` with `ranges;`
and `nonposted-mmio;` but no `dma-ranges`. The reference `t6030-j514s.dts:491` has
`dma-ranges = <0x00 0x00 0x00 0x00 0xffffffff 0xffffc000>;`.
Why it matters: every DMA master added by the SSD and input variants (`nvme`, `sart_ans`,
`mtp_dart`, `ans_mbox`) sits under this `soc`. Without `dma-ranges` the OF DMA code falls back
to a bus-width default; on a machine whose RAM starts at 0x10000000000 (`t6050-j714s.dts:53`)
a 32-bit fallback mask means every coherent allocation fails or silently bounces.
Fix: copy the reference `dma-ranges` onto `soc` in both dtsi files.

### D10 (medium) — `t6050-min.dtsi` is a hand-trimmed fork of `t6050.dtsi` with no shared source
`t6050-min.dtsi:1-238` duplicates `t6050.dtsi:1-475` minus 17 CPUs and the AIC `affinities`
block. Eleven of the twelve board files include the `-min` copy; only `t6050-j714s.dts:10`
includes the full one.
Why it matters: they have already drifted (the `affinities` block at `t6050.dtsi:309-322` has
no counterpart, and `t6050-min.dtsi:84-85` is the empty hole it left). Any fix to the AIC,
pinctrl or i2c nodes must be applied twice, and D9 above is an example of a defect that now
exists in two places.
Fix: make `t6050-min.dtsi` `#include "t6050.dtsi"` and express the trimming with
`/delete-node/`, or generate both from the ADT with a checked-in script.

### D11 (low) — `pinctrl_aop` alone has no `power-domains`
`t6050.dtsi:355-374` / `t6050-min.dtsi:118-137`. `pinctrl_nub` and `pinctrl_ap` both carry
one; `pinctrl_aop` at 0x290824000 carries none, with no comment saying why.
Why it matters: it reads as an omission rather than a decision, and it is the one pinctrl the
hv variants disable at `t6050-j714s-hv.dts:128` without also deleting a power-domains
property, so the asymmetry is load-bearing by accident.
Fix: add the AOP GPIO domain reference, or a one-line comment stating the block is always on.

## research-archive/t6050-j714s.dts and the boot-args variants

### D12 (medium) — six board files, five different command lines, no shared fragment
`t6050-j714s.dts:40` and `t6050-j714s-min.dts:40` are byte-identical
(`"console=tty0 ignore_loglevel debug maxcpus=1"`), including the same 15-line comment block
at `:25-39`. `t6050-j714s-serial.dts:40`, `t6050-j714s-bare.dts:35`,
`t6050-j714s-hv.dts:62`, `t6050-j714s-hv-nvme.dts:70` and
`t6050-j714s-native-input.dts:7` each carry a different string.
Why it matters: `t6050-j714s.dts` and `t6050-j714s-min.dts` differ only in which dtsi they
include, so one of them is dead. And none of the seven contains `azahi.ssd_root=1` or
`root=`, both of which `azahi_standalone.c:118-120` refuses to boot without — the archived DTs
cannot produce a bundle that the loader accepts.
Fix: delete `t6050-j714s-min.dts` (a duplicate of `t6050-j714s.dts`), and move the shared
tail of the command line into a `#define` in a common header so the diff between variants is
only the part that varies.

### D13 (medium) — `debug` and `ignore_loglevel` are in every shipped command line
`t6050-j714s.dts:40`, `t6050-j714s-min.dts:40`, `t6050-j714s-serial.dts:40`,
`t6050-j714s-bare.dts:35`, `t6050-j714s-hv.dts:62`, `t6050-j714s-hv-nvme.dts:70`.
Why it matters: these are bring-up flags. On the SSD-root path they mean every boot writes a
full debug log to the console and to the journal on a machine whose storage stack is the thing
under test. `rd.shell` (`hv.dts:62`, `bare.dts:35`) additionally drops to an unauthenticated
root shell on any initramfs failure.
Fix: keep them in the hv/bare diagnostic files, strip them from anything that boots from the
SSD, and note in the file header that `rd.shell` is a root shell.

### D14 (low) — `aliases { serial0 }` kept in variants that disable serial0
`t6050-j714s-bare.dts` has no aliases but `t6050-j714s-native-input.dts:11-13` disables
`serial0` while the alias inherited from `t6050-j714s-hv.dts:25-27` still points at it.
Why it matters: `stdout-path` resolution and `ttySAC` numbering follow the alias. A disabled
node behind an alias is a source of confusing "console not found" behaviour, which is exactly
what the comment at `t6050-j714s.dts:26-31` warns about.
Fix: delete the alias in the variants that disable the node.

## research-archive/plist2adt.py

### P1 (high) — integer property width is guessed from magnitude
`plist2adt.py:22`: `struct.pack("<I", v) if 0 <= v < 1 << 32 else struct.pack("<q", v)`.
Why it matters: `ioreg` normalises every ADT integer to a Python int, so the original property
width is already lost. Encoding by magnitude means a genuinely 64-bit property whose current
value happens to be small is written as 4 bytes. The reconstructed ADT is then what
`azahi_standalone.c:34-41` validates against via `adt_get_reg`, which reads address/size pairs
by cell width — a truncated `reg` cell shifts every subsequent value and the loader's
"ANS/SART register identity" check compares garbage. The failure is silent: the ADT parses.
Fix: only emit `bytes` values verbatim and skip integer/string/bool properties entirely
(they are IOKit-normalised, not ADT data), or carry an explicit per-key width table. State in
the header comment that the output is lossy for non-`<data>` properties.

### P2 (medium) — `<q>` raises on values >= 2^63 and mis-signs large u64s
`plist2adt.py:22`. Values in `[2**63, 2**64)` raise `struct.error` and abort the whole
conversion with a traceback; the script has no error context to say which property.
Why it matters: physical addresses on this machine start at 0x10000000000 and ADT masks
routinely have the top bit set.
Fix: use `<Q` for non-negative values and `<q` only for negatives, and wrap the pack in a
`try` that names the key.

### P3 (medium) — synthetic-key filter is a prefix match, and drops silently
`plist2adt.py:29,32`: `any(k.startswith(p) for p in SYNTHETIC)` and
`if b is None or len(k) > 31: continue`.
Why it matters: a real ADT property named e.g. `IODeviceMemoryFoo` is dropped, and any
property with a name longer than 31 chars or a dict/array value vanishes with no diagnostic.
The output is then compared against hardware by a loader that reports only "PMGR device
identity", giving no way to trace back to a dropped property.
Fix: collect dropped `(node, key, reason)` and print a count and the first few to stderr.

### P4 (low) — no argv check, unclosed file handles
`plist2adt.py:48,56` index `sys.argv[1]`/`[2]` with no length check and never close either
handle.
Fix: `if len(sys.argv) != 3: sys.exit("usage: plist2adt.py in.plist out.adt")`, and use
`with`.

## research-archive/deploy.sh

### S1 (medium) — the one file that changes host hypervisor behaviour is not verified
`deploy.sh:20` scps `m1n1/proxyclient/m1n1/hv/__init__.py` onto the host, overwriting it with
no backup. The verification at `:23` shasums the five files from the earlier `scp` and
py-compiles `vmtmrprobe.py`; `__init__.py` appears in neither list.
Why it matters: that file is described at `:19` as carrying the "PMGR shadow fix + T6050
CPUSTART entry" — the code that decides which guest PMGR writes reach real hardware. A
truncated transfer leaves the host hypervisor running a half-file with no indication, and the
failure mode per `t6050-j714s-hv.dts:96-99` is an SError on the host.
Fix: include `proxyclient/m1n1/hv/__init__.py` in the shasum list and add
`python3 -m py_compile` for it; keep a timestamped backup of the previous copy.

### S2 (low) — unquoted variable expansions
`deploy.sh:9,12,20,23`: `ssh -i $K ... $H` and `scp -i $K ... $H:...`.
Why it matters: `$D` is quoted everywhere but `$K` and `$H` are not, so a path or hostname
containing a space silently splits into extra arguments. With `set -e` and `-o BatchMode`,
that surfaces as a confusing ssh usage error.
Fix: quote them.

### S3 (low) — private key filename survived redaction
`deploy.sh:5-6`. The host and user were redacted to `PRIVATE-USER@PRIVATE-LAN-ENDPOINT-REMOVED`
but `~/.ssh/id_ed25519_azahi` was not.
Why it matters: it names a key that exists on the author's machine and confirms it is
passwordless-batch capable (`-o BatchMode=yes`). Small, but it is the kind of thing the
redaction pass was meant to catch, and the same pass missed the LBAs in D5.
Fix: `K=${AZAHI_SSH_KEY:?set AZAHI_SSH_KEY}`.

## research-archive/m1n1-vmtmr-ro.patch

### M1 (medium) — workaround gated on a hard-coded two-chip list
`m1n1-vmtmr-ro.patch:39-42`: `return chip_id == T6050 || chip_id == T6051;`.
Why it matters: the patch's own comment at `:104-105` says the new path "degenerates to the
plain SYSREG_MAP behavior" on chips where the flag is never set, so the workaround is safe
everywhere. Gating it on a literal chip list means the next die in the family (T6052/T6055)
silently takes the branch that livelocks the guest at its first timer tick, and the symptom
("guest hangs after the first tick") gives no pointer to this list.
Fix: probe it — try one `msr(SYS_IMP_APL_VM_TMR_FIQ_ENA_EL2, ...)` behind the existing UNDEF
handler at init and set a flag from the result — or just always take the architectural path
and delete the chip check and the old branch.

### M2 (low) — the macro's side effects depend on `|=` never becoming `||`
`m1n1-vmtmr-ro.patch:68-69`:
`fiq_pending |= HV_VM_TMR_UPDATE(CNTP_CTL_EL02, vm_tmr_imask_p);` then the same for `CNTV`.
Why it matters: `HV_VM_TMR_UPDATE` writes hardware and mutates per-CPU state. With `|=` both
run, which is correct; a later "cleanup" to `||` would short-circuit and leave the virtual
timer permanently masked whenever the physical timer is pending. Nothing in the code says so.
Fix: call the macro into two named locals first, then combine.

### M3 (low) — patch headers leak the local directory layout and uid
`m1n1-vmtmr-ro.patch:1-2`. `PRIVATE-USER` and `PRIVATE-UUID-REMOVED` were substituted, but
PRIVATE-PATH-REMOVED folder chain>/scratchpad/m1n1-fix/` (see the patch header)
survives, including the numeric macOS uid and the full directory chain.
Fix: regenerate with `diff -u` from a clean pair of paths, or `git format-patch`.

## research-archive/kconfig.txt

### K1 (medium) — the storage path is entirely modular while the loader freezes the initrd size
`kconfig.txt`: `CONFIG_NVME_APPLE=m`, `CONFIG_APPLE_SART=m`, `CONFIG_APPLE_DART=m`,
`CONFIG_HID_DOCKCHANNEL=m`, `CONFIG_APPLE_DOCKCHANNEL=m` (`:10858`), `CONFIG_MFD_MACSMC=m`
(`:6129`), `CONFIG_GPIO_MACSMC=m` (`:5458`), `CONFIG_PINCTRL_APPLE_GPIO=m`.
Why it matters: every one of these must be inside the initramfs for the SSD-root boot to
mount root or for the keyboard to work. Combined with C6 — `azahi_standalone.c:99` requires
the initrd to be exactly 70,698,084 bytes — adding a single missing module means editing C,
rebuilding the loader and reflashing. The README at `standalone-loader/README.md:7-9`
documents this having already blocked a rebuild.
Fix: build the boot-critical set (`NVME_APPLE`, `APPLE_SART`, `APPLE_MAILBOX`,
`APPLE_RTKIT`) into the kernel and drop them from the initramfs, which also shrinks it.

### K2 (low) — `CONFIG_DRM_PANIC_SCREEN_QR_CODE_URL=""`
`kconfig.txt:7493`, while `build-bundle.py:60` appends `drm.panic_screen=qr_code`.
Why it matters: with an empty URL the QR encodes the raw compressed log and needs the
`drm_panic_qr` helper script to read. That is fine, but the panic screen is the only
observability this machine has on the bare-metal path (`t6050-j714s-bare.dts:11-14`), so it
should be a deliberate choice rather than the default-empty value.
Fix: set the URL, or note in the bare-metal DT header how to decode the QR.

## Cross-cutting

### X1 (high) — the same physical facts are hard-coded in four languages with no shared source
`azahi_standalone.c:15-20` (six addresses/lengths), `build-bundle.py:33-34,48,83-85`,
`build-aligned.py:22-28`, `t6050-pmgr-nodes.dtsi`, `t6050-pmgr-refs.dtsi`, and the six board
`.dts` files. D1, C1, C6 and A2 are each an instance of two of these copies disagreeing.
Fix: one generated `t6050-facts.h` / `t6050-facts.py` / `t6050-facts.dtsi` emitted from the
ADT dump, consumed everywhere, with the generator checked in. That single change would have
caught the wrong PMGR base in D1 at build time.

### X2 (medium) — the redaction pass leaves usable private config behind
`t6050-j714s-native-rootguard.dts:7-8` (real LBAs next to a redacted UUID),
`deploy.sh:6` (key filename), `m1n1-vmtmr-ro.patch:1-2` (directory chain and uid),
`azahi_standalone.c:120` (a required boot-arg literal that names the redaction:
`root=PARTUUID=PRIVATE-LINUX-PARTUUID-NOT-CONFIGURED`).
Why it matters: `safety/check-publication.py` exists in this repo and did not catch any of
these, so the checker's pattern list is narrower than what the redaction actually needs to
cover.
Fix: add patterns for bare LBA-looking 9-digit integers in `azahi,*-lba` properties,
`id_*` key filenames, and `/private/tmp/claude-*/` paths.
