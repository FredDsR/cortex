---
name: tracking-work-sync
description: Use only when invoked by tracking-work to sync ~/.work/ across devices via a private GitHub repo. Handles one-shot bootstrap and per-checkpoint pull/push.
---

# tracking-work-sync

Optional sub-skill of `tracking-work`. Syncs the user's global store at `~/.work/` across devices using git + a private GitHub repo. Entirely opt-in.

## When to Invoke

Only invoked by the main `tracking-work` skill at these checkpoints:

| Caller situation | This skill's action |
|---|---|
| First run on a device, `~/.work/` unconfigured, no `.sync-disabled` sentinel | Run `scripts/setup.sh` (interactive) once. |
| Session start, after `sweep_active.sh` | Run `scripts/pull.sh`. |
| After any write to `tasks/<slug>.md` or `SUMMARY.md` | Run `scripts/commit_push.sh "<message>"`. |
| After session close (archive move) | Run `scripts/commit_push.sh "track: archive session <slug>"`. |

Every script no-ops cleanly when sync is not enabled (see `scripts/is_enabled.sh`).

## State

Three states, detected via `scripts/is_enabled.sh`:

- **Enabled** — `~/.work/` is a git repo with an `origin` remote and no `.sync-disabled` sentinel. `is_enabled.sh` exits 0.
- **Disabled by sentinel** — `~/.work/.sync-disabled` is present. `is_enabled.sh` exits 1. User chose "local only" during setup.
- **Unconfigured** — neither of the above. `is_enabled.sh` exits 1. Main skill should invoke `setup.sh` once.

## Commit message convention

`track: <verb> <session>/<task>` — e.g. `track: open task fix-auth in refactor-api`, `track: update summary for refactor-api`, `track: archive session refactor-api`.

## Conflict handling

- `SUMMARY.md` conflicts — auto-resolved by `pull.sh` (accepts upstream side), then prints `tracking-work-sync: SUMMARY.md regenerate-needed` so the caller knows to regenerate. Since SUMMARY is derived from task files, this is safe.
- Task-file conflicts — surfaced. `pull.sh` exits 2 with a list of conflicting paths; the caller surfaces them to the user for manual resolution.

## Files ignored from sync

See `templates/gitignore`:

```
.active.*
.meta
viz/
```

Rationale:

- `.active.<session-id>` is per-agent/shell and has no cross-device meaning.
- `.meta` holds a machine-specific `cwd:` path.
- `viz/` is `tracking-work-viz` output (per-workspace HTML and `vendor/` JS+CSS). Fully regenerable from `work-viz` + `install.sh`, so syncing it just bloats the repo.

**Retrofitting an existing sync repo** (one already initialised before `viz/` was ignored):

```bash
# Append the line if missing.
grep -qxF 'viz/' ~/.work/.gitignore || printf '\nviz/\n' >> ~/.work/.gitignore
git -C ~/.work rm --cached -r viz/ 2>/dev/null || true
bash $HOME/.claude/skills/tracking-work-sync/scripts/commit_push.sh \
  "track: stop syncing tracking-work-viz output (gitignore viz/)"
```

Files stay on disk locally; only the index entries are removed.

## Tests

`tests/run_all.sh` runs all tests. Tests use tempdirs and a fake `gh` (see `tests/helpers.sh`) — no real GitHub calls and no dependency on `~/.work/`.

## References

- Design: `docs/2026-04-23-design.md`
- Plan: `docs/2026-04-23-plan.md`
