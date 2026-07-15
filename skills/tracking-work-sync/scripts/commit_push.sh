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

push() { git push -q origin HEAD 2>/tmp/twsync-push.err; }

# Push. A rejection usually means the remote advanced (another device/session).
if push; then
    exit 0
fi

# Rejected: rebase onto the advanced remote via pull.sh, then retry once.
# pull.sh exit codes: 0 = rebased (SUMMARY.md may be auto-resolved to upstream),
# 2 = task-file/other conflict to resolve by hand, other = unexpected. Its stdout
# can carry the "SUMMARY.md regenerate-needed" signal, so forward it verbatim.
pull_out=$(bash "$SCRIPTS_DIR/pull.sh") && pull_rc=0 || pull_rc=$?
[[ -n "$pull_out" ]] && printf '%s\n' "$pull_out"

if [[ "$pull_rc" -ne 0 ]]; then
    echo "tracking-work-sync: push rejected and rebase did not complete (rc=$pull_rc); commit saved locally." >&2
    exit 0
fi

if ! push; then
    echo "tracking-work-sync: push still failing after rebase; commit saved locally. See /tmp/twsync-push.err" >&2
    exit 0
fi

exit 0
