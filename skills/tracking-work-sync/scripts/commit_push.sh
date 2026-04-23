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

# Push; don't crash on transient failure — commit is safe locally.
if ! git push -q origin HEAD 2>/tmp/twsync-push.err; then
    echo "tracking-work-sync: push failed; commit saved locally. See /tmp/twsync-push.err" >&2
    exit 0
fi

exit 0
