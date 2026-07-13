#!/usr/bin/env bash
# Self-contained e2e run: build+serve the fixture site, drive it with the
# Playwright library (assert.mjs), tear down. Writes results to run.log.
set -uo pipefail
cd "$(dirname "$0")"
LOG="run.log"; : > "$LOG"

bash serve-fixtures.sh >server.log 2>&1 &
SRV=$!

# wait for the server (internal sleeps are fine here; this is a bg script)
up=""
for i in $(seq 1 60); do
    if curl -s -o /dev/null "http://127.0.0.1:8799/"; then up=1; break; fi
    sleep 1
done
if [ -z "$up" ]; then echo "SERVER FAILED TO START" >>"$LOG"; cat server.log >>"$LOG"; kill "$SRV" 2>/dev/null; exit 1; fi

"$HOME/.bun/bin/bun" run assert.mjs >>"$LOG" 2>&1
RC=$?
kill "$SRV" 2>/dev/null
echo "EXIT=$RC" >>"$LOG"
exit "$RC"
