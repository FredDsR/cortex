# The `cortex` CLI

One command fronts the whole family. Every verb runs through the self-contained
`cortex` Python package; the former per-skill bash and Python CLIs are retired.

```
cortex kb    <command>   Author and query knowledge / workbench docs
cortex viz   <command>   Build and serve the visual dashboard
cortex query <command>   Query the work graph
cortex inject <command>  Opt-in session-start injection
cortex sync  <command>   Sync the store to a private repo
cortex migrate-store     Move a legacy ~/.work store to ~/.cortex
```

Installed at `~/.cortex/bin/cortex`. Add that directory to `PATH`.

Most commands resolve the workspace and session from the active session pointer,
so you rarely pass `--workspace` or `--session` by hand. Pass them when no
active session can be resolved, or when a slug is ambiguous.

---

## cortex kb

Authors the knowledge base. See [skills.md](skills.md#cortex-kb) for when to
reach for knowledge versus workbench.

```
cortex kb new    knowledge|workbench <slug> [flags]
cortex kb update knowledge|workbench <slug> [flags]
cortex kb index  [--workspace W] [--session S] [--max N] [--write]
cortex kb ingest [--from SRC] [--workspace W] [--write] [--only openapi|sql] [--max N]
```

**`new` is create-only** and errors with `already exists` if the file is there.
**`update` is modify-only** and errors if it is not. The split is deliberate: an
agent cannot silently clobber a note it meant to create.

`new` and `update` share these flags:

| Flag | Default | Notes |
|------|---------|-------|
| `--workspace <ws>` | active session pointer | Required if no active session resolves |
| `--session <sess>` | active session pointer | Workbench only |
| `--author human\|agent` | `agent` | Becomes `human` if `--open` is passed without `--author` |
| `--title <text>` | unset | Frontmatter title |
| `--type <text>` | unset | Frontmatter type, e.g. `Gotcha`, `Decision`, `Reference` |
| `--description <text>` | unset | One-line summary; this is what the index shows |
| `--body <text>` | empty | Inline body |
| `--body-from <file\|->` | unset | Read body from a file, or `-` for stdin |
| `--open` | off | After writing, `exec $EDITOR` |

```bash
# a note written by an agent, body piped in
echo "Auth tokens expire after 15m, not 60m as the docs claim." |
  cortex kb new knowledge token-expiry \
    --type Gotcha --description "Token TTL is 15m despite the docs"

# open one in your editor instead
cortex kb new knowledge api-design --open
```

**`index`** regenerates `INDEX.md` from the entries present. It is a dry run
until you pass `--write`.

**`ingest`** reads a source (a codebase, an OpenAPI spec, SQL schemas) and
writes knowledge entries into a workspace. Also dry-run by default; `--only`
narrows the extractors, `--max` bounds how much it writes.

---

## cortex query

```
cortex query neighbors <slug> [--workspace W] [--session S] [--kind task|knowledge|workbench] [--max N]
```

Prints a document's forward links and backlinks, grouped by edge kind with a
one-line summary each, plus its unresolved `[[...]]` ghost references.

This exists so an agent can expand context on demand without opening the viewer
or reading whole files. `--max` defaults to 20.

```bash
cortex query neighbors token-expiry
```

---

## cortex viz

```
cortex viz build [workspaces_root] [--out OUT]
cortex viz serve [out_dir] [--host H] [--port P] [--no-open] [--edit] [--workspaces-root R]
```

`build` generates a static site. `serve` serves a built directory and opens a
browser, unless `--no-open`.

**`--edit` is the one flag that grants write access.** Without it, `serve` is a
plain static file handler with no ability to modify anything. With it, you get
in-browser editing against the real store, bound to localhost.

```bash
cortex viz build --out ~/cortex-site
cortex viz serve --port 8080 --no-open
```

---

## cortex inject

```
cortex inject enable  [--workspace W] [--wire-hook <harness>]
cortex inject disable [--workspace W] [--unwire-hook <harness>]
cortex inject status  [--workspace W]
cortex inject here    [--format text|claude-code] [--workspace W] [--session S] [--max N]
```

Injection requires **two** independent guards, and either one alone injects
nothing:

1. the harness session-start hook is wired, and
2. the workspace has a `.inject-enabled` sentinel.

`here` is the universal renderer. It prints the byte-bounded `<cortex-index>`
block to stdout, or prints nothing when a guard is unmet. Any harness, skill, or
person can call it, which is what makes the feature portable rather than
Claude-Code-specific.

See [hooks-and-plugins.md](hooks-and-plugins.md) for the wiring details.

**Note:** `disable` removes the workspace's sentinel as well as unwiring the
hook, so it changes store state, not just harness config.

---

## cortex sync

```
cortex sync setup    # one-shot bootstrap: clone, create, or skip
cortex sync status   # enabled state + origin
cortex sync push "<message>"
cortex sync pull
```

Replicates `~/.cortex/` to a private git repo. `setup` runs once and records the
outcome; later invocations trust it.

**Every subcommand no-ops when sync is unavailable**, which is why the tracking
skill can call `push` at every write checkpoint without checking first.

If `pull` reports `SUMMARY.md regenerate-needed`, a summary was resolved to
upstream and must be rebuilt from its `tasks/*.md`.

---

## cortex migrate-store

```
cortex migrate-store           # dry run: shows what would move
cortex migrate-store --write   # perform the move
```

Moves a legacy `~/.work` store to `~/.cortex`. Idempotent and conflict-safe, and
it merges cleanly with the `~/.cortex/bin` scaffold that `install.sh` creates.

Only relevant if you used this project before the cortex rename.
