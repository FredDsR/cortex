#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SELF_DIR/helpers.sh"

tmp="$(make_test_home)"
trap "cleanup_test_home $tmp" EXIT
today="$(date +%Y-%m-%d)"
kdir="$tmp/.work/workspaces/ws-a/knowledge"
path="$kdir/note.md"

# Seed a doc with back-dated created/updated so a real bump is observable.
mkdir -p "$kdir"
cat > "$path" <<EOF
---
title: Original
type: Reference
author: agent
created: 2026-01-01
updated: 2026-01-01
description: original desc
---

original body
EOF

# update missing file -> exit 1
assert_exit 1 env HOME="$tmp" "$BIN" update knowledge does-not-exist

# pure touch: bumps updated, preserves everything else
HOME="$tmp" "$BIN" update knowledge note >/dev/null
assert_contains "$path" "created: 2026-01-01"
assert_contains "$path" "updated: $today"
assert_contains "$path" "title: Original"
assert_contains "$path" "type: Reference"
assert_contains "$path" "description: original desc"
assert_contains "$path" "original body"

# field merge: change only description, keep title/type, bump updated
HOME="$tmp" "$BIN" update knowledge note --description "new desc" >/dev/null
assert_contains "$path" "description: new desc"
assert_contains "$path" "title: Original"
assert_contains "$path" "type: Reference"
assert_contains "$path" "original body"

# body replace via --body
HOME="$tmp" "$BIN" update knowledge note --body "replaced body" >/dev/null
assert_contains "$path" "replaced body"
if grep -qF "original body" "$path"; then
    echo "FAIL: body should have been replaced" >&2; exit 1
fi
assert_contains "$path" "title: Original"

echo "test_update: PASS"
