#!/usr/bin/env bash
# Resolve workspace slug from CWD.
# Exits 0 on success (prints slug to stdout).
# Exits 2 on slug collision (prints existing registered cwd to stderr).
set -u

cwd="${1:-$PWD}"
cwd="$(cd "$cwd" && pwd)"
CORTEX_ROOT="${CORTEX_ROOT:-$HOME/.cortex}"
WORKSPACES="$CORTEX_ROOT/workspaces"
mkdir -p "$WORKSPACES"

slug=""
source_tag=""
remote=""

# 1. Git remote
if remote="$(git -C "$cwd" remote get-url origin 2>/dev/null)"; then
  trimmed="${remote%.git}"
  path=""
  case "$trimmed" in
    *://*)
      # scheme://host[/path] — strip scheme and host
      rest="${trimmed#*://}"
      path="${rest#*/}"
      ;;
    *:*)
      # git@host:owner/repo form — strip everything up to and including the colon
      path="${trimmed##*:}"
      ;;
    *)
      path="$trimmed"
      ;;
  esac
  if [[ "$path" == */* ]]; then
    # Keep only the last two segments (owner/repo), guards against nested paths
    repo="${path##*/}"
    parent="${path%/*}"
    owner="${parent##*/}"
    slug="$owner-$repo"
    source_tag="git-remote"
  fi
fi

# 2. Explicit .meta match
if [ -z "$slug" ]; then
  for meta in "$WORKSPACES"/*/.meta; do
    [ -e "$meta" ] || continue
    mcwd="$(awk -F': ' '$1=="cwd"{print $2}' "$meta" | head -n1)"
    if [ "$mcwd" = "$cwd" ]; then
      slug="$(basename "$(dirname "$meta")")"
      source_tag="meta"
      break
    fi
  done
fi

# 3. Basename fallback, with collision check
if [ -z "$slug" ]; then
  slug="$(basename "$cwd")"
  source_tag="basename"
  if [ -f "$WORKSPACES/$slug/.meta" ]; then
    existing_cwd="$(awk -F': ' '$1=="cwd"{print $2}' "$WORKSPACES/$slug/.meta" | head -n1)"
    if [ -n "$existing_cwd" ] && [ "$existing_cwd" != "$cwd" ]; then
      echo "$existing_cwd" >&2
      exit 2
    fi
  fi
fi

# Write/refresh .meta only when content changed.
# Avoids dirtying ~/.cortex/ on every session start (relevant when sync is enabled).
mkdir -p "$WORKSPACES/$slug"
meta_path="$WORKSPACES/$slug/.meta"
today="$(date -u +%Y-%m-%d)"
new_meta=$'cwd: '"$cwd"$'\nremote: '"$remote"$'\nsource: '"$source_tag"$'\nupdated: '"$today"

write_needed=1
if [ -f "$meta_path" ]; then
  existing="$(cat "$meta_path")"
  ex_cwd="$(awk -F': ' '$1=="cwd"{print $2}' "$meta_path" | head -n1)"
  ex_remote="$(awk -F': ' '$1=="remote"{print $2}' "$meta_path" | head -n1)"
  ex_source="$(awk -F': ' '$1=="source"{print $2}' "$meta_path" | head -n1)"
  if [ "$ex_cwd" = "$cwd" ] && [ "$ex_remote" = "$remote" ] && [ "$ex_source" = "$source_tag" ]; then
    write_needed=0
  fi
fi

if [ "$write_needed" = "1" ]; then
  printf '%s\n' "$new_meta" > "$meta_path"
fi

echo "$slug"
