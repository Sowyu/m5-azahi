#!/bin/bash
# Cross-build the J714s right-socket USB2 host candidate against the exact
# Fedora 7.0.13-400.asahi.fc44.aarch64+16k devel headers, on the macOS host.
# Same recipe as input-driver/build-module.sh (verified on hardware there),
# generalised to three modules plus two runtime device-tree overlays.
set -euo pipefail
cd "$(dirname "$0")"
root="$(cd .. && pwd)"
headers="$root/input-driver/build/headers/usr/src/kernels/7.0.13-400.asahi.fc44.aarch64+16k"
modpost="$root/input-driver/build/modpost"
cc=/opt/homebrew/opt/llvm/bin/clang
ld=/opt/homebrew/opt/lld/bin/ld.lld
test -x "$modpost"
guard=$(awk '$2 == "TSK_STACK_CANARY" { print $3 }' "$headers/include/generated/asm-offsets.h")
test -n "$guard"
mkdir -p build stage

# 1. overlays
dtc_quiet=(-W no-reg_format -W no-avoid_default_addr_size -W no-unit_address_vs_reg
  -W no-interrupts_property -W no-simple_bus_reg -W no-unique_unit_address
  -W no-avoid_unnecessary_addr_size -W no-interrupt_provider -W no-node_name_chars)
for v in minimal pmgr; do
  # 1a. compile with -@ so dtc emits __local_fixups__ for the intra-overlay phandles
  dtc -@ -I dts -O dtb "${dtc_quiet[@]}" \
    -o "build/t6050-j714s-usb-right-$v.sym.dtbo" "dts/t6050-j714s-usb-right-$v.dtso"
  # 1b. the kernel rejects __symbols__ when the live tree has none: strip it, keep local fixups
  dtc -q -I dtb -O dts "build/t6050-j714s-usb-right-$v.sym.dtbo" | python3 strip-symbols.py \
    > "build/t6050-j714s-usb-right-$v.stripped.dts"
  dtc -I dts -O dtb "${dtc_quiet[@]}" \
    -o "build/t6050-j714s-usb-right-$v.dtbo" "build/t6050-j714s-usb-right-$v.stripped.dts"
  fdtdump "build/t6050-j714s-usb-right-$v.dtbo" | grep -q "__local_fixups__"
  ! fdtdump "build/t6050-j714s-usb-right-$v.dtbo" | grep -q "__symbols__"
done
python3 mk-blob-header.py build/overlay-blobs.h \
  overlay_minimal=build/t6050-j714s-usb-right-minimal.dtbo \
  overlay_pmgr=build/t6050-j714s-usb-right-pmgr.dtbo

# 2. modules
common_flags=(--target=aarch64-linux-gnu -std=gnu11 -fms-extensions -O2 -g -nostdinc
  -D__KERNEL__ -DMODULE
  -I "$headers/arch/arm64/include" -I "$headers/arch/arm64/include/generated"
  -I "$headers/include" -I "$headers/arch/arm64/include/uapi"
  -I "$headers/arch/arm64/include/generated/uapi" -I "$headers/include/uapi"
  -I "$headers/include/generated/uapi" -include "$headers/include/linux/kconfig.h"
  -include "$headers/include/linux/compiler_types.h"
  -mgeneral-regs-only -mno-outline-atomics -mbranch-protection=pac-ret+bti
  -fno-pic -fno-pie -fno-strict-aliasing -fno-common -fshort-wchar
  -fno-asynchronous-unwind-tables -fno-unwind-tables
  -fno-delete-null-pointer-checks -fno-strict-overflow -fno-omit-frame-pointer
  -fstack-protector-strong -mstack-protector-guard=sysreg
  -mstack-protector-guard-reg=sp_el0 "-mstack-protector-guard-offset=$guard"
  -Wall -Wno-address-of-packed-member -Wno-gnu-variable-sized-type-not-at-end
  -Wno-microsoft-anon-tag -Wno-unused-function)

# name  source  extra-includes
mods=(
  "phy_apple_t6050_usb2 phy-apple-t6050-usb2.c"
  "azahi_usb_overlay azahi-usb-overlay.c -Ibuild"
  "dwc3_apple_t6050 dwc3-apple-t6050.c -Ivendor/dwc3"
)
objs=()
for spec in "${mods[@]}"; do
  set -- $spec
  name=$1; src=$2; shift 2
  obj="build/${src%.c}.o"
  "$cc" "${common_flags[@]}" "$@" "-DKBUILD_MODNAME=\"$name\"" "-DKBUILD_BASENAME=\"$name\"" \
    "-D__KBUILD_MODNAME=kmod_$name" -c "$src" -o "$obj"
  objs+=("$obj")
done

"$modpost" -M -e -i "$headers/Module.symvers" -o build/Module.symvers "${objs[@]}"
"$cc" "${common_flags[@]}" -c "$headers/scripts/module-common.c" -o build/module-common.o

for spec in "${mods[@]}"; do
  set -- $spec
  name=$1; src=$2
  base="build/${src%.c}"
  "$cc" "${common_flags[@]}" "-DKBUILD_MODNAME=\"$name\"" "-DKBUILD_BASENAME=\"$name\"" \
    "-D__KBUILD_MODNAME=kmod_$name" -c "$base.mod.c" -o "$base.mod.o"
  "$ld" -m aarch64elf -r -T "$headers/scripts/module.lds" -o "$base.ko" \
    "$base.o" "$base.mod.o" build/module-common.o
  cp "$base.ko" stage/
done
cp build/t6050-j714s-usb-right-minimal.dtbo build/t6050-j714s-usb-right-pmgr.dtbo stage/
cp dts/*.dtso stage/
cp usb-tether-test.sh stage/
# The deliverable manifest must describe exactly the files the server serves.
(cd stage && shasum -a 256 phy-apple-t6050-usb2.ko dwc3-apple-t6050.ko \
  azahi-usb-overlay.ko usb-tether-test.sh | tee SHA256SUMS)
python3 test-usb-candidate.py
python3 test-usb-runner.py
python3 test-usb-glue.py
mkdir -p deliver
cp stage/phy-apple-t6050-usb2.ko stage/dwc3-apple-t6050.ko \
  stage/azahi-usb-overlay.ko stage/usb-tether-test.sh stage/SHA256SUMS deliver/
(cd deliver && shasum -a 256 -c SHA256SUMS)
