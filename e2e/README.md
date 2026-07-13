# viz e2e (Playwright)

Browser tests for the `cortex viz` world-search feature. They build a
deterministic site from `cortex/tests/fixtures`, serve it, and drive it with the
Playwright browser library.

## Run

```bash
cd e2e
bun install                       # once: @playwright/test
bunx playwright install chromium  # once: browser (or reuse a cached build)
bash run-e2e.sh                   # build + serve fixtures, run assert.mjs, tear down
```

Results print as `PASS:`/`FAIL:` lines and a summary; exit code is non-zero on
any failure. `assert.mjs` auto-discovers a cached chromium under
`~/.cache/ms-playwright` (via `executablePath`) when Playwright's pinned build
is not downloadable.

## Scenarios (`assert.mjs`)

Index loads + box enabled; exact match; fuzzy/typo match; first-paragraph body
match; keyboard (ArrowDown + Enter); Escape + outside-click close; in-scope
result loads content + highlights + pulses; out-of-scope result navigates to the
doc's home page and opens it.
