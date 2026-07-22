#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SELF_DIR/../../.." && pwd)"
CORTEX="$REPO/skills/cortex-tracking/bin/cortex"

fail() { echo "FAIL: $1" >&2; exit 1; }

bindir="$(mktemp -d "${TMPDIR:-/tmp}/cortex-bin-XXXXXX")"
home="$(mktemp -d "${TMPDIR:-/tmp}/cortex-home-XXXXXX")"
trap 'rm -rf "$bindir" "$home"' EXIT
ln -s "$CORTEX" "$bindir/cortex"
mkdir -p "$home/.work/workspaces/ws-a"

# kb routing: creates a knowledge file
HOME="$home" "$bindir/cortex" kb new knowledge foo --workspace ws-a --body b >/dev/null
[ -f "$home/.work/workspaces/ws-a/knowledge/foo.md" ] || fail "cortex kb did not route to the kb engine"

# viz routing: --help exits 0 and mentions build
vout="$(HOME="$home" "$bindir/cortex" viz --help 2>&1)" || fail "cortex viz --help nonzero"
printf '%s\n' "$vout" | grep -qi "build" || fail "cortex viz --help not routed to the viz engine"

# query routing: neighbors of a known doc exits 0 and prints sections
HOME="$home" "$bindir/cortex" kb new knowledge qn --workspace ws-a --body b >/dev/null
qout="$(HOME="$home" "$bindir/cortex" query neighbors qn --workspace ws-a 2>&1)" \
    || fail "cortex query neighbors nonzero"
printf '%s\n' "$qout" | grep -qi "Ghost references" || fail "query neighbors output missing sections"

# top-level help lists all groups, exit 0
hout="$(HOME="$home" "$bindir/cortex" --help 2>&1)"; rc=$?
[ "$rc" -eq 0 ] || fail "cortex --help exit $rc"
printf '%s\n' "$hout" | grep -q "kb" && printf '%s\n' "$hout" | grep -q "viz" \
    && printf '%s\n' "$hout" | grep -q "query" || fail "help missing groups"

# unknown group exits 2
set +e; HOME="$home" "$bindir/cortex" bogus >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -eq 2 ] || fail "unknown group exit $rc (want 2)"

# bare via PATH self-locates
set +e; PATH="$bindir:$PATH" HOME="$home" cortex kb new knowledge bare --workspace ws-a --body b >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -eq 0 ] || fail "bare-via-PATH invocation failed ($rc)"

# harness-dir install shape: cortex is reached through a symlinked skill dir
# (mimics ~/.claude/skills/cortex-tracking/bin/cortex). Physical path resolution
# must still find the real repo root (where the top-level cortex/ package is).
hdir="$(mktemp -d "${TMPDIR:-/tmp}/cortex-harness-XXXXXX")"
trap 'rm -rf "$bindir" "$home" "$hdir"' EXIT
mkdir -p "$hdir/skills"
ln -s "$REPO/skills/cortex-tracking" "$hdir/skills/cortex-tracking"
HOME="$home" "$hdir/skills/cortex-tracking/bin/cortex" kb new knowledge harness --workspace ws-a --body b >/dev/null \
    || fail "harness-dir invocation did not route to the cortex engine"
[ -f "$home/.work/workspaces/ws-a/knowledge/harness.md" ] || fail "harness-dir kb new wrote no file"

echo "test_cortex: PASS"
