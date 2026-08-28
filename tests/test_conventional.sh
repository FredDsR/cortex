#!/usr/bin/env bash
# Covers the local commit-msg hook. The PR title gate is amannn/action-semantic-
# pull-request, which is tested upstream and not re-tested here.
set -u
cd "$(dirname "$0")"
. ../skills/cortex-tracking/scripts/tests/lib.sh

REPO="$(cd .. && pwd)"
HOOK="$REPO/.githooks/commit-msg"
TYPES="$REPO/.conventional-types"

check() {
  local msg="$1" tmp rc
  tmp="$(mktemp)"
  printf '%s\n' "$msg" > "$tmp"
  bash "$HOOK" "$tmp" >/dev/null 2>&1
  rc=$?
  rm -f "$tmp"
  return $rc
}

assert_accepts() {
  if check "$1"; then _pass=$((_pass + 1)); else
    _fail=$((_fail + 1)); echo "  FAIL: ${_current_test} should ACCEPT: '$1'"; fi
}

assert_rejects() {
  if check "$1"; then
    _fail=$((_fail + 1)); echo "  FAIL: ${_current_test} should REJECT: '$1'"
  else _pass=$((_pass + 1)); fi
}

test_accepts_valid_forms() {
  assert_accepts "feat: add a thing"
  assert_accepts "fix(kb): stop dropping frontmatter"
  assert_accepts "feat(store)!: rename the workspace resolver"
  assert_accepts "docs: update the readme"
}

test_accepts_every_declared_type() {
  while read -r t; do
    case "$t" in ''|\#*) continue ;; esac
    assert_accepts "$t: a valid subject"
  done < "$TYPES"
}

test_rejects_malformed() {
  assert_rejects "nope: unknown type"
  assert_rejects "feat missing colon"
  assert_rejects "feat:"
  assert_rejects "feat: trailing period."
  assert_rejects ""
}

test_rejects_over_72_chars() {
  local s66 s67
  s66="$(printf 'a%.0s' $(seq 1 66))"
  s67="$(printf 'a%.0s' $(seq 1 67))"
  assert_accepts "feat: $s66"
  assert_rejects "feat: $s67"
}

test_allows_merge_and_fixup() {
  assert_accepts "Merge branch 'main' into feat/x"
  assert_accepts "Revert \"feat: add a thing\""
  assert_accepts "fixup! feat: add a thing"
}

test_reads_types_from_file_not_hardcoded() {
  local dir tmp
  dir="$(mktemp -d)"
  printf 'banana\n' > "$dir/types"
  tmp="$(mktemp)"
  printf 'banana: a custom type\n' > "$tmp"
  if CORTEX_TYPES_FILE="$dir/types" bash "$HOOK" "$tmp" >/dev/null 2>&1; then
    _pass=$((_pass + 1))
  else
    _fail=$((_fail + 1))
    echo "  FAIL: ${_current_test} hook does not read CORTEX_TYPES_FILE"
  fi
  rm -rf "$dir" "$tmp"
}

test_error_message_names_the_problem() {
  local tmp out
  tmp="$(mktemp)"
  printf 'nope: unknown type\n' > "$tmp"
  out="$(bash "$HOOK" "$tmp" 2>&1 || true)"
  assert_contains "$out" "nope"
  assert_contains "$out" "feat"
  rm -f "$tmp"
}

run_test test_accepts_valid_forms
run_test test_accepts_every_declared_type
run_test test_rejects_malformed
run_test test_rejects_over_72_chars
run_test test_allows_merge_and_fixup
run_test test_reads_types_from_file_not_hardcoded
run_test test_error_message_names_the_problem
report
