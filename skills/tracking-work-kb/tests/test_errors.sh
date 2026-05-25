#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SELF_DIR/helpers.sh"

# Case 1: invalid slug
tmp1="$(make_test_home)"
HOME="$tmp1" assert_exit 1 "$BIN" new knowledge "BAD_Slug" --body x
cleanup_test_home "$tmp1"

# Case 2: file exists
tmp2="$(make_test_home)"
HOME="$tmp2" "$BIN" new knowledge dup --body first >/dev/null
HOME="$tmp2" assert_exit 1 "$BIN" new knowledge dup --body second
cleanup_test_home "$tmp2"

# Case 3: no active session, no --workspace -> error
tmp3="$(mktemp -d "${TMPDIR:-/tmp}/twkb-noactive-XXXXXX")"
mkdir -p "$tmp3/.work/workspaces/ws-orphan/knowledge"
HOME="$tmp3" assert_exit 1 "$BIN" new knowledge foo --body x
cleanup_test_home "$tmp3"

# Case 4: multiple active workspaces, no flag -> error
tmp4="$(make_test_home)"
mkdir -p "$tmp4/.work/workspaces/ws-b/sessions/sess-b"
echo "sess-b" > "$tmp4/.work/workspaces/ws-b/.active.testid2"
HOME="$tmp4" assert_exit 1 "$BIN" new knowledge foo --body x
cleanup_test_home "$tmp4"

# Case 5: --author human writes author: human
tmp5="$(make_test_home)"
HOME="$tmp5" "$BIN" new knowledge human-entry --author human --body x >/dev/null
assert_contains "$tmp5/.work/workspaces/ws-a/knowledge/human-entry.md" "author: human"
cleanup_test_home "$tmp5"

# Case 6: --body-from - reads stdin
tmp6="$(make_test_home)"
echo "piped body" | HOME="$tmp6" "$BIN" new knowledge piped --body-from - >/dev/null
assert_contains "$tmp6/.work/workspaces/ws-a/knowledge/piped.md" "piped body"
cleanup_test_home "$tmp6"

# Case 7: explicit --workspace overrides discovery
tmp7="$(make_test_home)"
mkdir -p "$tmp7/.work/workspaces/ws-c/knowledge"
HOME="$tmp7" "$BIN" new knowledge cross --workspace ws-c --body x >/dev/null
assert_file "$tmp7/.work/workspaces/ws-c/knowledge/cross.md"
cleanup_test_home "$tmp7"

# Case 8: --open with EDITOR=true succeeds, defaults author=human
tmp8="$(make_test_home)"
EDITOR=true HOME="$tmp8" "$BIN" new knowledge editable --body x --open
assert_file "$tmp8/.work/workspaces/ws-a/knowledge/editable.md"
assert_contains "$tmp8/.work/workspaces/ws-a/knowledge/editable.md" "author: human"
cleanup_test_home "$tmp8"

# Case 9: workbench --session flag honored
tmp9="$(make_test_home)"
mkdir -p "$tmp9/.work/workspaces/ws-a/sessions/sess-b/workbench"
HOME="$tmp9" "$BIN" new workbench from-other --session sess-b --body x >/dev/null
assert_file "$tmp9/.work/workspaces/ws-a/sessions/sess-b/workbench/from-other.md"
cleanup_test_home "$tmp9"

# Case 10: workbench with no active session + no --session -> error
tmp10="$(mktemp -d "${TMPDIR:-/tmp}/twkb-nosess-XXXXXX")"
mkdir -p "$tmp10/.work/workspaces/ws-x/sessions/sess-x/workbench"
HOME="$tmp10" assert_exit 1 "$BIN" new workbench foo --workspace ws-x --body x
cleanup_test_home "$tmp10"

echo "test_errors: PASS"
