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

echo "test_commit_push: PASS"
