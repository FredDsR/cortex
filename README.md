<p align="center">
  <img src="assets/cortex-logo.svg" alt="cortex" width="340">
</p>

# cortex

Portable bundle of file-based work-tracking skills for AI coding agents. Designed to work with any harness that reads `SKILL.md` from a skills directory: Claude Code, Codex, Copilot CLI, Antigravity.

One CLI fronts the whole family: **`cortex`**. Its verbs are `cortex kb` (author knowledge), `cortex viz` (visualize), `cortex query neighbors <slug>` (explore a doc's links), `cortex inject` (opt-in session-start injection), `cortex sync` (cross-device sync of the store), and `cortex migrate-store` (move a legacy `~/.work` store to `~/.cortex`). Every verb runs through one self-contained `cortex` Python package (`cortex/`); the former per-skill bash/Python CLIs have been retired.

## The dashboard

`cortex viz` builds a static, browser-based view of every workspace, session, and task: a collapsible tree, a hub-and-spoke graph of typed links, and a rendered-markdown content pane. Read-only by default; theme-aware (light + dark).

**Light theme**

<p align="center">
  <img src="assets/screenshots/viz-light.png" alt="cortex viz dashboard, light theme: tree, graph, and content panes" width="900">
</p>

**Dark theme**

<p align="center">
  <img src="assets/screenshots/viz-dark.png" alt="cortex viz dashboard, dark theme: tree, graph, and content panes" width="900">
</p>

## Concepts

Five nouns carry the model:

| Concept | Scope | Lifetime |
|---------|-------|----------|
| **Workspace** | One project, resolved from your git remote or directory name | Permanent |
| **Session** | A stretch of related work | Weeks, then archived |
| **Task** | One piece of that work, with a status | Days |
| **Knowledge note** | The workspace | Outlives every session |
| **Workbench note** | One session | Dies with the session |

A **workspace** contains **sessions**; a session contains **tasks** plus its
**workbench** notes; **knowledge** notes sit at the workspace level so every
session can reach them.

The distinction that earns its keep is the last two. **Workbench** is the
low-stakes place to think out loud, and it stops mattering when the session
closes. **Knowledge** is what you want to still have three months from now. When
a workbench note turns out to matter, promote it.

Task status is one of `Open`, `In Progress`, `Blocked`, `Resolved`. There is
deliberately no "won't do": abandoned work is archived with its tasks still
`Open`, so the archive records what happened rather than a completion that never
occurred.

Full treatment in [docs/concepts.md](docs/concepts.md).

## Skills in this repo

| Skill | Purpose |
|---|---|
| `cortex-tracking` | Main skill — file-based session/task tracking across workspaces, with global + local stores and concurrent-agent support. |
| `cortex-github` | Optional PR/commit drift detection via the `gh` CLI, invoked by the main skill when a session has `github:` frontmatter. |
| `cortex-migration` | Move a session between the global store (`~/.cortex/`) and a repo-local store. |
| `cortex-sync` | Optional cross-device sync of `~/.cortex/` via a private GitHub repo. See `skills/cortex-sync/docs/` for design. |
| `cortex-viz` | Browser-based viewer for `~/.cortex/`: three-pane tree + Cytoscape graph + rendered markdown, plus a cross-workspace dashboard. Ships a `cortex viz` CLI with `build` and `serve` (plus opt-in `serve --edit`). |
| `cortex-kb` | Author and bulk-ingest knowledge/workbench docs (`cortex kb` CLI): structured frontmatter, a pull-based index, and codebase ingestion. Rendered by `cortex-viz`, replicated by `cortex-sync`. |
| `cortex-inject` | Optional, off-by-default session-start context injection (`cortex inject` CLI). The single exception to the otherwise pull-based, no-auto-injection design. |

Only `cortex-tracking`, `cortex-kb`, and `cortex-viz` are ones you trigger. The
rest are sub-skills the main skill invokes when it needs them. See
[docs/skills.md](docs/skills.md).

## The `cortex` CLI

One command fronts the family, installed at `~/.cortex/bin/cortex`.

It exists for two reasons, both about what an agent would otherwise do instead.

**It standardizes the environment.** Without it, every skill would describe its
own file paths, frontmatter rules, and slug resolution in prose, and each agent
would reimplement them slightly differently. One binary means one definition of
where a workspace lives, how a slug resolves, and what valid frontmatter is. A
skill says `cortex kb new knowledge <slug>` instead of explaining a directory
layout and hoping the agent gets it right.

**It optimizes token usage.** Every verb is designed so the agent reads a small
bounded artifact rather than a large unbounded one. `cortex kb index` returns a
one-line-per-document table of contents instead of the documents. `cortex query
neighbors` returns a document's links with one-line summaries instead of the
linked files. `cortex inject here` emits a byte-bounded block. The pattern is
the same everywhere: answer the question at hand with the smallest artifact
that can answer it, and let the agent open the full file only when it decides
to.

The alternative is the agent globbing directories, reading whole files to find
one field, and re-deriving the layout every session. The CLI turns that into
one call with a bounded response.

| Verb | Does |
|------|------|
| `cortex kb` | Author and audit knowledge / workbench docs (`new`, `update`, `index`, `ingest`, `lint`) |
| `cortex viz` | Build and serve the dashboard (`build`, `serve`) |
| `cortex query` | Explore a doc's links and backlinks (`neighbors`) |
| `cortex inject` | Opt-in session-start injection (`enable`, `disable`, `status`, `here`) |
| `cortex sync` | Replicate the store to a private repo (`push`, `pull`, `setup`, `status`) |
| `cortex migrate-store` | Move a legacy `~/.work` store to `~/.cortex` |

Workspace and session are resolved from the active session pointer, so most
commands need no arguments:

```bash
cortex kb new knowledge token-expiry --type Gotcha --description "TTL is 15m"
cortex query neighbors token-expiry
cortex viz serve
```

Full reference in [docs/cli.md](docs/cli.md).

## Documentation

| Guide | Covers |
|-------|--------|
| [docs/README.md](docs/README.md) | Start here: the idea, and a first-session walkthrough |
| [docs/concepts.md](docs/concepts.md) | Workspace, session, task, knowledge, workbench |
| [docs/skills.md](docs/skills.md) | All seven skills and how they connect |
| [docs/cli.md](docs/cli.md) | Every `cortex` verb and flag |
| [docs/store.md](docs/store.md) | File layout, frontmatter, and typed links |
| [docs/hooks-and-plugins.md](docs/hooks-and-plugins.md) | The opt-in hook, plugin manifests, `/close-day` |

## Knowledge base

Beyond sessions and tasks, a workspace can hold durable notes. `cortex-kb`
(the `cortex kb` CLI) owns writing them:

- **Two document classes.** `knowledge/<slug>.md` is workspace-scoped (context
  shared across tasks); `workbench/<slug>.md` is session-scoped (drafts, spec /
  plan / brainstorm output).
- **Structured frontmatter.** Optional `title`, `type`, `description`, plus
  auto-maintained `author` / `created` / `updated`. `type` is a documented,
  evolvable convention (`Decision`, `Design`, `Reference`, `Runbook`,
  `Investigation`, `Convention`, `Comparison`; custom values allowed).
- **`cortex kb new` / `cortex kb update`.** Create-only vs modify-only (field merge
  and a pure `updated`-bump touch).
- **`cortex kb index`.** A compact, pull-based table of contents so agents can see
  what already exists before authoring a duplicate. Prints to stdout, or
  `--write` regenerates a derived `knowledge/INDEX.md` (like `SUMMARY.md`, never
  hand-maintained, never injected).
- **The brain (cross-workspace).** `cortex kb index --workspace=all` aggregates
  every global workspace's knowledge into one dictionary grouped by type; the
  viz root page renders the same data as a wiki whose concepts link across
  workspaces. Derived and regenerable, never hand-authored. Scope is the global
  store (`~/.cortex/workspaces/*`); repo-local `.cortex` stores are not included.
- **`cortex kb ingest`.** Bulk-ingest a codebase into a workspace's `knowledge/`:
  a deterministic path documents OpenAPI/Swagger and SQL DDL, and everything
  fuzzier (Prisma, README `## API` / `## Schema` sections, runbooks, model dirs)
  is surfaced as an agent worklist. Dry-run by default; `--write` is the gate;
  existing docs are never overwritten. `--from <src>` names the codebase to read,
  `--workspace <dest>` the KB to write.
- **`cortex kb lint`.** The health check for a store that has been accumulating.
  Five deterministic checks (references that resolve to nothing, backticked
  paths / symbols / flags that no longer exist in the repo, unlinked knowledge
  docs, stale `updated` dates, missing descriptions), then a judgment worklist
  for the contradiction and superseded-claim readings a machine should not
  assert. Report-only by default; `--strict` exits 1 for CI, and `--fix` is
  narrow on purpose: it repairs a reference whose target exists under a
  different unambiguous address, and touches nothing else.

### How the skills connect

- `cortex kb` **writes** knowledge/workbench docs; `cortex-viz` **renders**
  them (tree, graph, content, with the frontmatter fields above); and
  `cortex-sync` **replicates** the whole `~/.cortex/` store. All three
  share one file layout and the same `cortex sync push` hook.
- The main `cortex-tracking` skill invokes `cortex-kb` at its knowledge
  checkpoints (capturing durable notes, resolving `[[knowledge/...]]` ghost
  links, recording spec/plan output).
- `cortex kb ingest` reads a codebase and writes into a KB workspace. It is
  unrelated to `cortex-migration`, which **moves a session** between the
  global and local stores. Different verbs, opposite direction, different data.

## Ingesting a codebase

A knowledge base that starts empty tends to stay empty. `cortex kb ingest`
bootstraps one by reading a codebase and writing knowledge docs from what it
finds.

```bash
cortex kb ingest --from ~/some-service              # dry run: report only
cortex kb ingest --from ~/some-service --write      # actually write
cortex kb ingest --from ~/some-service --only sql   # narrow the extractors
```

It splits sources by whether a parser can be trusted with them.

**Deterministic extraction**, done by real parsers rather than model judgment:

| Source | Produces |
|--------|----------|
| OpenAPI / Swagger (`openapi*.yaml\|json`, `swagger*`) | One doc per schema, with fields and types preserved exactly |
| SQL DDL (`*.sql`) | One doc per `CREATE TABLE`, columns and types intact |

`$ref` targets become `[[schema-<slug>]]` links, so the extracted docs arrive
already cross-referenced rather than as a flat pile.

**An agent worklist** for everything a parser should not guess at: `*.prisma`
schemas, `README*.md` files carrying an `## API` or `## Schema` section, and
`runbook*` files. These are reported, never auto-written. The agent decides what
they mean.

Two safety properties worth knowing. It is **dry-run by default**, and `--write`
is the only gate. And it **never overwrites**: a doc that already exists is
skipped and reported, so re-running after adding sources only fills gaps.

### Compared to Karpathy's LLM Wiki

In April 2026 Andrej Karpathy published
[llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f),
an idea file arguing that instead of retrieving from raw documents at query
time, an LLM should incrementally build and maintain a persistent markdown
wiki, and queries should go to the wiki rather than the sources. His framing:
knowledge is "compiled once and then _kept current_, not re-derived on every
query," and the reason it works is division of labor, since "the tedious part of
maintaining a knowledge base is not the reading or the thinking, it's the
bookkeeping."

cortex's knowledge base is the same bet. Raw sources stay immutable, the agent
owns a directory of markdown, and `knowledge/INDEX.md` is the catalog you read
to find out what exists. Where the two differ is instructive in both directions.

| | Karpathy's llm-wiki | cortex |
|---|---|---|
| Ingest | LLM reads the source and writes pages | Parsers handle OpenAPI and SQL exactly; only ambiguous sources go to the agent |
| Index | `index.md`, LLM-maintained | `INDEX.md`, derived and regenerated by `cortex kb index --write` |
| Links | Cross-references between pages | Typed `[[wikilinks]]`, with unresolved ones surviving as visible ghost nodes |
| Change log | `log.md`, append-only, grep-able | No wiki-level equivalent; sessions keep their own day log |
| Lint | A named operation: contradictions, stale claims, orphans | `cortex kb lint`: five deterministic checks, plus a worklist for the judgment calls |
| Scope | Knowledge only | Knowledge plus work tracking: sessions, tasks, blockers |

**Where cortex is stronger.** Deterministic extraction means an OpenAPI schema
is transcribed rather than paraphrased, which matters because the failure mode
of LLM ingestion is a plausible field name that does not exist. A derived index
cannot drift from the filesystem the way a hand-maintained one can. And ghost
links make the gaps in a knowledge base visible instead of silent.

**Where it is not.** Karpathy's `log.md` is a real idea cortex lacks at the
knowledge layer: an append-only, grep-able record of what changed when. And
while `cortex kb lint` now covers the mechanical half of his lint operation, the
half that needs judgment (which of two overlapping notes supersedes the other)
is only a worklist. A machine can see that two docs overlap; it cannot see which
one is still true.

## Install

`install.sh` serves Claude Code, Codex, and Copilot CLI, symlinking each skill
into the harness's own `skills/` directory. Antigravity installs itself from the
repo and needs no symlinks. Claude Code additionally has a `/plugin` route.

### Quickest path: one-liner

```bash
curl -fsSL https://raw.githubusercontent.com/FredDsR/cortex/main/install.sh | bash
```

Piped, `install.sh` has no repo to symlink into, so it clones one to `~/cortex`
and re-runs itself from there. Re-running updates that checkout instead of
cloning again. If `~/cortex` exists and is not a cortex checkout, it stops
rather than writing over it.

| Setting | Effect |
|---------|--------|
| `CORTEX_DIR` | Where to clone (default `~/cortex`) |
| `CORTEX_REPO` | Which repo to clone, for forks |
| `--project [path]` | Install into `<path>/.<harness>/skills/` instead of `$HOME` (defaults to `$PWD`) |
| `-h`, `--help` | `install.sh` usage |

`CORTEX_*` are environment variables; the flags belong to `install.sh` and reach
it through `bash -s --`:

```bash
curl -fsSL .../install.sh | CORTEX_DIR=~/src/cortex bash
curl -fsSL .../install.sh | bash -s -- --project ~/some-repo
```

### From a clone

Clone anywhere, then run `install.sh`. It detects which agent harnesses you have on this device (by probing `~/.claude/`, `~/.codex/`, `~/.copilot/`) and symlinks each skill into their respective `skills/` directories.

```bash
git clone git@github.com:FredDsR/cortex.git ~/cortex
bash ~/cortex/install.sh
```

Put the clone anywhere you like — `install.sh` uses its own directory as the source, so symlinks will always point at wherever you cloned.

### Global vs project-scoped

Agents support skills at two scopes:
- **Global**: `$HOME/.<harness>/skills/<name>/` — visible to every project.
- **Project**: `<repo>/.<harness>/skills/<name>/` — visible only when the agent is run from that project.

`install.sh` supports both:

```bash
# Global (default) — all your agent sessions see these skills
bash install.sh

# Project-scoped — only this repo's agent sessions see them
cd ~/some-repo
bash /path/to/cortex/install.sh --project            # defaults to $PWD
bash /path/to/cortex/install.sh --project ~/some-repo  # or explicit path
```

Project-scoped install creates `<repo>/.claude/skills/`, `<repo>/.codex/skills/`, etc. as needed (but only for harnesses you already use globally, detected via presence of `$HOME/.<harness>/`). Re-run after `git pull` in the skills clone to refresh.

### Claude Code: `/plugin` (experimental)

Claude Code is covered by `install.sh` above. It also has a second option: a
`.claude-plugin/marketplace.json` + `plugin.json` make this repo addable as a
plugin marketplace.

```
/plugin marketplace add FredDsR/cortex
/plugin install cortex
```

Some cross-skill invocations hardcode `$HOME/.claude/skills/<sub-skill>/...`,
which only the symlink install produces, so that route stays the first-class
one. Use `/plugin` if you prefer the UX; behavior is best-effort.

### Antigravity: `agy plugin install`

Antigravity installs from the repo directly, reading `skills/` out of the git
URL. There is nothing to symlink, so `install.sh` does not target it:

```bash
agy plugin install https://github.com/FredDsR/cortex
```

Re-running the same command updates it.

cortex ships no session-start hook, so nothing auto-loads here: skills are
discovered and invoked on demand. `cortex inject` adds injection, but wires a
Claude Code hook only.

**Unverified.** This follows Antigravity's documented behavior but has not been
run against a real `agy` install. Confirm the skills are discoverable before
relying on it.

## Update

Because `install.sh` symlinks each skill into the harness directories, a single
`git pull` in this clone is enough for content changes; you only need to re-run
`install.sh` when a new skill folder appears, a new harness is detected, or
vendored assets need refreshing.

The bundled `update-skills.sh` does both in one shot, fails fast on uncommitted
changes, and prints which commits arrived:

```bash
bash <wherever-you-cloned-it>/update-skills.sh
```

It forwards extra arguments to `install.sh`, so project-scoped updates work the
same way:

```bash
bash <wherever-you-cloned-it>/update-skills.sh --project ~/some-repo
```

Or do it manually:

```bash
cd <wherever-you-cloned-it>
git pull
bash install.sh   # only if a new skill / harness / vendor asset
```

## Uninstall

`uninstall.sh` removes what the installer created: the skill symlinks in each
harness, the `close-day` slash command, and `~/.cortex/bin/cortex`. A wired
session-start hook is unwired first.

```bash
bash uninstall.sh
```

| Flag | Effect |
|------|--------|
| `--project [path]` | Remove a project-scoped install (defaults to `$PWD`) |
| `--dry-run` | Print every action; change nothing |
| `--purge-store` | **Also delete your work data** in `~/.cortex/`. Requires typed confirmation |
| `--yes` | Skip that confirmation. Refused without sync unless passed twice |

**Your work data is never touched without `--purge-store`.**

Only symlinks pointing into this repo are removed; a real directory, or a
symlink into another checkout, is reported and left in place. Removing the
`PATH` line from your shell rc is the one manual step left.

## Opt-in session-start injection

Off by default. `cortex inject enable --wire-hook claude-code` wires a Claude
Code `SessionStart` hook that injects the active workspace's knowledge index,
workbench, and open tasks at session start. Per-workspace opt-in via a sentinel;
`cortex inject disable --unwire-hook claude-code` reverses it. See
`skills/cortex-inject/SKILL.md`. This is the family's single exception to
its otherwise pull-based, no-auto-injection design.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, how to run the five test
suites, and the commit conventions. Note that PR titles are gated on
[Conventional Commits](https://www.conventionalcommits.org/), because this repo
squash-merges and the title becomes the commit on `main`.

## State data vs skill code

These skills are the **code**. Your actual session/task data lives in `~/.cortex/` on each machine. If you enable `cortex-sync`, that data is synced via a separate private repo (created by `cortex sync setup`). This repo contains no personal work data.
