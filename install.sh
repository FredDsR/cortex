#!/usr/bin/env bash
# Install / update cortex skills.
# Default: global install (symlinks each skill into $HOME/.<harness>/skills/).
# --project [path]: project-local install (symlinks into <path>/.<harness>/skills/).
# Idempotent. Safe to re-run after `git pull`.
#
# Runs two ways. From a clone it installs directly. Piped, it has no repo to
# symlink into, so it clones one first and re-runs itself from there:
#
#   curl -fsSL https://raw.githubusercontent.com/FredDsR/cortex/main/install.sh | bash
#   curl -fsSL .../install.sh | bash -s -- --project ~/some-repo
#
# CORTEX_DIR   where to clone when piped (default: ~/cortex)
# CORTEX_REPO  which repo to clone (default: the canonical one)
set -euo pipefail

# Empty when piped (`curl | bash`), since there is no script file on disk.
SELF="${BASH_SOURCE[0]:-}"
REPO_DIR=""
if [[ -n "$SELF" ]]; then
    REPO_DIR="$(cd "$(dirname "$SELF")" && pwd)"
fi

# --- mode selection ---------------------------------------------------------
# Two ways to install, because the engine can now install its own skills.
#
#   package  install the engine (PyPI or CORTEX_SPEC), then let it link the
#            skills. No clone, so this is the right path for `curl | bash`.
#   clone    the original path: a git checkout plus symlinks into each harness.
#            Still what runs when uv and pip are both unavailable, and what an
#            existing checkout keeps using.
#
# CORTEX_INSTALL_MODE   auto (default) | package | clone
# CORTEX_SPEC           what package mode installs (default: agentic-cortex)
# CORTEX_NO_UV_INSTALL  1 = never install uv; auto then falls back to clone
INSTALL_MODE="${CORTEX_INSTALL_MODE:-auto}"

if [[ "$INSTALL_MODE" == "auto" ]]; then
    if command -v uv >/dev/null 2>&1 || command -v pip >/dev/null 2>&1; then
        INSTALL_MODE="package"
    else
        INSTALL_MODE="clone"
    fi
fi

if [[ "$INSTALL_MODE" == "package" ]]; then
    case "${1:-}" in
        -h|--help)
            cat >&2 <<'PKGUSAGE'
Usage: install.sh [--project [path]]

Installs the cortex engine, then links its skills into each harness you use.
  --project [path]   link into <path>/.<harness>/skills/ instead of $HOME

  CORTEX_INSTALL_MODE=clone   force the git-checkout install instead
  CORTEX_SPEC=<spec>          install something other than agentic-cortex
PKGUSAGE
            exit 0
            ;;
    esac

    CORTEX_SPEC="${CORTEX_SPEC:-agentic-cortex}"

    if command -v uv >/dev/null 2>&1; then
        echo "==> Installing $CORTEX_SPEC with uv"
        uv tool install --force "$CORTEX_SPEC"
        # uv places tool binaries here and warns rather than failing when the
        # directory is off PATH, so make it reachable for the call below.
        export PATH="$HOME/.local/bin:$PATH"
    else
        echo "==> Installing $CORTEX_SPEC with pip"
        pip install --upgrade "$CORTEX_SPEC"
    fi

    if ! command -v cortex >/dev/null 2>&1; then
        echo "error: cortex was installed but is not on PATH." >&2
        echo "  Add the install directory to PATH, then run: cortex install-skills" >&2
        exit 1
    fi

    echo "==> Linking skills"
    cortex install-skills "$@"

    echo ""
    echo "cortex $(cortex version) installed. Restart your agent session."
    exit 0
fi

# --- bootstrap: acquire a repo when we were piped ---------------------------
# Guarded by CORTEX_BOOTSTRAPPED so a clone that somehow lacks skills/ fails
# loudly instead of cloning and re-execing forever.
if [[ -z "$REPO_DIR" || ! -d "$REPO_DIR/skills" ]]; then
    if [[ -n "${CORTEX_BOOTSTRAPPED:-}" ]]; then
        echo "error: bootstrapped checkout has no skills/ directory." >&2
        exit 1
    fi

    CORTEX_DIR="${CORTEX_DIR:-$HOME/cortex}"
    CORTEX_REPO="${CORTEX_REPO:-https://github.com/FredDsR/cortex.git}"

    command -v git >/dev/null 2>&1 || {
        echo "error: git is required but not on PATH." >&2; exit 1; }

    # Recognise an existing checkout by shape, not by remote URL, so forks,
    # renames, and ssh-vs-https all count as "already installed here".
    if [[ -e "$CORTEX_DIR" ]]; then
        if [[ -d "$CORTEX_DIR/.git" && -f "$CORTEX_DIR/install.sh" && -d "$CORTEX_DIR/skills" ]]; then
            echo "cortex: updating existing checkout at $CORTEX_DIR"
            git -C "$CORTEX_DIR" pull --ff-only || {
                echo "error: could not fast-forward $CORTEX_DIR. Resolve it by hand, then re-run." >&2
                exit 1; }
        else
            # Never clobber a directory we did not create. Piped installers are
            # exactly the case where nobody read the script first.
            echo "error: $CORTEX_DIR exists and is not a cortex checkout." >&2
            echo "  Move it aside, or choose another location:" >&2
            echo "    curl -fsSL <url> | CORTEX_DIR=~/somewhere-else bash" >&2
            exit 1
        fi
    else
        echo "cortex: cloning $CORTEX_REPO into $CORTEX_DIR"
        git clone --depth 1 "$CORTEX_REPO" "$CORTEX_DIR" || {
            echo "error: clone failed." >&2; exit 1; }
    fi

    echo ""
    CORTEX_BOOTSTRAPPED=1 exec bash "$CORTEX_DIR/install.sh" "$@"
fi

SKILLS_SRC="$REPO_DIR/skills"

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
# Harnesses that discover skills from a directory we can symlink into.
# Antigravity is deliberately absent: `agy plugin install` reads skills/ from
# the repo itself, so there is nothing here to link. See the README.
HARNESSES=(
    "claude-code:.claude/skills"
    "codex:.codex/skills"
    "copilot-cli:.copilot/skills"
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

        # A skill is a directory with a SKILL.md. Renames can leave behind a
        # husk holding only gitignored build artifacts (__pycache__,
        # .pytest_cache); without this guard the glob would re-link it right
        # after the stale-symlink cleanup above removed it.
        if [[ ! -f "$skill_dir/SKILL.md" ]]; then
            echo "[$harness] skipping $skill_name (no SKILL.md)"
            continue
        fi

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

# --- viz assets + stale bin cleanup ---
# The viewer's JS ships in the repo (and in the wheel), verified against
# src/cortex/viz/vendor/vendor.lock.json at build time, so there is nothing to
# fetch here any more. Earlier installs created a bin symlink; prune it, since
# the `cortex` command now comes from the installed package.
VIZ_BIN_DIR="$HOME/.cortex/bin"
if [ -d "$VIZ_BIN_DIR" ]; then
    for old in cortex work-viz work-kb; do
        [ -L "$VIZ_BIN_DIR/$old" ] && rm -f "$VIZ_BIN_DIR/$old"
    done
fi

echo "cortex: skills installed. This is the clone install, which does not"
echo "  provide the \`cortex\` command itself. Install the engine with:"
echo "    uv tool install agentic-cortex   # or: pip install agentic-cortex"
echo "  Then: cortex kb ... / cortex viz ... / cortex inject ..."

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
