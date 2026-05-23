# tracking-work-viz

Static browser-based viewer for `~/.work/workspaces/`. Three panes (collapsible tree, hub-and-spoke Cytoscape graph, rendered markdown content) over a copied markdown tree. Read-only.

## Install

From the repo root:

    bash install.sh

This symlinks `bin/work-viz` to `~/.work/bin/work-viz` and fetches four third-party JS files (Cytoscape, dagre, cytoscape-dagre, marked) into `skills/tracking-work-viz/templates/vendor/`. The generator stages those into the build output at build time. Add `~/.work/bin` to your `PATH` if it isn't already.

## Usage

```text
work-viz                                              # build + serve, opens browser
work-viz build [WORKSPACES_ROOT] [--out OUT]          # static build only
work-viz serve [OUT_DIR] [--host H] [--port P]        # serve an existing build
work-viz serve [OUT_DIR] --no-open                    # skip browser auto-open
```

`WORKSPACES_ROOT` defaults to `~/.work/workspaces/`. `OUT` and `OUT_DIR` default to `~/.cache/work-viz/out/`.

The build is a folder you can browse via the bundled static server, via `python -m http.server`, or as a plain markdown wiki in any markdown viewer (Obsidian, etc.). Opening the HTML directly via `file://` works for navigation but the content pane's marked.js fetch requires a server.

## UI panes

- **Tree** (left): the full hierarchy from `Fred's Work Tracking` down to individual tasks. Workspaces and sessions are links; tasks, knowledge docs, and workbench docs load their `.md` into the content pane on click.
- **Graph** (center): Cytoscape with dagre LR layout. Containment edges (root -> workspace -> session -> task) drawn as thin gray lines. Typed relations layered on top with colour. Ghost nodes (targets that did not resolve to a doc on disk) render with a dashed border and faded label.
- **Content** (right): the .md content of whichever doc is selected, rendered via `marked.js`.

## Typed edge kinds

Four authored relation kinds plus auto-generated containment. Footer chips toggle visibility per kind; state is persisted in the URL fragment so reloads keep the same view.

| Kind        | Default | Colour     | Stroke      | Source        |
|-------------|---------|------------|-------------|---------------|
| `blocked`   | on      | red        | solid       | typed         |
| `related`   | on      | mid-gray   | solid       | typed         |
| `follows`   | on      | dark-gray  | dashed      | typed         |
| `mentions`  | off     | light-blue | dotted      | inferred      |
| `contains`  | on      | thin gray  | thin solid  | auto (always) |

## Addressing grammar

Authored references in task / knowledge / workbench body or frontmatter resolve against the referencing doc's location:

```
task-foo                            -> local task, current session
knowledge/note                      -> knowledge doc in current workspace
workbench/draft                     -> workbench doc in current session
other-sess/task-bar                 -> task in sibling session, same workspace
other-sess/workbench/draft          -> workbench in sibling session
other-ws/knowledge/note             -> knowledge in another workspace
other-ws/other-sess/task-baz        -> task across both boundaries
other-ws/other-sess/workbench/foo   -> workbench across both boundaries
```

`knowledge` and `workbench` are reserved keywords. They cannot be used as workspace or session slugs. A target whose canonical id parses cleanly but has no on-disk file becomes a ghost node. A target that fails the grammar entirely is preserved on the source node but does not render as an edge.

## Output folder

```
<out>/
  index.html, index.md
  vendor/   (cytoscape, dagre, cytoscape-dagre, marked, app.js, app.css)
  workspaces/<ws>/
    index.html, index.md
    knowledge/index.md
    sessions/<sess>/
      index.html, index.md, SUMMARY.md
      workbench/index.md
      tasks/index.md, <slug>.md
```

`<slug>.md` and `SUMMARY.md` are byte-for-byte copies of the source files in `~/.work/`. The HTML shells render whichever `.md` the user clicks via `marked.js`.

## Tests

```bash
cd skills/tracking-work-viz
uvx --with pyyaml pytest -v
```

The suite covers the address grammar, parser (typed-relation extraction, mentions, ghost generation, cross-workspace resolution, code-fence skipping, edge dedup), generator (vendor staging, markdown copy, index.md emission per scope, HTML shell + JSON blob shape, scope filtering), the static server, and the CLI.

## Limitations

- Knowledge and workbench folders are first-class node kinds, but Spec A does not yet emit content into them. References to `knowledge/*` or `workbench/*` render as ghost nodes. Spec B fills in the read/write path.
- No search across the world (Spec B).
- No graph algorithm beyond dagre LR layout.
- No persistence of chip state in localStorage (it lives in the URL fragment, so it travels with shared URLs but is lost when typing a new URL).
- Opening `out/index.html` via `file://` works for graph + tree but the content pane needs a server because browsers block `fetch` on `file://`. Use `work-viz serve` or `python -m http.server` from inside `out/`.
