#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
. ./lib.sh

SCRIPT="$(cd .. && pwd)/session_start.sh"

test_emits_structured_header() {
  setup_tmp
  out="$(bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" $'WORKSPACE\t' "WORKSPACE line present"
  assert_contains "$out" $'SESSION_ID\t' "SESSION_ID line present"
  assert_contains "$out" $'SYNC\t' "SYNC line present (state depends on whether the cortex CLI + sync are configured)"
  assert_contains "$out" $'SESSIONS' "SESSIONS divider present"
  teardown_tmp
}

test_includes_existing_sessions() {
  setup_tmp
  ws="$TEST_HOME/.cortex/workspaces/$(basename "$TEST_CWD")"
  mkdir -p "$ws/sessions/sess-a"
  printf '# Session: A\n' > "$ws/sessions/sess-a/SUMMARY.md"
  out="$(bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" "sess-a" "sess-a session listed"
  teardown_tmp
}

test_collision_passes_through_exit_2() {
  setup_tmp
  base="$(basename "$TEST_CWD")"
  mkdir -p "$TEST_HOME/.cortex/workspaces/$base"
  printf 'cwd: /elsewhere\nremote:\nsource: basename\nupdated: 2026-04-20\n' \
    > "$TEST_HOME/.cortex/workspaces/$base/.meta"
  bash "$SCRIPT" "$TEST_CWD" >/dev/null 2>&1
  rc=$?
  assert_eq "$rc" "2" "collision should propagate exit 2"
  teardown_tmp
}

run_test test_emits_structured_header
run_test test_includes_existing_sessions
run_test test_collision_passes_through_exit_2

report
