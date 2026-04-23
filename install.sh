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
