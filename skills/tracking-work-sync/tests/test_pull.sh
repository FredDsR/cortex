#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SELF_DIR/helpers.sh"

SCRIPT="$SCRIPTS_DIR/pull.sh"

# Build a working "enabled" repo with a remote that already has content.
# Sets globals: TMP (home), WORK (work dir), REMOTE (bare remote path)
build_enabled() {
    TMP="$(make_test_home)"
    REMOTE="$(make_fake_remote "$TMP/remote.git")"
    WORK="$TMP/.work"
    git -C "$WORK" init -q -b main
    git -C "$WORK" config user.email test@example.com
    git -C "$WORK" config user.name test
    git -C "$WORK" remote add origin "$REMOTE"
    mkdir -p "$WORK/workspaces/demo/sessions/s1/tasks"
    echo "# Session" > "$WORK/workspaces/demo/sessions/s1/SUMMARY.md"
    echo "# Task foo" > "$WORK/workspaces/demo/sessions/s1/tasks/foo.md"
    git -C "$WORK" add .
    git -C "$WORK" commit -q -m "seed"
    git -C "$WORK" push -q -u origin main
    # Ensure we track upstream so `git pull --rebase origin HEAD` has a base
    git -C "$WORK" branch --set-upstream-to=origin/main main
}

simulate_remote_edit() {
    # Make a separate clone, run user-supplied shell fragment with $other as the clone path,
    # push back, then delete the clone. Usage: simulate_remote_edit '<bash code using $other>'
    local other="$TMP/other"
    rm -rf "$other"
    git clone -q "$REMOTE" "$other"
    git -C "$other" config user.email other@example.com
    git -C "$other" config user.name other
    bash -c "other='$other'; $1"
    rm -rf "$other"
}

# Case 1: disabled → exit 0, no-op
tmp_d="$(make_test_home)"
HOME="$tmp_d" assert_exit 0 bash "$SCRIPT"
cleanup_test_home "$tmp_d"

# Case 2: enabled, clean pull (remote has a new commit)
build_enabled
simulate_remote_edit '
echo "# Task bar" > "$other/workspaces/demo/sessions/s1/tasks/bar.md"
git -C "$other" add .
git -C "$other" commit -q -m "add bar"
git -C "$other" push -q
'
HOME="$TMP" bash "$SCRIPT"
assert_file "$WORK/workspaces/demo/sessions/s1/tasks/bar.md"
cleanup_test_home "$TMP"

# Case 3: SUMMARY.md conflict → auto-resolved, exit 0, marker on stdout
build_enabled
echo "# Session local" > "$WORK/workspaces/demo/sessions/s1/SUMMARY.md"
git -C "$WORK" commit -q -am "local summary edit"
simulate_remote_edit '
echo "# Session remote" > "$other/workspaces/demo/sessions/s1/SUMMARY.md"
git -C "$other" commit -q -am "remote summary edit"
git -C "$other" push -q
'
output=$(HOME="$TMP" bash "$SCRIPT")
echo "$output" | grep -q "SUMMARY.md regenerate-needed" || \
    { echo "FAIL: missing regenerate marker (output was: $output)" >&2; exit 1; }
[[ ! -d "$WORK/.git/rebase-merge" ]] || { echo "FAIL: rebase left in-progress"; exit 1; }
cleanup_test_home "$TMP"

# Case 4: task file conflict → abort, exit 2, report the file
build_enabled
echo "# Task foo local" > "$WORK/workspaces/demo/sessions/s1/tasks/foo.md"
git -C "$WORK" commit -q -am "local foo edit"
simulate_remote_edit '
echo "# Task foo remote" > "$other/workspaces/demo/sessions/s1/tasks/foo.md"
git -C "$other" commit -q -am "remote foo edit"
git -C "$other" push -q
'
set +e
output=$(HOME="$TMP" bash "$SCRIPT" 2>&1)
code=$?
set -e
assert_eq "2" "$code" "task conflict must exit 2"
echo "$output" | grep -q "tasks/foo.md" || { echo "FAIL: task path not named in output: $output"; exit 1; }
[[ ! -d "$WORK/.git/rebase-merge" ]] || { echo "FAIL: rebase not aborted"; exit 1; }
cleanup_test_home "$TMP"

echo "test_pull: PASS"
