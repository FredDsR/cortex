#!/usr/bin/env bash
# Bundle the recurring session-start orchestration into one call.
# Output is structured for agent consumption:
#
#   WORKSPACE\t<slug>
#   SESSION_ID\t<id>\t<source>
#   SYNC\t<state>          # ok | regenerate-needed | conflict | not-installed | error rc=<n>
#   SESSIONS               # divider
#   <list_sessions.sh TSV rows: origin\tslug\tmtime\tactive-ids>
#
# Exit codes:
#   0  normal
#   2  workspace slug collision (resolve_workspace.sh exited 2). The collision-source
#      cwd is on stderr; the caller must prompt per slug-resolution.md.
set -u

cwd="${1:-$PWD}"
cwd="$(cd "$cwd" && pwd)"
script_dir="$(cd "$(dirname "$0")" && pwd)"

# Legacy store notice: the store moved from ~/.work to ~/.cortex during the
# cortex rebrand. install.sh creates ~/.cortex/bin, so the presence of ~/.cortex
# alone does not mean the data moved. Gate on the workspaces/ dir instead: if the
# old store still has workspaces and the new one does not, migration is pending.
if [ -d "$HOME/.work/workspaces" ] && [ ! -d "$HOME/.cortex/workspaces" ]; then
    echo "cortex: legacy ~/.work store detected. Run: cortex migrate-store --write" >&2
fi

# 1. Workspace slug. Pass through exit 2 (collision); stderr goes to stderr.
slug="$(bash "$script_dir/resolve_workspace.sh" "$cwd")"
rc=$?
if [ "$rc" -ne 0 ]; then
  exit "$rc"
fi

# 2. Session ID + source tag (source goes to stderr in the script).
src_tmp="$(mktemp)"
sid="$(bash "$script_dir/resolve_session_id.sh" 2>"$src_tmp")"
sid_src="$(cat "$src_tmp" 2>/dev/null | tr -d '[:space:]')"
rm -f "$src_tmp"

# 3. Sweep stale active pointers (best-effort, never fail the bootstrap).
bash "$script_dir/sweep_active.sh" "$HOME/.cortex/workspaces/$slug" 7 >/dev/null 2>&1 || true

# 4. Conditionally pull sync via the cortex CLI. `cortex sync pull` self-gates
#    when sync is disabled or unconfigured (exits 0 with no output). Resolve the
#    bin from PATH, else the store bin dir (~/.cortex/bin or legacy ~/.work/bin),
#    so an unconfigured PATH does not silently skip the pull.
cortex_bin=""
if command -v cortex >/dev/null 2>&1; then
  cortex_bin="cortex"
elif [ -x "$HOME/.cortex/bin/cortex" ]; then
  cortex_bin="$HOME/.cortex/bin/cortex"
elif [ -x "$HOME/.work/bin/cortex" ]; then
  cortex_bin="$HOME/.work/bin/cortex"
fi
sync_state="not-installed"
if [ -n "$cortex_bin" ]; then
  if pull_out="$("$cortex_bin" sync pull 2>&1)"; then
    if echo "$pull_out" | grep -q "regenerate-needed"; then
      sync_state="regenerate-needed"
    else
      sync_state="ok"
    fi
  else
    rc=$?
    if [ "$rc" -eq 2 ]; then
      sync_state="conflict"
      # Surface conflict detail on stderr.
      echo "$pull_out" >&2
    else
      sync_state="error rc=$rc"
    fi
  fi
fi

# 5. Emit structured header.
printf 'WORKSPACE\t%s\n' "$slug"
printf 'SESSION_ID\t%s\t%s\n' "$sid" "$sid_src"
printf 'SYNC\t%s\n' "$sync_state"
printf 'SESSIONS\n'

# 6. Sessions list (one TSV row per session).
bash "$script_dir/list_sessions.sh" "$cwd"
