#!/usr/bin/env bash
# Uninstall cortex skills. Counterpart to install.sh.
# Default: remove the symlinks install.sh created, globally.
# --project [path]: remove a project-local install instead.
# Idempotent. Never removes your work data unless you ask for it explicitly.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$REPO_DIR/skills"
STORE_DIR="$HOME/.cortex"
BIN_DIR="$STORE_DIR/bin"

usage() {
    cat <<EOF
Usage: uninstall.sh [--project [path]] [--dry-run] [--purge-store] [--yes]
  (no flags)        Remove the global install from \$HOME/.<harness>/skills/.
  --project [path]  Remove a project-scoped install from <path>/.<harness>/skills/.
                    Defaults to \$PWD.
  --dry-run         Print what would be removed; change nothing.
  --purge-store     ALSO delete your work data in $STORE_DIR (workspaces,
                    archive, knowledge). Requires typed confirmation.
  --yes             Skip the typed confirmation for --purge-store. Refused when
                    sync is not configured, unless passed twice.
  -h, --help        Show this help.

By default this removes only symlinks that point into this repo. Real
directories, foreign installs, and everything in $STORE_DIR are left alone
and reported.
EOF
}

MODE="global"
TARGET_ROOT="$HOME"
DRY_RUN=0
PURGE_STORE=0
ASSUME_YES=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project)
            MODE="project"
            # Only consume $2 as a path when it is not another flag.
            if [[ -n "${2:-}" && "${2:-}" != --* ]]; then
                TARGET_ROOT="$2"
                shift
            else
                TARGET_ROOT="$PWD"
            fi
            if [[ ! -d "$TARGET_ROOT" ]]; then
                echo "error: $TARGET_ROOT does not exist" >&2
                exit 1
            fi
            TARGET_ROOT="$(cd "$TARGET_ROOT" && pwd)"
            ;;
        --dry-run) DRY_RUN=1 ;;
        --purge-store) PURGE_STORE=1 ;;
        --yes) ASSUME_YES=$((ASSUME_YES + 1)) ;;
        -h|--help) usage; exit 0 ;;
        *) echo "error: unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
    shift
done

# harness → skills-dir-under-<root>. Mirrors install.sh, plus gemini-cli, which
# older installs may still have even though it is no longer an install target.
HARNESSES=(
    "claude-code:.claude/skills"
    "codex:.codex/skills"
    "copilot-cli:.copilot/skills"
    "gemini-cli:.gemini/skills"
)

# Skill names install.sh has ever created: the current cortex-* set plus the
# pre-rebrand tracking-work-* names install.sh still cleans up.
SKILL_NAMES=()
if [[ -d "$SKILLS_SRC" ]]; then
    for skill_dir in "$SKILLS_SRC"/*/; do
        [[ -d "$skill_dir" ]] || continue
        SKILL_NAMES+=("$(basename "$skill_dir")")
    done
fi
# Explicit fallback so uninstall still works from a repo whose skills/ is gone.
for name in cortex-tracking cortex-github cortex-kb cortex-viz cortex-sync \
            cortex-migration cortex-inject \
            tracking-work tracking-work-github tracking-work-kb \
            tracking-work-viz tracking-work-sync tracking-work-migration \
            tracking-work-inject; do
    case " ${SKILL_NAMES[*]} " in
        *" $name "*) ;;
        *) SKILL_NAMES+=("$name") ;;
    esac
done

REMOVED=0
KEPT=()

# Remove a path only when it is a symlink pointing into this repo. Anything
# else is someone else's, and gets reported instead of deleted.
remove_link() {
    local path="$1" label="$2" require_repo="${3:-1}"

    [[ -L "$path" || -e "$path" ]] || return 0

    if [[ ! -L "$path" ]]; then
        KEPT+=("$path (not a symlink; left in place)")
        return 0
    fi

    if [[ "$require_repo" == "1" ]]; then
        local target
        target="$(readlink -f "$path" 2>/dev/null || true)"
        if [[ -z "$target" ]]; then
            # Dangling symlink from a moved/deleted repo. Ours to clean up.
            :
        elif [[ "$target" != "$REPO_DIR"/* && "$target" != "$REPO_DIR" ]]; then
            KEPT+=("$path -> $target (points outside this repo; left in place)")
            return 0
        fi
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        echo "  would remove $label"
    else
        rm -f "$path"
        echo "  removed $label"
    fi
    REMOVED=$((REMOVED + 1))
}

uninstall_from() {
    local harness="$1" rel_skills_dir="$2"
    local dest_root="$TARGET_ROOT/$rel_skills_dir"

    if [[ ! -d "$dest_root" ]]; then
        return 0
    fi

    echo "[$harness] $dest_root"
    local name
    for name in "${SKILL_NAMES[@]}"; do
        remove_link "$dest_root/$name" "$name"
    done

    # Report install.sh's backups rather than deleting them; they may hold work.
    local bak
    for bak in "$dest_root"/*.bak.*; do
        [[ -e "$bak" ]] || continue
        KEPT+=("$bak (install.sh backup; left in place)")
    done

    # Drop the skills dir only if install.sh created it and nothing else uses it.
    if [[ "$DRY_RUN" != "1" ]]; then
        rmdir "$dest_root" 2>/dev/null && echo "  removed empty $dest_root" || true
    fi
}

echo "Mode: $MODE | target root: $TARGET_ROOT"
[[ "$DRY_RUN" == "1" ]] && echo "DRY RUN: nothing will be changed"
echo ""

for entry in "${HARNESSES[@]}"; do
    uninstall_from "${entry%%:*}" "${entry#*:}"
done

# --- slash command (global installs only; install.sh only ever links it there) ---
if [[ "$MODE" == "global" ]]; then
    CC_COMMANDS_DIR="$HOME/.claude/commands"
    if [[ -e "$CC_COMMANDS_DIR/close-day.md" || -L "$CC_COMMANDS_DIR/close-day.md" ]]; then
        echo "[slash command] $CC_COMMANDS_DIR"
        remove_link "$CC_COMMANDS_DIR/close-day.md" "close-day.md"
    fi
fi

# --- session-start hook + cortex bin (global installs only) ---
if [[ "$MODE" == "global" ]]; then
    # Unwire the SessionStart hook BEFORE removing the bin, or the hook is left
    # pointing at a binary that no longer exists and every session start fails.
    # `cortex inject disable --unwire-hook` also drops the current workspace's
    # .inject-enabled sentinel, which is store data. Save and restore it,
    # keeping the default path store-neutral.
    if [[ -x "$BIN_DIR/cortex" ]] && "$BIN_DIR/cortex" inject status >/dev/null 2>&1; then
        if "$BIN_DIR/cortex" inject status 2>/dev/null | grep -qi "claude-code"; then
            echo "[hook] unwiring SessionStart hook"
            if [[ "$DRY_RUN" == "1" ]]; then
                echo "  would unwire claude-code SessionStart hook (sentinel preserved)"
            else
                SENTINEL=""
                while IFS= read -r line; do
                    case "$line" in
                        *.inject-enabled) SENTINEL="$line" ;;
                    esac
                done < <(find "$STORE_DIR/workspaces" -maxdepth 2 -name '.inject-enabled' 2>/dev/null || true)

                "$BIN_DIR/cortex" inject disable --unwire-hook claude-code >/dev/null 2>&1 || true
                # Restore the sentinel the disable call consumed.
                if [[ -n "$SENTINEL" && ! -f "$SENTINEL" ]]; then
                    printf 'on\n' > "$SENTINEL"
                    echo "  hook unwired; workspace opt-in sentinel preserved"
                else
                    echo "  hook unwired"
                fi
            fi
        fi
    fi

    if [[ -d "$BIN_DIR" ]]; then
        echo "[bin] $BIN_DIR"
        remove_link "$BIN_DIR/cortex" "cortex"
        # Bins superseded by the unified cortex CLI.
        remove_link "$BIN_DIR/work-viz" "work-viz" 0
        remove_link "$BIN_DIR/work-kb" "work-kb" 0
        if [[ "$DRY_RUN" != "1" ]]; then
            rmdir "$BIN_DIR" 2>/dev/null && echo "  removed empty $BIN_DIR" || true
        fi
    fi
fi

# --- optional: purge the work data store ---
if [[ "$PURGE_STORE" == "1" ]]; then
    echo ""
    if [[ ! -d "$STORE_DIR" ]]; then
        echo "[store] $STORE_DIR does not exist; nothing to purge"
    else
        SYNC_OK=0
        if git -C "$STORE_DIR" remote get-url origin >/dev/null 2>&1; then
            SYNC_OK=1
        fi

        echo "[store] PURGE REQUESTED. This deletes your work data:"
        for sub in workspaces archive knowledge; do
            [[ -d "$STORE_DIR/$sub" ]] && echo "  $STORE_DIR/$sub"
        done
        if [[ "$SYNC_OK" == "1" ]]; then
            echo "  Sync IS configured ($(git -C "$STORE_DIR" remote get-url origin))."
            echo "  A purge is recoverable by re-cloning that repo."
        else
            echo "  Sync is NOT configured. This data exists nowhere else."
        fi

        PROCEED=0
        if [[ "$DRY_RUN" == "1" ]]; then
            echo "  would delete the paths above (dry run)"
        elif [[ "$SYNC_OK" == "0" && "$ASSUME_YES" -lt 2 ]]; then
            if [[ "$ASSUME_YES" -ge 1 ]]; then
                echo "  refusing: --yes alone is not enough without sync." >&2
                echo "  Pass --yes --yes to confirm you accept unrecoverable loss." >&2
                exit 1
            fi
            printf '  Type exactly "delete my cortex data" to proceed: '
            read -r reply
            [[ "$reply" == "delete my cortex data" ]] && PROCEED=1 || echo "  aborted"
        elif [[ "$ASSUME_YES" -ge 1 ]]; then
            PROCEED=1
        else
            printf '  Type exactly "delete my cortex data" to proceed: '
            read -r reply
            [[ "$reply" == "delete my cortex data" ]] && PROCEED=1 || echo "  aborted"
        fi

        if [[ "$PROCEED" == "1" ]]; then
            rm -rf "${STORE_DIR:?}/workspaces" "${STORE_DIR:?}/archive" "${STORE_DIR:?}/knowledge"
            echo "  store purged"
            rmdir "$STORE_DIR" 2>/dev/null && echo "  removed empty $STORE_DIR" || true
        fi
    fi
fi

echo ""
if [[ ${#KEPT[@]} -gt 0 ]]; then
    echo "Left in place (not ours to remove):"
    for k in "${KEPT[@]}"; do echo "  $k"; done
    echo ""
fi

if [[ "$DRY_RUN" == "1" ]]; then
    echo "Dry run complete: $REMOVED item(s) would be removed."
else
    echo "Uninstalled: $REMOVED item(s) removed."
fi

if [[ "$PURGE_STORE" != "1" && -d "$STORE_DIR" ]]; then
    echo "Your work data is untouched in $STORE_DIR (use --purge-store to delete it)."
fi
echo "If you added $BIN_DIR to PATH, remove that line from your shell rc."
