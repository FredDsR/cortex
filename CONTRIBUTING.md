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

## Releasing

Releases are automated. `feat` and `fix` commits on `main` make release-please
open a release pull request; merging that pull request tags the version,
publishes a GitHub Release, and uploads to PyPI. `refactor`, `docs`, `perf` and
the rest appear in the changelog but do not trigger a release on their own, so
a refactor-heavy stretch stays unreleased until a `feat` or `fix` lands.

To force a version, or to release when no commit would otherwise qualify, put a
`Release-As` footer in the commit body:

```bash
git commit --allow-empty -m "chore: release 0.3.0" -m "Release-As: 0.3.0"
```

The PyPI upload waits on an environment approval, so a publish never happens
without someone clicking it.

### If a PyPI upload fails with "filename was previously used"

PyPI blocks a distribution filename **globally and permanently**, and that block
survives project deletion and change of ownership. So a version can be
unpublishable even when the project name itself is unregistered and the whole
pipeline is correct. It means someone once published that exact
name-and-version and deleted it, possibly years ago and possibly not you.

Two things worth knowing, because both cost time to rediscover:

- **A 404 from PyPI's JSON API only means the name is free to claim.** It does
  not mean every version is free to publish, and PyPI exposes no way to
  enumerate blocked filenames. The only signal is the upload itself failing.
- **A failed upload costs nothing.** The rejection happens before anything is
  stored, so no filename is consumed and retrying is free.

The remedy is PyPI's own: pick a version you have not uploaded before and
release that instead, using the `Release-As` footer above.

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
