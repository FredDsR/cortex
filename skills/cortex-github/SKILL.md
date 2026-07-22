---
name: cortex-github
description: Use only when invoked by cortex-tracking for a session that has a `github: <owner>/<repo>` frontmatter field. Syncs task files with PR state via the `gh` CLI.
---

# Tracking Work — GitHub Sync

Invoked by the core `cortex-tracking` skill when a session is marked as GitHub-backed. Never load standalone.

## When to Sync

- Session start (for GitHub-backed sessions only)
- User asks "overview" / "status" / "where are we"
- User explicitly asks to reconcile with GitHub

## `gh` recipes

```bash
# Per-PR detail used by drift detection.
gh pr view <num> --json number,state,title,mergedAt,closedAt

# Find a PR by ticket id when the task has no PR field yet.
gh pr list --state all --search "<ticket-id>"
```

## Drift Detection

1. For each task file with a PR reference, call `gh pr view <num> --json number,state,title,mergedAt,closedAt` and compare.
2. Surface mismatches rather than silently rewriting:
   - PR merged but task not Resolved → ask "Mark task-X Resolved? (y/n)"
   - PR closed unmerged but task still In Progress → ask "What's the new status?"
   - PR state consistent → no action
3. After user confirms each change, update SUMMARY.md + task files in a single pass.

## Finding PRs for Tasks Without a PR Field

If a task has a ticket ID but no PR link yet:

```bash
gh pr list --state all --search "<ticket-id>"
```

Match results against the task and propose adding the PR link (with confirmation).

## What Not to Do

- Don't write PR state into tracking files without user confirmation when there's a conflict.
- Don't call `gh` on every checkpoint — batch queries at session start and on explicit overview requests.
- Don't update a task's Status automatically on PR `closed` (unmerged) — that state is ambiguous (abandoned vs. superseded vs. reopening planned).

