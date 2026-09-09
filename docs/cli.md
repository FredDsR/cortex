# The `cortex` CLI

One command fronts the whole family. Every verb runs through the self-contained
`cortex` Python package; the former per-skill bash and Python CLIs are retired.

```
cortex kb    <command>   Author and query knowledge / workbench docs
cortex okf   <command>   Exchange Open Knowledge Format bundles
cortex viz   <command>   Build and serve the visual dashboard
cortex query <command>   Query the work graph
cortex inject <command>  Opt-in session-start injection
cortex sync  <command>   Sync the store to a private repo
cortex migrate-store     Move a legacy ~/.work store to ~/.cortex
```

Installing the package puts `cortex` on your `PATH`.

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
cortex kb log    [--workspace W] [--since DATE] [--max N] [--write]
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

**`log`** derives an [OKF][okf] §9 change log from the store's git history. It
reads the structured subjects `cortex sync` writes after every kb write, groups
them by commit date newest first, and resolves each slug to the doc's current
title and description, so an entry says what the note is rather than only which
file moved.

```markdown
# Knowledge change log

_Derived from 35 commits touching `knowledge/`, 2026-08-28 to 2026-09-06._

## 2026-09-06

* **Creation**: [ai-memory 2.0 vs cortex](ai-memory-comparison.md) - Akita's ...
* **Update**: [Close-day / .active pointer gotchas](close-day-active-pointer.md) - ...
```

Three verbs count as a knowledge write: `new`, `update`, and `add` (the bash
`work-kb` spelling of `new`, retired at the Python port but still throughout an
older store's history). `index` and `lint` commits are the tool's own
bookkeeping and are filtered, as are workbench writes and merge commits. One
entry per doc per day, a creation beating an update.

| Flag | Default | Notes |
|------|---------|-------|
| `--workspace <ws>` | active session pointer | Which workspace's `knowledge/` to read |
| `--since <date>` | unset | Passed to `git log --since`; the way to window the derived file |
| `--max <n>` | `100` | Caps stdout only. `--write` is uncapped, like `kb index` |
| `--write` | off | Derive `knowledge/log.md`, banner-marked, no frontmatter (§9) |

Two honest limits, both deliberate:

- **No git, no log.** A store is only a repo once somebody runs `git init`
  (usually via `cortex sync setup`). Without one there is no source, so `log`
  says so and writes nothing rather than deriving an empty file. Not an error.
- **A rename hides what came before it.** `git log` reads the directory's
  current path, and `--follow` handles a renamed file rather than a renamed
  directory, so a workspace that was renamed leaves its earlier writes under the
  old path. The header stays truthful because it reports the range actually
  read, which is why it names a range at all.

`log.md` and `index.md` are reserved **inside `knowledge/`**, so neither is ever
read back as a knowledge doc: they stay out of the index, out of `search`, out of
the viz graph, and out of `lint --check okf`, which would otherwise report a file
cortex derived itself as having no `type`. `cortex kb new knowledge log` is
refused for the same reason, since the next `--write` would overwrite it.

The reservation stops at `knowledge/`. Nothing is derived in `workbench/` or
`tasks/`, so `cortex kb new workbench log` is fine and that doc is indexed and
searchable like any other.

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

## cortex okf

Moves knowledge across the [Open Knowledge Format][okf] boundary, in both
directions.

```
cortex okf export [--workspace W] --out DIR [--since DATE]
cortex okf import <bundle> [--workspace W] [--write]
```

The store keeps `[[wikilinks]]` and does not also carry markdown links, because
two link grammars would have to be kept in sync forever. The cost is that an
external consumer reading an exported `knowledge/` sees the concepts and none of
the edges. These two verbs are where that translation happens instead: once, at
a boundary.

### export

Writes a workspace's `knowledge/` as a self-contained bundle.

- Every `[[knowledge/slug]]` and `[[slug]]` naming a concept the bundle holds
  becomes `[Title](/slug.md)`. §7 recommends bundle-absolute over relative, and
  every concept sits at the bundle root.
- Every reference that does not resolve becomes plain text, not a dangling
  link. A ghost node is authoring intent inside cortex, where `cortex query
  neighbors` shows it and `kb lint --check broken-ref` reports it; exported as a
  broken link it is only a defect in somebody else's bundle.
- References inside fenced blocks and inline code are left alone. A doc writing
  about the `[[...]]` grammar is illustrating the syntax, not using it.
- `index.md` (§8) and `log.md` (§9) come from the same renderers `kb index
  --write` and `kb log --write` use, so a bundle's catalog and the store's
  cannot disagree. The log is the reason `kb log` exists at all: a bundle has no
  `.git`, so §9 is the only shape the history can travel in. `--since` windows
  it exactly as on `kb log`.
- The index carries `okf_version: 0.2`, §8's one exception to index files having
  no frontmatter, and the only place a recipient can read what they are holding.
- The bundle is validated against §11 before the command reports success. A
  store doc with no `type:`, or none at all, fails the export loudly and names
  the file rather than shipping a bundle that does not parse.

`--out` must not already hold files: a bundle is defined by what is in the
directory, so exporting over other files would claim concepts the store never
had.

```bash
cortex okf export --workspace my-project --out /tmp/my-project-okf
```

### import

Reads somebody else's bundle into a workspace. **Dry run until you pass
`--write`**, and it never overwrites an existing doc, exactly like `kb ingest`.

- Markdown links between concepts become `[[knowledge/slug]]`. External URLs,
  in-page anchors, non-`.md` assets, and links to files this import did not take
  are left as they are: rewriting one would turn a working link into a reference
  that resolves to nothing.
- A nested bundle flattens, because `knowledge/` is flat. Two files sharing a
  stem keep the first, with a warning.
- `generated: {by, at}` (§5) maps where it maps. `generated.at` is "the
  content's last meaningful change", which is `updated` here, and a bundle
  carrying its own `created:` / `updated:` wins over both. Neither is stamped
  with today: an import is not a re-verification, and stamping would blind `kb
  lint --check stale` on every doc it touched. `author` is a two-value field, so
  a generator's name cannot go in it; the `generated:` block rides through
  verbatim, which is what actually preserves that provenance.
- Every other unknown key rides through verbatim too, which `cortex kb update`
  has preserved since #32.
- A concept with no `type:` is imported and reported, not refused. Dropping it
  would lose content over a field `cortex kb update --type` can add, and `kb
  lint --check okf` already lists exactly these.

**A bundle is untrusted input.** Its `description:` fields land in the
`<cortex-index>` block `cortex inject` hands a fresh agent at SessionStart,
before the user has said anything. So every string read out of a bundle goes
through `cortex/sanitize.py` -- not the ones that look risky, all of them,
frontmatter values and body alike. The one cost is that NFKC normalization
touches a foreign doc's text, which is the right trade in this direction: the
rule that keeps cortex from rewriting your own notes is the same rule that says
a stranger's bundle is not your notes.

```bash
cortex okf import /tmp/somebody-elses-bundle              # dry run
cortex okf import /tmp/somebody-elses-bundle --write
```

A round trip is not byte-identical, and in one way that is the point: a bare
`[[slug]]` normalizes to `[[knowledge/slug]]`, which turns a reference cortex
read as a ghost task into a real knowledge edge.

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
