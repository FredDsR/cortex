---
name: tracking-work-viz
description: Use when the user wants a visual overview of `~/.work/` sessions and tasks ("show me what's going on", "visualize my work", "open the dashboard"). Builds a static HTML site with three panes (tree, hub-and-spoke graph, rendered markdown) for browsing every workspace, session, and task. Read-only by default; opt-in `serve --edit` adds localhost in-browser editing.
---

# tracking-work-viz

Static browser-based viewer for `~/.work/workspaces/`. The CLI builds a folder of HTML + copied markdown and serves it locally over plain HTTP. The static build is read-only; an opt-in `serve --edit` mode adds localhost-only in-browser editing.

## Invocation

The user-facing command is `cortex viz` (the unified `cortex` bin, which `install.sh` symlinks to `~/.work/bin/cortex` and routes to this skill's `work-viz` script). The user must have `~/.work/bin/` on their `PATH` (or invoke via the absolute path).

| Command | What happens |
|---|---|
| `cortex viz` | Default: builds into `~/.cache/work-viz/out/` and serves it on a random local port, opens the browser. |
| `cortex viz build [WORKSPACES_ROOT] [--out OUT]` | Parses `WORKSPACES_ROOT` (default `~/.work/workspaces/`) and writes the static site into `OUT` (default `~/.cache/work-viz/out/`). |
| `cortex viz serve [OUT_DIR] [--host H] [--port P] [--no-open]` | Serves an existing built directory. No build, no watch. |
| `cortex viz serve [OUT_DIR] --edit [--workspaces-root PATH]` | Same, plus localhost-only in-browser editing. See "In-browser editing" below. |

The default action (no subcommand) is `build` then `serve` in sequence, intended to be a one-line "open the dashboard" command.

## When to invoke

Heuristics:

- "show me what's going on" / "where are we" / "visualize my work" -> run `cortex viz` (default).
- "open the dashboard" -> `cortex viz`.
- "rebuild after I edited some tasks" -> `cortex viz build` (then refresh the existing browser tab if a server is already running).
- "I want a snapshot folder I can share" -> `cortex viz build --out /path/to/share`.

The viewer's sidebar tree spans every workspace and session, so once a page is open the user navigates by clicking nodes; no per-workspace invocation is needed.

## Output layout

```
<out>/
  index.html, index.md                    # root dashboard
  vendor/                                 # cytoscape, marked, app.js, app.css
  workspaces/<ws>/index.html, index.md
  workspaces/<ws>/knowledge/index.md
  workspaces/<ws>/sessions/<sess>/index.html, index.md
  workspaces/<ws>/sessions/<sess>/SUMMARY.md           # copied from ~/.work/
  workspaces/<ws>/sessions/<sess>/tasks/<slug>.md      # copied from ~/.work/
  workspaces/<ws>/sessions/<sess>/workbench/index.md
```

The `index.md` files at every scope are auto-generated and OpenKB-style, so the folder is also navigable as a plain markdown wiki in Obsidian or any markdown editor.

## Read-only by default

The static `build` output and plain `cortex viz serve` never edit anything under
`~/.work/`. This keeps a shared or published build (e.g. GitHub Pages) safe.

## In-browser editing (`serve --edit`)

`cortex viz serve --edit` turns the local viewer into a read-write surface. It is
localhost-only and never part of a static build.

- Editable doc kinds: `task`, `knowledge`, `workbench`, and a session's
  `SUMMARY.md`. Generated index pages are not editable.
- An **Edit** button appears on those docs; it opens the raw markdown in a
  textarea. **Save** writes the source file, rebuilds the site, and refreshes
  the graph, tree, and content in place. New `[[...]]` links resolve from ghost
  to solid on save.
- Typing `[[` in the editor opens an autocomplete over every task / knowledge /
  workbench doc and inserts the most-abbreviated valid addressing-grammar token
  (bare slug for the same session, `session/slug` cross-session, and so on).
- The source root is read from the build manifest (`.work-viz-build.json`);
  pass `--workspaces-root PATH` to override it.
- Optimistic concurrency: if the file changed on disk since you opened it (sync
  pull, `cortex kb`, or an external editor), Save is refused and the browser
  reloads the current version so you can reapply your edit.
- A successful save runs `tracking-work-sync`'s `commit_push.sh` when sync is
  configured (no-op otherwise), mirroring `cortex kb`.

## Sync interaction

The build output lives at `~/.cache/work-viz/out/` by default, which is outside the synced tree. No interaction with `tracking-work-sync`.

For UI feature reference, the addressing grammar, and the typed-relation chips, see `README.md`.
