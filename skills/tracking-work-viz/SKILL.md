---
name: tracking-work-viz
description: Use when the user wants a visual overview of `~/.work/` sessions and tasks ("show me what's going on", "visualize my work", "open the dashboard"). Generates a browser-based tree+graph+content viewer for one workspace, or a cross-workspace dashboard. Read-only.
---

# tracking-work-viz

Generates a browser-based viewer for `~/.work/workspaces/<slug>/`.

## Invocation

The user-facing command is `work-viz`, installed by `install.sh` as `~/.work/bin/work-viz`. The user must have `~/.work/bin/` on their `PATH`.

- One-shot: `work-viz <workspace-slug>` writes `~/.work/viz/<slug>.html` and prints the path. Open in a browser to view.
- Watch: `work-viz <workspace-slug> --watch` starts a local server and opens the browser; the page auto-refreshes when files under the workspace change.
- Dashboard: `work-viz --workspace=all` writes `~/.work/viz/dashboard.html` with a row per workspace.
- JSON: `work-viz <workspace-slug> --json` prints the parsed model to stdout (debugging).

## When to invoke

Use this when the user is overwhelmed by their `~/.work/` content and asks for a visual overview, status snapshot, or dashboard. Always offer the watch mode if the user expects to keep the viewer open while they work.

## Read-only

This skill never edits anything under `~/.work/`. Editing tasks stays in the existing `tracking-work` flow.
