---
name: tracking-work
description: Use when the user mentions tasks, priorities, status, blockers, overview, "where are we", progress tracking, work sessions, or starts non-trivial work that spans multiple steps. Tracks any kind of work (code, writing, research, ops) across concurrent agent sessions using a global store at ~/.work/ with optional per-repo stores.
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

## When to Use

Triggers:
- User mentions tasks, priorities, status, overview, blockers, "where are we"
- User starts work that clearly spans multiple steps, commits, PRs, docs, or research artifacts
- User asks to "track" something or "remember" ongoing work
- User returns to a project after a break and needs orientation

Not for: one-off questions, single-commit fixes, pure Q&A about existing code.

## Session Start Flow

On trigger, always run these commands first — they are cheap and return the state you need:

```bash
SKILL_DIR="$HOME/.claude/skills/tracking-work"
SYNC_DIR="$HOME/.claude/skills/tracking-work-sync"
SLUG="$(bash "$SKILL_DIR/scripts/resolve_workspace.sh")"  # may exit 2 on collision
SID="$(bash "$SKILL_DIR/scripts/resolve_session_id.sh" 2>/dev/null)"
bash "$SKILL_DIR/scripts/sweep_active.sh" "$HOME/.work/workspaces/$SLUG" 7 >/dev/null
# Pull remote changes before listing (no-op if sync not enabled or sub-skill absent).
[[ -x "$SYNC_DIR/scripts/pull.sh" ]] && bash "$SYNC_DIR/scripts/pull.sh"
bash "$SKILL_DIR/scripts/list_sessions.sh"
```

Then decide:

1. **Collision (`resolve_workspace.sh` exits 2).** Read the existing CWD from its stderr and prompt using the wording in `slug-resolution.md`. Write the chosen slug into `~/.work/workspaces/<chosen>/.meta` with `cwd: <current>` before continuing.
2. **No sessions.** Ask the user if they want to start tracking. If yes, prompt for slug + global-vs-local store. Create `sessions/<slug>/SUMMARY.md` from the template and set `.active.<id>`.
3. **One session.** Summarize it. Ask continue/switch/new.
4. **Multiple sessions.** Render the `list_sessions.sh` output — tag each line with origin (`[local]` / `[global]`) and any active markers (`[claude:...]`, `[copilot:...]`, etc.). Ask which to continue or whether to start a new one.
5. **Other agent owns an `.active.<id>` in this workspace.** Surface it in the prompt so the user knows a concurrent session is active. Never overwrite another agent's `.active` file — always write only your own `.active.<SID>`.

## Checkpoint Rules

| Trigger | Action |
|---------|--------|
| Session start | Run the commands above. If the session has a `github:` frontmatter field, invoke `tracking-work-github` for drift detection. |
| After a `git commit` on a tracked branch | Append commit subject to the active task's **Scope** or **Notes**. |
| User asks "overview" / "status" / "where are we" | Regenerate SUMMARY.md from tasks/ + `git log` (if a repo). If GitHub is configured, also invoke `tracking-work-github`. |
| New work mentioned | Create `tasks/<slug>.md`, add to SUMMARY.md **Open** bucket. If multiple active sessions exist, ask which session. |
| User says "blocked on X" | Add to SUMMARY.md **Blockers**, set task **Status: Blocked**. |
| Blocker resolves | Remove from **Blockers**, unset **Blocked** on dependents. |
| User asks to move a session between stores | Invoke `tracking-work-migration`. |
| After any write to `tasks/*.md` or `SUMMARY.md` | If `tracking-work-sync` is installed, run `$HOME/.claude/skills/tracking-work-sync/scripts/commit_push.sh "<message>"` with an appropriate `track: ...` message. |
| `pull.sh` prints `SUMMARY.md regenerate-needed` | Regenerate the affected SUMMARY.md from its `tasks/*.md`. |
| On session close (after archive move) | If sync is installed, run `commit_push.sh "track: archive session <slug>"`. |

## Closing a Session

Explicit action only. When the user says "close session X" / "X is done" / "archive X":

1. List tasks that are not **Resolved**.
2. For each, ask: mark Resolved, leave Open, or move to another session (existing or new).
3. If a move targets a new session, prompt for slug + store.
4. Update the closing session's SUMMARY with `Closed: YYYY-MM-DD` and `Session status: Closed`.
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

If `~/.claude/skills/tracking-work-sync/` is installed and `~/.work/` is neither a git repo nor contains a `.sync-disabled` sentinel, invoke `$HOME/.claude/skills/tracking-work-sync/scripts/setup.sh` once before continuing. The user picks clone / create / skip. After that, subsequent invocations trust the recorded state and never prompt again.

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
