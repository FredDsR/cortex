#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
. ./lib.sh

SCRIPT="$(cd .. && pwd)/resolve_session_id.sh"

test_explicit_override_wins() {
  setup_tmp
  unset CLAUDE_SESSION_ID COPILOT_SESSION_ID CURSOR_SESSION_ID CODEX_SESSION_ID
  export WORK_SESSION_ID="explicit-override-123"
  out="$(bash "$SCRIPT" 2>/dev/null)"
  src="$(bash "$SCRIPT" 2>&1 >/dev/null)"
  assert_eq "$out" "explicit-override-123"
  assert_eq "$src" "env"
  unset WORK_SESSION_ID
  teardown_tmp
}

test_claude_env_wins_when_no_override() {
  setup_tmp
  unset WORK_SESSION_ID COPILOT_SESSION_ID CURSOR_SESSION_ID CODEX_SESSION_ID
  export CLAUDE_SESSION_ID="claude-abc-xyz"
  out="$(bash "$SCRIPT" 2>/dev/null)"
  src="$(bash "$SCRIPT" 2>&1 >/dev/null)"
  assert_eq "$out" "claude-abc-xyz"
  assert_eq "$src" "claude"
  unset CLAUDE_SESSION_ID
  teardown_tmp
}

test_copilot_env_wins_when_no_claude() {
  setup_tmp
  unset WORK_SESSION_ID CLAUDE_SESSION_ID CURSOR_SESSION_ID CODEX_SESSION_ID
  export COPILOT_SESSION_ID="copilot-xyz"
  src="$(bash "$SCRIPT" 2>&1 >/dev/null)"
  assert_eq "$src" "copilot"
  unset COPILOT_SESSION_ID
  teardown_tmp
}

test_ppid_fingerprint_is_stable() {
  setup_tmp
  unset WORK_SESSION_ID CLAUDE_SESSION_ID COPILOT_SESSION_ID CURSOR_SESSION_ID CODEX_SESSION_ID
  a="$(bash "$SCRIPT" 2>/dev/null)"
  b="$(bash "$SCRIPT" 2>/dev/null)"
  assert_eq "$a" "$b" "same PPID should produce same fingerprint"
  len="${#a}"
  assert_eq "$len" "12" "fingerprint length should be 12"
  teardown_tmp
}

test_lease_fallback_persists() {
  setup_tmp
  unset WORK_SESSION_ID CLAUDE_SESSION_ID COPILOT_SESSION_ID CURSOR_SESSION_ID CODEX_SESSION_ID
  export WORK_FORCE_LEASE=1
  a="$(bash "$SCRIPT" 2>/dev/null)"
  b="$(bash "$SCRIPT" 2>/dev/null)"
  assert_eq "$a" "$b" "lease file should persist the generated UUID"
  assert_file_exists "$XDG_RUNTIME_DIR/work-lease"
  unset WORK_FORCE_LEASE
  teardown_tmp
}

run_test test_explicit_override_wins
run_test test_claude_env_wins_when_no_override
run_test test_copilot_env_wins_when_no_claude
run_test test_ppid_fingerprint_is_stable
run_test test_lease_fallback_persists

report
