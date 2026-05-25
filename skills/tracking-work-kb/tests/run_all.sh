#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for t in "$SELF_DIR"/test_*.sh; do
    echo ">>> $(basename "$t")"
    bash "$t"
done
echo "ALL PASS"
