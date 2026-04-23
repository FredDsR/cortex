#!/usr/bin/env bash
# Remove stale .active.* pointers older than N days.
set -u

ws="${1:?usage: sweep_active.sh <workspace-dir> [days]}"
days="${2:-7}"

[ -d "$ws" ] || exit 0

find "$ws" -maxdepth 1 -type f -name '.active.*' -mtime "+$days" -print -delete 2>/dev/null
