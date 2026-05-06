# tracking-work skills

Portable bundle of file-based work-tracking skills for AI coding agents. Designed to work with any harness that reads `SKILL.md` from a skills directory: Claude Code, Codex, Copilot CLI, Gemini CLI.

## Skills in this repo

| Skill | Purpose |
|---|---|
| `tracking-work` | Main skill — file-based session/task tracking across workspaces, with global + local stores and concurrent-agent support. |
| `tracking-work-github` | Optional PR/commit drift detection via the `gh` CLI, invoked by the main skill when a session has `github:` frontmatter. |
| `tracking-work-migration` | Move a session between the global store (`~/.work/`) and a repo-local store. |
| `tracking-work-sync` | Optional cross-device sync of `~/.work/` via a private GitHub repo. See `skills/tracking-work-sync/docs/` for design. |
| `tracking-work-viz` | Browser-based viewer for `~/.work/`: three-pane tree + Cytoscape graph + rendered markdown, plus a cross-workspace dashboard. Ships a `work-viz` CLI with one-shot, `--watch`, `serve`, and `--workspace=all` modes. |

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
    rm -f "$h/skills/tracking-work"{,-github,-migration,-sync}
done
```

## State data vs skill code

These skills are the **code**. Your actual session/task data lives in `~/.work/` on each machine. If you enable `tracking-work-sync`, that data is synced via a separate private repo (created by `skills/tracking-work-sync/scripts/setup.sh`). This repo contains no personal work data.
