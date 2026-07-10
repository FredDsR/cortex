#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SELF_DIR/../../.." && pwd)"
CORTEX="$REPO/skills/tracking-work/bin/cortex"

fail() { echo "FAIL: $1" >&2; exit 1; }

bindir="$(mktemp -d "${TMPDIR:-/tmp}/cortex-bin-XXXXXX")"
home="$(mktemp -d "${TMPDIR:-/tmp}/cortex-home-XXXXXX")"
trap 'rm -rf "$bindir" "$home"' EXIT
ln -s "$CORTEX" "$bindir/cortex"
mkdir -p "$home/.work/workspaces/ws-a"

# kb routing: creates a knowledge file
HOME="$home" "$bindir/cortex" kb new knowledge foo --workspace ws-a --body b >/dev/null
[ -f "$home/.work/workspaces/ws-a/knowledge/foo.md" ] || fail "cortex kb did not route to work-kb"

# viz routing: --help exits 0 and mentions build
vout="$(HOME="$home" "$bindir/cortex" viz --help 2>&1)" || fail "cortex viz --help nonzero"
printf '%s\n' "$vout" | grep -qi "build" || fail "cortex viz --help not routed to work-viz"

# top-level help lists both groups, exit 0
hout="$(HOME="$home" "$bindir/cortex" --help 2>&1)"; rc=$?
[ "$rc" -eq 0 ] || fail "cortex --help exit $rc"
printf '%s\n' "$hout" | grep -q "kb" && printf '%s\n' "$hout" | grep -q "viz" || fail "help missing groups"

# unknown group exits 2
set +e; HOME="$home" "$bindir/cortex" bogus >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -eq 2 ] || fail "unknown group exit $rc (want 2)"

# bare via PATH self-locates
set +e; PATH="$bindir:$PATH" HOME="$home" cortex kb index --workspace ws-a >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -eq 0 ] || fail "bare-via-PATH invocation failed ($rc)"

# harness-dir install shape: the skill dir is a symlink and cortex is a real file
# inside it, with sibling skills co-symlinked (mimics ~/.claude/skills/...).
hdir="$(mktemp -d "${TMPDIR:-/tmp}/cortex-harness-XXXXXX")"
trap 'rm -rf "$bindir" "$home" "$hdir"' EXIT
mkdir -p "$hdir/skills"
ln -s "$REPO/skills/tracking-work" "$hdir/skills/tracking-work"
ln -s "$REPO/skills/tracking-work-kb" "$hdir/skills/tracking-work-kb"
ln -s "$REPO/skills/tracking-work-viz" "$hdir/skills/tracking-work-viz"
HOME="$home" "$hdir/skills/tracking-work/bin/cortex" kb index --workspace ws-a >/dev/null \
    || fail "harness-dir invocation did not route to work-kb"

# missing sibling -> clear error, not a raw exec failure
solo="$(mktemp -d "${TMPDIR:-/tmp}/cortex-solo-XXXXXX")"; mkdir -p "$solo/skills"
ln -s "$REPO/skills/tracking-work" "$solo/skills/tracking-work"
set +e; err="$(HOME="$home" "$solo/skills/tracking-work/bin/cortex" kb index --workspace ws-a 2>&1)"; rc=$?; set -e
rm -rf "$solo"
[ "$rc" -ne 0 ] || fail "missing-sibling case should fail"
printf '%s\n' "$err" | grep -qi "cannot find" || fail "missing-sibling gave no clear error"

echo "test_cortex: PASS"
