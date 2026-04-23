#!/usr/bin/env bash
# Exit 0 if tracking-work sync is enabled for this device; exit 1 otherwise.
set -euo pipefail

WORK_DIR="${HOME}/.work"

# Sentinel wins: user explicitly opted out.
[[ -f "$WORK_DIR/.sync-disabled" ]] && exit 1

# Must be a git repo.
git -C "$WORK_DIR" rev-parse --git-dir >/dev/null 2>&1 || exit 1

# Must have an origin remote.
git -C "$WORK_DIR" remote get-url origin >/dev/null 2>&1 || exit 1

exit 0
