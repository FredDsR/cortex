---
name: tracking-work-viz
description: Use when the user wants a visual overview of `~/.work/` sessions and tasks ("show me what's going on", "visualize my work", "open the dashboard"). Generates a browser-based tree+graph+content viewer for one workspace, or a cross-workspace dashboard with hot reload. Read-only.
---

# tracking-work-viz

Browser-based viewer for `~/.work/workspaces/<slug>/`. Three panes (tree, Cytoscape graph, rendered markdown) plus a cross-workspace dashboard. Read-only against the user's tracking data.

## Invocation

The user-facing command is `work-viz`, installed by `install.sh` as a symlink at `~/.work/bin/work-viz`. The user must have `~/.work/bin/` on their `PATH` (or invoke via the absolute path).

| Mode | Command | What happens |
|---|---|---|
| One-shot HTML | `work-viz <slug>` | Writes `~/.work/viz/<slug>.html` and prints the path. Open in a browser. |
| Per-workspace watch | `work-viz <slug> --watch` | Local 127.0.0.1 server with SSE hot reload. Page refreshes when files under the workspace change. |
| Dashboard one-shot | `work-viz --workspace=all` | Writes `dashboard.html` plus a per-workspace HTML for every workspace. |
| Dashboard server | `work-viz serve` | Static-files server fronting `~/.work/viz/` over HTTP, regenerating on every page request. SSE hot reload watches all workspaces. Bypasses snap-Firefox `file://` restrictions. |
| JSON | `work-viz <slug> --json` | Prints the parsed model to stdout (debugging). |

Common flags:

- `--workspaces-root <path>` overrides `~/.work/workspaces` (used by tests and CI).
- `--out-dir <path>` overrides `~/.work/viz` for generated HTML; vendor JS/CSS must already exist in `<out-dir>/vendor/`.
- `--port <N>` for `--watch` (default range 8765-8775) or `serve` (default range 8800-8810).
- `--no-open` skips the browser auto-open in server modes.

## When to invoke

Use this when the user is overwhelmed by their `~/.work/` content and asks for a visual overview, status snapshot, or dashboard. Heuristics:

- "show me what's going on" / "where are we" / "visualize my work" -> default to `serve` so they get a live dashboard.
- "open the dashboard" -> `serve` (interactive) or `--workspace=all` (one-shot).
- "let me see workspace X" -> `work-viz X --watch` if they expect to keep editing.
- One-off snapshot for sharing -> `work-viz <slug>` and hand them the HTML path.

The viewer has a workspace-switcher dropdown in the topbar, so once a workspace page is open the user can navigate to siblings without restarting `work-viz`.

## UI features (worth knowing for support questions)

- Tree pane: workspace -> session -> task with status pills, agent badges, ellipsis-truncated long names.
- Graph pane: Cytoscape with dagre LR layout. Status-colored nodes, dashed red blocker edges. Auto-fits to the pane on resize and pane toggle.
- Content pane: kicker + title + status pill header, key/value field grid, rendered markdown body. Intra-task links navigate inside the UI.
- Topbar toggles: Hide tree / Hide graph / Hide closed / Show archive. Each pane collapses cleanly via CSS Grid areas (no orphaned columns).
- Search: filter sessions and tasks by substring against slugs. Tree and graph both update live.
- Idle-workspace collapse on the dashboard: workspaces with no in-progress / blocked / open work AND >7 days since last edit AND no active agents fold under a "N idle workspaces" expander.
- Hot reload: in `--watch` and `serve`, an injected SSE listener does `location.reload()` (serve) or hot-swap (watch) when files under the workspace tree change.

## Read-only

This skill never edits anything under `~/.work/`. Editing tasks stays in the existing `tracking-work` flow.

## Security posture

- Servers bind to `127.0.0.1` only.
- `/vendor/<rel>` route resolves and `.relative_to(base)` checks every request, blocking path traversal.
- JSON inlined into `<script>` blocks is escaped (`</` -> `<\/`, U+2028 / U+2029 -> JSON escapes) so a task body containing `</script>` cannot break out and inject HTML.
- `/data.json` and the dashboard generator handle per-workspace failures gracefully (clean error responses, placeholder dashboard rows) instead of aborting.

## v1 limitations

- The "focused session" indicator (highlighting which session each agent currently has selected, derived from workspace-level `.active.<id>` files) is not rendered in the UI. Per-session agent badges show count, not which agent is focused.
- Hot reload in `serve` mode does `location.reload()` rather than hot-swap; per-workspace `--watch` mode preserves selection and zoom across reloads.

## Publishing to GitHub Pages

`--out-dir` makes Pages workflows easy: `work-viz --workspace=all --out-dir _site` stages HTML + vendor in a build directory ready for `actions/upload-pages-artifact`. The published Pages site is a static snapshot; hot reload works only on the local `serve` mode.
