#!/bin/bash
# No target access. Compile/run exact policy with host sanitizers.
set -euo pipefail
cd "$(dirname "$0")"
test_dir=$(mktemp -d "${TMPDIR:-/tmp}/azahi-root-policy.XXXXXX")
clang -std=c11 -Wall -Wextra -Werror -UNDEBUG -fsanitize=undefined,address \
  -o "$test_dir/policy-test" test-root-write-policy.c
"$test_dir/policy-test"
echo "Host test executable retained at $test_dir/policy-test"
