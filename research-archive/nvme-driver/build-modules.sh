#!/bin/bash
# Exact-kernel external modules, built locally without touching the target.
set -euo pipefail
cd "$(dirname "$0")"
mode=${1:-readonly}
case "$mode" in
  readonly) output=build; mode_flags=() ;;
  rootguard) output=build-rootguard; mode_flags=(-DAZAHI_ROOT_WRITES=1) ;;
  *) echo 'usage: build-modules.sh [readonly|rootguard]' >&2; exit 2 ;;
esac
mkdir -p "$output"
headers="$PWD/../input-driver/build/headers/usr/src/kernels/7.0.13-400.asahi.fc44.aarch64+16k"
cc=/opt/homebrew/opt/llvm/bin/clang
ld=/opt/homebrew/opt/lld/bin/ld.lld
guard=$(awk '$2 == "TSK_STACK_CANARY" { print $3 }' "$headers/include/generated/asm-offsets.h")
test -n "$guard"
flags=(--target=aarch64-linux-gnu -std=gnu11 -fms-extensions -O2 -g -nostdinc
  -D__KERNEL__ -DMODULE
  -I "$PWD/build/linux-7.0.13/drivers/nvme/host"
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
for spec in apple:nvme-apple sart:apple-sart; do
  source=${spec%:*}
  module=${spec#*:}
  normalized=${module//-/_}
  identity=("-DKBUILD_MODNAME=\"$normalized\"" "-DKBUILD_BASENAME=\"$source\""
    "-D__KBUILD_MODNAME=kmod_$normalized")
  "$cc" "${flags[@]}" "${mode_flags[@]}" "${identity[@]}" -c "$source.c" -o "$output/$module.o"
  ../input-driver/build/modpost -M -e -i "$headers/Module.symvers" \
    -o "$output/$module.symvers" "$output/$module.o"
  "$cc" "${flags[@]}" "${mode_flags[@]}" "${identity[@]}" -c "$output/$module.mod.c" -o "$output/$module.mod.o"
  "$cc" "${flags[@]}" "${mode_flags[@]}" "${identity[@]}" -c "$headers/scripts/module-common.c" -o "$output/$module-common.o"
  "$ld" -m aarch64elf -r -T "$headers/scripts/module.lds" \
    -o "$output/$module.ko" "$output/$module.o" "$output/$module.mod.o" "$output/$module-common.o"
  shasum -a 256 "$output/$module.ko"
done
# The consumer must resolve these from the finished provider, not merely
# from the kernel package's preexisting Module.symvers. -M is essential.
for symbol in devm_apple_sart_get apple_sart_add_allowed_region apple_sart_remove_allowed_region; do
  /opt/homebrew/opt/llvm/bin/llvm-nm "$output/apple-sart.ko" | rg -q " __ksymtab_${symbol}$"
  rg -q "[[:space:]]${symbol}[[:space:]]" "$output/apple-sart.symvers"
done
echo SART_EXPORT_TABLE_VERIFIED
