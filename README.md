# tracking-work skills

Portable bundle of file-based work-tracking skills for AI coding agents. Designed to work with any harness that reads `SKILL.md` from a skills directory: Claude Code, Codex, Copilot CLI, Gemini CLI.

## Skills in this repo

| Skill | Purpose |
|---|---|
| `tracking-work` | Main skill — file-based session/task tracking across workspaces, with global + local stores and concurrent-agent support. |
| `tracking-work-github` | Optional PR/commit drift detection via the `gh` CLI, invoked by the main skill when a session has `github:` frontmatter. |
| `tracking-work-migration` | Move a session between the global store (`~/.work/`) and a repo-local store. |
| `tracking-work-sync` | Optional cross-device sync of `~/.work/` via a private GitHub repo. See `skills/tracking-work-sync/docs/` for design. |

## Install

Clone anywhere, then run `install.sh`. It detects which agent harnesses you have on this device (by probing `~/.claude/`, `~/.codex/`, `~/.copilot/`, `~/.gemini/`) and symlinks each skill into their respective `skills/` directories.

```bash
git clone git@github.com:FredDsR/tracking-work-skills.git ~/Workspace/agentic/tracking-work-skills
bash ~/Workspace/agentic/tracking-work-skills/install.sh
```

## Update

```bash
cd ~/Workspace/agentic/tracking-work-skills
git pull
# install.sh uses symlinks, so `git pull` alone is usually enough.
# Re-run install.sh only if a new skill directory was added or you added a new harness.
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
