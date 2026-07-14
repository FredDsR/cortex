---
name: tracking-work-kb
description: Use when authoring workspace-scoped knowledge entries or session-scoped workbench drafts in the ~/.work knowledge base. Creates markdown files at the correct path with valid frontmatter; agents pass --body or pipe content via stdin.
---

# Tracking Work: Knowledge Base writes

Authors `knowledge/<slug>.md` (workspace-scoped) and `workbench/<slug>.md`
(session-scoped) markdown files in the `~/.work/` (global) or
`<repo>/.work/` (local) tracking store. Sibling skill to
`tracking-work-viz`, which renders the resulting files in the graph and
tree.

> The CLI is `cortex kb` (`cortex kb new|update|index|ingest`), implemented in
> the `cortex` Python engine (top-level `cortex/` package). This skill dir is
> now docs + the one-shot `scripts/migrate_kb_frontmatter.py`; there is no bash
> `work-kb` bin anymore.

## When to use

- The user (or you, the agent) wants to record a durable note that other
  documents will reference.
- `[[knowledge/foo]]` appears in a task body as a ghost (unresolved) link
  and the user asks to create the missing entry.
- Spec, plan, or brainstorm output should be captured as a knowledge
  entry rather than dropped on the floor.

## CLI surface

```
cortex kb new    knowledge <slug> [flags]
cortex kb new    workbench <slug> [flags]
cortex kb update knowledge <slug> [flags]
cortex kb update workbench <slug> [flags]
cortex kb index  [--workspace <ws>] [--session <sess>] [--max <N>] [--write]
cortex kb ingest [--from <src>] [--workspace <dest>] [--write] [--only openapi|sql] [--max <N>]
```

## Querying the graph

`cortex query neighbors <slug>` prints a doc's forward links and backlinks
(grouped by edge kind, each with a one-line summary) plus its ghost/unresolved
`[[...]]` references, so an agent can expand context on demand without opening
the viewer. Narrow an ambiguous slug with `--workspace` / `--session`; bound the
listing with `--max` (default 20). Works for `task`, `knowledge`, and
`workbench` docs.

```
cortex query neighbors <slug> [--workspace <ws>] [--session <sess>] [--max <N>]
```

`new` and `update` share the same flags:

| Flag | Default | Notes |
|------|---------|-------|
| `--workspace <ws>` | from active session pointer | Required if no active session can be resolved |
| `--session <sess>` | from active session pointer | Workbench only |
| `--author <human\|agent>` | `agent` (or `human` if `--open` and `--author` not passed) | Must be one of `human`, `agent` |
| `--title <text>` | unset | Optional frontmatter title |
| `--type <text>` | unset | Optional frontmatter type (see vocabulary below) |
| `--description <text>` | unset | Optional one-line frontmatter description |
| `--body <text>` | empty | Inline body |
| `--body-from <file\|->` | unset | File or stdin |
| `--open` | off | After write, `exec ${EDITOR:-vi}` |

### `new` vs `update`

- **`new`** is create-only. If the target file already exists it errors
  `already exists` (exit 1).
- **`update`** is modify-only. If the target file does not exist it errors
  `not found` (exit 1). It preserves `created`, sets `updated` to today, and
  merges: `--title`/`--type`/`--description`/`--author` change only when the
  flag is passed, otherwise the existing value is kept. The body is replaced
  only when `--body`/`--body-from` is given; bare stdin is NOT auto-consumed by
  `update` (unlike `new`). So `cortex kb update <kind> <slug>` with no other flags
  is a pure "touch": it bumps `updated` and rewrites nothing else.

### `cortex kb index`

Prints a compact, pull-based table of contents (one line per doc,
`<slug> [<type>] - <description>`) for the resolved workspace's `knowledge/`,
plus the active (or `--session`) session's `workbench/` when one resolves.
Ordered by type then slug (untyped last), bounded by `--max` (default 100) per
section with a `... K more (raise --max)` notice. By default it writes to
stdout. `--write` (re)generates a derived, banner-marked `knowledge/INDEX.md`
(the knowledge section only), regenerated like `SUMMARY.md` and never
hand-maintained or injected into any context. `INDEX.md` is excluded from the
viz graph.

### Bulk ingestion (`cortex kb ingest`)

Bulk-ingest documentable artifacts from a codebase into a workspace's
`knowledge/`. **Direction:** `--from <src>` reads a codebase (default `.`);
`--workspace <dest>` writes the KB (default: the active workspace), same as
`new`/`update`/`index`. Not to be confused with `tracking-work-migration`
(which moves a session between stores).

- **Dry-run by default**; `--write` is the confirmation gate. Existing
  `knowledge/<slug>.md` is never overwritten (reported under `## skipped`).
- **Hybrid extraction.** A deterministic path documents **OpenAPI/Swagger**
  (one doc per operation + per schema) and **SQL DDL** (one doc per table,
  columns verbatim, `REFERENCES` -> `[[...]]` links). Everything fuzzier
  (Prisma, README `## API`/`## Schema` sections, runbooks, model/entity dirs)
  is printed as an **agent worklist** (`## agent worklist`); the CLI never
  fabricates prose docs.
- **Agent workflow for the worklist:** for each entry, read the artifact,
  classify it to a `type`, and run
  `cortex kb new knowledge <slug> --type ... --title ... --description ... --body ...`
  preserving exact field names/types and using `[[knowledge/<slug>]]`
  cross-links.
- `--only openapi|sql` restricts the deterministic scan; `--max <N>` caps writes
  (default 100) with a `... K more (raise --max)` notice.
- **Dependency / fallback.** The deterministic path uses a Python helper
  (stdlib + PyYAML, no new pip deps), selected via `${WORK_KB_PYTHON:-python3}`.
  If Python/PyYAML is unavailable, structured files fall into the agent worklist
  and the run still exits 0 (plain-shell harness-agnosticism preserved).

## Related skills

- `tracking-work-viz` renders these docs (graph/tree/content) including the
  `type`/`title`/`description`/`updated` fields.
- `tracking-work-sync` replicates the store; both write paths call its
  `commit_push.sh`.
- `tracking-work-migration` is a different thing entirely (session store moves),
  despite the surface similarity to `ingest`.

## Agent invocation patterns

Capture an agent-generated note with the body inline:

```bash
cortex kb new knowledge api-versioning-decision --body "$(cat <<'END'
## Decision

We will use header-based versioning for the public API.
END
)"
```

Pipe a longer body from stdin:

```bash
some-pipeline | cortex kb new knowledge daily-summary --body-from -
```

Workbench note tied to the current session:

```bash
cortex kb new workbench draft-pr-description --body-from /tmp/pr-draft.md
```

## Resolution rules

- Workspace discovery walks up from cwd (only within `$HOME`) to find a
  local `.work/` first; otherwise scans `~/.work/workspaces/*/` for the
  unique workspace that has any `.active.*` pointer. Errors if zero or
  multiple.
- Session discovery (workbench only) reads `.active.*` pointers in the
  resolved workspace and uses the unique session. Errors on ambiguity.
- The CLI never guesses on ambiguity. It always names the flag that
  resolves the conflict.

## Frontmatter

Both kinds emit fields in this deterministic order (only fields with a value
are written; `author`/`created`/`updated` are always present):

```yaml
---
title: <optional, from --title>
type: <optional, from --type>
author: <human|agent>
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
description: <optional, from --description>
---

<body>
```

The slug is the filename stem; no `slug:` field. Body is written verbatim after
the frontmatter. `updated` equals `created` on `new` and is bumped to today by
`update`. When no `--title` is given, the viz falls back to the body's first
`# heading` for the display title.

### `type` vocabulary

`type` is a documented, evolvable convention, not a validated enum. Reuse a
canonical value where it fits: `Decision`, `Design`, `Reference`, `Runbook`,
`Investigation`, `Convention`, `Comparison`. Custom values are accepted without
error, but prefer the canonical set so the index groups sensibly.

`cortex kb` reads frontmatter with a scalar-only line reader (only the known keys
above). It is not a general YAML parser: any structured/unknown key is ignored,
never misparsed. The viz uses real YAML for its own reads.

## Exit codes

- 0: success
- 1: missing context, invalid slug, file already exists (`new`), file not found
  (`update`), malformed frontmatter (`update`)
- 2: usage error (bad subcommand, bad flag)

## What this skill does NOT do

- Rewrite the body of an existing file except via `update` (which also bumps
  `updated`). Full-body rewrites need an explicit `--body`/`--body-from`.
- List, show, mv, or rm. Use `ls`, `cat`, `git mv`, `rm`.
- Validate `[[...]]` references at write time. Broken refs surface in the
  viz as ghost nodes; existing behavior.
- Open the editor by default. Agent-primary CLI; `$EDITOR` opens only
  when `--open` is passed.
- Inject the index into any context. `cortex kb index` is pull-based (stdout or a
  derived `INDEX.md`). Opt-in session-start injection (which builds on this index)
  is a separate, off-by-default feature: see `tracking-work-inject` (`cortex inject`).

## Sync integration

After a successful write, calls
`$HOME/.claude/skills/tracking-work-sync/scripts/commit_push.sh` if
present and executable. No-op if sync is not installed or disabled.

## Tests

The kb commands are tested in the engine package:

```bash
.venv/bin/python -m pytest cortex/tests -q
```

`cortex/tests/test_kb_*.py` set up a temp `HOME`, drive `cortex.cli.main(["kb", ...])`,
and assert file contents / exit codes (parity ports of the former bash suites).
The one-shot migration keeps its own test at
`skills/tracking-work-kb/tests/test_migrate_kb_frontmatter.py`.
