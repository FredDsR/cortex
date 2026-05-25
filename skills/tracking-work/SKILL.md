---
name: tracking-work
description: Tracks tasks, priorities, status, blockers, and progress across concurrent agent sessions, using ~/.work/ (global) or <repo>/.work/ (local). Use when the user mentions tasks, priorities, status, blockers, overview, "where are we", or starts non-trivial work that spans multiple steps.
---

# Tracking Work

## Overview

A composable, file-based workflow for tracking work across sessions and workspaces. Supports:

- A **global store** at `~/.work/workspaces/<slug>/` (default) so tracking is not tied to any one repo.
- An **optional local store** at `<repo>/.work/` when the user wants to commit session state alongside code.
- **Concurrent agents:** one `.active.<session-id>` pointer per agent/shell, resolved by a layered ID algorithm.
- **Any runtime:** works with Claude Code, Copilot CLI, Codex, or a plain shell. No hard dependency on a specific harness.

Sub-skills handle optional concerns:

- `tracking-work-github` — PR/commit sync when a session has a `github:` field.
- `tracking-work-migration` — per-session moves between local and global stores.
- `tracking-work-sync` — cross-device sync of `~/.work/` via a private GitHub repo (opt-in).
- `tracking-work-kb`: authors `knowledge/<slug>.md` and `workbench/<slug>.md` via the `work-kb` CLI.

## When to Use

Triggers:
- User mentions tasks, priorities, status, overview, blockers, "where are we"
- User starts work that clearly spans multiple steps, commits, PRs, docs, or research artifacts
- User asks to "track" something or "remember" ongoing work
- User returns to a project after a break and needs orientation

Not for: one-off questions, single-commit fixes, pure Q&A about existing code.

## Session Start Flow

On trigger, run the bundled bootstrap. It resolves slug + session id, sweeps stale active pointers, conditionally pulls sync, and emits a structured header followed by the session list:

```bash
bash "$HOME/.claude/skills/tracking-work/scripts/session_start.sh"
```

Output shape (TAB-separated):

```
WORKSPACE\t<slug>
SESSION_ID\t<id>\t<source-tag>
SYNC\t<ok|regenerate-needed|conflict|not-installed|disabled|error rc=N>
SESSIONS
<origin>\t<session-slug>\t<mtime>\t<active-ids-csv>
...
```

Then decide:

1. **Collision (`session_start.sh` exits 2).** Read the existing CWD from its stderr and prompt using the wording in `slug-resolution.md`. Write the chosen slug into `~/.work/workspaces/<chosen>/.meta` with `cwd: <current>` before retrying.
2. **No sessions.** Ask the user if they want to start tracking. If yes, prompt for slug + global-vs-local store. Create `sessions/<slug>/SUMMARY.md` from the template and set `.active.<id>`.
3. **One session.** Summarize it. Ask continue/switch/new.
4. **Multiple sessions.** Render the `list_sessions.sh` output — tag each line with origin (`[local]` / `[global]`) and any active markers (`[claude:...]`, `[copilot:...]`, etc.). Ask which to continue or whether to start a new one.
5. **Other agent owns an `.active.<id>` in this workspace.** Surface it in the prompt so the user knows a concurrent session is active. Never overwrite another agent's `.active` file — always write only your own `.active.<SID>`.

## Checkpoint Rules

| Trigger | Action |
|---------|--------|
| Session start | Run `session_start.sh` (above). If the session has a `github:` frontmatter field, invoke `tracking-work-github` for drift detection. If `SYNC` is `regenerate-needed` or `conflict`, follow the protocol in `tracking-work-sync/SKILL.md`. |
| After a `git commit` on a tracked branch | Append commit subject to the active task's **Scope** or **Notes**. |
| User asks "overview" / "status" / "where are we" | Run `bash $SKILL_DIR/scripts/manifest.sh` for a one-row-per-task TSV snapshot; only read individual task files for In-Progress / Blocked items. Regenerate SUMMARY.md from tasks/ + `git log` (if a repo) only when the user asks for a full rewrite. If GitHub is configured, also invoke `tracking-work-github`. |
| New work mentioned | Create `tasks/<slug>.md`, add to SUMMARY.md **Open** bucket. If multiple active sessions exist, ask which session. |
| User says "blocked on X" | Add to SUMMARY.md **Blockers**, set task frontmatter `status: Blocked`. |
| Blocker resolves | Remove from **Blockers**, unset **Blocked** on dependents. |
| User asks to move a session between stores | Invoke `tracking-work-migration`. |
| After any write to `tasks/*.md` or `SUMMARY.md` | Run `commit_push.sh "<track: ... message>"`. |
| `pull.sh` prints `SUMMARY.md regenerate-needed` | Regenerate the affected SUMMARY.md from its `tasks/*.md`. |
| On session close (after archive move) | Run `commit_push.sh "track: archive session <slug>"`. |

All `tracking-work-sync/scripts/*` no-op when sync is unavailable, so checkpoints call them unconditionally. Full path: `$HOME/.claude/skills/tracking-work-sync/scripts/`.

## Closing a Session

Explicit action only. When the user says "close session X" / "X is done" / "archive X":

1. List tasks that are not **Resolved**.
2. For each, ask: mark Resolved, leave Open, or move to another session (existing or new).
3. If a move targets a new session, prompt for slug + store.
4. Update the closing session's SUMMARY frontmatter: set `closed: YYYY-MM-DD` and `status: Closed`.
5. Move `sessions/<slug>/` to `archive/YYYY-MM-DD-<slug>/` in the same store it lived in.
6. Delete any `.active.<id>` file pointing at the closed session.

## GitHub Integration (optional)

If a session's SUMMARY.md has a `github: <owner>/<repo>` frontmatter field, invoke `tracking-work-github` for PR sync. Otherwise skip entirely — `gh` is not needed for non-code workspaces.

## Local vs Global Store

- **Global is the default.** Use it unless the user explicitly wants to commit tracking files.
- **Local store** is opt-in — ask on session creation: *"Track this session globally in `~/.work/` or locally in `<repo>/.work/` (git-committable)?"*. Default = global.
- `list_sessions.sh` merges both; the skill tags each session with origin.
- **Never auto-migrate.** Migration is explicit via `tracking-work-migration`.

## Sync (optional)

First-run bootstrap only: if `~/.claude/skills/tracking-work-sync/` is installed and `~/.work/` is neither a git repo nor contains a `.sync-disabled` sentinel, invoke `setup.sh` once. The user picks clone / create / skip; subsequent invocations trust the recorded state.

See the sub-skill's SKILL.md for invocation contracts at each checkpoint.

## What This Skill Does Not Do

- Replace GitHub Issues / JIRA — tickets remain canonical
- Auto-commit tracking files — the user decides
- Enforce priorities, story points, or estimates — free-form fields
- Use hooks or background automation
- Require a specific agent runtime — works wherever `bash` + the scripts run

## References

- `file-layout.md` — SUMMARY / task / `.active` / `.meta` formats
- `slug-resolution.md` — workspace slug algorithm + collision prompt
- `session-id-resolution.md` — session ID layered resolver
- `templates/` — starter SUMMARY.md and task.md
- `scripts/manifest.sh`: one-row-per-task TSV; cheap snapshot for status questions.
- `scripts/migrate_to_frontmatter.py`: one-shot legacy bold-pair to YAML frontmatter migrator.
