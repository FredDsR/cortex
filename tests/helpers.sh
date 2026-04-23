#!/usr/bin/env bash
# Shared test helpers. Source this from each test_*.sh.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$SKILL_DIR/scripts"

# Create a fresh tempdir that acts as HOME for the test; returns the path.
make_test_home() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/twsync-test-XXXXXX")"
    mkdir -p "$tmp/.work"
    echo "$tmp"
}

# Remove a test home created by make_test_home.
cleanup_test_home() {
    local home_dir="$1"
    [[ -n "$home_dir" && -d "$home_dir" ]] && rm -rf "$home_dir"
}

# Install a fake `gh` that records its args and returns success.
# Usage: mock_gh_path "$test_home"  → prints a dir to prepend to PATH
mock_gh_path() {
    local home_dir="$1"
    local bindir="$home_dir/fakebin"
    mkdir -p "$bindir"
    cat > "$bindir/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >> "${GH_CALL_LOG:-/tmp/gh_calls.log}"
case "$1" in
    auth)
        # `gh auth status` succeeds
        exit 0
        ;;
    repo)
        # `gh repo create <name> --private --source <dir> --push`
        # simulate by setting a remote to a local bare repo and pushing
        shift
        if [[ "$1" == "create" ]]; then
            shift
            local name="$1"; shift
            # find --source
            local source_dir=""
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --source) source_dir="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            local bare="$(dirname "$source_dir")/${name}.git"
            git init --bare "$bare" >/dev/null
            git -C "$source_dir" remote add origin "$bare"
            git -C "$source_dir" push -u origin HEAD >/dev/null 2>&1 || true
        fi
        exit 0
        ;;
esac
exit 0
EOF
    chmod +x "$bindir/gh"
    echo "$bindir"
}

# Create a bare git repo and return its path (used as a fake remote to clone from).
make_fake_remote() {
    local dir="$1"
    git init --bare --initial-branch=main "$dir" >/dev/null
    echo "$dir"
}

# Assert helpers
assert_eq() {
    local expected="$1" actual="$2" msg="${3:-}"
    if [[ "$expected" != "$actual" ]]; then
        echo "FAIL: ${msg:-assertion}: expected '$expected', got '$actual'" >&2
        return 1
    fi
}

assert_exit() {
    local expected_code="$1"; shift
    local actual=0
    "$@" >/dev/null 2>&1 || actual=$?
    assert_eq "$expected_code" "$actual" "exit code of: $*"
}

assert_file() {
    local path="$1"
    [[ -f "$path" ]] || { echo "FAIL: file not found: $path" >&2; return 1; }
}

assert_not_file() {
    local path="$1"
    [[ ! -f "$path" ]] || { echo "FAIL: file should not exist: $path" >&2; return 1; }
}
