# cortex docs

cortex is a file-based memory layer for AI coding agents. It keeps sessions,
tasks, and knowledge as plain markdown in a store your agent reads and writes,
so context survives between conversations and across machines.

Nothing here is a service. It is markdown files, a few bash scripts, and one
Python CLI.

## The guides

| Guide | Covers |
|-------|--------|
| [skills.md](skills.md) | All seven skills: what triggers each, and which ones you invoke versus which get invoked for you |
| [cli.md](cli.md) | The `cortex` command: `kb`, `viz`, `query`, `inject`, `sync`, `migrate-store` |
| [store.md](store.md) | The file layout: workspaces, sessions, tasks, knowledge, and the frontmatter each uses |
| [hooks-and-plugins.md](hooks-and-plugins.md) | The one optional hook, the Claude Code plugin manifests, and the `/close-day` command |

Installation lives in the [top-level README](../README.md).

## The idea in one paragraph

Your agent forgets everything between sessions. cortex gives it somewhere to
write things down: a **session** groups related work, **tasks** track individual
pieces of it, and **knowledge** entries capture things worth remembering after
the tasks are done. All of it is markdown on disk, addressed by slug, linked
with `[[wikilinks]]`. The agent reads it when you ask "where are we", writes to
it as work progresses, and the whole store can sync to a private git repo so
your other machine sees the same thing.

## Your first session

**1. Start work and say something that triggers tracking.** Any of "where are
we", "let's track this", or just beginning work that clearly spans several
steps will do. The `cortex-tracking` skill resolves which workspace you are in
(from the git remote or directory name) and lists any sessions it finds.

**2. Let it create a session.** With no sessions yet, it offers to start one.
You pick a slug, and it asks whether to store it globally in `~/.cortex/` or
locally in `<repo>/.cortex/`. Global is the default and is usually right; local
is for when you want tracking committed alongside the code.

**3. Work.** As tasks come up, the agent writes `tasks/<slug>.md` files and
keeps `SUMMARY.md` current. Say "blocked on X" and the blocker gets recorded on
both the task and the summary.

**4. Ask "where are we" later.** In this session or a week from now, the agent
reads the store back and tells you. This is the whole point.

**5. Capture what you learned.** When something is worth remembering past the
task, it becomes a knowledge entry through `cortex kb`. Tasks get closed and
archived; knowledge stays.

**6. Wrap up.** Say "close the day" and it saves everything, updates statuses,
writes any pending knowledge notes, and syncs. The session stays open so
tomorrow resumes where you stopped.

## What cortex will not do

It does not replace your issue tracker. GitHub Issues and JIRA remain
canonical; cortex tracks the *agent's* working state, which is a different and
much shorter-lived thing.

It does not automatically inject anything into your sessions. The agent reads
the store when a skill fires, not on every message. The single exception is
[opt-in session-start injection](hooks-and-plugins.md), which is off until you
explicitly turn it on.

It does not commit your tracking files for you. Whether the store is synced,
and when, is your call.
