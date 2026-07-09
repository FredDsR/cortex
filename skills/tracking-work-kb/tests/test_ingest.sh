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
# accounts has no cross-links; its body (columns) must still survive the
# record wire format (regression: empty links field must not shift the body out).
assert_contains "$acc" "DECIMAL(10,2)"
assert_contains "$ord" "[[knowledge/table-accounts]]"
assert_contains "$tmp2/.work/workspaces/ws-a/knowledge/op-get-users.md" "type: API"

# Regression (finding 1): a summary with ':' and '#' must yield VALID YAML
# frontmatter that round-trips, not a corrupted/truncated block.
opo="$tmp2/.work/workspaces/ws-a/knowledge/op-post-orders.md"
assert_file "$opo"
for d in "$tmp2"/.work/workspaces/ws-a/knowledge/*.md; do
    "$WORK_KB_PYTHON" - "$d" <<'PYEOF'
import sys, yaml
fm = open(sys.argv[1]).read().split("---", 2)[1]
yaml.safe_load(fm)  # raises if the frontmatter is not valid YAML
PYEOF
done
"$WORK_KB_PYTHON" - "$opo" <<'PYEOF'
import sys, yaml
fm = yaml.safe_load(open(sys.argv[1]).read().split("---", 2)[1])
assert fm["description"] == "Create order: v2 # urgent", fm.get("description")
PYEOF

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

# Regression (finding 5): extractor diagnostics must be surfaced, not swallowed.
badrepo="$(mktemp -d "${TMPDIR:-/tmp}/ingest-bad-XXXXXX")"
printf 'openapi: 3.0.0\npaths: {\n' > "$badrepo/openapi.yaml"   # malformed YAML
warned="$(HOME="$tmp" "$BIN" ingest --from "$badrepo" --workspace ws-a)"
printf '%s\n' "$warned" | grep -qF "## warnings" || { echo "FAIL: parse failure not surfaced" >&2; exit 1; }
printf '%s\n' "$warned" | grep -qiF "cannot parse" || { echo "FAIL: no parse diagnostic" >&2; exit 1; }
rm -rf "$badrepo"

echo "test_ingest: PASS"
