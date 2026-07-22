# cortex-viz

Static browser-based viewer for `~/.cortex/workspaces/`. Three panes (collapsible tree, hub-and-spoke Cytoscape graph, rendered markdown content) over a copied markdown tree. Read-only.

It surfaces the knowledge/workbench frontmatter authored by `cortex-kb` (the `cortex kb` CLI): `type`, `title`, `description`, and `updated` show up in the tree (row tooltip) and content pane. Derived `INDEX.md` files (from `cortex kb index`) are excluded from the graph.

## Install

From the repo root:

    bash install.sh

This symlinks the unified `cortex` bin to `~/.cortex/bin/cortex` (reach the viewer via `cortex viz ...`) and fetches two third-party JS files (Cytoscape, marked) into `cortex/viz/templates/vendor/`. The generator stages those into the build output at build time. Add `~/.cortex/bin` to your `PATH` if it isn't already.

## Usage

```text
cortex viz                                              # build + serve, opens browser
cortex viz build [WORKSPACES_ROOT] [--out OUT]          # static build only
cortex viz serve [OUT_DIR] [--host H] [--port P]        # serve an existing build
cortex viz serve [OUT_DIR] --no-open                    # skip browser auto-open
cortex viz serve [OUT_DIR] --edit                       # localhost in-browser editing
cortex viz serve [OUT_DIR] --edit --workspaces-root DIR # override the source root
```

`WORKSPACES_ROOT` defaults to `~/.cortex/workspaces/`. `OUT` and `OUT_DIR` default to `~/.cache/cortex/out/`.

The build is a folder you can browse via the bundled static server, via `python -m http.server`, or as a plain markdown wiki in any markdown viewer (Obsidian, etc.). Opening the HTML directly via `file://` works for navigation but the content pane's marked.js fetch requires a server.

## In-browser editing

`cortex viz serve --edit` adds a localhost-only read-write mode on top of the
static build. An **Edit** button appears on `task`, `knowledge`, `workbench`,
and session (`SUMMARY.md`) docs; it opens the raw markdown in a textarea. Save
writes the source file, rebuilds the site, and refreshes the graph, tree, and
content in place. The source root comes from the build manifest
(`.cortex-build.json`); `--workspaces-root PATH` overrides it. Typing `[[` in
the editor opens an autocomplete over task / knowledge / workbench docs and
inserts the most-abbreviated valid addressing-grammar token.

Saves are guarded by an on-disk content hash: if the file changed since you
opened it, Save is refused and the current version is reloaded so you can
reapply your edit. A successful save runs `cortex sync push` when sync is
configured. The plain `serve` and static `build`
have no write API and stay Pages-safe.

## UI panes

- **Tree** (left): the full hierarchy from `Fred's Work Tracking` down to individual tasks. Workspaces and sessions are links; tasks, knowledge docs, and workbench docs load their `.md` into the content pane on click.
- **Graph** (center): Cytoscape with a hierarchical layout (`concentric-hier` by default, with an optional force-directed `cose` mode toggled from the topbar). Containment edges (root -> workspace -> session -> task) drawn as thin gray lines. Typed relations layered on top with colour. Ghost nodes (targets that did not resolve to a doc on disk) render with a dashed border and faded label.
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
  vendor/   (cytoscape, marked, app.js, app.css)
  workspaces/<ws>/
    index.html, index.md
    knowledge/index.md
    sessions/<sess>/
      index.html, index.md, SUMMARY.md
      workbench/index.md
      tasks/index.md, <slug>.md
```

`<slug>.md` and `SUMMARY.md` are byte-for-byte copies of the source files in `~/.cortex/`. The HTML shells render whichever `.md` the user clicks via `marked.js`.

## Tests

The viz tests moved into the unified engine suite at `cortex/tests/` and run
from the repo root alongside the rest of `cortex`:

```bash
uvx --with pyyaml pytest cortex -v
```

The suite covers the address grammar, parser (typed-relation extraction, mentions, ghost generation, cross-workspace resolution, code-fence skipping, edge dedup), generator (vendor staging, markdown copy, index.md emission per scope, HTML shell + JSON blob shape, scope filtering, `build_payload` parity, build manifest), the static server, the CLI, and the edit backend + live edit server (source mapping, hash-guarded save, atomic write, rebuild, token/traversal rejection).

## Limitations

- Knowledge and workbench docs are authored via the `cortex-kb` CLI (`cortex kb`) or, for existing docs, the `serve --edit` mode. Unresolved `knowledge/*` or `workbench/*` references still render as ghost nodes until the target file exists.
- No search across the world (Spec B).
- No graph algorithm beyond the built-in hierarchical and `cose` layouts.
- No persistence of chip state in localStorage (it lives in the URL fragment, so it travels with shared URLs but is lost when typing a new URL).
- Opening `out/index.html` via `file://` works for graph + tree but the content pane needs a server because browsers block `fetch` on `file://`. Use `cortex viz serve` or `python -m http.server` from inside `out/`.
