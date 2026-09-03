# The `cortex` CLI

One command fronts the whole family. Every verb runs through the self-contained
`cortex` Python package; the former per-skill bash and Python CLIs are retired.

```
cortex kb    <command>   Author and query knowledge / workbench docs
cortex viz   <command>   Build and serve the visual dashboard
cortex query <command>   Query the work graph
cortex inject <command>  Opt-in session-start injection
cortex sync  <command>   Sync the store to a private repo
cortex migrate-store     Move a legacy ~/.work store to ~/.cortex
```

Installed at `~/.cortex/bin/cortex`. Add that directory to `PATH`.

Most commands resolve the workspace and session from the active session pointer,
so you rarely pass `--workspace` or `--session` by hand. Pass them when no
active session can be resolved, or when a slug is ambiguous.

---

## cortex kb

Authors the knowledge base. See [skills.md](skills.md#cortex-kb) for when to
reach for knowledge versus workbench.

```
cortex kb new    knowledge|workbench <slug> [flags]
cortex kb update knowledge|workbench <slug> [flags]
cortex kb index  [--workspace W] [--session S] [--max N] [--write]
cortex kb ingest [--from SRC] [--workspace W] [--write] [--only openapi|sql] [--max N]
cortex kb lint   [--workspace W|all] [--repo PATH] [--check C,...] [--stale-days N]
                 [--max N] [--archive] [--fix] [--strict]
```

**`new` is create-only** and errors with `already exists` if the file is there.
**`update` is modify-only** and errors if it is not. The split is deliberate: an
agent cannot silently clobber a note it meant to create.

`new` and `update` share these flags:

| Flag | Default | Notes |
|------|---------|-------|
| `--workspace <ws>` | active session pointer | Required if no active session resolves |
| `--session <sess>` | active session pointer | Workbench only |
| `--author human\|agent` | `agent` | Becomes `human` if `--open` is passed without `--author` |
| `--title <text>` | unset | Frontmatter title |
| `--type <text>` | unset | Frontmatter type, e.g. `Gotcha`, `Decision`, `Reference` |
| `--description <text>` | unset | One-line summary; this is what the index shows |
| `--body <text>` | empty | Inline body |
| `--body-from <file\|->` | unset | Read body from a file, or `-` for stdin |
| `--open` | off | After writing, `exec $EDITOR` |

```bash
# a note written by an agent, body piped in
echo "Auth tokens expire after 15m, not 60m as the docs claim." |
  cortex kb new knowledge token-expiry \
    --type Gotcha --description "Token TTL is 15m despite the docs"

# open one in your editor instead
cortex kb new knowledge api-design --open
```

**`index`** regenerates `INDEX.md` from the entries present. It is a dry run
until you pass `--write`.

**`ingest`** reads a source (a codebase, an OpenAPI spec, SQL schemas) and
writes knowledge entries into a workspace. Also dry-run by default; `--only`
narrows the extractors, `--max` bounds how much it writes.

**`lint`** is the health check for a store that has been accumulating. A
knowledge base collects statements that were true when written and quietly
stopped being true, and neither the index nor the graph notices. Report-only
unless you pass `--fix`.

Five deterministic checks, one line per finding, grouped under a `## <check>`
header:

| Check | Fires when |
|-------|-----------|
| `broken-ref` | A reference resolves to no doc. Marked `(repairable)` when the slug it names exists elsewhere under exactly one address |
| `dead-ref` | A backticked path, symbol, or `--flag` in a doc body appears nowhere in the repo |
| `orphan` | A knowledge doc has no authored backlink (`contains` does not count) |
| `stale` | `updated` is older than `--stale-days` (default 180), missing, or unparseable |
| `missing-description` | No `description:`, which is the field the index and graph display |

Then an `## agent worklist (needs judgment)` section, in the same spirit as
`ingest`'s: pairs of same-typed docs whose summaries overlap enough to be worth
reading, phrased as candidates because a contradiction and two legitimately
distinct notes look identical from outside. It is selectable as `overlap`, but
it is not a check: its pairs never count toward the tally and never affect
`--strict`.

| Flag | Default | Notes |
|------|---------|-------|
| `--workspace <ws>\|all` | active session pointer | `all` lints every workspace in the global store |
| `--repo <path>` | the `cwd:` in the workspace `.meta` | What `dead-ref` checks against; the check is skipped with a note when neither resolves |
| `--check <c,...>` | everything | Comma-separated subset of the five checks plus `overlap` (the worklist) |
| `--stale-days <n>` | `180` | Age past which `updated` counts as stale |
| `--max <n>` | `50` | Per-section cap, with a `... K more` notice |
| `--archive` | off | Also lint archived sessions. Archives are always *resolved* against, so a link into one is never reported broken |
| `--fix` | off | Rewrite repairable `broken-ref` addresses in place |
| `--strict` | off | Exit 1 when findings remain, for CI |

```bash
cortex kb lint                                   # everything, current workspace
cortex kb lint --check broken-ref,orphan         # just the graph checks
cortex kb lint --check broken-ref --fix          # repair mistyped addresses
cortex kb lint --strict                          # gate a commit or a CI job
```

**What `--fix` deliberately will not do.** It rewrites a reference only when
the slug it names belongs to exactly one doc in the store, so the edit changes
an address and never a claim. It does not delete a dangling link, because a
link to a doc nobody has written yet is authoring intent and is what the viz
renders as a ghost node. It does not bump `updated`, because that would erase
the signal the `stale` check reads. Everything else is yours to decide.

**On `dead-ref` precision.** It only reads inline code spans outside fenced
blocks, on the theory that a backtick is the author saying "this is code", and
it ignores attribute access (`args.max`), placeholders (`<slug>.md`), and
home- or env-relative paths. It still cannot know that a doc is *about* another
project, so a note comparing cortex to something else will report that other
project's symbols as dead. Narrow with `--check` when that is the doc you have.

---

## cortex query

```
cortex query neighbors <slug> [--workspace W] [--session S] [--kind task|knowledge|workbench] [--max N]
```

Prints a document's forward links and backlinks, grouped by edge kind with a
one-line summary each, plus its unresolved `[[...]]` ghost references.

This exists so an agent can expand context on demand without opening the viewer
or reading whole files. `--max` defaults to 20.

```bash
cortex query neighbors token-expiry
```

---

## cortex viz

```
cortex viz build [workspaces_root] [--out OUT]
cortex viz serve [out_dir] [--host H] [--port P] [--no-open] [--edit] [--workspaces-root R]
```

`build` generates a static site. `serve` serves a built directory and opens a
browser, unless `--no-open`.

**`--edit` is the one flag that grants write access.** Without it, `serve` is a
plain static file handler with no ability to modify anything. With it, you get
in-browser editing against the real store, bound to localhost.

```bash
cortex viz build --out ~/cortex-site
cortex viz serve --port 8080 --no-open
```

---

## cortex inject

```
cortex inject enable  [--workspace W] [--wire-hook <harness>]
cortex inject disable [--workspace W] [--unwire-hook <harness>]
cortex inject status  [--workspace W]
cortex inject here    [--format text|claude-code] [--workspace W] [--session S] [--max N]
```

Injection requires **two** independent guards, and either one alone injects
nothing:

1. the harness session-start hook is wired, and
2. the workspace has a `.inject-enabled` sentinel.

`here` is the universal renderer. It prints the byte-bounded `<cortex-index>`
block to stdout, or prints nothing when a guard is unmet. Any harness, skill, or
person can call it, which is what makes the feature portable rather than
Claude-Code-specific.

See [hooks-and-plugins.md](hooks-and-plugins.md) for the wiring details.

**Note:** `disable` removes the workspace's sentinel as well as unwiring the
hook, so it changes store state, not just harness config.

---

## cortex sync

```
cortex sync setup    # one-shot bootstrap: clone, create, or skip
cortex sync status   # enabled state + origin
cortex sync push "<message>"
cortex sync pull
```

Replicates `~/.cortex/` to a private git repo. `setup` runs once and records the
outcome; later invocations trust it.

**Every subcommand no-ops when sync is unavailable**, which is why the tracking
skill can call `push` at every write checkpoint without checking first.

If `pull` reports `SUMMARY.md regenerate-needed`, a summary was resolved to
upstream and must be rebuilt from its `tasks/*.md`.

---

## cortex migrate-store

```
cortex migrate-store           # dry run: shows what would move
cortex migrate-store --write   # perform the move
```

Moves a legacy `~/.work` store to `~/.cortex`. Idempotent and conflict-safe, and
it merges cleanly with the `~/.cortex/bin` scaffold that `install.sh` creates.

Only relevant if you used this project before the cortex rename.
