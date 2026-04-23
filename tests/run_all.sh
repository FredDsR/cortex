#!/usr/bin/env bash
# Run all test_*.sh files in this directory. Exit non-zero if any fails.
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

fail=0
for t in "$SELF_DIR"/test_*.sh; do
    echo ">>> $t"
    if ! bash "$t"; then
        echo "!!! FAIL: $t"
        fail=1
    fi
done

if [[ $fail -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "TEST FAILURES PRESENT"
    exit 1
fi
