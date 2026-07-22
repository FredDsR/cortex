#!/usr/bin/env bash
# Update the cortex-tracking skills bundle: pull latest from origin, then re-run
# install.sh so any new skill folder, harness, or vendored asset is picked up.
#
# Usage:
#   bash update-skills.sh                # global update (default)
#   bash update-skills.sh --project [path]   # project-scoped update, forwarded to install.sh
#
# Exits non-zero if either the pull or the install step fails.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Refuse to run when there are local uncommitted changes that would block a
# fast-forward pull. The user can stash or commit and re-run.
if ! git -C "$REPO_DIR" diff --quiet || ! git -C "$REPO_DIR" diff --cached --quiet; then
    echo "error: uncommitted changes in $REPO_DIR" >&2
    git -C "$REPO_DIR" status --short >&2
    echo "  Stash or commit them, then re-run." >&2
    exit 1
fi

CURRENT_BRANCH="$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD)"
BEFORE="$(git -C "$REPO_DIR" rev-parse HEAD)"

echo "Pulling $CURRENT_BRANCH in $REPO_DIR..."
git -C "$REPO_DIR" pull --ff-only

AFTER="$(git -C "$REPO_DIR" rev-parse HEAD)"

if [ "$BEFORE" = "$AFTER" ]; then
    echo "Already up to date ($BEFORE)."
else
    echo "Updated $BEFORE -> $AFTER"
    echo ""
    echo "Changes:"
    git -C "$REPO_DIR" log --oneline "$BEFORE..$AFTER"
fi

echo ""
echo "Running install.sh..."
bash "$REPO_DIR/install.sh" "$@"

echo ""
echo "Update complete."
