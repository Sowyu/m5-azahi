#!/bin/sh
# Host-only tests of the shared C transport; no root or device access.
set -eu
cd "$(dirname "$0")"
mkdir -p build
output=$(mktemp -d "$PWD/build/host-transport.XXXXXX")
for test in test-spmi4 test-hpm-awake; do
  # The logical HPM test supplies fake transfers; the lower-level static
  # transport helper included by the shared header is unused in that test.
  "${CC:-clang}" -std=c11 -Wall -Wextra -Werror -Wno-unused-function -g -O1 \
    -fsanitize=address,undefined -fno-omit-frame-pointer \
    "$test.c" -o "$output/$test"
  "$output/$test"
done
printf 'Sanitized host test executables retained: %s\n' "$output"
