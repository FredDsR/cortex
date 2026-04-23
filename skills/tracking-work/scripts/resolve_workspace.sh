#!/usr/bin/env bash
# Resolve workspace slug from CWD.
# Exits 0 on success (prints slug to stdout).
# Exits 2 on slug collision (prints existing registered cwd to stderr).
set -u

cwd="${1:-$PWD}"
cwd="$(cd "$cwd" && pwd)"
WORK_ROOT="${WORK_ROOT:-$HOME/.work}"
WORKSPACES="$WORK_ROOT/workspaces"
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

# Write/refresh .meta
mkdir -p "$WORKSPACES/$slug"
{
  echo "cwd: $cwd"
  echo "remote: $remote"
  echo "source: $source_tag"
  echo "updated: $(date -u +%Y-%m-%d)"
} > "$WORKSPACES/$slug/.meta"

echo "$slug"
