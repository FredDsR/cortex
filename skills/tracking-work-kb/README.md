# tracking-work-kb

Thin CLI for authoring `knowledge/<slug>.md` (workspace-scoped) and
`workbench/<slug>.md` (session-scoped) markdown files in the `~/.work/`
tracking store. Sibling to `tracking-work-viz`, which renders them.

## Install

The root `install.sh` registers this skill alongside the other
`tracking-work-*` skills.

## Usage

```bash
# Create a knowledge entry with structured frontmatter and body on stdin.
echo "## Decision: ..." | work-kb new knowledge api-versioning \
    --type Decision --title "API versioning" --description "header-based" --body-from -

# Create a workbench note in the active session, then open in $EDITOR.
work-kb new workbench draft-pr-description --open

# Modify an existing entry: change one field, bump `updated` (created preserved).
work-kb update knowledge api-versioning --description "revised rationale"

# Pure touch: bump `updated` only, keep everything else.
work-kb update knowledge api-versioning

# Compact, pull-based table of contents of what already exists.
work-kb index                 # stdout
work-kb index --write         # (re)generate derived knowledge/INDEX.md

# Explicit workspace when ambiguous.
work-kb new knowledge cross-project-note --workspace personal
```

Frontmatter fields: `title`, `type`, `author`, `created`, `updated`,
`description` (only `author`/`created`/`updated` are always present). `type` is
a documented convention (`Decision`, `Design`, `Reference`, `Runbook`,
`Investigation`, `Convention`, `Comparison`; custom values allowed).

See `SKILL.md` for the agent-facing contract and full resolution rules.

## Tests

```bash
bash tests/run_all.sh
```
