# The skills

Seven skills ship in this repo, but they are not seven things you need to
learn. Three are entry points you trigger; four are sub-skills that
`cortex-tracking` calls when it needs them.

| Skill | You trigger it | What it does |
|-------|:--------------:|--------------|
| [cortex-tracking](#cortex-tracking) | yes | Sessions, tasks, blockers, status |
| [cortex-kb](#cortex-kb) | yes | Writes knowledge and workbench notes |
| [cortex-viz](#cortex-viz) | yes | Builds the browsable dashboard |
| [cortex-github](#cortex-github) | no | Syncs tasks with PR state |
| [cortex-sync](#cortex-sync) | no | Replicates the store across machines |
| [cortex-migration](#cortex-migration) | no | Moves a session between stores |
| [cortex-inject](#cortex-inject) | on request | Wires the opt-in session-start hook |

The four in the lower half declare "Use only when invoked by cortex-tracking"
in their descriptions. You can call them directly, but the normal path is that
you never think about them.

---

## cortex-tracking

**The entry point.** Everything else hangs off this one.

**Triggers on:** tasks, priorities, status, blockers, overview, "where are we",
or starting work that clearly spans multiple steps, commits, or PRs. It
deliberately does *not* trigger on one-off questions or single-commit fixes.

**What happens on trigger.** It runs `session_start.sh`, which resolves your
workspace slug, resolves a session id for this particular agent, sweeps stale
pointers, conditionally pulls sync, and lists the sessions it found. Then it
either summarizes the one session, asks you to pick among several, or offers to
create the first one.

**Checkpoints.** The skill defines when it writes, rather than writing
constantly:

| Trigger | What it does |
|---------|--------------|
| Session start | Resolve workspace + session, list state, pull sync |
| After a commit on a tracked branch | Append the subject to the task's Scope or Notes |
| "overview" / "status" / "where are we" | Run `manifest.sh` for a cheap snapshot; only open In-Progress or Blocked task files |
| New work mentioned | Create `tasks/<slug>.md`, add it to SUMMARY's Open bucket |
| "blocked on X" | Record it in SUMMARY Blockers and set `status: Blocked` |
| Blocker resolves | Clear it from both places |
| Any write to tasks or SUMMARY | `cortex sync push` |
| "close the day" | The close-day routine: snapshot, propose, confirm once, write, sync |

**Two lifecycle routines worth knowing apart.** *Closing the day* saves
everything and signs off but never archives, so the session resumes tomorrow.
*Closing a session* is a separate, explicit act: it asks what to do with every
unresolved task, then moves the session to `archive/YYYY-MM-DD-<slug>/`.

**Known limitation.** `SKILL.md` line 40 hardcodes
`$HOME/.claude/skills/cortex-tracking/scripts/session_start.sh`, and lines 69
and 98 reference a `$SKILL_DIR` variable that is never defined anywhere in the
repo. On Claude Code with a symlink install this resolves fine. On a harness
that installs elsewhere it does not, and the agent has to infer the path.

---

## cortex-kb

**Writes durable notes.** Two kinds, differing in scope and lifetime:

- **knowledge** (`knowledge/<slug>.md`) is workspace-scoped. It outlives every
  session and is the right home for anything more than one task refers to.
- **workbench** (`workbench/<slug>.md`) is session-scoped. Drafts, scratch
  thinking, and notes that stop mattering when the session closes.

**Use it when** you want to record something durable, when a `[[knowledge/foo]]`
ghost link needs a real entry behind it, or when spec and plan output would
otherwise be dropped on the floor.

Entries carry frontmatter (`title`, `type`, `author`, `created`, `updated`,
`description`) and link to each other with `[[wikilinks]]`. A link to something
that does not exist yet is a **ghost**: the viewer draws it with a dashed
border, so unwritten notes are visible rather than silently missing.

Full flag reference in [cli.md](cli.md#cortex-kb).

---

## cortex-viz

**Renders the store as a browsable site.** Three panes: a collapsible tree, a
hub-and-spoke graph of typed links, and a rendered-markdown content pane.
Theme-aware, and read-only by default.

```bash
cortex viz build          # generate the static site
cortex viz serve          # build output on localhost, opens a browser
cortex viz serve --edit   # opt in to editing files from the browser
```

`--edit` is genuinely opt-in: without it the server is a plain static file
handler that cannot write anything.

---

## cortex-github

**Syncs task files against PR state**, using the `gh` CLI.

Runs only when a session's `SUMMARY.md` has a `github: <owner>/<repo>`
frontmatter field. Without that field it never fires, which is what keeps `gh`
from being a dependency for non-code workspaces. `cortex-tracking` invokes it
at session start for drift detection, and again on status checkpoints.

---

## cortex-sync

**Replicates `~/.cortex/` across machines** through a private git repo you own.

Entirely opt-in. `cortex sync setup` runs once and offers clone, create, or
skip. After that, `cortex-tracking` calls `push` and `pull` at its checkpoints,
and both no-op harmlessly when sync was never configured, so the checkpoints do
not need to check first.

The store repo is separate from this one. Your work data never lands in the
skills repo.

---

## cortex-migration

**Moves one session between the global and local stores.**

Global (`~/.cortex/workspaces/<slug>/`) is the default. Local
(`<repo>/.cortex/`) is for when you want session state committed with the code.
A session lives in one or the other, never both.

Migration is always per-session and always explicit. Nothing auto-migrates.

---

## cortex-inject

**Wires the opt-in session-start hook** and is the family's single exception to
its no-auto-injection design. Off by default, and it takes an explicit request
to turn on.

Covered in full in [hooks-and-plugins.md](hooks-and-plugins.md).

---

## How they connect

```
                      you
                       |
                cortex-tracking  ...... the entry point
                 /     |      \
                /      |       \
        cortex-kb  cortex-github  cortex-migration
            |          |
            |      (gh CLI, only with a github: field)
            |
            +--> knowledge/ + workbench/ files
                       |
                 cortex-viz  ...... renders them
                       |
                 cortex-sync  ...... replicates the whole store
```

The connections that actually matter:

**`cortex-kb` writes, `cortex-viz` reads.** They share one file layout, so
anything the first creates the second can render without translation.

**`cortex-sync` sits under everything.** It replicates the store as a whole, so
tasks, knowledge, and workbench notes travel together and stay consistent.
Every write checkpoint ends with the same `cortex sync push` call.

**`cortex-tracking` calls `cortex-kb`** at its knowledge checkpoints: capturing
a durable note, filling in a `[[knowledge/...]]` ghost link, or recording spec
and plan output.

**`cortex kb ingest` and `cortex-migration` are unrelated**, despite both
sounding like they move things. `ingest` reads a codebase and writes knowledge
into a workspace. `migration` moves a session between stores. Different verbs,
opposite directions, different data.
