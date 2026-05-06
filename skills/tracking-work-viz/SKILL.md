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

## Read-only

This skill never edits anything under `~/.work/`. Editing tasks stays in the existing `tracking-work` flow.

For UI feature reference, screenshots, and v1 limitations, see `README.md`.

## Sync interaction

Output is written under `~/.work/viz/` by default. The `tracking-work-sync` template gitignore excludes `viz/`, so generated HTML and vendor assets are never pushed to the sync remote. If a pre-existing sync repo still tracks `viz/`, see the retrofit snippet in `tracking-work-sync/SKILL.md`.
