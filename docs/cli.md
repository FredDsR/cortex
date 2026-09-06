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
| `--type <text>` | unset | Frontmatter type: `Decision`, `Design`, `Reference`, `Runbook`, `Investigation`, `Gotcha`, `Convention`, `Comparison`. A convention, not an enum, so a custom value is accepted. **Required on `new knowledge`**: OKF v0.2 §11 makes it the one mandatory field. Optional on `workbench`, which is never exported |
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
cortex kb new knowledge api-design --type Design --open
```

**`index`** regenerates the knowledge index from the entries present. It is a
dry run until you pass `--write`.

Stdout and the file are two renderings of the same rows. Stdout is the flat
`<slug> [<type>] - <description>` listing an agent reads, and the shape
`cortex inject` emits. `--write` derives `knowledge/index.md` in [Open
Knowledge Format][okf] §8 form instead: `## <type>` group headings over
`* [Title](slug.md) - description` entries, which is what a bundle consumer
parses. `--workspace=all --write` derives `~/.cortex/knowledge/index.md` the
same way, with URLs relative to that file.

`--max` bounds the printed listing only. The derived file is uncapped: it is
the catalog a bundle consumer reads, and one that silently omits entries is not
a catalog, nor is `... K more (raise --max)` a §8 entry. A bad `--max` still
errors either way.

The file is lowercase `index.md` because §8 reserves that name. A `--write`
over a store that predates this retires the old `INDEX.md` in the same commit,
so a `cortex sync pull` on a second device cannot resurrect it beside the new
one.

[okf]: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md

**`ingest`** reads a source (a codebase, an OpenAPI spec, SQL schemas) and
writes knowledge entries into a workspace. Also dry-run by default; `--only`
narrows the extractors, `--max` bounds how much it writes.

**`lint`** is the health check for a store that has been accumulating. A
knowledge base collects statements that were true when written and quietly
stopped being true, and neither the index nor the graph notices. Report-only
unless you pass `--fix`.

Six deterministic checks, one line per finding, grouped under a `## <check>`
header:

| Check | Fires when |
|-------|-----------|
| `broken-ref` | A reference resolves to no doc. Marked `(repairable)` when the slug it names exists elsewhere under exactly one address |
| `dead-ref` | A backticked path, symbol, or `--flag` in a doc body appears nowhere in the repo |
| `orphan` | A knowledge doc has no authored backlink (`contains` does not count) |
| `stale` | `updated` is older than `--stale-days` (default 180), missing, or unparseable |
| `missing-description` | No `description:`, which is the field the index and graph display |
| `okf` | A knowledge doc has no `type:` (OKF §11), or the derived index is not §8: a leftover `INDEX.md`, or an `index.md` with a hand-edited line |

Then an `## agent worklist (needs judgment)` section, in the same spirit as
`ingest`'s: pairs of same-typed docs whose summaries overlap enough to be worth
reading, phrased as candidates because a contradiction and two legitimately
distinct notes look identical from outside. It is selectable as `overlap`, but
it is not a check: its pairs never count toward the tally and never affect
`--strict`.

| Flag | Default | Notes |
|------|---------|-------|
| `--workspace <ws>\|all` | active session pointer | `all` lints every workspace in the global store, and says so when that leaves out a repo-local one |
| `--repo <path>` | the `cwd:` in the workspace `.meta`, or the repo itself for a repo-local store | What `dead-ref` checks against; the check is skipped with a note when none resolves |
| `--check <c,...>` | everything | Comma-separated subset of the six checks plus `overlap` (the worklist) |
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
cortex kb lint --check okf                       # OKF conformance only
```

The `okf` rows double as the backfill worklist for a store written before
`type` was required: each names the doc's title and description, which is what
you need to choose a value. Fix one with `cortex kb update knowledge <slug>
--type <T>`. It is deliberately not a `--fix`, because a migration that guesses
a type makes the store conformant and the field meaningless.

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

```
cortex query search <terms>... [--kind knowledge|workbench|task|all] [--workspace W|all] [--max N] [--archive]
```

Keyword search over the store, ranked by BM25. This is the headless counterpart
to the viz's in-browser search: before it, an agent with no tab open could not
answer "do we already know something about this". `cortex kb index` is a table
of contents over `description:` fields, which answers a different question.

| Flag | Default | Does |
|------|---------|------|
| `--kind` | `all` | `all` searches prose and tasks and fuses the two rankings; the others select one |
| `--workspace` | resolved | `all` searches every workspace in the global store, and says so when that leaves out a repo-local one |
| `--max` | `10` | Result ceiling; a truncated list reports how many more matched |
| `--archive` | off | Include archived sessions |

**Two indexes, fused.** Knowledge prose and task files differ in length, in
fields, and in what a query about them means, so they are indexed separately;
one merged corpus would let BM25's length normalization favour whichever kind
runs longer. When a query spans both, the rankings fuse by Reciprocal Rank
Fusion, which compares rank position rather than score, because BM25 scores
from two corpora are not on a common scale. Workbench docs share the prose
index with knowledge, since they match it on all three counts.

**No stemming.** `retries` will not match `retry`. Search for the stem, or for
a distinctive word from the passage you remember. Hyphens and underscores do
split, so `active pointer` reaches `close-day-active-pointer` and `parse world`
reaches `parse_world`.

Output is one line per hit: rank, kind, canonical id, and the first body line
matching the query. There is no score column, because under `--kind all` the
number is an RRF score rather than a BM25 one and carries nothing a reader can
act on. The canonical id passes straight to `cortex query neighbors`.

```bash
cortex query search atomic write            # ranked hits in this workspace
cortex query search retry --kind task       # only task files
cortex query search mkstemp --workspace all # across every workspace
```

**What `all` covers.** The global store, `~/.cortex/workspaces`, and only that.
A repo-local `<repo>/.cortex` is not in it: `all` exists to reach across
workspaces, and a per-repo store belongs to one repo. `search`, `related`, and
`lint` all name the excluded store in a trailing note rather than returning a
result that reads as complete, because `(no matches)` over an empty global
store is otherwise indistinguishable from "searched everything, found nothing".
Omit `--workspace` to work in the repo-local store.

```
cortex query related <slug> [--workspace W|all] [--session S] [--kind task|knowledge|workbench]
                            [--max N] [--min-score F] [--archive]
```

Link candidates for one document: the same BM25 ranking as `search`, but with
the document itself as the query. `cortex kb lint --check orphan` can already
say a doc has no inbound edges; it can never say what should fill the hole, and
guessing costs a full-store read.

| Flag | Default | Does |
|------|---------|------|
| `--workspace` | resolved | `all` ranks across every workspace in the global store, and says so when that leaves out a repo-local one |
| `--session` | resolved | Narrows an ambiguous slug |
| `--kind` | unset | Narrows an ambiguous slug. It does **not** pick the candidate kind |
| `--max` | `5` | Candidate ceiling, deliberately low |
| `--min-score` | `0` | Drop candidates below this BM25 score |
| `--archive` | off | Include archived sessions |

**The query is derived, not chosen.** It is an ordered dedup of the doc's
`title`, `description`, and body, through the same tokeniser `search` uses. A
sweep that picked its own search terms per document would return different
candidates on a second run over an unchanged store, and none of it would be
testable. Deduplicated because a repeated query term is scored once per
occurrence, so the raw token list would weight terms by how often the *source*
doc happened to say them.

**What it excludes.** The doc itself, everything it links to, and everything
that links to it. A candidate you have already acted on is noise.

**One kind, one index.** Candidates are always the resolved doc's own kind, so
knowledge ranks against knowledge. There is no `--kind all` here: fusing two
corpora with RRF would put `--min-score` on a scale where `0.016` is a good
result. Ranking inside one index keeps the score a raw BM25 number, and the
score column is printed for exactly that reason: a threshold flag whose values
you cannot see is a decorative knob. Scores compare within one run, not across
two.

Output is one line per candidate: rank, score, canonical id, summary, and the
shared terms that earned the rank, highest-contribution first. The terms are
the point. A ranked list nobody can interrogate gets either trusted blindly or
ignored, and both are worse than seeing that a candidate ranked on `resolved,
pointer, workspace` rather than on `again, now, say`.

```bash
cortex query related close-day-active-pointer          # top 5 link candidates
cortex query related close-day-active-pointer --max 3 --min-score 70
```

**Turning candidates into links** is judgment, and it lives in the
`cortex-kb` skill under "Sweeping for missing links". The CLI ranks; it never
writes an edge.

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
