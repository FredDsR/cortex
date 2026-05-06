#!/usr/bin/env bash
# Emit a compact TSV manifest of every task under the resolved workspace,
# parsing YAML frontmatter (preferred) or legacy bold-pair fields as fallback.
#
# Output columns (TAB-separated):
#   origin  session  slug  status  blocked_by  pr  title
#
# - origin: "global" or "local"
# - status: Open | In Progress | Blocked | Resolved | "" (unknown)
# - blocked_by: comma-separated task slugs, or empty
# - pr: PR number/string from frontmatter `pr:`, or empty
# - title: first H1 heading from the body, or the task slug if missing
#
# Usage:
#   bash manifest.sh            # use $PWD as cwd
#   bash manifest.sh /some/path
set -u

cwd="${1:-$PWD}"
cwd="$(cd "$cwd" && pwd)"
script_dir="$(cd "$(dirname "$0")" && pwd)"

slug="$(bash "$script_dir/resolve_workspace.sh" "$cwd" 2>/dev/null)" || exit 0
WORK_ROOT="${WORK_ROOT:-$HOME/.work}"
global_ws="$WORK_ROOT/workspaces/$slug"
local_ws="$cwd/.work"

emit_task() {
  local origin="$1" session="$2" task_path="$3"
  local task_slug
  task_slug="$(basename "$task_path" .md)"

  awk -v origin="$origin" -v session="$session" -v slug="$task_slug" '
    BEGIN {
      in_fm = 0; fm_done = 0; line_no = 0
      status = ""; pr = ""; blocked = ""; title = ""
    }
    {
      line_no++
      # Frontmatter detection: starts at line 1 with "---", ends at next "---".
      if (line_no == 1 && $0 == "---") { in_fm = 1; next }
      if (in_fm) {
        if ($0 == "---") { in_fm = 0; fm_done = 1; next }
        # key: value
        idx = index($0, ":")
        if (idx > 0) {
          key = substr($0, 1, idx - 1)
          val = substr($0, idx + 1)
          gsub(/^[ \t]+|[ \t]+$/, "", key)
          gsub(/^[ \t]+|[ \t]+$/, "", val)
          if (key == "status" && status == "") status = val
          else if (key == "pr" && pr == "") pr = val
        }
        next
      }
      # Body section.
      # Capture first H1 as title.
      if (title == "" && $0 ~ /^# /) {
        sub(/^# +/, "", $0); title = $0; next
      }
      # Legacy bold-pair fields (only when frontmatter did not provide).
      if (status == "" && match($0, /^\*\*Status:\*\*[ \t]*/)) {
        status = substr($0, RSTART + RLENGTH); next
      }
      if (pr == "" && match($0, /^\*\*PR:\*\*[ \t]*/)) {
        rest = substr($0, RSTART + RLENGTH)
        # If "[#456](url)", extract the bracketed text.
        if (match(rest, /\[[^]]+\]/)) {
          inner = substr(rest, RSTART + 1, RLENGTH - 2)
          sub(/^#/, "", inner)
          pr = inner
        } else {
          pr = rest
        }
        next
      }
      # Blocked by: line (frontmatter does not carry this; body is canonical).
      if ($0 ~ /Blocked by/) {
        pos = index($0, "Blocked by")
        rest = substr($0, pos + length("Blocked by"))
        # Strip leading ":", trailing bold markers, and surrounding whitespace.
        sub(/^:[ \t]*/, "", rest)
        sub(/^\**[ \t]*/, "", rest)
        # Strip markdown link wrappers: [text](url) -> text.
        gsub(/\[([^]]+)\]\([^)]*\)/, "\\1", rest)
        n = split(rest, parts, /,[ \t]*/)
        for (i = 1; i <= n; i++) {
          item = parts[i]
          gsub(/^[ \t*]+|[ \t*]+$/, "", item)
          if (item == "") continue
          if (blocked == "") blocked = item
          else blocked = blocked "," item
        }
      }
    }
    END {
      if (title == "") title = slug
      printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n", origin, session, slug, status, blocked, pr, title
    }
  ' "$task_path"
}

walk_store() {
  local origin="$1" root="$2"
  [ -d "$root/sessions" ] || return 0
  local sess sess_slug task
  for sess in "$root/sessions"/*/; do
    [ -d "$sess" ] || continue
    sess_slug="$(basename "$sess")"
    [ -d "$sess/tasks" ] || continue
    for task in "$sess/tasks"/*.md; do
      [ -f "$task" ] || continue
      emit_task "$origin" "$sess_slug" "$task"
    done
  done
}

# Header for downstream parsing.
printf 'origin\tsession\tslug\tstatus\tblocked_by\tpr\ttitle\n'

walk_store "global" "$global_ws"
walk_store "local" "$local_ws"
