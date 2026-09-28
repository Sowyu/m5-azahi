# Build and test limitations

The original macOS driver build scripts expect the exact Fedora Asahi
`7.0.13-400.asahi.fc44.aarch64+16k` devel headers, `Module.symvers`, a compatible
host-built `modpost`, Homebrew LLVM/LLD and device-tree tools. These are not
included. This is not a generic DKMS package or installation guide.

## USB candidates on Linux, added 2026-09-28

The exact devel RPM is still available from the official
[Fedora Asahi COPR repository](https://download.copr.fedorainfracloud.org/results/@asahi/kernel/fedora-44-aarch64/).
Its `.config` is byte-for-byte identical to `research-archive/kconfig.txt`.
It includes 30,752 kernel/module exports in `Module.symvers`. The target
disables `CONFIG_MODVERSIONS`, so these are export/dependency checks, not
symbol CRC validation.

`usb-driver/build-linux.py` builds the PHY, DWC3 glue, overlay and one-shot
HPM helper from a checksum-pinned RPM. It rebuilds `modpost` for the host,
retains target-generated structure offsets, and rejects missing exports.
It neither installs drivers nor changes the existing installer pins.
Add `--with-input` to also build the DockChannel input candidate. It no longer
needs the private `drivers/hid/hid-ids.h` include path.

Requirements: Linux, Python 3.11+, host GCC/binutils, `bsdtar`, `dtc`, and the AArch64
GCC 16.1 toolchain described below. Download the RPM into a directory outside
this repository, then run from the repository root:

```sh
curl -fL -o /path/to/kernel-devel.rpm \
  'https://download.copr.fedorainfracloud.org/results/@asahi/kernel/fedora-44-aarch64/Packages/k/kernel-16k-devel-7.0.13-400.asahi.fc44.aarch64.rpm'
python3 usb-driver/build-linux.py \
  --devel-rpm /path/to/kernel-devel.rpm \
  --cross-prefix aarch64-linux- \
  --output /path/to/new-usb-build
AZAHI_USB_BUILD=/path/to/new-usb-build python3 usb-driver/test-build-linux.py
```

RPM SHA-256:
`ad835398b8d443619030c5baccc79246fc97d175fc2d17633738d35fd0319c0a`.
The builder refuses a different checksum and an existing output directory.
All outputs, sources and command logs are retained, including on failure.
`manifest.json` records source/artifact hashes and limitations. Remove an
unwanted build with `trash-put /absolute/path/to/build`.

Four modules passed strict `modpost` and AArch64/vermagic checks on the Linux
host. Seven build tests also passed, including real missing-export and module
structure failures. The final linked modules are checked against the export
table too, including their generated module metadata objects.
Two fresh output directories produced identical hashes for all four modules
and both final overlays using the same inputs and toolchain.
The input candidate also passes export, vermagic and target module-structure
checks. Its eight host test groups cover firmware startup, ACK/timeout paths,
HID report types, GPIO error acknowledgements and concurrent packet transmission.
They also check that the 50 ms pulse option defaults off and requires J714s.
A two-thread test forces an overlap
between interfaces and checks wire framing; removing the shared TX lock
reproduces corruption. The lock is released before waiting for a reply.
They are **offline candidates**, with no target load or cold-boot result.
The compiler differs from Fedora GCC 16.1.1; these manual builds omit BTF,
ftrace instrumentation and signatures. The overlay test merges both variants
onto the sanitized rootguard DT and checks their PHY/DART/AIC references.
The exact installed private DTB and live PHY tunables remain unavailable.
Do not replace installer hashes merely to accept these files.

To build the separate [FIFO timeout fix](../input-driver/README.md#optional-fifo-timeout-fix),
add `--dockchannel-source /path/to/linux/drivers/soc/apple/dockchannel.c`.
The builder checks the original source hash before creating output and applies
the patch only in the new build directory. It uses the kernel's module name,
`apple-dockchannel.ko`, and checks all four required exports in the provider
and its generated symbol table. The option works alongside `--with-input`,
SMC, battery and either storage option. Without it, the FIFO driver is omitted.
This prepares a separate boot candidate. Do not unload or unbind the running
parent driver, whose removal reaches the HID driver's `BUG_ON(1)`.

The optional SMC candidate is documented in [smc-driver/README.md](../smc-driver/README.md).
Pass `--smc-source /path/to/linux/drivers/mfd/macsmc.c` to include it. The builder
requires the exact source hash and applies the patch in its new output tree.
The six-module build passes strict export checks; the expanded builder suite
has eight passing tests. This prepares an offline core-driver replacement,
with no change to installation pins or SMC child-driver blacklists.

`--smc-power-source /path/to/linux/drivers/power/supply/macsmc-power.c`
also includes the matching battery compatibility backport. It requires the
SMC core input and checks the battery source hash separately. The seven-module
set passes strict export checks and nine builder tests. The firmware conversion
tests and hardware restrictions are in the same SMC README.

`--nvme-header /path/to/linux/drivers/nvme/host/nvme.h` adds the public ANS and
SART modules. The internal header is pinned to SHA-256
`0ed6fec6c7e7067fca642241e1c8710391f7da949c41759b10ccfa45010b92cf`.
The builder checks the SART provider's three exports in the linked module
and generated symbol table, separately from the kernel's export table.
All nine modules build together, and eleven builder checks pass. The new
storage outputs enforce the J714s read-only mode; they cannot replace the
private writable-root driver. The public rootguard compile refusal remains.
Run `python3 nvme-driver/test-readonly.py` for the submission and sleep-guard
host checks. See [the storage README](../nvme-driver/README.md) for scope.

For a separate firmware compatibility experiment, pass
`--nvme-core-source /path/to/linux/drivers/nvme/host`. This pins twelve source
files, selects read-only ANS/SART automatically, and adds a paired
`nvme-core.ko` built for the same kernel. It applies the newer upstream
admin-alignment and TCB fixes while preserving the M5 register mappings.
A required custom export prevents the Apple candidate from loading against
the stock core. The [storage README](../nvme-driver/README.md#optional-firmware-compatibility-pair)
records the source commits, checks and limits. This option prepares an
experiment, with no installation or writable-root migration.

Additional scratch builds of the SPMI4 controller, PCIe driver and vendored
SN201202x driver passed strict `modpost` using this export table. The latter
includes the existing `no-tbt-switch.patch`. Those checks stop at objects and
module metadata; they do not produce installable modules or test hardware.

## Compile checks on a Linux host (added 2026-09-25)

For source-only compile checks beyond the USB modules above, the exact kernel
source and a cross compiler are public:

```sh
git clone --depth 1 --branch kernel-7.0.13-400.asahi \
  https://gitlab.com/fedora-asahi/kernel-asahi.git linux-7.0.13-400
# aarch64 cross GCC 16.1 from kernel.org crosstool (x86_64 host)
curl -LO https://mirrors.edge.kernel.org/pub/tools/crosstool/files/bin/x86_64/16.1.0/x86_64-gcc-16.1.0-nolibc-aarch64-linux.tar.xz
tar xf x86_64-gcc-16.1.0-nolibc-aarch64-linux.tar.xz
export PATH=$PWD/gcc-16.1.0-nolibc/aarch64-linux/bin:$PATH ARCH=arm64 CROSS_COMPILE=aarch64-linux-
cd linux-7.0.13-400
cp <repo>/research-archive/kconfig.txt .config   # the target's own config
scripts/config --disable RUST                    # C modules only; avoids the Rust toolchain
make olddefconfig && make -j"$(nproc)" modules_prepare
```

Host tools needed: flex, bison, bc, m4, dtc. Without root, `apt download`
plus `dpkg -x` into a local prefix works; set `BISON_PKGDATADIR` to the
extracted `usr/share/bison`.

Then build a module out of tree from a scratch copy:

```sh
echo 'obj-m += phy-apple-t6050-usb2.o' > Makefile
make -C <kernel-tree> M=$PWD KBUILD_MODPOST_WARN=1 W=1 modules
```

This proves the source compiles against the exact target headers and config.
This source-only recipe does not produce validated loadable modules: there
is no `Module.symvers` (so
unresolved-symbol warnings are expected), Rust is disabled, the compiler is
not the target's GCC 16.1.1 Red Hat build, and nothing is signed. Never
install these objects on the target.

The public macOS 27.0 (26A428) restore image is the same OS the target runs.
[`ipsw`](https://github.com/blacktop/ipsw) can extract its J714s device tree
and Mac17,9 kernelcache over HTTP range requests without downloading the
whole image, for example `ipsw extract --dtree --remote <ipsw-url>` and
`ipsw extract --kernel --remote --device Mac17,9 <ipsw-url>`. Apple files
obtained this way stay outside the repository.

## Tests runnable from the public source

```sh
python3 input-driver/test-power-request.py
python3 input-driver/test-firmware-lifetime.py
bash nvme-driver/test-root-write-policy.sh
python3 usb-driver/test-usb-runner.py
python3 usb-driver/test-usb-glue.py
CC=gcc python3 usb-driver/pd-backport/test-proxy-hpm.py
```

Input checks compile the actual functions against transport stubs: v2
bytes/order, error handling, packet receive bounds, ACK lifetime, firmware
failures and concurrent sends. The firmware-lifetime check also verifies CPU
staging cleanup while retaining DMA buffers across failed uploads. The
old-board power request remains unchanged.
Storage checks compile the actual policy with address/undefined sanitizers.
USB checks use shell mocks and a C harness; they do not load kernel modules.
The HPM proxy tests compile a host FFI library and use simulated transactions.
Eighteen pass on Linux; the private live-ADT identity test skips when absent.
The storage test prints where its temporary executable was retained.

## Tests/builds requiring private inputs

Courier-v2 correction adds `test-transfer-v6.py` (five passing image tests) and
`test-courier-vm.py` (QEMU ARM64, six successful scenario markers using the
exact original initrd tools). The VM has no disks, network or USB passthrough.
It reproduces the original missing-mktemp failure before testing the fix.
These require private v3/v4/v5/v6 image fixtures and QEMU; they cannot run from
this source-only public clone alone. Test-only initrd additions are not part
of the target boot image. Original pinned courier/build scripts are preserved.

Publication validation on 2026-09-13 reran all four host commands above in the
sanitized public clone: input transport checks passed, **525,366 storage policy
checks passed**, and **19 runner + 3 glue/overlay tests passed**. No target
hardware was accessed by these tests.

- `usb-driver/test-usb-candidate.py`: saved real ADT, baseline DTB, built modules,
  exact devel headers and the m1n1 Python library.
- `usb-driver/test-transfer-fixed.py`: original v3/v4/v5 images and JSON receipts.
- Bundle builders: original kernel/initrds/firmware, private boot arguments,
  image receipts and the separately maintained isolated loader tree.

The public source is sanitized, so private artifact hashes **will not match**
locally rebuilt public scripts/modules. Never bypass a manifest failure.
The v4 builder is retained only to document the regression and supply helper
functions used by the correction. **Do not install its output.**

## Public safety transformations

Private Linux filesystem/partition UUIDs have been replaced with
`PRIVATE-LINUX-FSUUID-NOT-CONFIGURED` and
`PRIVATE-LINUX-PARTUUID-NOT-CONFIGURED`. These are not valid disk identities.
The public root-write policy raises a compile error for a kernel build with
`AZAHI_ROOT_WRITES`, while remaining available to host policy tests.
This is not permission to remove guards: enabling writes requires a new,
independent storage audit. Historical LBA constants are research evidence only.

The custom sources alone are not a complete boot image. The
[full loader link check](../standalone-loader/README.md#complete-offline-link-check)
now combines the archived standalone integration, current fixes and pinned
upstream m1n1 sources. Both C/assembly/Rust ELF files link without undefined
symbols, with the one-core and disk-placeholder guards retained. This does
not reconstruct the exact private v7 image or include its kernel/DT/initrd.
