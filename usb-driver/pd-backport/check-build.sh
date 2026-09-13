#!/bin/bash
# HOST ONLY: compile an unmodified pinned Asahi PD driver against our exact
# target headers. Produces objects and a modpost report, NEVER a loadable .ko,
# overlay, installer, firmware, target access, or delivery bundle.
set -euo pipefail
cd "$(dirname "$0")"
root=$(cd ../.. && pwd)
headers="$root/input-driver/build/headers/usr/src/kernels/7.0.13-400.asahi.fc44.aarch64+16k"
cc=/opt/homebrew/opt/llvm/bin/clang
ld=/opt/homebrew/opt/lld/bin/ld.lld
modpost="$root/input-driver/build/modpost"
guard=$(awk '$2 == "TSK_STACK_CANARY" { print $3 }' "$headers/include/generated/asm-offsets.h")
test -n "$guard"
(cd vendor && shasum -a 256 -c SHA256SUMS)
mkdir -p build
flags=(--target=aarch64-linux-gnu -std=gnu11 -fms-extensions -O2 -g -nostdinc
  -D__KERNEL__ -DMODULE
  -I "$headers/arch/arm64/include" -I "$headers/arch/arm64/include/generated"
  -I "$headers/include" -I "$headers/arch/arm64/include/uapi"
  -I "$headers/arch/arm64/include/generated/uapi" -I "$headers/include/uapi"
  -I "$headers/include/generated/uapi" -include "$headers/include/linux/kconfig.h"
  -include "$headers/include/linux/compiler_types.h"
  -I "$PWD/vendor/tipd"
  -mgeneral-regs-only -mno-outline-atomics -mbranch-protection=pac-ret+bti
  -fno-pic -fno-pie -fno-strict-aliasing -fno-common -fshort-wchar
  -fno-asynchronous-unwind-tables -fno-unwind-tables
  -fno-delete-null-pointer-checks -fno-strict-overflow -fno-omit-frame-pointer
  -fstack-protector-strong -mstack-protector-guard=sysreg
  -mstack-protector-guard-reg=sp_el0 "-mstack-protector-guard-offset=$guard"
  -Wall -Werror=implicit-function-declaration
  -Wno-address-of-packed-member -Wno-gnu-variable-sized-type-not-at-end
  -Wno-microsoft-anon-tag -Wno-unused-function
  '-DKBUILD_MODNAME="azahi_sn201202x_check"'
  -D__KBUILD_MODNAME=kmod_azahi_sn201202x_check)
failed=0
for unit in core spmi trace; do
  if "$cc" "${flags[@]}" "-DKBUILD_BASENAME=\"$unit\"" \
    -c "vendor/tipd/$unit.c" -o "build/$unit.o"; then
    echo "COMPILE PASS: $unit"
  else
    echo "COMPILE FAIL: $unit" >&2
    failed=1
  fi
done
test "$failed" = 0 || exit 1
"$ld" -m aarch64elf -r -o build/azahi-sn201202x-check.o \
  build/core.o build/spmi.o build/trace.o
"$modpost" -M -e -i "$headers/Module.symvers" \
  -o build/Module.symvers build/azahi-sn201202x-check.o
echo 'Compile and modpost passed. No loadable module created; hardware remains untested.'
