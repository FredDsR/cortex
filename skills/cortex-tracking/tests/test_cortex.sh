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
mkdir -p "$home/.cortex/workspaces/ws-a"

# kb routing: creates a knowledge file
HOME="$home" "$bindir/cortex" kb new knowledge foo --type Reference --workspace ws-a --body b >/dev/null
[ -f "$home/.cortex/workspaces/ws-a/knowledge/foo.md" ] || fail "cortex kb did not route to the kb engine"

# knowledge requires --type (OKF v0.2 section 11), through the front door
set +e; HOME="$home" "$bindir/cortex" kb new knowledge untyped --workspace ws-a \
    --body b >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -eq 1 ] || fail "kb new knowledge without --type exit $rc (want 1)"
[ ! -f "$home/.cortex/workspaces/ws-a/knowledge/untyped.md" ] || fail "typeless kb new wrote a file"

# kb index --write derives lowercase index.md in OKF section 8 form
HOME="$home" "$bindir/cortex" kb index --workspace ws-a --write >/dev/null
idx="$home/.cortex/workspaces/ws-a/knowledge/index.md"
[ -f "$idx" ] || fail "kb index --write did not derive index.md"
[ ! -f "$home/.cortex/workspaces/ws-a/knowledge/INDEX.md" ] || fail "legacy INDEX.md survived"
grep -q '^\* \[foo\](foo.md) - ' "$idx" || fail "index.md is not in section 8 form"

# kb log routing: no git in the store means it says so and writes nothing
lgout="$(HOME="$home" "$bindir/cortex" kb log --workspace ws-a 2>&1)" \
    || fail "cortex kb log nonzero without a repo"
printf '%s\n' "$lgout" | grep -q "not a git repo" || fail "kb log did not name the missing repo"
HOME="$home" "$bindir/cortex" kb log --workspace ws-a --write >/dev/null 2>&1
[ ! -f "$home/.cortex/workspaces/ws-a/knowledge/log.md" ] || fail "kb log --write wrote without a repo"

# ... and with one, it derives a section 9 log the index never picks up
git -C "$home/.cortex" init -q
git -C "$home/.cortex" config user.email t@example.com
git -C "$home/.cortex" config user.name t
git -C "$home/.cortex" add -A .
git -C "$home/.cortex" commit -q -m "track(kb): new knowledge foo"
HOME="$home" "$bindir/cortex" kb log --workspace ws-a --write >/dev/null \
    || fail "cortex kb log --write nonzero"
log="$home/.cortex/workspaces/ws-a/knowledge/log.md"
[ -f "$log" ] || fail "kb log --write derived no log.md"
grep -q '^\* \*\*Creation\*\*: ' "$log" || fail "log.md is not in section 9 form"
head -c 3 "$log" | grep -q -- '---' && fail "log.md must have no frontmatter (section 9)"
HOME="$home" "$bindir/cortex" kb index --workspace ws-a --write >/dev/null
grep -q 'log.md' "$home/.cortex/workspaces/ws-a/knowledge/index.md" \
    && fail "reserved log.md leaked into the index"

# viz routing: --help exits 0 and mentions build
vout="$(HOME="$home" "$bindir/cortex" viz --help 2>&1)" || fail "cortex viz --help nonzero"
printf '%s\n' "$vout" | grep -qi "build" || fail "cortex viz --help not routed to the viz engine"

# query routing: neighbors of a known doc exits 0 and prints sections
HOME="$home" "$bindir/cortex" kb new knowledge qn --type Reference --workspace ws-a --body b >/dev/null
qout="$(HOME="$home" "$bindir/cortex" query neighbors qn --workspace ws-a 2>&1)" \
    || fail "cortex query neighbors nonzero"
printf '%s\n' "$qout" | grep -qi "Ghost references" || fail "query neighbors output missing sections"

# kb lint routing: reports sections, and --strict exits 1 on a finding
lout="$(HOME="$home" "$bindir/cortex" kb lint --workspace ws-a 2>&1)" \
    || fail "cortex kb lint nonzero"
printf '%s\n' "$lout" | grep -q "## summary" || fail "kb lint output missing summary"
set +e; HOME="$home" "$bindir/cortex" kb lint --workspace ws-a --check orphan --strict \
    >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -eq 1 ] || fail "kb lint --strict exit $rc (want 1 with findings)"

# top-level help lists all groups, exit 0
hout="$(HOME="$home" "$bindir/cortex" --help 2>&1)"; rc=$?
[ "$rc" -eq 0 ] || fail "cortex --help exit $rc"
printf '%s\n' "$hout" | grep -q "kb" && printf '%s\n' "$hout" | grep -q "viz" \
    && printf '%s\n' "$hout" | grep -q "query" || fail "help missing groups"

# unknown group exits 2
set +e; HOME="$home" "$bindir/cortex" bogus >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -eq 2 ] || fail "unknown group exit $rc (want 2)"

# bare via PATH self-locates
set +e; PATH="$bindir:$PATH" HOME="$home" cortex kb new knowledge bare --type Reference --workspace ws-a --body b >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -eq 0 ] || fail "bare-via-PATH invocation failed ($rc)"

# harness-dir install shape: cortex is reached through a symlinked skill dir
# (mimics ~/.claude/skills/cortex-tracking/bin/cortex). Physical path resolution
# must still find the real repo root (where the top-level cortex/ package is).
hdir="$(mktemp -d "${TMPDIR:-/tmp}/cortex-harness-XXXXXX")"
trap 'rm -rf "$bindir" "$home" "$hdir"' EXIT
mkdir -p "$hdir/skills"
ln -s "$REPO/skills/cortex-tracking" "$hdir/skills/cortex-tracking"
HOME="$home" "$hdir/skills/cortex-tracking/bin/cortex" kb new knowledge harness --type Reference --workspace ws-a --body b >/dev/null \
    || fail "harness-dir invocation did not route to the cortex engine"
[ -f "$home/.cortex/workspaces/ws-a/knowledge/harness.md" ] || fail "harness-dir kb new wrote no file"

echo "test_cortex: PASS"
