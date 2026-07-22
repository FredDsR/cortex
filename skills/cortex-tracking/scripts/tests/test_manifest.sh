#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
. ./lib.sh

SCRIPT="$(cd .. && pwd)/manifest.sh"

mk_task_fm() {
  local path="$1" status="$2" pr="${3:-}"
  mkdir -p "$(dirname "$path")"
  {
    printf -- '---\n'
    printf 'status: %s\n' "$status"
    [ -n "$pr" ] && printf 'pr: %s\n' "$pr"
    printf -- '---\n\n# %s\n\n## Description\nbody\n' "$(basename "$path" .md)"
  } > "$path"
}

mk_task_bp() {
  local path="$1" status="$2"
  mkdir -p "$(dirname "$path")"
  {
    printf '# %s\n\n' "$(basename "$path" .md)"
    printf -- '**Status:** %s\n' "$status"
    printf '**Blocked by:** task-foo\n'
    printf '\n## Description\nlegacy body\n'
  } > "$path"
}

test_emits_header_and_rows() {
  setup_tmp
  ws="$TEST_HOME/.cortex/workspaces/$(basename "$TEST_CWD")"
  mk_task_fm "$ws/sessions/sess-a/tasks/task-foo.md" "In Progress" "456"
  mk_task_bp "$ws/sessions/sess-a/tasks/task-bar.md" "Open"
  out="$(bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" $'origin\tsession\tslug\tstatus\tblocked_by\tpr\ttitle' "header present"
  assert_contains "$out" $'global\tsess-a\ttask-foo\tIn Progress\t\t456' "frontmatter task row"
  assert_contains "$out" $'global\tsess-a\ttask-bar\tOpen\ttask-foo\t' "bold-pair task with blocked_by"
  teardown_tmp
}

test_local_store_walked() {
  setup_tmp
  mk_task_fm "$TEST_CWD/.cortex/sessions/local-sess/tasks/task-x.md" "Resolved"
  out="$(bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" $'local\tlocal-sess\ttask-x\tResolved' "local-store row"
  teardown_tmp
}

test_pr_link_extracted_from_legacy() {
  setup_tmp
  ws="$TEST_HOME/.cortex/workspaces/$(basename "$TEST_CWD")"
  mkdir -p "$ws/sessions/s/tasks"
  cat > "$ws/sessions/s/tasks/task-pr.md" <<'EOF'
# task-pr

**Status:** Open
**PR:** [#789](https://example.com/789)

## Description
EOF
  out="$(bash "$SCRIPT" "$TEST_CWD")"
  assert_contains "$out" $'task-pr\tOpen\t\t789' "PR number extracted from markdown link"
  teardown_tmp
}

test_no_sessions_emits_only_header() {
  setup_tmp
  out="$(bash "$SCRIPT" "$TEST_CWD")"
  lines=$(echo "$out" | grep -c .)
  assert_eq "$lines" "1" "only header line when no tasks"
  teardown_tmp
}

run_test test_emits_header_and_rows
run_test test_local_store_walked
run_test test_pr_link_extracted_from_legacy
run_test test_no_sessions_emits_only_header

report
