---
name: tracking-work-viz
description: Use when the user wants a visual overview of `~/.work/` sessions and tasks ("show me what's going on", "visualize my work", "open the dashboard"). Builds a static HTML site with three panes (tree, hub-and-spoke graph, rendered markdown) for browsing every workspace, session, and task. Read-only.
---

# tracking-work-viz

Static browser-based viewer for `~/.work/workspaces/`. The CLI builds a folder of HTML + copied markdown and serves it locally over plain HTTP. No hot reload, no SSE, no server-side regeneration.

## Invocation

The user-facing command is `work-viz`, symlinked by `install.sh` to `~/.work/bin/work-viz`. The user must have `~/.work/bin/` on their `PATH` (or invoke via the absolute path).

| Command | What happens |
|---|---|
| `work-viz` | Default: builds into `~/.cache/work-viz/out/` and serves it on a random local port, opens the browser. |
| `work-viz build [WORKSPACES_ROOT] [--out OUT]` | Parses `WORKSPACES_ROOT` (default `~/.work/workspaces/`) and writes the static site into `OUT` (default `~/.cache/work-viz/out/`). |
| `work-viz serve [OUT_DIR] [--host H] [--port P] [--no-open]` | Serves an existing built directory. No build, no watch. |

The default action (no subcommand) is `build` then `serve` in sequence, intended to be a one-line "open the dashboard" command.

## When to invoke

Heuristics:

- "show me what's going on" / "where are we" / "visualize my work" -> run `work-viz` (default).
- "open the dashboard" -> `work-viz`.
- "rebuild after I edited some tasks" -> `work-viz build` (then refresh the existing browser tab if a server is already running).
- "I want a snapshot folder I can share" -> `work-viz build --out /path/to/share`.

The viewer's sidebar tree spans every workspace and session, so once a page is open the user navigates by clicking nodes; no per-workspace invocation is needed.

## Output layout

```
<out>/
  index.html, index.md                    # root dashboard
  vendor/                                 # cytoscape, dagre, cytoscape-dagre, marked, app.js, app.css
  workspaces/<ws>/index.html, index.md
  workspaces/<ws>/knowledge/index.md
  workspaces/<ws>/sessions/<sess>/index.html, index.md
  workspaces/<ws>/sessions/<sess>/SUMMARY.md           # copied from ~/.work/
  workspaces/<ws>/sessions/<sess>/tasks/<slug>.md      # copied from ~/.work/
  workspaces/<ws>/sessions/<sess>/workbench/index.md
```

The `index.md` files at every scope are auto-generated and OpenKB-style, so the folder is also navigable as a plain markdown wiki in Obsidian or any markdown editor.

## Read-only

This skill never edits anything under `~/.work/`. Editing tasks stays in the `tracking-work` flow.

## Sync interaction

The build output lives at `~/.cache/work-viz/out/` by default, which is outside the synced tree. No interaction with `tracking-work-sync`.

For UI feature reference, the addressing grammar, and the typed-relation chips, see `README.md`.
