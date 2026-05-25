# tracking-work-kb

Thin CLI for authoring `knowledge/<slug>.md` (workspace-scoped) and
`workbench/<slug>.md` (session-scoped) markdown files in the `~/.work/`
tracking store. Sibling to `tracking-work-viz`, which renders them.

## Install

The root `install.sh` registers this skill alongside the other
`tracking-work-*` skills.

## Usage

```bash
# Create a knowledge entry in the active workspace, with body on stdin.
echo "## Decision: ..." | work-kb new knowledge api-versioning --body-from -

# Create a workbench note in the active session, then open in $EDITOR.
work-kb new workbench draft-pr-description --open

# Explicit workspace when ambiguous.
work-kb new knowledge cross-project-note --workspace personal
```

See `SKILL.md` for the agent-facing contract and full resolution rules.

## Tests

```bash
bash tests/run_all.sh
```
