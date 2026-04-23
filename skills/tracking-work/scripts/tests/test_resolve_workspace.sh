#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
. ./lib.sh

SCRIPT="$(cd .. && pwd)/resolve_workspace.sh"

test_git_remote_wins() {
  setup_tmp
  git -C "$TEST_CWD" init -q
  git -C "$TEST_CWD" remote add origin git@github.com:psgequity/OPTX-AI.git
  out="$(bash "$SCRIPT" "$TEST_CWD")"
  assert_eq "$out" "psgequity-OPTX-AI" "git remote should produce owner-repo slug"
  assert_file_exists "$TEST_HOME/.work/workspaces/psgequity-OPTX-AI/.meta"
  teardown_tmp
}

test_https_remote_wins() {
  setup_tmp
  git -C "$TEST_CWD" init -q
  git -C "$TEST_CWD" remote add origin https://github.com/psgequity/OPTX-AI.git
  out="$(bash "$SCRIPT" "$TEST_CWD")"
  assert_eq "$out" "psgequity-OPTX-AI" "https remote should produce same slug"
  teardown_tmp
}

test_basename_fallback_when_no_remote() {
  setup_tmp
  out="$(bash "$SCRIPT" "$TEST_CWD")"
  expected="$(basename "$TEST_CWD")"
  assert_eq "$out" "$expected" "basename fallback when not a git repo"
  teardown_tmp
}

test_meta_registry_match() {
  setup_tmp
  mkdir -p "$TEST_HOME/.work/workspaces/explicit-slug"
  printf 'cwd: %s\nremote:\nsource: manual\nupdated: 2026-04-20\n' "$TEST_CWD" \
    > "$TEST_HOME/.work/workspaces/explicit-slug/.meta"
  out="$(bash "$SCRIPT" "$TEST_CWD")"
  assert_eq "$out" "explicit-slug" "existing .meta registry match should win over basename"
  teardown_tmp
}

test_basename_collision_exits_2() {
  setup_tmp
  mkdir -p "$TEST_HOME/.work/workspaces/$(basename "$TEST_CWD")"
  printf 'cwd: /elsewhere\nremote:\nsource: basename\nupdated: 2026-04-20\n' \
    > "$TEST_HOME/.work/workspaces/$(basename "$TEST_CWD")/.meta"
  bash "$SCRIPT" "$TEST_CWD" >/dev/null 2>&1
  rc=$?
  assert_eq "$rc" "2" "collision should exit with code 2"
  teardown_tmp
}

run_test test_git_remote_wins
run_test test_https_remote_wins
run_test test_basename_fallback_when_no_remote
run_test test_meta_registry_match
run_test test_basename_collision_exits_2

report
