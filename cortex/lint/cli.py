"""`cortex kb lint`: argparse in, terminal out.

The only IO in this package beyond `fix.py`'s writes. Every write to a terminal
is here, which is what makes the sanitization rule auditable: a doc id is a
store path and stays byte-exact so it can be opened, and everything else is doc
content that `kb ingest` may have extracted from a codebase nobody here wrote.
See cortex/sanitize.py.
"""
from __future__ import annotations
import datetime
from pathlib import Path

from cortex import parser
from cortex import store
from cortex.errors import CortexError, UsageError
from cortex.kb import _home, parse_max, sync_after
from cortex.lint.checks import (CHECKS, MAX_FILE_BYTES, MAX_TOTAL_BYTES,
                                SELECTABLE, WORKLIST, Finding, collect,
                                index_repo, overlaps)
from cortex.lint.fix import apply_fixes
from cortex.sanitize import sanitize


def _parse_checks(raw: str) -> tuple:
    if not raw:
        return SELECTABLE
    picked = {c.strip() for c in raw.split(",") if c.strip()}
    bad = sorted(c for c in picked if c not in SELECTABLE)
    if bad:
        raise UsageError(f"--check: unknown {', '.join(bad)}; "
                         f"choose from {', '.join(SELECTABLE)}")
    return tuple(c for c in SELECTABLE if c in picked)


def _scope(args) -> store.Scope:
    """Thin adapter: unpack argparse and hand off to the shared resolver.
    `cortex query search` and `cortex query related` need the identical scope,
    so the logic lives in `store`, beside every other piece of workspace
    resolution."""
    return store.resolve_scope(args.workspace, home=_home(), cwd=Path.cwd())


def _repo_for(root: Path, ws: str, explicit: str) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_dir():
            raise CortexError(f"--repo path not found: {p}")
        return p
    recorded = store._meta_cwd(root / ws)
    if recorded:
        p = Path(recorded).expanduser()
        if p.is_dir():
            return p
    # A repo-local store is `<repo>/.cortex`, so `_scope`'s root IS the repo it
    # documents. Without this, `cortex kb lint` in a repo with a local store
    # skips dead-ref and asks for a --repo that is the directory it is standing
    # in. Guarded on the root as well as the name, since a global workspace may
    # itself be called `.cortex` and its root is not anybody's repo.
    if ws == ".cortex" and root.resolve() != (_home() / ".cortex" / "workspaces").resolve():
        return root
    return None


def _print_rows(header: str, rows: list, max_n: int) -> None:
    if not rows:
        return
    print(header)
    for r in rows[:max_n]:
        print(r)
    if len(rows) > max_n:
        print(f"... {len(rows) - max_n} more (raise --max)")
    print()


def _row(f: Finding) -> str:
    # The doc id is a store path and stays byte-exact so it can be opened; the
    # detail is doc content, which `kb ingest` may have extracted from a
    # codebase nobody here wrote, so it is sanitized before it reaches an
    # agent's terminal. Same split as ingest's worklist. See cortex/sanitize.py.
    return f"{f.doc}  ->  {sanitize(f.detail)}"


def cmd_lint(args) -> int:
    if args.repo and args.workspace == "all":
        raise UsageError("--repo cannot be combined with --workspace=all")
    selected = _parse_checks(args.check)
    checks = tuple(c for c in selected if c in CHECKS)
    max_n = parse_max(args.max)
    stale_days = parse_max(args.stale_days, "--stale-days")
    root, names, scope_notes = _scope(args)

    # Archives are always parsed, never always linted: a live task pointing at
    # an archived one is a resolved reference, and leaving archives out would
    # report every such link as broken. `--archive` decides what gets checked,
    # not what exists.
    world = parser.parse_world(root, include_archive=True)

    # Scope notes lead: what the run covered frames every row under it.
    notes, repos = list(scope_notes), {}
    if "dead-ref" in checks:
        for ws in names:
            repo = _repo_for(root, ws, args.repo)
            if repo is None:
                notes.append(f"dead-ref skipped for {ws}: no repo "
                             f"(pass --repo, or set cwd: in the workspace .meta)")
            else:
                repos[ws] = index_repo(repo)
                if repos[ws].partial:
                    notes.append(f"dead-ref read only part of {repo.name}'s text "
                                 f"(files over {MAX_FILE_BYTES >> 20} MiB, or past "
                                 f"{MAX_TOTAL_BYTES >> 20} MiB total): a symbol or "
                                 f"flag living only in a skipped file reads as dead")

    # The derived indexes this run covers: one per workspace, plus the root
    # brain index under `all`, which belongs to no workspace and would
    # otherwise never be checked -- a leftover root `INDEX.md` staying
    # invisible is the same stale artefact the per-workspace check exists for.
    index_dirs = [(root / ws / "knowledge", ws) for ws in sorted(names)]
    if args.workspace == "all":
        index_dirs.append((_home() / ".cortex" / "knowledge", "~/.cortex"))

    findings = collect(world, names=names, checks=checks, repos=repos,
                       today=datetime.date.today(), stale_days=stale_days,
                       archived=args.archive, index_dirs=index_dirs)

    fixed, written = [], []
    if args.fix:
        fixed, written = apply_fixes(findings)
        done = {id(f) for f in fixed}
        findings = [f for f in findings if id(f) not in done]

    for check in checks:
        _print_rows(f"## {check}",
                    [_row(f) for f in findings if f.check == check], max_n)
    _print_rows("## fixed (addresses rewritten; no claim changed)",
                [_row(f) for f in fixed], max_n)

    pairs = overlaps([world.docs[c] for c in sorted(world.docs)
                       if world.docs[c].id.kind == "knowledge"
                       and world.docs[c].id.workspace in names
                       and (args.archive or not world.docs[c].archived)]
                      ) if WORKLIST in selected else []
    if pairs:
        print("## agent worklist (needs judgment)")
        print("# Candidate pairs only. Same type and overlapping summaries is"
              " what a contradiction or a superseded claim looks like from the"
              " outside; it is also what two legitimately distinct notes look"
              " like. Read them before concluding anything.")
        for row in pairs[:max_n]:
            print(sanitize(row))
        if len(pairs) > max_n:
            print(f"... {len(pairs) - max_n} more (raise --max)")
        print()

    _print_rows("## notes", notes, max_n)

    print("## summary")
    if findings:
        tally = ", ".join(f"{c} {sum(1 for f in findings if f.check == c)}"
                          for c in checks if any(f.check == c for f in findings))
        n = len(findings)
        print(f"{n} finding{'' if n == 1 else 's'}: {tally}")
    else:
        print("no findings")
    if written:
        print(f"fixed {len(fixed)} reference{'' if len(fixed) == 1 else 's'} "
              f"in {len(written)} doc{'' if len(written) == 1 else 's'}")
        sync_after("lint", "refs", f"{len(written)} docs")

    return 1 if (args.strict and findings) else 0
