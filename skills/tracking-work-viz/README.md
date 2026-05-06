# tracking-work-viz

Browser-based viewer for `~/.work/workspaces/<slug>/`. Three panes: tree (workspace > session > task), Cytoscape graph (with blocker edges and status colors), rendered markdown content. Plus a cross-workspace dashboard with status proportion bars and aggregate counts.

## Install

From the repo root:

    bash install.sh

This symlinks `bin/work-viz` to `~/.work/bin/work-viz` and downloads four vendor JS files (Cytoscape, dagre, cytoscape-dagre, marked) into `vendor/`, then copies them plus first-party `app.js` / `app.css` to `~/.work/viz/vendor/`. Add `~/.work/bin` to your `PATH` if it isn't already.

## Usage

```text
work-viz <slug>                    # generate ~/.work/viz/<slug>.html (one-shot)
work-viz <slug> --watch            # per-workspace server with SSE hot reload
work-viz --workspace=all           # one-shot dashboard + per-workspace pages
work-viz serve                     # dashboard server with SSE hot reload
work-viz <slug> --json             # parsed model as JSON (debugging)

work-viz <slug> --out-dir _site    # write HTML somewhere other than ~/.work/viz
work-viz <slug> --watch --port 8765 --no-open
```

Both side panes are individually collapsible via the topbar. The topbar also has a workspace switcher dropdown, a search input, and filters for "Hide closed" and "Show archive".

## UI panes

- **Tree** pane: workspace > session > task, with status pills, per-session agent badges, and ellipsis-truncated long names.
- **Graph** pane: Cytoscape with dagre LR layout. Status-colored nodes, dashed red blocker edges. Auto-fits on resize and pane toggle.
- **Content** pane: kicker + title + status pill header, key/value field grid, rendered markdown body. Intra-task links navigate inside the UI.
- **Search**: substring filter against session and task slugs; tree and graph both update live.
- **Idle workspaces** on the dashboard: workspaces with no in-progress / blocked / open work, no active agents, and >7 days since last edit fold under an "N idle workspaces" expander.
- **Hot reload**: in `--watch` and `serve`, an injected SSE listener does `location.reload()` (serve) or hot-swap (watch) when files under the workspace tree change.

## Publishing to GitHub Pages

`--out-dir` is intended for Pages workflows: `work-viz --workspace=all --out-dir _site` stages HTML + vendor in a build directory ready for `actions/upload-pages-artifact`. The published Pages site is a static snapshot; hot reload works only on the local `serve` mode.

## When to use which mode

- `<slug>` (one-shot): you want an HTML file you can email or open later.
- `<slug> --watch`: you're actively editing one workspace and want the viewer to stay in sync.
- `--workspace=all`: snapshot of every workspace plus a dashboard, all static files.
- `serve`: you want the dashboard open and the page to update automatically when ANY workspace changes. Also the right answer if your browser is snap-confined and can't read `file://` paths under `~/.work/`.

## Output layout

```
~/.work/viz/
├── dashboard.html            # cross-workspace overview (--workspace=all or serve)
├── <workspace-slug>.html     # one per workspace
└── vendor/                   # cytoscape, dagre, marked, app.js, app.css
```

`--out-dir <path>` overrides `~/.work/viz` for the generated HTML. Vendor assets must already exist under `<out-dir>/vendor/` (used by GitHub Actions workflows that stage Pages artifacts).

## Tests

```bash
cd skills/tracking-work-viz
uv run --with pytest python -m pytest -v
```

23 tests covering the parser, generator, CLI, watch-mode SSE, dashboard server, hot-reload script injection, path-traversal protection, and the script-tag JSON injection escape.

## Security

- Both servers bind to `127.0.0.1` only.
- The `/vendor/<rel>` route validates resolved paths against the vendor base directory; `..` traversal returns 404.
- Inlined JSON escapes `</` and the JS-illegal U+2028 / U+2029 characters, so workspace data containing `</script>` cannot break out of inline `<script>` blocks.
- `/data.json` returns clean JSON error responses on parse failure rather than torn TCP connections.
- `_summarize` isolates per-workspace failures so one corrupt workspace never aborts the whole dashboard.

## Limitations

- Watch mode hot-swaps data without a full page reload (preserves zoom/pan/selection); serve mode does `location.reload()` (simpler, drops UI state).
- The workspace-level "focused session" marker (which session a given agent currently has selected) is not surfaced in the UI; only per-session agent counts appear.
- Polling-based watcher does an `os.walk()` per second; fine for thousands of files, may be worth replacing with a fingerprint or `inotify` for tens-of-thousands.
