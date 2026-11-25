#!/usr/bin/env bash
# Fails if anything that should never be public is in the tracked files:
# local machine paths and names, account numbers, private emails, keys and
# tokens, or local/secret file types. Run before every push to main; CI runs
# it too (.github/workflows/public-check.yml).
set -u
cd "$(git rev-parse --show-toplevel)" || exit 2

fail=0
report() { printf '%s\n' "$1"; fail=1; }

# Text checks over tracked files (binary files skipped). This script is excluded
# because it has to spell the patterns out; encrypted bundles (*.enc.json) are
# excluded because random ciphertext can look like a key.
scan() {
  local label=$1 pattern=$2
  local hits
  hits=$(git grep -I -n -E -i -e "$pattern" -- . ':!tools/public-check.sh' ':!*.enc.json' | cut -c1-200)
  [ -n "$hits" ] && report "== $label" && printf '%s\n' "$hits" | head -20
}

scan "local machine paths"   '/Users/[A-Za-z]|/Volumes/[A-Za-z]|C:\\Users\\|/home/[a-z]+/(Desktop|Documents|Downloads)'
scan "local machine names"   "Johns-Mac|John['’]s Mac mini|Mac[- ]mini \(|Samsung SSD"
scan "brokerage accounts"    '802548230|5XE16551|account[ _-]?(number|no\.?)[^a-z]{0,4}[0-9A-Z]{6,}'
scan "private email"         'johnrthrasher@'
scan "private keys"          'BEGIN [A-Z ]*PRIVATE KEY'
scan "API keys and tokens"   'ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|X-API-KEY:'

# File checks.
files=$(git ls-files | grep -i -E '(^|/)(\.DS_Store|\._.*|Thumbs\.db|\.env(\..*)?|id_rsa.*)$|\.(pem|key|p12)$|password|secret' || true)
[ -n "$files" ] && report "== files that should not be public" && printf '%s\n' "$files"

if [ "$fail" -ne 0 ]; then
  echo "public-check: FAILED. Remove the items above before publishing."
  exit 1
fi
echo "public-check: clean"
