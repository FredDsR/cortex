---
name: tracking-work-kb
description: Use when authoring workspace-scoped knowledge entries or session-scoped workbench drafts in the ~/.work knowledge base. Creates markdown files at the correct path with valid frontmatter; agents pass --body or pipe content via stdin.
---

# Tracking Work: Knowledge Base writes

Authors `knowledge/<slug>.md` (workspace-scoped) and `workbench/<slug>.md`
(session-scoped) markdown files in the `~/.work/` (global) or
`<repo>/.work/` (local) tracking store. Sibling skill to
`tracking-work-viz`, which renders the resulting files in the graph and
tree.

## When to use

- The user (or you, the agent) wants to record a durable note that other
  documents will reference.
- `[[knowledge/foo]]` appears in a task body as a ghost (unresolved) link
  and the user asks to create the missing entry.
- Spec, plan, or brainstorm output should be captured as a knowledge
  entry rather than dropped on the floor.

## CLI surface

```
work-kb new knowledge <slug> [flags]
work-kb new workbench <slug> [flags]
```

| Flag | Default | Notes |
|------|---------|-------|
| `--workspace <ws>` | from active session pointer | Required if no active session can be resolved |
| `--session <sess>` | from active session pointer | Workbench only |
| `--author <human\|agent>` | `agent` (or `human` if `--open` and `--author` not passed) | Must be one of `human`, `agent` |
| `--body <text>` | empty | Inline body |
| `--body-from <file\|->` | unset | File or stdin |
| `--open` | off | After write, `exec ${EDITOR:-vi}` |

## Agent invocation patterns

Capture an agent-generated note with the body inline:

```bash
work-kb new knowledge api-versioning-decision --body "$(cat <<'END'
## Decision

We will use header-based versioning for the public API.
END
)"
```

Pipe a longer body from stdin:

```bash
some-pipeline | work-kb new knowledge daily-summary --body-from -
```

Workbench note tied to the current session:

```bash
work-kb new workbench draft-pr-description --body-from /tmp/pr-draft.md
```

## Resolution rules

- Workspace discovery walks up from cwd (only within `$HOME`) to find a
  local `.work/` first; otherwise scans `~/.work/workspaces/*/` for the
  unique workspace that has any `.active.*` pointer. Errors if zero or
  multiple.
- Session discovery (workbench only) reads `.active.*` pointers in the
  resolved workspace and uses the unique session. Errors on ambiguity.
- The CLI never guesses on ambiguity. It always names the flag that
  resolves the conflict.

## Frontmatter

Both kinds emit the same two fields:

```yaml
---
author: <human|agent>
created: <YYYY-MM-DD>
---

<body>
```

The slug is the filename stem; no `slug:` field. Body is written
verbatim after the frontmatter. No automatic title insertion.

## Exit codes

- 0: success
- 1: missing context, invalid slug, file already exists
- 2: usage error (bad subcommand, bad flag)

## What this skill does NOT do

- Edit existing files. Use `$EDITOR`, or `work-kb new ... --open` for new
  files.
- List, show, mv, or rm. Use `ls`, `cat`, `git mv`, `rm`.
- Validate `[[...]]` references at write time. Broken refs surface in the
  viz as ghost nodes; existing behavior.
- Open the editor by default. Agent-primary CLI; `$EDITOR` opens only
  when `--open` is passed.

## Sync integration

After a successful write, calls
`$HOME/.claude/skills/tracking-work-sync/scripts/commit_push.sh` if
present and executable. No-op if sync is not installed or disabled.

## Tests

```bash
bash skills/tracking-work-kb/tests/run_all.sh
```

Each test sets up a temp `.work/`, invokes the binary with `HOME`
overridden, asserts file contents and exit codes, tears down. No
external dependencies.
