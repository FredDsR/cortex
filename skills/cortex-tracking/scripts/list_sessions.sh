#!/usr/bin/env bash
# Enumerate sessions across global and local stores for the resolved workspace.
# Output: origin<TAB>slug<TAB>mtime<TAB>active-ids(csv)  — sorted by mtime desc.
set -u

cwd="${1:-$PWD}"
cwd="$(cd "$cwd" && pwd)"
script_dir="$(cd "$(dirname "$0")" && pwd)"

slug="$(bash "$script_dir/resolve_workspace.sh" "$cwd" 2>/dev/null)" || exit 0
WORK_ROOT="${WORK_ROOT:-$HOME/.work}"
global_ws="$WORK_ROOT/workspaces/$slug"
local_ws="$cwd/.work"

declare -A active_map=()
for af in "$global_ws"/.active.* "$local_ws"/.active.*; do
  [ -f "$af" ] || continue
  id="${af##*.active.}"
  target="$(head -n1 "$af")"
  [ -n "$target" ] || continue
  if [ -n "${active_map[$target]:-}" ]; then
    active_map[$target]="${active_map[$target]},$id"
  else
    active_map[$target]="$id"
  fi
done

emit_sessions() {
  local origin="$1" root="$2"
  local sdir slug_name mtime
  [ -d "$root/sessions" ] || return 0
  for sdir in "$root/sessions"/*/; do
    [ -d "$sdir" ] || continue
    slug_name="$(basename "$sdir")"
    if [ -f "$sdir/SUMMARY.md" ]; then
      mtime="$(date -u -r "$sdir/SUMMARY.md" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
              || stat -c '%y' "$sdir/SUMMARY.md" 2>/dev/null \
              || echo "")"
    else
      mtime=""
    fi
    printf '%s\t%s\t%s\t%s\n' "$origin" "$slug_name" "$mtime" "${active_map[$slug_name]:-}"
  done
}

{
  emit_sessions global "$global_ws"
  emit_sessions local "$local_ws"
} | sort -k3 -r
