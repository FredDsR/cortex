#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SELF_DIR/helpers.sh"

SCRIPT="$SCRIPTS_DIR/commit_push.sh"

setup_enabled_repo() {
    local home_dir="$1"
    local remote
    remote="$(make_fake_remote "$home_dir/remote.git")"
    git -C "$home_dir/.work" init -q -b main
    git -C "$home_dir/.work" config user.email test@example.com
    git -C "$home_dir/.work" config user.name test
    git -C "$home_dir/.work" remote add origin "$remote"
    # make an initial commit so push has a base
    echo "seed" > "$home_dir/.work/seed.txt"
    git -C "$home_dir/.work" add seed.txt
    git -C "$home_dir/.work" commit -q -m "seed"
    git -C "$home_dir/.work" push -q -u origin main
}

# Case 1: sync disabled → no-op, exit 0
tmp="$(make_test_home)"; trap "cleanup_test_home $tmp" EXIT
HOME="$tmp" assert_exit 0 bash "$SCRIPT" "track: test"

# Case 2: sync enabled, no changes → exit 0, no new commit
tmp2="$(make_test_home)"
setup_enabled_repo "$tmp2"
before=$(git -C "$tmp2/.work" rev-parse HEAD)
HOME="$tmp2" bash "$SCRIPT" "track: no-op"
after=$(git -C "$tmp2/.work" rev-parse HEAD)
assert_eq "$before" "$after" "no-op should not add a commit"
cleanup_test_home "$tmp2"

# Case 3: sync enabled, a change → new commit, remote has it
tmp3="$(make_test_home)"
setup_enabled_repo "$tmp3"
echo "new data" > "$tmp3/.work/new.md"
HOME="$tmp3" bash "$SCRIPT" "track: add new"
# message should be present in log
git -C "$tmp3/.work" log -1 --format=%s | grep -q "^track: add new$" || \
    { echo "FAIL: commit message not found" >&2; exit 1; }
# remote should have the commit
remote_has="$(git --git-dir "$tmp3/remote.git" log -1 --format=%s)"
assert_eq "track: add new" "$remote_has" "push must propagate to remote"
cleanup_test_home "$tmp3"

# Case 4: ignored files are not staged
tmp4="$(make_test_home)"
setup_enabled_repo "$tmp4"
# write the gitignore like setup.sh would
cp "$SKILL_DIR/templates/gitignore" "$tmp4/.work/.gitignore"
git -C "$tmp4/.work" add .gitignore
git -C "$tmp4/.work" commit -q -m "add gitignore"
git -C "$tmp4/.work" push -q
touch "$tmp4/.work/.active.foobar"
touch "$tmp4/.work/.meta"
echo "real" > "$tmp4/.work/real.md"
HOME="$tmp4" bash "$SCRIPT" "track: mixed"
# only real.md should be in the new commit
changed=$(git -C "$tmp4/.work" show --name-only --format= HEAD | sort | tr '\n' ' ')
[[ "$changed" == *"real.md"* ]] || { echo "FAIL: real.md missing"; exit 1; }
[[ "$changed" != *".active."* ]] || { echo "FAIL: .active.* leaked"; exit 1; }
[[ "$changed" != *".meta"* ]] || { echo "FAIL: .meta leaked"; exit 1; }
cleanup_test_home "$tmp4"

# Advance the remote from a throwaway second clone. Usage:
#   advance_remote "$home_dir" '<bash using $other as the clone path>'
advance_remote() {
    local home_dir="$1" frag="$2"
    local other="$home_dir/other"
    rm -rf "$other"
    git clone -q "$home_dir/remote.git" "$other"
    git -C "$other" config user.email other@example.com
    git -C "$other" config user.name other
    bash -c "set -e; other='$other'; $frag"
    rm -rf "$other"
}

# Case 5: remote advanced, non-conflicting local change → rebase + retry, push succeeds
tmp5="$(make_test_home)"
setup_enabled_repo "$tmp5"
advance_remote "$tmp5" '
echo "from other" > "$other/other.md"
git -C "$other" add other.md
git -C "$other" commit -q -m "other advances remote"
git -C "$other" push -q
'
echo "local change" > "$tmp5/.work/local.md"
HOME="$tmp5" bash "$SCRIPT" "track: local after remote advanced"
remote_subjects="$(git --git-dir "$tmp5/remote.git" log --format=%s | tr '\n' '|')"
[[ "$remote_subjects" == *"track: local after remote advanced"* ]] || \
    { echo "FAIL: local commit not pushed after rebase" >&2; exit 1; }
[[ "$remote_subjects" == *"other advances remote"* ]] || \
    { echo "FAIL: remote commit lost after rebase" >&2; exit 1; }
cleanup_test_home "$tmp5"

# Case 6: remote advanced with a conflicting SUMMARY.md edit → surfaced, NOT
# clobbered, commit stays local, remote unchanged, exit 0 (commit-safe-local)
tmp6="$(make_test_home)"
setup_enabled_repo "$tmp6"
mkdir -p "$tmp6/.work/ws/s"
echo "shared" > "$tmp6/.work/ws/s/SUMMARY.md"
git -C "$tmp6/.work" add .
git -C "$tmp6/.work" commit -q -m "seed summary"
git -C "$tmp6/.work" push -q
advance_remote "$tmp6" '
echo "remote summary" > "$other/ws/s/SUMMARY.md"
git -C "$other" commit -q -am "remote summary edit"
git -C "$other" push -q
'
echo "local summary" > "$tmp6/.work/ws/s/SUMMARY.md"
set +e
out6="$(HOME="$tmp6" bash "$SCRIPT" "track: local summary edit" 2>&1)"; code6=$?
set -e
assert_eq "0" "$code6" "commit path stays commit-safe-local on conflict"
assert_eq "local summary" "$(cat "$tmp6/.work/ws/s/SUMMARY.md")" "local SUMMARY must not be clobbered"
remote_top="$(git --git-dir "$tmp6/remote.git" log -1 --format=%s)"
assert_eq "remote summary edit" "$remote_top" "local commit must not reach remote on conflict"
echo "$out6" | grep -q "SUMMARY.md" || { echo "FAIL: SUMMARY conflict not surfaced: $out6" >&2; exit 1; }
[[ ! -d "$tmp6/.work/.git/rebase-merge" ]] || { echo "FAIL: rebase left in progress" >&2; exit 1; }
cleanup_test_home "$tmp6"

echo "test_commit_push: PASS"
