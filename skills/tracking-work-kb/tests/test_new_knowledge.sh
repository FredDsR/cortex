#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SELF_DIR/helpers.sh"

# Case 1: happy path - active session resolves workspace, knowledge file created.
tmp="$(make_test_home)"
trap "cleanup_test_home $tmp" EXIT

out="$(HOME="$tmp" "$BIN" new knowledge sample --body "hello world")"

expected_path="$tmp/.work/workspaces/ws-a/knowledge/sample.md"
assert_eq "$expected_path" "$out" "printed path"
assert_file "$expected_path"
assert_contains "$expected_path" "author: agent"
assert_contains "$expected_path" "created: $(date +%Y-%m-%d)"
assert_contains "$expected_path" "hello world"

echo "test_new_knowledge: PASS"
