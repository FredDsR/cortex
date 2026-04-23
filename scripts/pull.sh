#!/usr/bin/env bash
# Pull --rebase ~/.work/. Auto-resolve SUMMARY.md conflicts; surface task-file conflicts.
# Exit 0 clean or SUMMARY-resolved. Exit 2 for task-file conflict. Other non-zero for unexpected.
set -euo pipefail

WORK_DIR="${HOME}/.work"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Gate.
if ! bash "$SCRIPTS_DIR/is_enabled.sh"; then
    exit 0
fi

cd "$WORK_DIR"

# Fetch first so we can inspect.
if ! git fetch -q origin 2>/tmp/twsync-fetch.err; then
    echo "tracking-work-sync: fetch failed; continuing offline" >&2
    exit 0
fi

# Attempt rebase pull.
if git pull -q --rebase origin HEAD 2>/tmp/twsync-pull.err; then
    exit 0
fi

# Rebase had conflicts. Inspect them.
conflicts=$(git diff --name-only --diff-filter=U || true)

if [[ -z "$conflicts" ]]; then
    # Unexpected — rebase failed but no conflicted files. Abort and bail.
    git rebase --abort >/dev/null 2>&1 || true
    echo "tracking-work-sync: pull failed (no conflicts reported)" >&2
    cat /tmp/twsync-pull.err >&2 || true
    exit 1
fi

# Classify: task files, SUMMARY.md, other.
task_conflicts=$(echo "$conflicts" | grep -E '(^|/)tasks/[^/]+\.md$' || true)
summary_conflicts=$(echo "$conflicts" | grep -E '(^|/)SUMMARY\.md$' || true)
other_conflicts=$(echo "$conflicts" | grep -vE '(^|/)(tasks/[^/]+\.md|SUMMARY\.md)$' || true)

if [[ -n "$task_conflicts" || -n "$other_conflicts" ]]; then
    # Surface and abort.
    git rebase --abort >/dev/null 2>&1 || true
    echo "tracking-work-sync: conflict in tracked file(s):" >&2
    echo "$conflicts" | sed 's/^/  - /' >&2
    echo "Resolve manually in $WORK_DIR and re-run the skill." >&2
    exit 2
fi

# Only SUMMARY.md conflicts remain — auto-resolve by taking the upstream side.
# During `git rebase`, "ours" = upstream being rebased onto; "theirs" = local commits.
# We want upstream, so --ours.
while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    git checkout --ours -- "$path"
    git add -- "$path"
done <<< "$summary_conflicts"

# Continue the rebase. If more conflicts appear (shouldn't for SUMMARY-only), surface them.
export GIT_EDITOR=true
if ! git rebase --continue >/tmp/twsync-continue.err 2>&1; then
    git rebase --abort >/dev/null 2>&1 || true
    echo "tracking-work-sync: unexpected conflict after SUMMARY auto-resolve" >&2
    cat /tmp/twsync-continue.err >&2 || true
    exit 2
fi

echo "tracking-work-sync: SUMMARY.md regenerate-needed"
exit 0
