---
status: Open
started: YYYY-MM-DD
ticket: XXX-123
ticket_url:
pr:
pr_url:
branch:
---

# <Task Title>

## Description

Short paragraph on why this task exists.

## Scope

- Work item
- Work item

## Acceptance criteria

- Observable outcome
- Observable outcome

## Notes

_Progress log, decisions, commit references, links._

## Relations

Body-line form (any order, anywhere in the body):

    Blocked by: [task-foo]
    Related to: [other-session/task-bar], task-baz
    Follows: [task-prev]

Frontmatter list form (alternative):

    ---
    blocked_by: [task-foo]
    related_to: [other-session/task-bar, task-baz]
    follows: [task-prev]
    ---

Targets accept up to two `/` separators:
- `task-foo` resolves within the same session
- `session-slug/task-foo` resolves within the same workspace
- `ws-slug/session-slug/task-foo` resolves to a fully qualified ID
