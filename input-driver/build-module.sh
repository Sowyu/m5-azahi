#!/bin/bash
# Cross-build only the input module against the exact Fedora devel package.
set -euo pipefail
cd "$(dirname "$0")"
headers="$PWD/build/headers/usr/src/kernels/7.0.13-400.asahi.fc44.aarch64+16k"
cc=/opt/homebrew/opt/llvm/bin/clang
ld=/opt/homebrew/opt/lld/bin/ld.lld
guard=$(awk '$2 == "TSK_STACK_CANARY" { print $3 }' "$headers/include/generated/asm-offsets.h")
test -n "$guard"
flags=(--target=aarch64-linux-gnu -std=gnu11 -fms-extensions -O2 -g -nostdinc
  -D__KERNEL__ -DMODULE '-DKBUILD_MODNAME="dockchannel_hid"'
  '-DKBUILD_BASENAME="dockchannel_hid"' '-D__KBUILD_MODNAME=kmod_dockchannel_hid'
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
  -Wno-address-of-packed-member -Wno-gnu-variable-sized-type-not-at-end
  -Wno-microsoft-anon-tag)
"$cc" "${flags[@]}" -c dockchannel-hid.c -o build/dockchannel-hid.o
build/modpost -e -i "$headers/Module.symvers" -o build/Module.symvers build/dockchannel-hid.o
"$cc" "${flags[@]}" -c build/dockchannel-hid.mod.c -o build/dockchannel-hid.mod.o
"$cc" "${flags[@]}" -c "$headers/scripts/module-common.c" -o build/module-common.o
"$ld" -m aarch64elf -r -T "$headers/scripts/module.lds" \
  -o build/dockchannel-hid.ko build/dockchannel-hid.o build/dockchannel-hid.mod.o build/module-common.o
shasum -a 256 build/dockchannel-hid.ko
