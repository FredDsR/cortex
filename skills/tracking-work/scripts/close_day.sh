#!/usr/bin/env bash
# Read-only end-of-session snapshot for the "Closing the Day" routine.
# Resolves the active session for the current workspace and prints a TSV
# wrap-up signal. Performs NO writes.
#
# Output (TAB-separated, sectioned):
#   STATUS    <ok | no-workspace | no-active-session>
#   SESSION   <session-slug>    <started-date-or-empty>
#   NEXT_DAY  <tomorrow | Monday>
#   TASKS
#   <slug>    <status>    <mtime-iso>
#   COMMITS              (only if cwd is a git repo)
#   <short-sha>    <subject>
#   UNCOMMITTED          (only if cwd is a git repo)
#   <porcelain-line>
#
# Usage:
#   bash close_day.sh            # use $PWD as cwd
#   bash close_day.sh /some/path
set -u

cwd="${1:-$PWD}"
cwd="$(cd "$cwd" && pwd)"
script_dir="$(cd "$(dirname "$0")" && pwd)"

slug="$(bash "$script_dir/resolve_workspace.sh" "$cwd" 2>/dev/null)" || {
  printf 'STATUS\tno-workspace\n'; exit 0;
}
WORK_ROOT="${WORK_ROOT:-$HOME/.work}"
global_ws="$WORK_ROOT/workspaces/$slug"
local_ws="$cwd/.work"

sid="$(bash "$script_dir/resolve_session_id.sh" 2>/dev/null)"

session=""; store=""
for ws in "$global_ws" "$local_ws"; do
  af="$ws/.active.$sid"
  if [ -s "$af" ]; then
    session="$(head -n1 "$af")"
    store="$ws"
    break
  fi
done

if [ -z "$session" ] || [ ! -d "$store/sessions/$session" ]; then
  printf 'STATUS\tno-active-session\n'
  exit 0
fi

sess_dir="$store/sessions/$session"
summary="$sess_dir/SUMMARY.md"

started=""
if [ -f "$summary" ]; then
  started="$(awk -F': ' '$1=="started"{print $2; exit}' "$summary" | tr -d '[:space:]')"
fi

printf 'STATUS\tok\n'
printf 'SESSION\t%s\t%s\n' "$session" "$started"

dow="${WORK_TODAY_DOW:-$(date +%u)}"
case "$dow" in
  1|2|3|4) next_day="tomorrow" ;;
  *)       next_day="Monday" ;;
esac
printf 'NEXT_DAY\t%s\n' "$next_day"

printf 'TASKS\n'
if [ -d "$sess_dir/tasks" ]; then
  for t in "$sess_dir/tasks"/*.md; do
    [ -f "$t" ] || continue
    tslug="$(basename "$t" .md)"
    status="$(awk '
      NR==1 && $0=="---" { fm=1; next }
      fm && $0=="---" { exit }
      fm {
        i=index($0,":")
        if (i>0) {
          k=substr($0,1,i-1); v=substr($0,i+1)
          gsub(/^[ \t]+|[ \t]+$/,"",k); gsub(/^[ \t]+|[ \t]+$/,"",v)
          if (k=="status") { print v; exit }
        }
      }' "$t")"
    mtime="$(date -r "$t" +%Y-%m-%dT%H:%M:%S 2>/dev/null || echo "")"
    printf '%s\t%s\t%s\n' "$tslug" "$status" "$mtime"
  done
fi

if git -C "$cwd" rev-parse --git-dir >/dev/null 2>&1; then
  printf 'COMMITS\n'
  if [ -n "$started" ]; then
    git -C "$cwd" log --since="$started 00:00:00" --pretty=format:'%h%x09%s' 2>/dev/null
  else
    git -C "$cwd" log -n 50 --pretty=format:'%h%x09%s' 2>/dev/null
  fi
  printf '\n'
  printf 'UNCOMMITTED\n'
  git -C "$cwd" status --porcelain 2>/dev/null
fi
