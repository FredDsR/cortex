#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SELF_DIR/helpers.sh"

SCRIPT="$SCRIPTS_DIR/is_enabled.sh"

# Case 1: ~/.work is not a git repo → exit 1
tmp="$(make_test_home)"; trap "cleanup_test_home $tmp" EXIT
HOME="$tmp" assert_exit 1 bash "$SCRIPT"

# Case 2: git repo, no remote → exit 1
git -C "$tmp/.work" init -q
HOME="$tmp" assert_exit 1 bash "$SCRIPT"

# Case 3: git repo with remote → exit 0
remote="$(make_fake_remote "$tmp/remote.git")"
git -C "$tmp/.work" remote add origin "$remote"
HOME="$tmp" assert_exit 0 bash "$SCRIPT"

# Case 4: sentinel present → exit 1 even with remote
touch "$tmp/.work/.sync-disabled"
HOME="$tmp" assert_exit 1 bash "$SCRIPT"

echo "test_is_enabled: PASS"
