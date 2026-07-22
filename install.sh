#!/usr/bin/env bash
# Install / update cortex skills.
# Default: global install (symlinks each skill into $HOME/.<harness>/skills/).
# --project [path]: project-local install (symlinks into <path>/.<harness>/skills/).
# Idempotent. Safe to re-run after `git pull`.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$REPO_DIR/skills"

if [[ ! -d "$SKILLS_SRC" ]]; then
    echo "error: $SKILLS_SRC not found" >&2
    exit 1
fi

usage() {
    cat <<EOF
Usage: install.sh [--project [path]]
  (no flags)        Global install into \$HOME/.<harness>/skills/ for each detected harness.
  --project [path]  Project-scoped install into <path>/.<harness>/skills/. Defaults to \$PWD.
                    Only installs for harnesses you already use globally (\$HOME/.<harness>/ exists).
  -h, --help        Show this help.
EOF
}

MODE="global"
TARGET_ROOT="$HOME"

case "${1:-}" in
    --project)
        MODE="project"
        TARGET_ROOT="${2:-$PWD}"
        if [[ ! -d "$TARGET_ROOT" ]]; then
            echo "error: $TARGET_ROOT does not exist" >&2
            exit 1
        fi
        TARGET_ROOT="$(cd "$TARGET_ROOT" && pwd)"
        ;;
    -h|--help)
        usage
        exit 0
        ;;
    "")
        ;;
    *)
        usage
        exit 1
        ;;
esac

# harness → skills-dir-under-<root>
HARNESSES=(
    "claude-code:.claude/skills"
    "codex:.codex/skills"
    "copilot-cli:.copilot/skills"
    "gemini-cli:.gemini/skills"
)

install_into() {
    local harness="$1"
    local rel_skills_dir="$2"
    local user_harness_root="$HOME/${rel_skills_dir%/skills}"
    local dest_root="$TARGET_ROOT/$rel_skills_dir"

    # Presence of $HOME/.<harness>/ is the proxy for "user uses this harness".
    if [[ ! -d "$user_harness_root" ]]; then
        echo "[$harness] $user_harness_root not present, skipping"
        return 0
    fi

    mkdir -p "$dest_root"

    # Clean up stale pre-rebrand symlinks (tracking-work* -> cortex*).
    for old in tracking-work tracking-work-github tracking-work-kb \
               tracking-work-viz tracking-work-sync tracking-work-migration \
               tracking-work-inject; do
        if [[ -L "$dest_root/$old" ]]; then
            rm -f "$dest_root/$old"
            echo "[$harness] removed stale $old symlink"
        fi
    done

    for skill_dir in "$SKILLS_SRC"/*/; do
        local skill_name
        skill_name=$(basename "$skill_dir")
        local dest="$dest_root/$skill_name"

        if [[ -L "$dest" ]]; then
            ln -sfn "$skill_dir" "$dest"
            echo "[$harness] relinked $skill_name → $dest"
        elif [[ -e "$dest" ]]; then
            local backup="${dest}.bak.$(date +%s)"
            mv "$dest" "$backup"
            ln -s "$skill_dir" "$dest"
            echo "[$harness] replaced $skill_name (backup: ${backup##*/})"
        else
            ln -s "$skill_dir" "$dest"
            echo "[$harness] installed $skill_name → $dest"
        fi
    done
}

echo "Mode: $MODE | target root: $TARGET_ROOT"
echo ""

for entry in "${HARNESSES[@]}"; do
    harness="${entry%%:*}"
    path="${entry#*:}"
    install_into "$harness" "$path"
done

echo ""
echo "cortex skills installed. Restart your agent session to pick up changes."

# --- cortex-viz install ---
VIZ_BIN_DIR="$HOME/.cortex/bin"
VIZ_VENDOR="$REPO_DIR/cortex/viz/templates/vendor"

mkdir -p "$VIZ_BIN_DIR" "$VIZ_VENDOR"

# Unified cortex bin (replaces the former work-viz / work-kb bins).
ln -sf "$REPO_DIR/skills/cortex-tracking/bin/cortex" "$VIZ_BIN_DIR/cortex"
# Remove superseded bins from prior installs (symlinks only).
for old in work-viz work-kb; do
    [ -L "$VIZ_BIN_DIR/$old" ] && rm -f "$VIZ_BIN_DIR/$old"
done

# Vendored JS (only fetched if missing). The generator stages templates/vendor/
# into out/vendor/ at build time, so populating templates/vendor/ is the only
# install-time requirement.
fetch_if_missing() {
  local dest="$1"
  local url="$2"
  if [ ! -s "$dest" ]; then
    echo "Fetching $(basename "$dest")"
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "$url" -o "$dest"
    elif command -v wget >/dev/null 2>&1; then
      wget -q "$url" -O "$dest"
    else
      echo "warning: neither curl nor wget available; skip $url" >&2
      return 1
    fi
  fi
}

REQUIRED_VENDOR=(
  "cytoscape.min.js|https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"
  "marked.min.js|https://unpkg.com/marked@12.0.2/marked.min.js"
  "minisearch.min.js|https://unpkg.com/minisearch@7.1.0/dist/umd/index.js"
)

VIZ_FETCH_FAILED=()
for entry in "${REQUIRED_VENDOR[@]}"; do
  name="${entry%%|*}"
  url="${entry#*|}"
  if ! fetch_if_missing "$VIZ_VENDOR/$name" "$url"; then
    VIZ_FETCH_FAILED+=("$name")
  fi
done

# Verify every required third-party file landed in templates/vendor/.
VIZ_MISSING=()
for entry in "${REQUIRED_VENDOR[@]}"; do
  name="${entry%%|*}"
  if [ ! -s "$VIZ_VENDOR/$name" ]; then
    VIZ_MISSING+=("$name")
  fi
done

if [ ${#VIZ_MISSING[@]} -gt 0 ]; then
  echo "" >&2
  echo "ERROR: cortex-viz install incomplete." >&2
  echo "  Missing vendor file(s) in $VIZ_VENDOR/:" >&2
  for m in "${VIZ_MISSING[@]}"; do
    echo "    - $m" >&2
  done
  if [ ${#VIZ_FETCH_FAILED[@]} -gt 0 ]; then
    echo "  (fetch_if_missing failed for: ${VIZ_FETCH_FAILED[*]})" >&2
  fi
  echo "  The viewer will not work until these are present. Re-run install.sh with network access," >&2
  echo "  or copy the files manually. See SKILL.md for the canonical URLs." >&2
  exit 1
fi

echo "cortex: installed. Add $VIZ_BIN_DIR to PATH if not already, then run: cortex kb ... / cortex viz ... / cortex inject ..."
# --- end cortex-viz install ---

# --- slash command install (Claude Code symlink path) ---
# Plugin/marketplace installs pick up commands/ natively. For symlink installs,
# expose the command from ~/.claude/commands/ when that harness is present.
CC_COMMANDS_DIR="$HOME/.claude/commands"
if [ -d "$HOME/.claude" ]; then
  mkdir -p "$CC_COMMANDS_DIR"
  ln -sfn "$REPO_DIR/commands/close-day.md" "$CC_COMMANDS_DIR/close-day.md"
  echo "slash command: linked close-day.md → $CC_COMMANDS_DIR (use /close-day)"
fi
# --- end slash command install ---

# --- cortex-kb install ---
# The kb CLI is now reached via `cortex kb ...`; no separate bin is installed.
# (cortex symlink is handled in the viz block above; both live in ~/.cortex/bin.)
# --- end cortex-kb install ---
