#!/usr/bin/env bash
# Install / update tracking-work skills.
# Default: global install — symlinks each skill into $HOME/.<harness>/skills/.
# --project [path]: project-local install — symlinks into <path>/.<harness>/skills/.
# Idempotent — safe to re-run after `git pull`.
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
echo "tracking-work skills installed. Restart your agent session to pick up changes."

# --- tracking-work-viz install ---
VIZ_DIR="$HOME/.work/bin"
VIZ_VENDOR="$REPO_DIR/skills/tracking-work-viz/vendor"

mkdir -p "$VIZ_DIR" "$VIZ_VENDOR"

# Symlink work-viz onto ~/.work/bin
ln -sf "$REPO_DIR/skills/tracking-work-viz/bin/work-viz" "$VIZ_DIR/work-viz"

# Vendored JS (only fetched if missing)
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
  "dagre.min.js|https://unpkg.com/dagre@0.8.5/dist/dagre.min.js"
  "cytoscape-dagre.min.js|https://unpkg.com/cytoscape-dagre@2.5.0/cytoscape-dagre.js"
  "marked.min.js|https://unpkg.com/marked@12.0.2/marked.min.js"
)

VIZ_FETCH_FAILED=()
for entry in "${REQUIRED_VENDOR[@]}"; do
  name="${entry%%|*}"
  url="${entry#*|}"
  if ! fetch_if_missing "$VIZ_VENDOR/$name" "$url"; then
    VIZ_FETCH_FAILED+=("$name")
  fi
done

# Copy vendor + templates to a stable runtime location used by the generator and server
RUNTIME_DIR="$HOME/.work/viz"
mkdir -p "$RUNTIME_DIR/vendor"
cp "$VIZ_VENDOR/"*.js "$RUNTIME_DIR/vendor/" 2>/dev/null || true

# Copy first-party JS/CSS (committed in templates/vendor/) to the runtime vendor dir
SRC_VENDOR="$REPO_DIR/skills/tracking-work-viz/templates/vendor"
if [ -d "$SRC_VENDOR" ]; then
  cp "$SRC_VENDOR/"*.js "$RUNTIME_DIR/vendor/" 2>/dev/null || true
  cp "$SRC_VENDOR/"*.css "$RUNTIME_DIR/vendor/" 2>/dev/null || true
fi

# Verify required vendor files actually landed in the runtime dir.
VIZ_MISSING=()
for entry in "${REQUIRED_VENDOR[@]}"; do
  name="${entry%%|*}"
  if [ ! -s "$RUNTIME_DIR/vendor/$name" ]; then
    VIZ_MISSING+=("$name")
  fi
done

if [ ${#VIZ_MISSING[@]} -gt 0 ]; then
  echo "" >&2
  echo "ERROR: tracking-work-viz install incomplete." >&2
  echo "  Missing vendor file(s) in $RUNTIME_DIR/vendor/:" >&2
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

echo "tracking-work-viz: installed. Add $VIZ_DIR to PATH if not already, then run: work-viz <workspace>"
# --- end tracking-work-viz install ---
