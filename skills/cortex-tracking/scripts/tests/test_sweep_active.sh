#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
. ./lib.sh

SCRIPT="$(cd .. && pwd)/sweep_active.sh"

test_removes_old_and_keeps_new() {
  setup_tmp
  ws="$TEST_HOME/.work/workspaces/example"
  mkdir -p "$ws"
  old="$ws/.active.oldid"
  touch "$old"
  touch -d "10 days ago" "$old"
  new="$ws/.active.newid"
  touch "$new"

  out="$(bash "$SCRIPT" "$ws" 7)"
  assert_contains "$out" ".active.oldid"
  assert_file_absent "$old"
  assert_file_exists "$new"
  teardown_tmp
}

test_noop_on_empty_workspace() {
  setup_tmp
  ws="$TEST_HOME/.work/workspaces/empty"
  mkdir -p "$ws"
  out="$(bash "$SCRIPT" "$ws" 7)"
  assert_eq "$out" ""
  teardown_tmp
}

test_respects_custom_threshold() {
  setup_tmp
  ws="$TEST_HOME/.work/workspaces/custom"
  mkdir -p "$ws"
  f="$ws/.active.threedays"
  touch "$f"
  touch -d "3 days ago" "$f"
  out="$(bash "$SCRIPT" "$ws" 7)"
  assert_file_exists "$f"
  bash "$SCRIPT" "$ws" 1 >/dev/null
  assert_file_absent "$f"
  teardown_tmp
}

run_test test_removes_old_and_keeps_new
run_test test_noop_on_empty_workspace
run_test test_respects_custom_threshold

report
