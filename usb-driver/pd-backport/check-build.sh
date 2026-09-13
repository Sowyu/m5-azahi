#!/bin/bash
# HOST ONLY: compile a pinned Asahi PD driver against our exact
# target headers. Most variants produce only objects and a modpost report;
# hpm-once also links a loadable .ko. No target access or installation occurs.
set -euo pipefail
cd "$(dirname "$0")"
variant=${1:-upstream}
case "$variant" in
  upstream|without-tbt-switch|controller|hpm-once) ;;
  *) echo 'Usage: bash check-build.sh [upstream|without-tbt-switch|controller|hpm-once]' >&2; exit 2 ;;
esac
test "$#" -le 1 || exit 2
root=$(cd ../.. && pwd)
headers="$root/input-driver/build/headers/usr/src/kernels/7.0.13-400.asahi.fc44.aarch64+16k"
cc=/opt/homebrew/opt/llvm/bin/clang
ld=/opt/homebrew/opt/lld/bin/ld.lld
modpost="$root/input-driver/build/modpost"
guard=$(awk '$2 == "TSK_STACK_CANARY" { print $3 }' "$headers/include/generated/asm-offsets.h")
test -n "$guard"
(cd vendor && shasum -a 256 -c SHA256SUMS)
mkdir -p build
output=$(mktemp -d "$PWD/build/compile-$variant.XXXXXX")
source_dir="$output/src"
mkdir "$source_dir"
module=azahi_sn201202x_check
units=(core spmi trace)
cp vendor/tipd/core.c vendor/tipd/spmi.c vendor/tipd/trace.c \
  vendor/tipd/tps6598x.h vendor/tipd/trace.h "$source_dir/"
if [[ "$variant" = controller ]]; then
  module=azahi_spmi4_check
  units=(controller)
  cp spmi4-controller.c "$source_dir/controller.c"
  cp spmi4-transport.h "$source_dir/"
fi
if [[ "$variant" = hpm-once ]]; then
  module=azahi_hpm_once
  units=(hpm-once)
  cp hpm-once.c hpm-awake.h spmi4-transport.h "$source_dir/"
fi
if [[ "$variant" = without-tbt-switch ]]; then
  patch --batch --fuzz=0 -p1 -d "$source_dir" -i "$PWD/no-tbt-switch.patch"
fi
echo "HOST-ONLY build variant: $variant; objects: $output"
flags=(--target=aarch64-linux-gnu -std=gnu11 -fms-extensions -O2 -g -nostdinc
  -D__KERNEL__ -DMODULE
  -I "$headers/arch/arm64/include" -I "$headers/arch/arm64/include/generated"
  -I "$headers/include" -I "$headers/arch/arm64/include/uapi"
  -I "$headers/arch/arm64/include/generated/uapi" -I "$headers/include/uapi"
  -I "$headers/include/generated/uapi" -include "$headers/include/linux/kconfig.h"
  -include "$headers/include/linux/compiler_types.h"
  -I "$source_dir"
  -mgeneral-regs-only -mno-outline-atomics -mbranch-protection=pac-ret+bti
  -fno-pic -fno-pie -fno-strict-aliasing -fno-common -fshort-wchar
  -fno-asynchronous-unwind-tables -fno-unwind-tables
  -fno-delete-null-pointer-checks -fno-strict-overflow -fno-omit-frame-pointer
  -fstack-protector-strong -mstack-protector-guard=sysreg
  -mstack-protector-guard-reg=sp_el0 "-mstack-protector-guard-offset=$guard"
  -Wall -Werror=implicit-function-declaration
  -Wno-address-of-packed-member -Wno-gnu-variable-sized-type-not-at-end
  -Wno-microsoft-anon-tag -Wno-unused-function
  "-DKBUILD_MODNAME=\"$module\""
  "-D__KBUILD_MODNAME=kmod_$module")
failed=0
objects=()
for unit in "${units[@]}"; do
  objects+=("$output/$unit.o")
  if "$cc" "${flags[@]}" "-DKBUILD_BASENAME=\"$unit\"" \
    -c "$source_dir/$unit.c" -o "$output/$unit.o"; then
    echo "COMPILE PASS: $unit"
  else
    echo "COMPILE FAIL: $unit" >&2
    failed=1
  fi
done
test "$failed" = 0 || exit 1
"$ld" -m aarch64elf -r -o "$output/$module.o" "${objects[@]}"
"$modpost" -M -e -i "$headers/Module.symvers" \
  -o "$output/Module.symvers" "$output/$module.o"
if [[ "$variant" = hpm-once ]]; then
  "$cc" "${flags[@]}" -c "$headers/scripts/module-common.c" -o "$output/module-common.o"
  "$cc" "${flags[@]}" -c "$output/$module.mod.c" -o "$output/$module.mod.o"
  "$ld" -m aarch64elf -r -T "$headers/scripts/module.lds" -o "$output/$module.ko" \
    "$output/$module.o" "$output/$module.mod.o" "$output/module-common.o"
  echo "HPM_ONLY_CANDIDATE $output/$module.ko; default status only; not installed"
else
  echo 'Compile and modpost passed. No loadable module created; hardware remains untested.'
fi
