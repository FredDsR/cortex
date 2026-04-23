# File Layout

Exact format of files in the global and local stores, and how they interact.

## Stores

- **Global (default):** `~/.work/workspaces/<slug>/`
- **Local (opt-in):** `<repo>/.work/`

Both share the same internal layout. A session exists in one store or the other, not both. `list_sessions.sh` merges them for display.

## Per-workspace files

```
<store>/
├── .meta                     # present only in global store — workspace registry record
├── .active.<session-id>      # one per concurrent agent/shell — points at a session slug
├── sessions/
│   └── <session-slug>/
│       ├── SUMMARY.md
│       └── tasks/
│           └── <task-slug>.md
└── archive/
    └── YYYY-MM-DD-<session-slug>/
```

## `.active.<session-id>`

One line: the session slug this agent/shell is working on.

- **Read:** on session start. Sweep first, then resolve the current agent's `<session-id>`, then read `.active.<id>`.
- **Update:** on user action (pick, create, close).
- **Missing or points at nonexistent session:** treat as unset; list sessions, prompt to pick.
- **Multiple present for the same workspace:** each belongs to a different concurrent agent. Show all with their source tags.

## `SUMMARY.md`

Same shape as the previous skill. See `templates/SUMMARY.md`. Optional GitHub-sync opt-in via a frontmatter field:

```markdown
---
github: <owner>/<repo>
---

# Session: ...
```

When `github:` is set, the core skill invokes `tracking-work-github` at appropriate checkpoints.

**Regenerate (full rewrite):** when the user asks "overview" / "status" / "where are we". Rebuild from task files + `git log` (if a repo) + `gh` (if `github:` is set).

## `tasks/<task-slug>.md`

Unchanged from the previous skill. See `templates/task.md`.

## `.meta` (global store only)

Workspace registry record. See `slug-resolution.md` for fields.

## Archive

`archive/YYYY-MM-DD-<session-slug>/` — moved by explicit close action. Never modified after archive.

## Interaction rules (unchanged)

- SUMMARY.md is derived from task files — regenerate, don't hand-edit.
- Task files are the source of truth for task detail.
- Blockers live in SUMMARY.md only; task files show `Blocked by:` references.
- `.active.<id>` is metadata — never listed in SUMMARY.md.
