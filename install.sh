#!/usr/bin/env bash
# Install / update tracking-work skills into every detected agent harness.
# Symlinks each skill in ./skills/ into the harness's skills directory.
# Idempotent — safe to re-run after `git pull`.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$REPO_DIR/skills"

if [[ ! -d "$SKILLS_SRC" ]]; then
    echo "error: $SKILLS_SRC not found" >&2
    exit 1
fi

# harness → skills-dir-under-$HOME
HARNESSES=(
    "claude-code:.claude/skills"
    "codex:.codex/skills"
    "copilot-cli:.copilot/skills"
    "gemini-cli:.gemini/skills"
)

install_into() {
    local harness="$1"
    local rel_skills_dir="$2"
    local harness_root="$HOME/${rel_skills_dir%/skills}"
    local dest_root="$HOME/$rel_skills_dir"

    if [[ ! -d "$harness_root" ]]; then
        echo "[$harness] $harness_root not present, skipping"
        return 0
    fi

    mkdir -p "$dest_root"

    for skill_dir in "$SKILLS_SRC"/*/; do
        local skill_name
        skill_name=$(basename "$skill_dir")
        local dest="$dest_root/$skill_name"

        if [[ -L "$dest" ]]; then
            ln -sfn "$skill_dir" "$dest"
            echo "[$harness] relinked $skill_name"
        elif [[ -e "$dest" ]]; then
            local backup="${dest}.bak.$(date +%s)"
            mv "$dest" "$backup"
            ln -s "$skill_dir" "$dest"
            echo "[$harness] replaced $skill_name (backup: ${backup##*/})"
        else
            ln -s "$skill_dir" "$dest"
            echo "[$harness] installed $skill_name"
        fi
    done
}

for entry in "${HARNESSES[@]}"; do
    harness="${entry%%:*}"
    path="${entry#*:}"
    install_into "$harness" "$path"
done

echo ""
echo "tracking-work skills installed. Restart your agent session to pick up changes."
