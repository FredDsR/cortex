# Contributing to cortex

Thanks for considering it. cortex is plain markdown, bash, and one small
Python package, so the setup is short.

## Setup

```bash
git clone https://github.com/FredDsR/cortex.git ~/cortex
cd ~/cortex
python -m venv .venv && source .venv/bin/activate
pip install pytest pyyaml
git config core.hooksPath .githooks   # enables the commit message check
```

`bash install.sh` symlinks the skills into your harness. It is safe to re-run.

PyYAML is the one runtime dependency, declared in `pyproject.toml`,
so anything touching the graph (`query`, `viz`, `inject`) needs it. Everything
else is stdlib.

Adding a harness adapter for session-start injection: register it in
`src/cortex/inject/adapters.py`, the only module that knows any particular
harness exists.

## Running the tests

Two runners, one per language:

```bash
python -m pytest -q          # the Python suite
bash tests/shell/run.sh      # every shell suite
```

`tests/shell/run.sh` runs each `test_*.sh` beside it, covering the session and
task scripts, the CLI entry point, the install round trip, and the commit
message hook.

The e2e suite drives a real browser and is not part of PR CI:

```bash
bash tests/e2e/run-e2e.sh
```

The Python suite needs no install: `pythonpath` in `pyproject.toml` puts `src`
and `tests` on the path. The shell suite exercises the `cortex` command, so
install the package first:

```bash
uv pip install -e ".[dev]"   # or: pip install -e ".[dev]"
```

## Commits and pull requests

**The PR title matters more than your commit messages.** This repo
squash-merges, so the title becomes the single commit on `main` while your
individual commits are discarded. CI blocks on the title.

Both follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope)?: subject
```

Types live in `.conventional-types`: `feat`, `fix`, `docs`, `refactor`,
`test`, `chore`, `perf`, `ci`, `build`, `revert`. Optional scopes name a
module: `kb`, `viz`, `sync`, `inject`, `tracking`, `store`, `ingest`, `cli`.
Keep the header at 72 characters or fewer, with no trailing period. Mark a
breaking change with `!`, as in `feat(store)!: rename the resolver`.

Branches use `type/short-description`, for example `feat/bm25-search`. CI
warns on other shapes but does not block, since the branch name never reaches
`main`.

The local hook gives you the same check at commit time. It is convenience
rather than enforcement, and `--no-verify` skips it.

## Conventions worth knowing

**Write tests.** Python goes in `tests/unit/`, with shared paths in
`tests/support.py`. Bash suites go in `tests/shell/`, source the `lib.sh`
beside them, and use `run_test` / `report`; copy the shape from any
`test_*.sh` already there. `tests/shell/run.sh` picks up a new file
automatically.

**Never use an em dash or en dash** in code, docs, or commit messages.

**Do not modify `docs/superpowers/`.** It is an internal archive of dated
design and planning documents, and it is gitignored.

**Do not paste real store contents** into an issue or PR. `~/.cortex/` holds
actual workspace, session, and client names. Reproduce with the synthetic
fixtures in `cortex/tests/fixtures/`.

## Known limitation

`skills/cortex-tracking/SKILL.md:40` hardcodes
`$HOME/.claude/skills/cortex-tracking/scripts/session_start.sh`, and the
`$SKILL_DIR` referenced at lines 69 and 98 is not defined anywhere. On Claude
Code with a symlink install this resolves; on other harnesses it does not.
This is the first thing that breaks when porting, and it is not yet fixed.

## Reporting problems

Bugs and features go in [issues](https://github.com/FredDsR/cortex/issues).
Security reports follow [SECURITY.md](SECURITY.md) instead.
