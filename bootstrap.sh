#!/usr/bin/env bash
# One-line installer for cortex.
#
#   curl -fsSL https://raw.githubusercontent.com/FredDsR/cortex/main/bootstrap.sh | bash
#
# Pass install.sh flags through with `bash -s --`:
#
#   curl -fsSL .../bootstrap.sh | bash -s -- --project ~/some-repo
#
# install.sh cannot be piped directly: it symlinks INTO the repo, so the repo
# has to exist on disk. This clones it first, then hands off.
#
# CORTEX_DIR  where to clone (default: ~/cortex)
# CORTEX_REPO which repo to clone (default: the canonical one)
set -euo pipefail

CORTEX_DIR="${CORTEX_DIR:-$HOME/cortex}"
CORTEX_REPO="${CORTEX_REPO:-https://github.com/FredDsR/cortex.git}"

die() { echo "error: $*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || die "git is required but not on PATH."

# Recognise an existing cortex checkout by its shape rather than its remote URL,
# so a fork, a rename, or an ssh-vs-https remote all still count as "already
# installed here" instead of being treated as a stranger's directory.
is_cortex_checkout() {
    [ -d "$1/.git" ] && [ -f "$1/install.sh" ] && [ -d "$1/skills" ]
}

if [ -e "$CORTEX_DIR" ]; then
    if is_cortex_checkout "$CORTEX_DIR"; then
        echo "cortex: updating existing checkout at $CORTEX_DIR"
        git -C "$CORTEX_DIR" pull --ff-only \
            || die "could not fast-forward $CORTEX_DIR. Resolve it by hand, then re-run."
    else
        # Never clobber a directory we did not create. A piped installer is
        # precisely the case where nobody read the script first.
        die "$CORTEX_DIR exists and is not a cortex checkout.
  Move it aside, or choose another location:
    curl -fsSL <url> | CORTEX_DIR=~/somewhere-else bash"
    fi
else
    echo "cortex: cloning $CORTEX_REPO into $CORTEX_DIR"
    git clone --depth 1 "$CORTEX_REPO" "$CORTEX_DIR" \
        || die "clone failed."
fi

[ -f "$CORTEX_DIR/install.sh" ] || die "$CORTEX_DIR/install.sh missing after checkout."

echo ""
exec bash "$CORTEX_DIR/install.sh" "$@"
