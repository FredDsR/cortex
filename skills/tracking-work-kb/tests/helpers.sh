#!/usr/bin/env bash
# Shared test helpers for tracking-work-kb. Source from each test_*.sh.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$SKILL_DIR/bin/work-kb"

# Create a fresh tempdir that acts as HOME for the test; returns the path.
# Sets up ~/.work/workspaces/ws-a/sessions/sess-a/ with one active pointer.
make_test_home() {
    local home_dir
    home_dir="$(mktemp -d "${TMPDIR:-/tmp}/twkb-test-XXXXXX")"
    mkdir -p "$home_dir/.work/workspaces/ws-a/sessions/sess-a/tasks"
    mkdir -p "$home_dir/.work/workspaces/ws-a/sessions/sess-a/workbench"
    echo "sess-a" > "$home_dir/.work/workspaces/ws-a/.active.testid"
    cat > "$home_dir/.work/workspaces/ws-a/sessions/sess-a/SUMMARY.md" <<EOF
---
slug: sess-a
started: 2026-05-25
status: Active
---

# sess-a
EOF
    echo "$home_dir"
}

cleanup_test_home() {
    local home_dir="$1"
    if [[ -n "$home_dir" && -d "$home_dir" ]]; then
        rm -rf "$home_dir"
    fi
    return 0
}

assert_eq() {
    local expected="$1" actual="$2" msg="${3:-}"
    if [[ "$expected" != "$actual" ]]; then
        echo "FAIL: ${msg:-assertion}: expected '$expected', got '$actual'" >&2
        return 1
    fi
}

assert_exit() {
    local expected_code="$1"; shift
    local actual=0
    "$@" >/dev/null 2>&1 || actual=$?
    assert_eq "$expected_code" "$actual" "exit code of: $*"
}

assert_file() {
    local path="$1"
    [[ -f "$path" ]] || { echo "FAIL: file not found: $path" >&2; return 1; }
}

assert_not_file() {
    local path="$1"
    [[ ! -f "$path" ]] || { echo "FAIL: file should not exist: $path" >&2; return 1; }
}

assert_contains() {
    local path="$1" needle="$2"
    grep -q -F "$needle" "$path" || { echo "FAIL: $path missing literal: $needle" >&2; return 1; }
}
