#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SELF_DIR/helpers.sh"

SCRIPT="$SCRIPTS_DIR/setup.sh"

# Case 1: --skip writes sentinel
tmp="$(make_test_home)"; trap "cleanup_test_home $tmp" EXIT
HOME="$tmp" bash "$SCRIPT" --skip
assert_file "$tmp/.work/.sync-disabled"
cleanup_test_home "$tmp"

# Case 2: --clone on empty ~/.work succeeds
tmp2="$(make_test_home)"
# create a bare remote and push a seed commit to it
remote="$(make_fake_remote "$tmp2/remote.git")"
seed="$tmp2/seed"; git clone -q "$remote" "$seed"
git -C "$seed" config user.email s@s; git -C "$seed" config user.name s
echo hi > "$seed/hello.txt"; git -C "$seed" add .; git -C "$seed" commit -q -m init
git -C "$seed" push -q -u origin HEAD:main
rm -rf "$seed"
rmdir "$tmp2/.work"  # clone requires empty/absent target
# mock gh so ensure_gh_authed passes
fakebin2="$(mock_gh_path "$tmp2")"
export GH_CALL_LOG="$tmp2/gh_calls.log"
PATH="$fakebin2:$PATH" HOME="$tmp2" bash "$SCRIPT" --clone "$remote"
assert_file "$tmp2/.work/hello.txt"
# remote should be set
git -C "$tmp2/.work" remote get-url origin >/dev/null
unset GH_CALL_LOG
cleanup_test_home "$tmp2"

# Case 3: --clone refuses if ~/.work non-empty
tmp3="$(make_test_home)"
echo "existing" > "$tmp3/.work/keep.md"
remote3="$(make_fake_remote "$tmp3/remote.git")"
fakebin3="$(mock_gh_path "$tmp3")"
export GH_CALL_LOG="$tmp3/gh_calls.log"
set +e
PATH="$fakebin3:$PATH" HOME="$tmp3" bash "$SCRIPT" --clone "$remote3" 2>/dev/null
code=$?
set -e
assert_eq "3" "$code" "clone must refuse non-empty ~/.work"
assert_file "$tmp3/.work/keep.md"
unset GH_CALL_LOG
cleanup_test_home "$tmp3"

# Case 4: --init creates repo, adds gitignore, calls gh repo create
tmp4="$(make_test_home)"
echo "existing" > "$tmp4/.work/keep.md"
fakebin4="$(mock_gh_path "$tmp4")"
export GH_CALL_LOG="$tmp4/gh_calls.log"
PATH="$fakebin4:$PATH" HOME="$tmp4" bash "$SCRIPT" --init --name test-work
# gitignore was written
assert_file "$tmp4/.work/.gitignore"
grep -q '^\.active\.\*$' "$tmp4/.work/.gitignore"
grep -q '^\.meta$' "$tmp4/.work/.gitignore"
# gh repo create was invoked
grep -q "repo create test-work" "$GH_CALL_LOG"
# remote origin is set (by the mock)
git -C "$tmp4/.work" remote get-url origin >/dev/null
# content preserved
assert_file "$tmp4/.work/keep.md"
unset GH_CALL_LOG
cleanup_test_home "$tmp4"

echo "test_setup: PASS"
