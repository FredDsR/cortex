#!/usr/bin/env bash
# Resolve a session ID. Prints ID to stdout, source tag to stderr.
set -u

emit() { echo "$1"; echo "$2" >&2; exit 0; }

sha12() {
  local s
  s="$(printf '%s' "$1" | sha1sum 2>/dev/null | awk '{print $1}')"
  [ -z "$s" ] && s="$(printf '%s' "$1" | shasum 2>/dev/null | awk '{print $1}')"
  echo "${s:0:12}"
}

# 1. Explicit override
if [ -n "${WORK_SESSION_ID:-}" ]; then
  emit "${WORK_SESSION_ID:0:64}" "env"
fi

# 2. Known harness env vars
for var in CLAUDE_SESSION_ID COPILOT_SESSION_ID CURSOR_SESSION_ID CODEX_SESSION_ID; do
  val="$(eval "echo \${${var}:-}")"
  if [ -n "$val" ]; then
    tag="$(echo "${var%%_*}" | tr '[:upper:]' '[:lower:]')"
    emit "${val:0:64}" "$tag"
  fi
done

if [ "${WORK_FORCE_LEASE:-}" != "1" ]; then
  # 3. Session-leader fingerprint.
  # Walks to the session leader (typically the interactive shell or the agent
  # harness) via `ps -o sid`, then fingerprints sid + its process-start-time.
  # This is stable across subshells and command substitutions within the same
  # terminal session, unlike PPID which shifts with each `$(...)`.
  sid=""
  if command -v ps >/dev/null 2>&1; then
    sid="$(ps -o sid= -p $$ 2>/dev/null | tr -d '[:space:]' || true)"
  fi
  if [ -n "$sid" ] && [ "$sid" != "0" ]; then
    start=""
    if [ -r "/proc/$sid/stat" ]; then
      start="$(awk '{print $22}' "/proc/$sid/stat" 2>/dev/null || true)"
    else
      start="$(ps -o lstart= -p "$sid" 2>/dev/null | tr -d '[:space:]' || true)"
    fi
    if [ -n "$start" ]; then
      emit "$(sha12 "sid:$sid:$start")" "ppid"
    fi
  fi

  # 4. TTY fingerprint
  tty_name="$(tty 2>/dev/null || true)"
  if [ -n "$tty_name" ] && [ "$tty_name" != "not a tty" ]; then
    login="$(who am i 2>/dev/null | awk '{print $3,$4}' || true)"
    if [ -n "$login" ]; then
      emit "$(sha12 "tty:$tty_name:$login")" "tty"
    fi
  fi
fi

# 5. UUID lease
lease_dir="${XDG_RUNTIME_DIR:-/tmp}"
lease_file="$lease_dir/work-lease"
[ -d "$lease_dir" ] || lease_file="/tmp/work-lease-$(id -u)"

if [ -s "$lease_file" ]; then
  uuid="$(cat "$lease_file")"
else
  if [ -r /proc/sys/kernel/random/uuid ]; then
    uuid="$(cat /proc/sys/kernel/random/uuid)"
  else
    uuid="$(uuidgen 2>/dev/null || date +%s%N | sha1sum | awk '{print $1}')"
  fi
  echo "$uuid" > "$lease_file"
fi

emit "$(sha12 "lease:$uuid")" "lease"
