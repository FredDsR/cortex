# The store

Everything cortex knows lives in one directory of markdown files. No database,
no server. You can read it with `cat`, edit it with any editor, and diff it in
git.

## Two stores

| Store | Path | When |
|-------|------|------|
| **Global** | `~/.cortex/workspaces/<slug>/` | The default. Tracking is not tied to any one repo |
| **Local** | `<repo>/.cortex/` | Opt-in, when you want session state committed with the code |

Both use the identical internal layout. A session lives in one or the other,
never both, and moving between them is always explicit through
`cortex-migration`.

## Layout

```
~/.cortex/
├── bin/cortex                     the CLI symlink
├── knowledge/INDEX.md             cross-workspace synthesis (the "brain")
└── workspaces/
    └── <workspace-slug>/
        ├── .meta                  workspace registry record (global store only)
        ├── .active.<session-id>   one per concurrent agent, points at a session
        ├── .inject-enabled        sentinel; present only if injection is opted in
        ├── knowledge/             workspace-scoped notes, outlive every session
        │   └── <slug>.md
        ├── sessions/
        │   └── <session-slug>/
        │       ├── SUMMARY.md
        │       ├── workbench/     session-scoped drafts
        │       └── tasks/
        │           └── <task-slug>.md
        └── archive/
            └── YYYY-MM-DD-<session-slug>/
```

**Archived sessions are never modified after archiving.** That rule is what
makes the archive trustworthy as a record of what actually happened, including
work that was abandoned rather than finished.

## `.active.<session-id>`

A one-line file naming the session an agent is working on. One per concurrent
agent or shell, which is how several agents work the same workspace without
fighting.

Each agent writes only its own `.active.<id>` and never touches another's.
Missing, or pointing at a session that no longer exists, means unset: the skill
lists sessions and asks.

## `SUMMARY.md`

YAML frontmatter for structured fields, markdown body for humans.

```markdown
---
slug: my-session
started: 2026-08-28
last_updated: 2026-08-28
status: Active
branch: main
github: owner/repo      # optional; presence is what enables cortex-github
closed: 2026-09-01      # set when the session is archived
---

# Session: ...

## Tasks
### In Progress / Open / Blocked / Resolved

## Blockers
## Notes
```

**SUMMARY.md is derived from the task files.** Regenerate it rather than
hand-editing, or the two drift. Blockers live here only; task files reference
them the other way, through `Blocked by:`.

## `tasks/<task-slug>.md`

```markdown
---
status: Open
started: 2026-08-28
ticket: PROJ-123
ticket_url: https://...
pr:
pr_url:
branch:
---

# Title
```

`status` is one of **`Open`**, **`In Progress`**, **`Blocked`**, **`Resolved`**.
That vocabulary is fixed in `cortex/model.py`. There is deliberately no
"dropped" or "won't do" status: work that gets abandoned is archived with its
tasks still Open, so the archive records what really happened instead of
claiming a completion that never occurred.

Task files are the source of truth for detail.

## Links between documents

Tasks can declare typed edges, which the viewer renders as typed graph edges:

| Kind | Meaning | Rendered as |
|------|---------|-------------|
| `blocked_by` | Cannot proceed until the target is done | Red solid |
| `related_to` | Thematically linked, no ordering | Gray solid |
| `follows` | Starts after, but not hard-blocked | Dashed |
| `mentions` | A slug appearing in prose | Dotted, auto-detected |

`mentions` cannot be declared by hand; it is inferred. The others work either as
a body line or as frontmatter:

```
Blocked by: [task-foo], [task-bar]
Related to: session-a/task-baz
```
```yaml
blocked_by: [task-foo, task-bar]
related_to: [session-a/task-baz]
```

**Addressing** widens as needed: `task-slug` resolves in the same session,
`session-slug/task-slug` within the workspace, and
`ws-slug/session-slug/task-slug` anywhere.

**Ghost nodes.** A link to something that does not exist still renders, with a
dashed border and a faded label. Unwritten notes stay visible instead of
silently vanishing, which is what makes `[[wikilinks]]` safe to write before the
target exists.

## Knowledge and workbench frontmatter

```markdown
---
title: "Close-day pointer gotchas"
type: Gotcha
author: agent
created: 2026-07-14
updated: 2026-07-14
description: "One-line summary; this is what the index and graph show."
---
```

`description` earns its keep: it is what appears in `INDEX.md` and in the
viewer, so an agent can judge relevance without opening the file.

## Legacy format

Files using the old `**Field:** value` bold-pair convention are still parsed.
`skills/cortex-tracking/scripts/migrate_to_frontmatter.py --apply` converts them
in place, once.
