#!/usr/bin/env bash
# Stage, commit with the given message, and push ~/.work/ to origin.
# No-op if sync is not enabled. Idempotent when nothing to commit.
set -euo pipefail

MSG="${1:?usage: commit_push.sh <commit-message>}"
WORK_DIR="${HOME}/.work"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Gate: no-op if not enabled.
if ! bash "$SCRIPTS_DIR/is_enabled.sh"; then
    exit 0
fi

cd "$WORK_DIR"

git add -A .

# If nothing staged, done.
if git diff --cached --quiet; then
    exit 0
fi

git commit -q -m "$MSG"

PUSH_ERR=/tmp/twsync-push.err
push() { git push -q origin HEAD 2>"$PUSH_ERR"; }

# Push. A rejection usually means the remote advanced (another device/session).
if push; then
    exit 0
fi

# Only a non-fast-forward rejection is fixable by rebasing. Auth failures,
# protected branches, and pre-receive hook rejections are not — don't rewrite
# history pointlessly; report and keep the commit local.
if ! grep -qiE 'non-fast-forward|fetch first|\[rejected\]' "$PUSH_ERR"; then
    echo "tracking-work-sync: push failed (not a fast-forward conflict); commit saved locally. See $PUSH_ERR" >&2
    exit 0
fi

# Rebase onto the advanced remote via pull.sh, then retry once. Pass
# SUMMARY_CONFLICT=surface: the SUMMARY.md we just committed is a fresh edit, so
# a conflict on it must be surfaced (exit 2), not auto-resolved to upstream.
# pull.sh exit codes: 0 = rebased cleanly, 2 = conflict to resolve by hand,
# other = unexpected. Forward any stdout it produces verbatim.
pull_out=$(SUMMARY_CONFLICT=surface bash "$SCRIPTS_DIR/pull.sh") && pull_rc=0 || pull_rc=$?
[[ -n "$pull_out" ]] && printf '%s\n' "$pull_out"

if [[ "$pull_rc" -ne 0 ]]; then
    echo "tracking-work-sync: push rejected and rebase did not complete (rc=$pull_rc); commit saved locally." >&2
    exit 0
fi

if ! push; then
    echo "tracking-work-sync: push still failing; commit saved locally. See $PUSH_ERR" >&2
    exit 0
fi

exit 0
