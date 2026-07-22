---
name: cortex-sync
description: Use only when invoked by cortex-tracking to sync ~/.cortex/ across devices via a private GitHub repo. Handles one-shot bootstrap and per-checkpoint pull/push.
---

# cortex-sync

Optional sub-skill of `cortex-tracking`. Syncs the user's global store at `~/.cortex/` across devices using git + a private GitHub repo. Entirely opt-in. All behavior is fronted by the `cortex sync` CLI subcommands.

## When to Invoke

Only invoked by the main `cortex-tracking` skill at these checkpoints:

| Caller situation | This skill's action |
|---|---|
| First run on a device, `~/.cortex/` unconfigured, no `.sync-disabled` sentinel | Run `cortex sync setup` (interactive, or `--skip` / `--clone URL` / `--init`) once. |
| Session start, after `sweep_active.sh` | Run `cortex sync pull`. |
| After any write to `tasks/<slug>.md` or `SUMMARY.md` | Run `cortex sync push "<message>"`. |
| After session close (archive move) | Run `cortex sync push "track: archive session <slug>"`. |

Every `cortex sync` subcommand no-ops cleanly when sync is not enabled (`cortex sync status` reports the current state).

## State

Three states, reported via `cortex sync status`:

- **Enabled** the store is a git repo with an `origin` remote and no `.sync-disabled` sentinel. `cortex sync status` exits 0.
- **Disabled by sentinel** `~/.cortex/.sync-disabled` is present. `cortex sync status` exits 1. User chose "local only" during setup.
- **Unconfigured** neither of the above. `cortex sync status` exits 1. Main skill should run `cortex sync setup` once.

## Commit message convention

`track: <verb> <session>/<task>`, e.g. `track: open task fix-auth in refactor-api`, `track: update summary for refactor-api`, `track: archive session refactor-api`.

## Conflict handling

- `SUMMARY.md` conflicts are auto-resolved by `cortex sync pull` (it accepts the upstream side), then prints `cortex-sync: SUMMARY.md regenerate-needed` so the caller knows to regenerate. Since SUMMARY is derived from task files, this is safe.
- Task-file conflicts are surfaced. `cortex sync pull` exits 2 with a list of conflicting paths; the caller surfaces them to the user for manual resolution.

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
- `viz/` is `cortex-viz` output (per-workspace HTML and `vendor/` JS+CSS). Fully regenerable from `cortex viz` + `install.sh`, so syncing it just bloats the repo.

**Retrofitting an existing sync repo** (one already initialised before `viz/` was ignored):

```bash
# Append the line if missing.
grep -qxF 'viz/' ~/.cortex/.gitignore || printf '\nviz/\n' >> ~/.cortex/.gitignore
git -C ~/.cortex rm --cached -r viz/ 2>/dev/null || true
cortex sync push "track: stop syncing cortex-viz output (gitignore viz/)"
```

Files stay on disk locally; only the index entries are removed.

## Tests

Behavior is covered by `cortex/tests/test_sync.py` (the gate, push to a local origin, and clean/`SUMMARY`-resolve pulls), using tempdir git repos with no real GitHub calls.

## References

- Design: `docs/2026-04-23-design.md`
- Plan: `docs/2026-04-23-plan.md`
