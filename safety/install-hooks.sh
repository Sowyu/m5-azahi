#!/bin/bash
# Run only after manually reviewing the guard and exact-path allowlist.
set -euo pipefail
cd "$(dirname "$0")/.."
gitdir=$(git rev-parse --absolute-git-dir)
guard="$gitdir/privacy-guard"
if [[ -e "$guard" ]]; then
    echo 'An installed policy already exists; refusing automatic replacement.' >&2
    exit 1
fi
mkdir -p "$guard/hooks"
cp safety/check-publication.py safety/allowed-paths.txt "$guard/"
cp safety/pre-commit safety/pre-push "$guard/hooks/"
chmod 700 "$guard/hooks/pre-commit" "$guard/hooks/pre-push"
chmod 500 "$guard/check-publication.py"
chmod 400 "$guard/allowed-paths.txt"
git config --local core.hooksPath "$guard/hooks"
echo 'Installed independent commit/push policy. Source edits do not change this installed copy.'
