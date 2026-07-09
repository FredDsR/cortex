#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SELF_DIR/helpers.sh"
export WORK_KB_PYTHON="$(cd "$SELF_DIR/../../.." && pwd)/.venv/bin/python"
REPO="$SELF_DIR/fixtures/ingest-repo"

tmp="$(make_test_home)"
trap "cleanup_test_home $tmp" EXIT

# Dry-run: plans, writes nothing.
out="$(HOME="$tmp" "$BIN" ingest --from "$REPO" --workspace ws-a)"
printf '%s\n' "$out" | grep -qF "would create (deterministic)" || { echo "FAIL: no create section" >&2; exit 1; }
printf '%s\n' "$out" | grep -qF "table-accounts [Reference]" || { echo "FAIL: no accounts concept" >&2; exit 1; }
printf '%s\n' "$out" | grep -qF "op-get-users [API]" || { echo "FAIL: no op concept" >&2; exit 1; }
printf '%s\n' "$out" | grep -qF "agent worklist" || { echo "FAIL: no worklist" >&2; exit 1; }
printf '%s\n' "$out" | grep -qiF "schema.prisma" || { echo "FAIL: prisma not in worklist" >&2; exit 1; }
printf '%s\n' "$out" | grep -qiF "README.md" || { echo "FAIL: readme not in worklist" >&2; exit 1; }
[[ ! -f "$tmp/.work/workspaces/ws-a/knowledge/table-accounts.md" ]] || { echo "FAIL: dry-run wrote a file" >&2; exit 1; }

# --only sql restricts deterministic set.
sqlonly="$(HOME="$tmp" "$BIN" ingest --from "$REPO" --workspace ws-a --only sql)"
printf '%s\n' "$sqlonly" | grep -qF "table-accounts" || { echo "FAIL: sql-only missing table" >&2; exit 1; }
if printf '%s\n' "$sqlonly" | grep -qF "op-get-users"; then echo "FAIL: sql-only leaked openapi" >&2; exit 1; fi

# Fallback: unusable python -> structured files go to worklist, exit 0.
fb="$(HOME="$tmp" WORK_KB_PYTHON=/bin/false "$BIN" ingest --from "$REPO" --workspace ws-a)"; rc=$?
assert_eq 0 "$rc" "fallback exit"
printf '%s\n' "$fb" | grep -qiF "openapi.yaml" || { echo "FAIL: fallback openapi not in worklist" >&2; exit 1; }

# --write creates one doc per concept with frontmatter + cross-link, skips existing.
tmp2="$(make_test_home)"
HOME="$tmp2" "$BIN" ingest --from "$REPO" --workspace ws-a --write >/dev/null
acc="$tmp2/.work/workspaces/ws-a/knowledge/table-accounts.md"
ord="$tmp2/.work/workspaces/ws-a/knowledge/table-orders.md"
assert_file "$acc"; assert_file "$ord"
assert_contains "$acc" "type: Reference"
assert_contains "$acc" "title: accounts"
assert_contains "$ord" "[[knowledge/table-accounts]]"
assert_contains "$tmp2/.work/workspaces/ws-a/knowledge/op-get-users.md" "type: API"

# Idempotent: second --write skips all existing.
again="$(HOME="$tmp2" "$BIN" ingest --from "$REPO" --workspace ws-a --write)"
printf '%s\n' "$again" | grep -qF "skipped (exists)" || { echo "FAIL: no skipped section" >&2; exit 1; }

# --max caps writes and prints truncation notice.
tmp3="$(make_test_home)"
capped="$(HOME="$tmp3" "$BIN" ingest --from "$REPO" --workspace ws-a --write --max 1)"
printf '%s\n' "$capped" | grep -qF "more (raise --max)" || { echo "FAIL: no truncation notice" >&2; exit 1; }
written="$(find "$tmp3/.work/workspaces/ws-a/knowledge" -name '*.md' | wc -l | tr -d ' ')"
assert_eq 1 "$written" "max caps writes"
cleanup_test_home "$tmp2"; cleanup_test_home "$tmp3"

echo "test_ingest: PASS"
