# Cross-session/workspace task graph: design spec

> Re-derived 2026-05-07 from the nine `tasks/*.md` files under
> `~/.work/workspaces/FredDsR-tracking-work-skills/sessions/task-graph/`
> after the original spec was lost. The task files remain the source of
> truth for per-step Scope and Acceptance criteria; this document captures
> only the cross-cutting design decisions.

## Problem

`tracking-work-viz` today renders one Cytoscape edge kind: `Blocked by`,
parsed by `_parse_blocked_by` over the task body. That is enough to draw
critical-path arrows inside a single session, but the parser drops every
other relationship the user actually writes in tasks: "Related to",
"Follows", and the very common case of one task casually mentioning
another by slug. It also has no notion of edges that cross session or
workspace boundaries, so there is no way to see how, for example, a
follow-up session in one workspace continues from a session in another.

We want the graph pane to reflect the full relationship structure that
users already encode in their task files, with cross-workspace resolution
and a clear visual distinction per relation kind.

## Scope of this change

In scope:

1. Four edge kinds: `Blocked by`, `Related to`, `Follows`, `Mentions`.
2. A multi-workspace `World` model that resolves edges across workspace
   and session boundaries.
3. A `Local` / `Global` mode toggle in the viz, plus per-kind chip
   toggles.
4. Ghost nodes for edge targets that cannot be resolved.
5. Documentation updates so users know the syntax.

Out of scope:

- Editing task files from the viz. Read-only stays read-only.
- Graph algorithms beyond the existing dagre layout.
- Persistence of toggle state across reloads.
- Bidirectional auto-creation (an edge `A blocked by B` does not also
  emit `B blocks A`; only the source-side edge is stored).

## Edge kinds

| Kind        | Source    | Default visibility | Style                       |
|-------------|-----------|--------------------|-----------------------------|
| `blocked`   | typed     | on                 | red solid                   |
| `related`   | typed     | on                 | gray solid                  |
| `follows`   | typed     | on                 | dashed                      |
| `mentions`  | inferred  | off                | dotted                      |

Typed relations are explicit lines or frontmatter list keys. Mentions are
inferred from any `[task-slug]` link or bare `task-<slug>` reference that
is not part of a typed-relation line and not inside a fenced code block.
Mentions are off by default because they are noisier and the user has not
explicitly endorsed them.

### Syntax

Body line form:

```markdown
Blocked by: [task-foo], [task-bar]
Related to: task-baz
Follows: [other-session/task-old]
```

Frontmatter list form:

```yaml
---
status: Open
blocked_by: [task-foo, task-bar]
related_to: [task-baz]
follows: [other-session/task-old]
---
```

Frontmatter and body lines are unioned, deduped per `(kind, target)`,
and source-order preserved.

`_parse_blocked_by` survives as a back-compat shim that reads the new
typed-relations result and filters to `kind == "blocked"`. Existing
callers do not change.

## Addressing scheme

Targets are raw strings at parse time. Resolution to a canonical
`<ws>/<sess>/<task>` ID happens in `parse_world`, by counting `/`s in
the raw token:

| Slashes | Interpretation                            | Example                          |
|---------|-------------------------------------------|----------------------------------|
| 0       | local session: `<src-ws>/<src-sess>/<x>`  | `task-foo`                       |
| 1       | cross-session: `<src-ws>/<x>`             | `viz-followups/task-bar`         |
| 2       | fully qualified                           | `other-ws/sister/task-pinned`    |

Any unresolvable raw target becomes a `World.ghosts` entry. The
`Edge.resolved` flag stays `False` until resolution succeeds. Ghost
edges still render but the target node is drawn as a ghost (dashed
border, faded label).

## World model

```
World
  workspaces: list[Workspace]
  edges:      list[Edge]   # resolved canonical edges
  ghosts:     list[str]    # unresolved raw or partially-resolved IDs

Edge
  source: str   # canonical ID, always resolved
  target: str   # canonical ID if resolved=True, raw token otherwise
  kind:   str   # "blocked" | "related" | "follows" | "mentions"
  resolved: bool

Task (extended)
  edges_out: list[Edge]    # populated during _parse_session
```

`parse_world(workspaces_root)` walks every workspace under the root,
builds an index keyed by canonical ID, then walks each task's raw
`edges_out` and rewrites in place to the resolved form. A second
fixture workspace `other` exists only to exercise cross-WS resolution
in tests.

## Generator data shape

The HTML emitter inlines a single JSON payload per page:

```jsonc
{
  "modes": {
    "local":  { "nodes": [...], "edges": [...] },
    "global": { "nodes": [...], "edges": [...] }
  },
  "ghosts": [...],
  "default_mode": "local"
}
```

- Local mode includes only nodes inside the current workspace plus
  ghost nodes for any out-of-workspace targets.
- Global mode for a workspace page additionally includes 1-hop
  neighbors in other workspaces. The dashboard's global mode includes
  every workspace.
- Each edge entry carries `kind` and `resolved`. Each node carries
  `ws`, `session`, `status`, and `ghost`.

The frontend reads `default_mode`, then flips between `modes.local` and
`modes.global` on click of the `Global` chip via `renderMode(cy, mode)`,
which swaps the elements and re-runs the dagre layout.

## Frontend chips

Five chips in the topbar: `Blocked by`, `Related to`, `Follows`,
`Mentions`, `Global`.

- `Blocked by`, `Related to`, `Follows` start with class `chip on`.
- `Mentions` and `Global` start with class `chip` (off).
- `bindChips(cy, cy_data)` wires click handlers; the kind chips call
  `syncEdgeVisibility(cy)`, the `Global` chip calls `renderMode`.
- Per-kind color shift on the `.chip.on` state matches the edge color.

## Failure modes and fallbacks

- Targets with three or more `/`s are treated as ghosts. We do not
  invent a deeper hierarchy.
- Self-references are dropped during mention scanning.
- Code-fenced blocks are skipped when scanning for mentions.
- Frontmatter typed-relation keys with non-list values are tolerated by
  treating a single string as a one-element list.

## Acceptance signal

The feature is "done" when:

1. The fixture workspace pair (`demo`, `other`) renders the cross-WS
   edge in global mode and shows it as a ghost in local mode of either
   side.
2. All four edge kinds toggle independently.
3. A real run against `~/.work/` does not crash on any existing
   workspace's tasks (mentions detection is the most likely regression
   path).
