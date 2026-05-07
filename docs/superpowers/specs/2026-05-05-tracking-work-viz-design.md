# tracking-work-viz: design

## Problem

`~/.work/workspaces/` already holds the truth (sessions, tasks, blockers, concurrent agents), but reading it across five workspaces and dozens of task files is overwhelming. The user wants a single UI to:

1. See status fast: which sessions exist, which tasks each session has, how each task stands.
2. Drill into a task without leaving the UI: click a task, read its full markdown body inline.
3. Optionally see relationships: blocker edges between tasks, concurrent agents on a session.

The visualization is read-only. Editing tasks stays in the existing markdown-and-skills flow.

## Approach

A small Python tool (`work-viz`) that parses one workspace and produces a browser-based viewer. Two run modes:

- **One-shot:** `work-viz <slug>` writes a self-contained `~/.work/viz/<slug>.html` with all data embedded as JSON. Open in a browser. Re-run to refresh.
- **Watch:** `work-viz <slug> --watch` runs a tiny local HTTP server on `127.0.0.1:<port>` that serves the UI, watches `~/.work/workspaces/<slug>/` for changes, and pushes updates to the open page over Server-Sent Events. The page reloads its data without losing pane state, scroll, or selection.

The viewer itself is a single HTML page with three panes:

```
+---------+----------------+----------+
| tree    | graph          | content  |
| (col.)  | (col.)         |          |
+---------+----------------+----------+
```

Both side panes are individually collapsible (caret toggles in their headers). The content pane is the always-visible anchor: clicking any node in either side pane populates it.

## Components

### Parser (Python, stdlib only)

Walks `~/.work/workspaces/<slug>/` and produces an in-memory model:

```
Workspace
  slug, has_meta
  sessions: [Session]
  archived_sessions: [Session]   # from archive/, opt-in display
  active_count_by_session: dict  # from .active.<id> files at workspace level

Session
  slug
  summary_text         # raw SUMMARY.md body
  summary_meta         # parsed YAML frontmatter (e.g. github)
  active_agent_count   # number of .active.<id> files in the session dir
  tasks: [Task]
  task_status_by_slug  # derived from SUMMARY.md section headings

Task
  slug
  body                 # raw markdown body
  inline_fields        # parsed from "**Key:** value" lines (Status, Started, PR, Ticket, Branch, Closed, Surfaced by, ...)
  blocked_by: [str]    # task slugs parsed from "Blocked by:" lines
  status               # canonical, derived from SUMMARY.md heading; falls back to inline Status
```

**Status derivation rules:**

- Walk SUMMARY.md headings. A task slug appearing under `### In Progress` is `in_progress`; under `### Open` is `open`; under `### Blocked` is `blocked`; under `### Resolved` is `resolved`.
- Match by either the linked filename (`[task-foo](tasks/task-foo.md)`) or the bare task slug appearing in the bullet text.
- If a task file isn't referenced from SUMMARY.md, fall back to parsing its `**Status:**` inline field with a coarse keyword match (`Resolved` / `Closed` keyword wins over the rest; otherwise `open`).
- If neither source resolves, status is `unknown` (rendered grey).

**Concurrent agents:** count `.active.<id>` files inside `<session>/`. The workspace-level `.active.<id>` files identify which session each agent is currently focused on; render the focused session(s) with a small "agent here" marker.

**Blocker edges:** scan task body for lines starting with `Blocked by:` followed by one or more comma-separated slugs (or markdown links to `tasks/<slug>.md`). Each yields a `task -> task` edge.

The parser is also reusable as a CLI: `work-viz <slug> --json` prints the model to stdout for debugging or piping.

### Generator (one-shot mode)

Renders `templates/index.html` with the JSON model inlined as a `<script id="data" type="application/json">` block. Output: `~/.work/viz/<slug>.html`. Self-contained, no network needed at view time. Cytoscape and the markdown renderer are vendored (downloaded once on first install) under `~/.work/viz/vendor/`.

### Server (watch mode)

`work-viz <slug> --watch` starts a server on the first free port from `8765..8775` and opens the browser. Endpoints:

- `GET /` -> the same `index.html`, but pulls data from `/data.json` instead of an inline block.
- `GET /data.json` -> current parsed model.
- `GET /events` -> Server-Sent Events stream emitting `{"type": "change"}` whenever a file under `~/.work/workspaces/<slug>/` is modified, created, or deleted.
- `GET /vendor/...` -> served from `~/.work/viz/vendor/`.

Change detection uses `os.walk` + mtime polling at a 1s interval (stdlib only, no `watchdog` dependency). On change, the server emits one SSE event after a 250ms debounce.

The page listens to SSE; on `change`, it re-fetches `/data.json` and diffs into the existing UI:

- Tree: re-renders, preserving expanded/collapsed state per session and the current selection.
- Graph: updates Cytoscape elements via `cy.json({elements: ...})`, preserving zoom, pan, and selection.
- Content: if the selected task/session still exists, re-render its body; otherwise leave the previous content with a small "(this item no longer exists)" notice.

### UI (HTML + CSS + vanilla JS)

**Layout (CSS grid):**

```
header bar:  [workspace name]  [switcher]   [hide closed] [show archive]
main row:    | tree | graph | content |
```

- Tree pane: collapsible per session. Each session row shows `<status-pill> <slug> <agent-badge?>`. Each task row shows `<status-pill> <slug>`.
- Graph pane: Cytoscape, layout = `dagre` (top-down hierarchy, falls back to `cose` if dagre layout extension is too heavy to vendor). Nodes:
  - Workspace: rectangle, top.
  - Session: rounded rectangle, status by aggregate (any in-progress -> blue, all resolved -> green/grey).
  - Task: ellipse, status by its own derived status.
  - Concurrent-agent badge as a small floating count on the session node when `> 1`.
  - Edges: solid for `session -> task`, dashed for `task -> task` blockers.
- Content pane: rendered markdown of the selected node's body. Header shows the inline fields as a small key/value strip. Anchor clicks within the body that point at sibling task files navigate inside the UI rather than the browser.

**Color palette (status pills and node fills):**

- `open` -> neutral grey
- `in_progress` -> blue
- `blocked` -> red
- `resolved` -> green, dimmed when "hide closed" is off but the user is showing them
- `unknown` -> light grey with question-mark icon

**Toggles in header:**

- "Hide closed": removes `resolved` tasks from the tree; greys them in the graph.
- "Show archive": pulls in `archive/<date>-<slug>/` sessions, rendered with an "archived" tag.
- "Tree" and "Graph" caret buttons collapse those panes.

**Workspace switcher:** dropdown showing all workspaces under `~/.work/workspaces/`. Selecting one in one-shot mode is a hint that the user should re-run; in watch mode, the server reconfigures and pushes a fresh `data.json`.

### Dashboard mode (`--workspace=all`)

Separate, simpler page at `~/.work/viz/dashboard.html` (or `/` in watch mode without a slug). One row per workspace with:

- Workspace slug
- Session count, task count
- Last-updated timestamp (max mtime across SUMMARY.md and task files)
- Number of concurrent agents (workspace-level `.active.<id>` files)
- Click-through to that workspace's viz page

No graph, no content pane. Just a dense table that answers "which projects need attention".

## File layout

The new skill follows the existing repo pattern:

```
skills/tracking-work-viz/
  SKILL.md
  viz.py                  # parser + generator + server, single file
  templates/
    index.html
    dashboard.html
  vendor/                  # populated by install.sh
    cytoscape.min.js
    dagre.min.js
    cytoscape-dagre.min.js
    marked.min.js
  README.md
```

`install.sh` (top-level repo script) is updated to:

- Symlink `viz.py` to `~/.work/bin/work-viz` (creating `~/.work/bin/` if needed and reminding the user to add it to `PATH`).
- Download vendor JS files into `skills/tracking-work-viz/vendor/` if not already present (idempotent).

The new skill's `SKILL.md` teaches Claude to invoke `work-viz <slug>` (or `--watch`) when the user asks for a visualization, an overview, or "show me what's going on".

## Testing

`skills/tracking-work-viz/tests/` contains:

- `fixtures/`: a synthetic `~/.work/`-shaped tree with two sessions, blocker links, multiple `.active.*` files, an archived session, and edge cases (task in SUMMARY but no file; task file with no SUMMARY entry).
- `test_parser.py`: parses the fixture and asserts the model shape (status derivation, blocker edges, agent counts).
- `test_generator.py`: runs one-shot mode against the fixture, asserts the resulting HTML contains the expected JSON payload and that key UI elements are present.
- `test_server.py`: spins up watch mode against a temp copy of the fixture, asserts the SSE channel emits `change` after a touched file, and that `/data.json` reflects the change.

All artifacts go to `skills/tracking-work-viz/tests/tmp/` (already covered by repo `.gitignore`).

## Out of scope (v1)

- Editing tasks from the UI.
- Cross-workspace blocker edges.
- Authentication or remote access (the server binds to `127.0.0.1` only).
- Diffing or history views; this is a snapshot of the current `~/.work/`.
- Mobile / narrow-viewport layout. Three panes assume a desktop window.

## Open questions for implementation plan

- Vendor download: bundled with the repo, or fetched on first `install.sh` run? (Leaning fetched, to keep the repo lean; falls back to inline CDN URLs if offline.)
- Markdown renderer choice: `marked` (small, fast, no syntax highlighting) vs `markdown-it` (heavier, plugin ecosystem). Leaning `marked`; can revisit.
- Whether to pre-render markdown server-side in watch mode (lower client CPU) or keep it client-side (simpler payload).
