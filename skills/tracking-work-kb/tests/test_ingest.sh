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

echo "test_ingest: PASS"
