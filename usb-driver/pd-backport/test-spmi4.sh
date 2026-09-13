#!/bin/sh
# Host-only tests of the shared C transport; no root or device access.
set -eu
cd "$(dirname "$0")"
mkdir -p build
output=$(mktemp -d "$PWD/build/host-transport.XXXXXX")
"${CC:-clang}" -std=c11 -Wall -Wextra -Werror -g -O1 \
  -fsanitize=address,undefined -fno-omit-frame-pointer \
  test-spmi4.c -o "$output/test-spmi4"
"$output/test-spmi4"
printf 'Sanitized host test executable: %s\n' "$output/test-spmi4"
