# Hooks and plugins

Two separate things, often confused. **Hooks** are how a harness runs a command
automatically at some moment. **Plugins** are how a harness discovers and
installs the skills in the first place.

cortex ships exactly one hook, off by default, and it is the only automatic
behaviour in the entire family.

---

## The one hook: session-start injection

Normally the agent reads the store when a skill fires, and not before. That is
the design: pull, not push. Injection inverts it, putting your workspace's
knowledge index, active workbench, and open tasks into the context window at
session start, before you have said anything.

It is off until you explicitly turn it on, and turning it on takes two
independent steps.

### Both guards are required

```
1. The harness session-start hook is wired      (per harness, global, one-time)
2. The workspace has a .inject-enabled sentinel (per workspace)
```

Either alone injects nothing. That is what keeps it off by default even after
you have used it once somewhere else: wiring the hook globally does not opt in
any workspace, and opting in a workspace does nothing without the hook.

### Turning it on

```bash
cortex inject enable --wire-hook claude-code   # both guards at once
cortex inject status                           # sentinel state + wired harnesses
cortex inject disable --unwire-hook claude-code
```

On Claude Code, `--wire-hook` idempotently adds a `SessionStart` hook to
`~/.claude/settings.json` with matcher `startup|clear|compact`, running
`cortex inject here --format=claude-code`.

Note that `disable` removes the workspace sentinel **as well as** unwiring the
hook. If you only meant to unwire, be aware it also opts that workspace out.

### It is a snapshot, not a subscription

Injected context is captured at session start, and at `/clear` and compact,
since those are in the matcher. It does **not** update mid-session. After
writing new knowledge or tasks, `/clear` to refresh.

### Other harnesses

Only Claude Code has an adapter today. For anything else, the recipe is: have
that harness's session-start hook run `cortex inject here` and inject its
stdout. `here` prints plain text and is the universal renderer, so no adapter is
strictly required to use the feature. A native adapter is added by registering
one in `cortex/inject.py`.

---

## Plugins

### Claude Code

`.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json` make this
repo installable as a plugin marketplace:

```
/plugin marketplace add FredDsR/cortex
/plugin install cortex
```

The manifests declare the plugin id `cortex` and the marketplace name `cortex`.

**The symlink install stays first-class.** Some cross-skill invocations hardcode
`$HOME/.claude/skills/<sub-skill>/...`, paths that only the symlink install
produces, so the plugin route is best-effort. Use it if you prefer the `/plugin`
UX; use `install.sh` if you want everything to resolve.

### Antigravity

Antigravity reads `skills/` from the repo directly:

```bash
agy plugin install https://github.com/FredDsR/cortex
```

No manifest and no symlinks. Since cortex ships no session-start hook by
default, nothing auto-loads: skills are discovered and invoked on demand.

This path is documented from Antigravity's published behaviour and has not been
run against a real `agy` install. Confirm the skills are discoverable before
relying on it.

### Codex and Copilot CLI

Covered by `install.sh`, which symlinks each skill into `~/.codex/skills/` and
`~/.copilot/skills/`. No manifest involved.

---

## Slash commands

One command ships in `commands/`:

**`/close-day`** wraps up the active session: it snapshots the state, proposes
task and knowledge updates in a single batch, takes one confirmation, writes,
syncs, and signs off. It never archives, so tomorrow resumes where you stopped.

Plugin and marketplace installs pick up `commands/` natively. For symlink
installs, `install.sh` links it into `~/.claude/commands/` so `/close-day`
works there too.

The command is a convenience, not a requirement. Saying "close the day",
"that's all for today", or "wrapping up" triggers the same routine, and phrases
work on every harness while slash commands do not.
