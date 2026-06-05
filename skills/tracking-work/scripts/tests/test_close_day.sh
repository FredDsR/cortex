#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
. ./lib.sh

SCRIPT="$(cd .. && pwd)/close_day.sh"

# Build a workspace with an active session pointing at <session>.
# Slug resolves to basename(TEST_CWD) == "cwd".
mk_active_session() {
  local session="$1" started="${2:-}"
  local ws="$TEST_HOME/.work/workspaces/cwd"
  mkdir -p "$ws/sessions/$session/tasks"
  {
    printf -- '---\n'
    printf 'slug: %s\n' "$session"
    [ -n "$started" ] && printf 'started: %s\n' "$started"
    printf 'status: Active\n'
    printf -- '---\n\n# Session: %s\n' "$session"
  } > "$ws/sessions/$session/SUMMARY.md"
  printf '%s\n' "$session" > "$ws/.active.testsid"
}

# --- Task 1: resolution + STATUS ---

test_status_emits_a_status_line() {
  setup_tmp
  out="$(WORK_SESSION_ID=testsid bash "$SCRIPT" "$TEST_HOME")"
  assert_contains "$out" "STATUS" "emits a STATUS line"
  teardown_tmp
}

test_status_no_active_session() {
  setup_tmp
  out="$(WORK_SESSION_ID=testsid bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" $'STATUS\tno-active-session' "no .active pointer -> no-active-session"
  teardown_tmp
}

test_status_ok_and_session_line() {
  setup_tmp
  mk_active_session "sess-a" "2026-06-01"
  out="$(WORK_SESSION_ID=testsid bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" $'STATUS\tok' "resolves -> ok"
  assert_contains "$out" $'SESSION\tsess-a\t2026-06-01' "SESSION line with started date"
  teardown_tmp
}

# --- Task 2: NEXT_DAY ---

test_next_day_weekday_is_tomorrow() {
  setup_tmp
  mk_active_session "sess-a" "2026-06-01"
  out="$(WORK_SESSION_ID=testsid WORK_TODAY_DOW=4 bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" $'NEXT_DAY\ttomorrow' "Thu -> tomorrow"
  teardown_tmp
}

test_next_day_friday_is_monday() {
  setup_tmp
  mk_active_session "sess-a" "2026-06-01"
  out="$(WORK_SESSION_ID=testsid WORK_TODAY_DOW=5 bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" $'NEXT_DAY\tMonday' "Fri -> Monday"
  teardown_tmp
}

test_next_day_sunday_is_monday() {
  setup_tmp
  mk_active_session "sess-a" "2026-06-01"
  out="$(WORK_SESSION_ID=testsid WORK_TODAY_DOW=7 bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" $'NEXT_DAY\tMonday' "Sun -> Monday"
  teardown_tmp
}

# --- Task 3: TASKS section ---

test_tasks_lists_active_session_only() {
  setup_tmp
  mk_active_session "sess-a" "2026-06-01"
  local ws="$TEST_HOME/.work/workspaces/cwd"
  {
    printf -- '---\nstatus: In Progress\n---\n\n# Task A\n'
  } > "$ws/sessions/sess-a/tasks/task-a.md"
  mkdir -p "$ws/sessions/sess-b/tasks"
  {
    printf -- '---\nstatus: Open\n---\n\n# Task B\n'
  } > "$ws/sessions/sess-b/tasks/task-b.md"

  out="$(WORK_SESSION_ID=testsid bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" "TASKS" "TASKS section header"
  assert_contains "$out" $'task-a\tIn Progress' "active session task with status"
  assert_not_contains "$out" "task-b" "sibling session task excluded"
  teardown_tmp
}

# --- Task 4: COMMITS + UNCOMMITTED ---

test_commits_and_uncommitted_in_repo() {
  setup_tmp
  mk_active_session "sess-a" "2026-06-01"
  git -C "$TEST_CWD" init -q
  git -C "$TEST_CWD" config user.email t@t.t
  git -C "$TEST_CWD" config user.name t
  echo a > "$TEST_CWD/a.txt"
  git -C "$TEST_CWD" add a.txt
  git -C "$TEST_CWD" commit -q -m "add alpha file"
  echo b > "$TEST_CWD/b.txt"

  out="$(WORK_SESSION_ID=testsid bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" "COMMITS" "COMMITS header"
  assert_contains "$out" "add alpha file" "commit subject since started"
  assert_contains "$out" "UNCOMMITTED" "UNCOMMITTED header"
  assert_contains "$out" "b.txt" "untracked file surfaced"
  teardown_tmp
}

test_non_repo_omits_git_sections_but_status_ok() {
  setup_tmp
  mk_active_session "sess-a" "2026-06-01"
  out="$(WORK_SESSION_ID=testsid bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" $'STATUS\tok' "non-repo still ok"
  assert_not_contains "$out" "COMMITS" "no COMMITS section without a repo"
  assert_not_contains "$out" "UNCOMMITTED" "no UNCOMMITTED section without a repo"
  teardown_tmp
}

# --- Task 5: no writes ---

test_helper_does_not_write_session_files() {
  setup_tmp
  mk_active_session "sess-a" "2026-06-01"
  local ws="$TEST_HOME/.work/workspaces/cwd"
  {
    printf -- '---\nstatus: Open\n---\n\n# Task A\n'
  } > "$ws/sessions/sess-a/tasks/task-a.md"

  before="$(find "$ws/sessions" -type f -exec sha1sum {} \; | sort)"
  WORK_SESSION_ID=testsid bash "$SCRIPT" "$TEST_CWD" >/dev/null
  after="$(find "$ws/sessions" -type f -exec sha1sum {} \; | sort)"

  assert_eq "$after" "$before" "session files unchanged by snapshot"
  teardown_tmp
}

run_test test_status_emits_a_status_line
run_test test_status_no_active_session
run_test test_status_ok_and_session_line
run_test test_next_day_weekday_is_tomorrow
run_test test_next_day_friday_is_monday
run_test test_next_day_sunday_is_monday
run_test test_tasks_lists_active_session_only
run_test test_commits_and_uncommitted_in_repo
run_test test_non_repo_omits_git_sections_but_status_ok
run_test test_helper_does_not_write_session_files
report
