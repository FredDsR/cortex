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

YAML frontmatter for structured fields, markdown body for the human view. See `templates/SUMMARY.md` for the canonical template.

```markdown
---
slug: <session-slug>
started: YYYY-MM-DD
last_updated: YYYY-MM-DD
status: Active
branch: <optional>
github: <owner>/<repo>   # optional; triggers tracking-work-github
---

# Session: ...
```

When `github:` is set, the core skill invokes `tracking-work-github` at appropriate checkpoints.

**Regenerate (full rewrite):** when the user asks "overview" / "status" / "where are we". Rebuild from task files + `git log` (if a repo) + `gh` (if `github:` is set). For a cheap snapshot without a full regen, run `scripts/manifest.sh` first.

## `tasks/<task-slug>.md`

YAML frontmatter for structured fields. See `templates/task.md`.

```markdown
---
status: Open
started: YYYY-MM-DD
ticket: XXX-123
ticket_url: https://...
pr:
pr_url:
branch:
---

# <Title>
...
```

Legacy `**Field:** value` bold-pair format is still parsed by the viz, but new files should use frontmatter. Run `scripts/migrate_to_frontmatter.py --apply` once to convert legacy files in place.

## Cross-task relations

Task files can declare typed edges to other tasks. The viz reads these and renders them as typed graph edges.

### Edge kinds

- **Blocked by**: this task cannot proceed until the target is done. Red solid edge in the graph.
- **Related to**: thematically linked, no dependency order. Gray solid edge.
- **Follows**: this task starts after the target, but is not hard-blocked. Dashed edge.
- **Mentions**: a task slug that appears in prose but was not declared as a typed relation. Dotted edge. Auto-detected; not written explicitly.

### Addressing forms

A target is one of:
- `task-slug` -- resolves within the same session.
- `session-slug/task-slug` -- resolves within the same workspace.
- `ws-slug/session-slug/task-slug` -- fully qualified, resolves across workspaces.

### Where edges may appear

Body-line form (label followed by a colon, targets separated by commas):

```
Blocked by: [task-foo], [task-bar]
Related to: session-a/task-baz
Follows: task-prev
```

Frontmatter list form (keys `blocked_by`, `related_to`, `follows` only):

```yaml
blocked_by: [task-foo, task-bar]
related_to: [session-a/task-baz]
follows: [task-prev]
```

`mentions` is auto-detected from prose slugs and cannot be declared explicitly.

### Ghost nodes

If a target does not match any known task file, the viz still renders it as a ghost node: dashed border, faded label, `resolved=False` in the data model. Ghost nodes appear for cross-workspace targets in local mode and for genuinely missing tasks.

## `.meta` (global store only)

Workspace registry record. See `slug-resolution.md` for fields.

## Archive

`archive/YYYY-MM-DD-<session-slug>/` — moved by explicit close action. Never modified after archive.

## Interaction rules (unchanged)

- SUMMARY.md is derived from task files — regenerate, don't hand-edit.
- Task files are the source of truth for task detail.
- Blockers live in SUMMARY.md only; task files show `Blocked by:` references.
- `.active.<id>` is metadata — never listed in SUMMARY.md.
