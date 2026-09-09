#!/usr/bin/env bash
# Build a deterministic viz site from the test fixtures and serve it on :8799.
# Used as the Playwright webServer command.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# The repo venv when there is one, else whatever python is on PATH. CI has no
# .venv: it installs the package into the runner's interpreter instead.
if [ -n "${CORTEX_E2E_PYTHON:-}" ]; then
    PY="$CORTEX_E2E_PYTHON"
elif [ -x "$REPO/.venv/bin/python" ]; then
    PY="$REPO/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
else
    echo "serve-fixtures: no python interpreter found" >&2
    exit 1
fi

ROOT="$(mktemp -d)/workspaces"
mkdir -p "$ROOT"
for ws in demo-ws other-ws kb-ghosts-ws authored-ws; do
    cp -r "$REPO/tests/fixtures/$ws" "$ROOT/$ws"
done

OUT="$(mktemp -d)/out"
PYTHONPATH="$REPO/src" "$PY" -m cortex.cli viz build "$ROOT" --out "$OUT" >/dev/null

exec env PYTHONPATH="$REPO/src" "$PY" -m cortex.cli viz serve "$OUT" \
    --host 127.0.0.1 --port 8799 --no-open
