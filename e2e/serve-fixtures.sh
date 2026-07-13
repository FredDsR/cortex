#!/usr/bin/env bash
# Build a deterministic viz site from the test fixtures and serve it on :8799.
# Used as the Playwright webServer command.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/.venv/bin/python"

ROOT="$(mktemp -d)/workspaces"
mkdir -p "$ROOT"
for ws in demo-ws other-ws kb-ghosts-ws authored-ws; do
    cp -r "$REPO/cortex/tests/fixtures/$ws" "$ROOT/$ws"
done

OUT="$(mktemp -d)/out"
PYTHONPATH="$REPO" "$PY" -m cortex.cli viz build "$ROOT" --out "$OUT" >/dev/null

exec env PYTHONPATH="$REPO" "$PY" -m cortex.cli viz serve "$OUT" \
    --host 127.0.0.1 --port 8799 --no-open
