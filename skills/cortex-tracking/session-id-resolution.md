# Session ID Resolution

Each agent/shell instance gets its own `.active.<id>` pointer so multiple concurrent sessions never overwrite each other's active state. IDs are resolved by `scripts/resolve_session_id.sh`.

## Resolution order (first match wins)

1. **`$WORK_SESSION_ID`** — explicit override. The documented escape hatch for any harness, including CI and plain shell. Set it manually or via harness config.
2. **Known harness env vars** — probed in order:
   - `CLAUDE_SESSION_ID`
   - `COPILOT_SESSION_ID`
   - `CURSOR_SESSION_ID`
   - `CODEX_SESSION_ID`
3. **Session-leader fingerprint** — walks to the session leader via `ps -o sid= -p $$`, then fingerprints `sid + process-start-time`, truncated to 12 hex chars. Stable across subshells and `$(...)` within the same terminal session (PPID is not — it shifts with each subshell).
4. **TTY fingerprint** — `sha1(tty + login-time)`, truncated to 12 hex chars.
5. **UUID lease** — persistent UUID in `$XDG_RUNTIME_DIR/work-lease` (or `/tmp/work-lease-$UID`). Generated on first miss, reused thereafter, cleared on reboot.

## Display conventions

The skill shows IDs with their source tag:

- `[env:abc123]`, `[claude:a3f9c1]`, `[copilot:xy9082]`
- `[ppid:e0d2f1]`, `[tty:def456]`
- `[lease:c91fa0]`

Note: the `ppid:` tag is retained for user-facing display even though the implementation anchors on the session leader (SID), not PPID — users think of it as "this shell/agent".

## Cleanup

`scripts/sweep_active.sh <workspace-dir> [days]` removes `.active.*` files older than N days (default 7). Run opportunistically at session start.

No liveness probing — that would reintroduce harness-specific code.

## Windows note

Outside WSL, steps 3 and 4 degrade (no `/proc`, no reliable TTY). Step 5 still works. Windows-native agent usage is marginal; WSL is the supported path.
