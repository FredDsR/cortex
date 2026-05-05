# tracking-work-viz

Browser-based viewer for `~/.work/workspaces/<slug>/`.

## Install

`./install.sh` from the repo root sets up the symlink and downloads vendored JS.

## Usage

    work-viz <slug>           # generate ~/.work/viz/<slug>.html
    work-viz <slug> --watch   # serve + auto-refresh
    work-viz --workspace=all  # cross-workspace dashboard
    work-viz <slug> --json    # parsed model as JSON (debug)

The viewer has three panes: tree (workspace > session > task), graph (Cytoscape with blocker edges), and content (rendered markdown). Both side panes are individually collapsible.
