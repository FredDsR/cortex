#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
. ./lib.sh

SCRIPT="$(cd .. && pwd)/list_sessions.sh"
RESOLVE="$(cd .. && pwd)/resolve_workspace.sh"

test_lists_global_and_local_merged() {
  setup_tmp
  mkdir -p "$TEST_CWD/repo"
  cwd="$TEST_CWD/repo"
  ws_slug="$(bash "$RESOLVE" "$cwd")"

  global="$TEST_HOME/.work/workspaces/$ws_slug/sessions"
  mkdir -p "$global/alpha" "$global/beta"
  touch "$global/alpha/SUMMARY.md" "$global/beta/SUMMARY.md"
  sleep 0.1
  touch "$global/beta/SUMMARY.md"
  echo "alpha" > "$TEST_HOME/.work/workspaces/$ws_slug/.active.xyz"

  localws="$cwd/.work/sessions"
  mkdir -p "$localws/gamma"
  touch "$localws/gamma/SUMMARY.md"

  out="$(bash "$SCRIPT" "$cwd")"
  assert_contains "$out" "global"
  assert_contains "$out" "local"
  assert_contains "$out" "alpha"
  assert_contains "$out" "beta"
  assert_contains "$out" "gamma"
  assert_contains "$out" "xyz"
  teardown_tmp
}

test_empty_when_no_sessions() {
  setup_tmp
  mkdir -p "$TEST_CWD/empty"
  out="$(bash "$SCRIPT" "$TEST_CWD/empty")"
  assert_eq "$out" ""
  teardown_tmp
}

run_test test_lists_global_and_local_merged
run_test test_empty_when_no_sessions

report
