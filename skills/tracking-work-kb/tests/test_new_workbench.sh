#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SELF_DIR/helpers.sh"

# Happy path: workbench file goes to active session's workbench dir.
tmp="$(make_test_home)"
trap "cleanup_test_home $tmp" EXIT

out="$(HOME="$tmp" "$BIN" new workbench draft-notes --body "scratch")"

expected_path="$tmp/.work/workspaces/ws-a/sessions/sess-a/workbench/draft-notes.md"
assert_eq "$expected_path" "$out" "printed path"
assert_file "$expected_path"
assert_contains "$expected_path" "author: agent"
assert_contains "$expected_path" "scratch"

echo "test_new_workbench: PASS"
