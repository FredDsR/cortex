# Cross-session/workspace task graph: implementation plan

> Re-derived 2026-05-07 from the nine `tasks/*.md` files under
> `~/.work/workspaces/FredDsR-tracking-work-skills/sessions/task-graph/`
> after the original plan was lost. Each task file's `plan_step` field
> indexes into the numbered steps below. The task files contain the
> per-step Scope and Acceptance criteria; this plan covers ordering,
> dependencies, and which files each step touches.
>
> **For agentic workers:** REQUIRED SUB-SKILL.
> Use `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to execute task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `tracking-work-viz` so the Cytoscape graph shows typed
relations (`Blocked by`, `Related to`, `Follows`, `Mentions`) across
sessions and workspaces, with per-relation toggle chips and a Local /
Global scope toggle.

**Reference spec:** `docs/superpowers/specs/2026-05-06-task-graph-design.md`

**Tech stack:** Python 3.11+ stdlib only. HTML / CSS / vanilla JS in
`templates/` and `templates/vendor/`. pytest for tests.

---

## Dependency graph

```
1 edge-world-model
   |
   +-- 2 typed-relations-parser ---+
   |                               |
   +-- 3 mentions-detector --------+--> 4 edges-out-wiring
                                            |
                                            v
                                       5 parse-world
                                            |
                                            v
                                       6 generator-edge-data
                                            |
                                +-----------+-----------+
                                v                       v
                         7 cli-server-               8 frontend-chips-
                           parse-world                 toggle

9 graph-docs (parallel, no code dependencies)
```

---

## Step 1: Edge / World data model

- [ ] Add `EDGE_KINDS = ("blocked", "related", "follows", "mentions")`,
      `Edge` dataclass, and `World` dataclass to
      `skills/tracking-work-viz/work_viz/model.py`.
- [ ] Add `edges_out: list = field(default_factory=list)` to `Task`.
- [ ] New `tests/test_model.py` covering defaults.

Task file: `task-edge-world-model.md`. Pure additive, no behavior change.

## Step 2: Typed-relations parser

- [ ] Generalise `_parse_blocked_by` into
      `_parse_typed_relations(body, frontmatter)` returning
      `[(kind, raw_target), ...]`.
- [ ] Cover body-line form for `Blocked by`, `Related to`, `Follows`,
      and frontmatter list keys `blocked_by`, `related_to`, `follows`.
- [ ] Accept `[bracketed]`, bare slugs, and up to two `/` separators.
- [ ] Keep `_parse_blocked_by` as a thin shim.
- [ ] Tests in `tests/test_parser.py`.

Task file: `task-typed-relations-parser.md`. Depends on Step 1.

## Step 3: Mentions detector

- [ ] `_strip_code_fences(body)` helper.
- [ ] `_LINK_NESTED_RE`, `_TYPED_REL_LINE_RE`.
- [ ] `_parse_mentions(body, typed_targets, source_slug)` walking lines,
      skipping typed-relation lines, deduping against typed targets,
      skipping self-reference and code fences.
- [ ] Six new tests in `tests/test_parser.py`.

Task file: `task-mentions-detector.md`. Depends on Step 1.

## Step 4: Wire `edges_out` into `_parse_session`

- [ ] Import `Edge` from `.model` in `parser.py`.
- [ ] Build `edges = [Edge(source=task_slug, target=raw, kind=..., resolved=False), ...]`
      from typed relations + mentions.
- [ ] Pass `edges_out=edges` to `Task(...)` while preserving the
      `blocked_by` field for back-compat.
- [ ] Extend the `demo` fixture so a regression test asserts content of
      `edges_out`.

Task file: `task-edges-out-wiring.md`. Depends on Steps 2 and 3.

## Step 5: `parse_world` cross-WS resolution

- [ ] `_list_workspace_slugs`, `_build_task_index`, `_resolve_target`
      helpers.
- [ ] `parse_world(workspaces_root) -> World`.
- [ ] Mutate each `Task.edges_out` in place to the resolved form.
- [ ] Add second fixture workspace `other/` with session `sister/` and
      task `task-pinned` referencing `demo/feature-x/task-foo`.
- [ ] Add `Related to: [other/sister/task-pinned]` on `demo`'s
      `task-foo`.
- [ ] Tests for local resolution, cross-WS both directions, ghost
      target.

Task file: `task-parse-world.md`. Depends on Step 4.

## Step 6: Generator emits per-edge-class data

- [ ] Helpers: `_collect_workspace_nodes`, `_collect_world_nodes`,
      `_serialize_edge`, `_build_local_mode`,
      `_build_global_mode_for_workspace`, `_build_dashboard_global`.
- [ ] `build_workspace_html(world, slug)` and
      `build_dashboard_html(world)` take `World`.
- [ ] Embed payload via
      `<script>window.__CY_DATA__ = {json};</script>`.
- [ ] New tests in `tests/test_generator.py`.

Task file: `task-generator-edge-data.md`. Depends on Step 5.

## Step 7: CLI + server switch to `parse_world`

- [ ] Replace `parse_workspace(...)` calls in `cli.py` and `server.py`
      with `parse_world(...)`.
- [ ] Update `--workspace=all` to write `dashboard.html` plus per-WS
      pages.
- [ ] Server per-request regenerator dispatches on route.
- [ ] CLI test asserting the emitted HTML contains
      `window.__CY_DATA__` and the `"global"` mode payload.

Task file: `task-cli-server-parse-world.md`. Depends on Step 6.

## Step 8: Frontend chips and Global toggle

- [ ] Per-kind Cytoscape stylesheet rules in
      `templates/vendor/app.js` plus CSS in
      `templates/vendor/app.css`.
- [ ] Five chips: `Blocked by`, `Related to`, `Follows`, `Mentions`,
      `Global`. First three default `chip on`; latter two default
      `chip`.
- [ ] `renderMode(cy, modeData)`, `syncEdgeVisibility(cy)`,
      `bindChips(cy, cyData)`.
- [ ] Smoke pytest cases for chip markup.
- [ ] Manual browser pass against the fixture: confirm Global toggle
      adds the cross-WS neighbor and Mentions toggle reveals dotted
      edges.

Task file: `task-frontend-chips-toggle.md`. Depends on Step 6 (parallel
with Step 7).

## Step 9: Docs

- [ ] `skills/tracking-work/templates/task.md`: append a `## Relations`
      block.
- [ ] `skills/tracking-work/file-layout.md`: new "Cross-task relations"
      section.
- [ ] `skills/tracking-work-viz/README.md`: replace the Graph-pane
      bullet with one describing the five chips, defaults, and ghosts.

Task file: `task-graph-docs.md`. No code dependencies; can run in
parallel with any earlier step.

---

## Verification

After Step 8 lands:

1. `cd skills/tracking-work-viz && python -m pytest` passes the full
   suite.
2. `bash install.sh` (from repo root) populates `vendor/`.
3. `work-viz demo --workspaces-root skills/tracking-work-viz/tests/fixtures/sample_work --out-dir /tmp/viz-test`
   emits HTML containing `window.__CY_DATA__` with both `local` and
   `global` mode keys.
4. Open the emitted HTML in a browser; confirm the four kind chips
   filter edges and the `Global` chip pulls in the cross-WS neighbor.
5. `work-viz serve --workspaces-root <fixture>` regenerates on file
   change.
