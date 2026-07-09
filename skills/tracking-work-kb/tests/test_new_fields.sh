#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SELF_DIR/helpers.sh"

tmp="$(make_test_home)"
trap "cleanup_test_home $tmp" EXIT

today="$(date +%Y-%m-%d)"
path="$tmp/.work/workspaces/ws-a/knowledge/decided.md"

HOME="$tmp" "$BIN" new knowledge decided \
    --title "A decision" --type Decision --description "why we chose X" \
    --body "body text" >/dev/null

assert_file "$path"
assert_contains "$path" "title: A decision"
assert_contains "$path" "type: Decision"
assert_contains "$path" "author: agent"
assert_contains "$path" "created: $today"
assert_contains "$path" "updated: $today"
assert_contains "$path" "description: why we chose X"
assert_contains "$path" "body text"

# Body preserved after the frontmatter block.
first_body_line="$(sed -n '/^---$/,/^---$/!p' "$path" | sed '/^$/d' | head -n1)"
assert_eq "body text" "$first_body_line" "body preserved"

# No empty optional fields when flags omitted.
HOME="$tmp" "$BIN" new knowledge plain --body "hi" >/dev/null
plain="$tmp/.work/workspaces/ws-a/knowledge/plain.md"
if grep -qE '^(title|type|description):' "$plain"; then
    echo "FAIL: plain doc should not carry optional fields" >&2; exit 1
fi
assert_contains "$plain" "updated: $today"

echo "test_new_fields: PASS"
