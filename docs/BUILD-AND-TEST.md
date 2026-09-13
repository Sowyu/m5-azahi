# Build and test limitations

The driver build scripts expect the exact Fedora Asahi
`7.0.13-400.asahi.fc44.aarch64+16k` devel headers, `Module.symvers`, a compatible
host-built `modpost`, Homebrew LLVM/LLD and device-tree tools. These are not
included. This is not a generic DKMS package or installation guide.

## Tests runnable from the public source

```sh
python3 input-driver/test-power-request.py
bash nvme-driver/test-root-write-policy.sh
python3 usb-driver/test-usb-runner.py
python3 usb-driver/test-usb-glue.py
```

Input checks compile the actual patched reset function against a transport
stub: v2 bytes/order, error handling and the unchanged old-board path.
Storage checks compile the actual policy with address/undefined sanitizers.
USB checks use shell mocks and a C harness; they do not load kernel modules.
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

The custom `azahi_standalone.c/.h` are only the added loader component, not all
integration changes or upstream m1n1 sources. Published builders cannot create
a complete bootable image from this snapshot alone.
