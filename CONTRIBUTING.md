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

PyYAML is the one runtime dependency: `cortex/parser.py` imports it directly,
so anything touching the graph (`query`, `viz`, `inject`) needs it. Everything
else is stdlib.

## Running the tests

There is no single runner. Each suite stands alone, and CI runs all of them:

```bash
python -m pytest -q                                    # 276 tests
bash skills/cortex-tracking/scripts/tests/run.sh       # session/task scripts
bash skills/cortex-tracking/tests/test_cortex.sh       # CLI entry point
bash tests/test_install_uninstall.sh                   # install round trip
bash tests/test_conventional.sh                        # commit message hook
```

The e2e suite drives a real browser and is not part of PR CI:

```bash
bash e2e/run-e2e.sh
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

**Write tests.** Python goes in `cortex/tests/`. Bash suites source
`skills/cortex-tracking/scripts/tests/lib.sh` and use `run_test` / `report`;
copy the shape from `tests/test_install_uninstall.sh`.

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
