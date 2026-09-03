# cortex-kb

Thin CLI for authoring `knowledge/<slug>.md` (workspace-scoped) and
`workbench/<slug>.md` (session-scoped) markdown files in the `~/.cortex/`
tracking store. Sibling to `cortex-viz`, which renders them.

## Install

The root `install.sh` registers this skill alongside the other
`cortex-tracking-*` skills.

## Usage

```bash
# Create a knowledge entry with structured frontmatter and body on stdin.
echo "## Decision: ..." | cortex kb new knowledge api-versioning \
    --type Decision --title "API versioning" --description "header-based" --body-from -

# Create a workbench note in the active session, then open in $EDITOR.
cortex kb new workbench draft-pr-description --open

# Modify an existing entry: change one field, bump `updated` (created preserved).
cortex kb update knowledge api-versioning --description "revised rationale"

# Pure touch: bump `updated` only, keep everything else.
cortex kb update knowledge api-versioning

# Compact, pull-based table of contents of what already exists.
cortex kb index                 # stdout
cortex kb index --write         # (re)generate derived knowledge/INDEX.md

# Bulk-ingest a codebase into the KB. --from reads the codebase, --workspace
# writes the KB. Dry-run first (plans, writes nothing), then --write.
cortex kb ingest --from ./my-service --workspace my-ws          # dry-run plan
cortex kb ingest --from ./my-service --workspace my-ws --write  # create docs

# Audit the store: broken refs, dead code references, orphans, stale dates,
# missing descriptions. Report-only; --fix repairs mistyped addresses only.
cortex kb lint                              # every check, current workspace
cortex kb lint --check broken-ref --fix     # repair addresses that resolve elsewhere

# Explicit workspace when ambiguous.
cortex kb new knowledge cross-project-note --workspace personal
```

`ingest` deterministically documents OpenAPI and SQL DDL; fuzzier sources
(Prisma, README `## API`/`## Schema`, runbooks) come back as an agent worklist.
It never overwrites existing docs. This is unrelated to `cortex-migration`
(which moves a session between stores).

Frontmatter fields: `title`, `type`, `author`, `created`, `updated`,
`description` (only `author`/`created`/`updated` are always present). `type` is
a documented convention (`Decision`, `Design`, `Reference`, `Runbook`,
`Investigation`, `Convention`, `Comparison`; custom values allowed).

See `SKILL.md` for the agent-facing contract and full resolution rules.

## Tests

The kb commands live in the `cortex` engine and are tested there:

```bash
.venv/bin/python -m pytest cortex/tests -q
```
