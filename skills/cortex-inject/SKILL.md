---
name: cortex-inject
description: Use only when the user explicitly opts into session-start context injection ("orient me at session start", "auto-load what we know", "inject the index"). Wires a strictly opt-in, off-by-default hook that injects a workspace's knowledge index + workbench + open tasks via the `cortex inject` CLI. The single exception to the family's no-auto-injection philosophy.
---

# cortex-inject

Strictly opt-in session-start injection. Off by default. This is the ONE
exception to the cortex-tracking family's no-auto-injection philosophy, and it
stays an exception: never enable it without an explicit user request.

## Two guards, both required

Injection happens only when BOTH are true:

1. The harness session-start hook is wired (per harness, global, one-time).
2. The resolved workspace has a sentinel: `~/.work/workspaces/<slug>/.inject-enabled`.

Either guard alone injects nothing. This is what keeps it off by default.

## Commands

```
cortex inject enable  [--workspace W] [--wire-hook <harness>]
cortex inject disable [--workspace W] [--unwire-hook <harness>]
cortex inject status  [--workspace W]
cortex inject here    [--format text|claude-code] [--workspace W] [--session S] [--max N]
```

- `cortex inject here` is the universal renderer: it prints the byte-bounded
  `<tracking-work-index>` block (knowledge index + active workbench + open or
  in-progress tasks) to stdout, or nothing when a guard is not satisfied. Any
  harness, skill, or human can call it.
- Enable in a tracked repo, wiring Claude Code in one line:
  `cortex inject enable --wire-hook claude-code`.
- Reverse it: `cortex inject disable --unwire-hook claude-code`.

## Harness support

- **Claude Code** (v1, auto-wired): `--wire-hook claude-code` idempotently adds a
  `SessionStart` hook (matcher `startup|clear|compact`) to `~/.claude/settings.json`
  that runs `cortex inject here --format=claude-code`.
- **Other harnesses** (Codex, Copilot, Gemini): no adapter yet. Recipe: add that
  harness's session-start hook to run `cortex inject here` and inject its stdout.
  A native adapter is added by registering one in `cortex/inject.py`.

## Refresh

Injected context is a snapshot taken at session start (and at `/clear` / compact,
which are in the matcher). It does NOT live-update mid-session. Run `/clear` to
refresh after writing new knowledge or tasks.

## When to offer

If a workspace resolves and `cortex inject status` shows the hook is not wired,
you MAY offer to enable it. Never auto-enable.
