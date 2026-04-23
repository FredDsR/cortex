---
name: tracking-work-migration
description: Use only when invoked by tracking-work to move a session between the global store (~/.work/workspaces/<slug>/) and a repo-local store (<repo>/.work/). Per-session, explicit, never implicit.
---

# Tracking Work — Migration

Invoked by the core `tracking-work` skill when the user asks to move a session between stores. Never moves data on its own.

## When to Invoke

- User says "move this session to git" / "track this locally" → migrate global → local
- User says "move this session out of the repo" / "make it personal" → migrate local → global
- User picks a `[local]` session on session start and explicitly chooses "migrate to global"

## Procedure

Given a session at `<src-store>/sessions/<slug>/` moving to `<dst-store>/sessions/<slug>/`:

1. Confirm with the user: **"Move `<slug>` from `<src-store>` to `<dst-store>`? (yes/no)"**. Show both paths absolute.
2. Fail if `<dst-store>/sessions/<slug>/` already exists. Ask user whether to pick a new slug or cancel.
3. `mv <src-store>/sessions/<slug> <dst-store>/sessions/<slug>`.
4. If migrating **away from a local store**, leave a tombstone so a teammate pulling the branch sees why the session folder is gone:

   ```
   <src-store>/sessions/<slug>/MOVED.md
   ```

   Content:
   ```markdown
   This session moved to the global store on YYYY-MM-DD.
   New path: ~/.work/workspaces/<workspace-slug>/sessions/<session-slug>/

   If you're on a different machine, recreate the session locally or ask the author.
   ```

5. `.active.<id>` files store the session slug (not a path), and the slug is unchanged by migration within the same workspace, so no update is needed as long as the agent stays in that workspace.
6. Report the new absolute path to the user.

## Never

- Never migrate without an explicit confirmation prompt.
- Never migrate archived sessions.
- Never migrate if both stores have a session with the same slug — require disambiguation first.
