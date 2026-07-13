# cortex

Portable bundle of file-based work-tracking skills for AI coding agents. Designed to work with any harness that reads `SKILL.md` from a skills directory: Claude Code, Codex, Copilot CLI, Gemini CLI.

One CLI fronts the whole family: **`cortex`** (`cortex kb ...` to author knowledge, `cortex viz ...` to visualize, `cortex query neighbors <slug>` to explore a doc's links). Internally the skills are still named `tracking-work-*`.

> **Migration:** the former `work-kb` / `work-viz` bins are replaced by `cortex kb` / `cortex viz`. Re-run `install.sh` to pick up the `cortex` bin (the old bins are removed). To bring an existing `~/.work/` store up to the current knowledge frontmatter, run `skills/tracking-work-kb/scripts/migrate_kb_frontmatter.py` (dry-run by default; `--write` to apply).

## Skills in this repo

| Skill | Purpose |
|---|---|
| `tracking-work` | Main skill — file-based session/task tracking across workspaces, with global + local stores and concurrent-agent support. |
| `tracking-work-github` | Optional PR/commit drift detection via the `gh` CLI, invoked by the main skill when a session has `github:` frontmatter. |
| `tracking-work-migration` | Move a session between the global store (`~/.work/`) and a repo-local store. |
| `tracking-work-sync` | Optional cross-device sync of `~/.work/` via a private GitHub repo. See `skills/tracking-work-sync/docs/` for design. |
| `tracking-work-viz` | Browser-based viewer for `~/.work/`: three-pane tree + Cytoscape graph + rendered markdown, plus a cross-workspace dashboard. Ships a `cortex viz` CLI with one-shot, `--watch`, `serve`, and `--workspace=all` modes. |
| `tracking-work-kb` | Author and bulk-ingest knowledge/workbench docs (`cortex kb` CLI): structured frontmatter, a pull-based index, and codebase ingestion. Rendered by `tracking-work-viz`, replicated by `tracking-work-sync`. |

## Knowledge base

Beyond sessions and tasks, a workspace can hold durable notes. `tracking-work-kb`
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
- **`cortex kb ingest`.** Bulk-ingest a codebase into a workspace's `knowledge/`:
  a deterministic path documents OpenAPI/Swagger and SQL DDL, and everything
  fuzzier (Prisma, README `## API` / `## Schema` sections, runbooks, model dirs)
  is surfaced as an agent worklist. Dry-run by default; `--write` is the gate;
  existing docs are never overwritten. `--from <src>` names the codebase to read,
  `--workspace <dest>` the KB to write.

### How the skills connect

- `cortex kb` **writes** knowledge/workbench docs; `tracking-work-viz` **renders**
  them (tree, graph, content, with the frontmatter fields above); and
  `tracking-work-sync` **replicates** the whole `~/.work/` store. All three
  share one file layout and the same `commit_push.sh` sync hook.
- The main `tracking-work` skill invokes `tracking-work-kb` at its knowledge
  checkpoints (capturing durable notes, resolving `[[knowledge/...]]` ghost
  links, recording spec/plan output).
- `cortex kb ingest` reads a codebase and writes into a KB workspace. It is
  unrelated to `tracking-work-migration`, which **moves a session** between the
  global and local stores. Different verbs, opposite direction, different data.

## Install

### Primary path — symlink install (any harness)

Clone anywhere, then run `install.sh`. It detects which agent harnesses you have on this device (by probing `~/.claude/`, `~/.codex/`, `~/.copilot/`, `~/.gemini/`) and symlinks each skill into their respective `skills/` directories.

```bash
git clone git@github.com:FredDsR/tracking-work-skills.git ~/tracking-work-skills
bash ~/tracking-work-skills/install.sh
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
bash /path/to/tracking-work-skills/install.sh --project            # defaults to $PWD
bash /path/to/tracking-work-skills/install.sh --project ~/some-repo  # or explicit path
```

Project-scoped install creates `<repo>/.claude/skills/`, `<repo>/.codex/skills/`, etc. as needed (but only for harnesses you already use globally, detected via presence of `$HOME/.<harness>/`). Re-run after `git pull` in the skills clone to refresh.

### Alternate path — Claude Code `/plugin` (experimental)

A `.claude-plugin/marketplace.json` + `plugin.json` are included so this repo is also addable as a Claude Code plugin marketplace:

```
/plugin marketplace add FredDsR/tracking-work-skills
/plugin install tracking-work
```

Note: some cross-skill invocations in the main skill hardcode `$HOME/.claude/skills/<sub-skill>/...` paths, so the symlink path is the first-class install. The plugin route is provided as a convenience for Claude-Code-only users who prefer the `/plugin` UX; behavior is best-effort.

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

Remove the symlinks in each harness's skills directory:

```bash
for h in ~/.claude ~/.codex ~/.copilot ~/.gemini; do
    rm -f "$h/skills/tracking-work"{,-github,-migration,-sync,-viz,-kb}
done
```

## State data vs skill code

These skills are the **code**. Your actual session/task data lives in `~/.work/` on each machine. If you enable `tracking-work-sync`, that data is synced via a separate private repo (created by `skills/tracking-work-sync/scripts/setup.sh`). This repo contains no personal work data.
