#!/usr/bin/env bash
# Runs every test_*.sh in this directory. Exit 0 if all pass.

set -u
cd "$(dirname "$0")"

failed=0
for t in test_*.sh; do
  [ -f "$t" ] || continue
  echo "== $t =="
  if bash "$t"; then
    :
  else
    failed=$((failed + 1))
  fi
done

echo
if [ "$failed" -gt 0 ]; then
  echo "SUITE FAIL: $failed test files failed"
  exit 1
fi
echo "SUITE PASS"
