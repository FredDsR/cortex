#!/usr/bin/env bash
# Interactive / flag-driven bootstrap for tracking-work-sync.
# Three paths: --skip (local-only sentinel), --clone <url>, --init [--name N].
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPTS_DIR")"
TEMPLATE_GITIGNORE="$SKILL_DIR/templates/gitignore"
WORK_DIR="${HOME}/.work"

usage() {
    cat <<EOF
Usage: setup.sh [--skip | --clone <url> | --init [--name <repo>]]
  --skip        Write ~/.work/.sync-disabled; do not set up sync.
  --clone URL   Clone an existing sync repo into ~/.work/ (must be empty).
  --init        Initialize a new repo and create a private GitHub repo.
    --name N    Override the default repo name (default: work-tracking).
  (no flags)    Interactive menu.
EOF
}

mkdir -p "$WORK_DIR"

ensure_gh_authed() {
    if ! command -v gh >/dev/null 2>&1; then
        echo "setup: gh CLI not found. Install https://cli.github.com/" >&2
        exit 4
    fi
    if ! gh auth status >/dev/null 2>&1; then
        echo "setup: gh is not authenticated. Run: gh auth login" >&2
        exit 5
    fi
}

do_skip() {
    touch "$WORK_DIR/.sync-disabled"
    echo "tracking-work-sync: disabled (sentinel written at $WORK_DIR/.sync-disabled)"
}

do_clone() {
    local url="$1"
    # Refuse if ~/.work/ has any content other than the sentinel.
    if [[ -d "$WORK_DIR" ]]; then
        if find "$WORK_DIR" -mindepth 1 -maxdepth 1 \
                ! -name .sync-disabled -print -quit 2>/dev/null | grep -q .; then
            echo "setup: $WORK_DIR is not empty; refusing to clone over existing content." >&2
            echo "Move or remove its contents first, then re-run." >&2
            exit 3
        fi
    fi
    ensure_gh_authed  # private repos via https typically need gh auth
    rm -rf "$WORK_DIR"
    git clone -q "$url" "$WORK_DIR"
    echo "tracking-work-sync: cloned $url into $WORK_DIR"
}

do_init() {
    local name="${1:-work-tracking}"
    ensure_gh_authed
    # git init (idempotent)
    if [[ ! -d "$WORK_DIR/.git" ]]; then
        git -C "$WORK_DIR" init -q -b main
    fi
    # gitignore (copy template)
    cp "$TEMPLATE_GITIGNORE" "$WORK_DIR/.gitignore"
    # configure identity if missing
    git -C "$WORK_DIR" config user.email >/dev/null 2>&1 \
        || git -C "$WORK_DIR" config user.email "$(git config --global user.email 2>/dev/null || echo tracking@local)"
    git -C "$WORK_DIR" config user.name >/dev/null 2>&1 \
        || git -C "$WORK_DIR" config user.name "$(git config --global user.name 2>/dev/null || echo tracking)"
    # stage everything (respecting gitignore) and commit if there's anything
    git -C "$WORK_DIR" add -A .
    if ! git -C "$WORK_DIR" diff --cached --quiet; then
        git -C "$WORK_DIR" commit -q -m "track: initial sync state"
    fi
    # create the GitHub repo and push
    gh repo create "$name" --private --source "$WORK_DIR" --push
    echo "tracking-work-sync: initialized repo '$name' and pushed from $WORK_DIR"
}

interactive_menu() {
    cat <<EOF
tracking-work-sync setup
------------------------
1) Clone an existing sync repo (for a second/Nth device)
2) Create a new sync repo (first device)
3) Skip — local only

EOF
    read -r -p "Choose [1/2/3]: " choice
    case "$choice" in
        1)
            read -r -p "Clone URL or <owner>/<repo>: " url
            [[ "$url" != *://* && "$url" != *@* ]] && url="https://github.com/$url.git"
            do_clone "$url"
            ;;
        2)
            read -r -p "Repo name [work-tracking]: " name
            do_init "${name:-work-tracking}"
            ;;
        3) do_skip ;;
        *) echo "unknown choice"; exit 1 ;;
    esac
}

# Parse flags.
case "${1:-}" in
    --skip) do_skip ;;
    --clone)
        [[ -z "${2:-}" ]] && { usage; exit 1; }
        do_clone "$2"
        ;;
    --init)
        shift
        name="work-tracking"
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --name) name="$2"; shift 2 ;;
                *) usage; exit 1 ;;
            esac
        done
        do_init "$name"
        ;;
    "") interactive_menu ;;
    -h|--help) usage ;;
    *) usage; exit 1 ;;
esac
