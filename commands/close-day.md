---
description: Wrap up the active tracking-work session for the day — save work, update tasks and knowledge notes, sync, and sign off.
---

Invoke the `tracking-work` skill's **Closing the Day** routine for the current
workspace's active session(s).

Follow that routine exactly:

1. Run `close_day.sh` to snapshot the active session (tasks, commits since the
   session started, uncommitted changes, next workday).
2. If `STATUS` is not `ok`, tell me there's nothing to close and stop.
3. Propose — in a SINGLE batch for one confirmation — the task status/notes
   updates and any knowledge notes worth capturing, reconciled against what's
   already recorded.
4. On my confirmation, write the task/SUMMARY updates, create/update knowledge
   notes via `cortex kb`, run `commit_push.sh`, and sign off with the day-aware
   greeting ("see you tomorrow" / "see you Monday").

Do NOT archive or close the session — it stays active for tomorrow.
