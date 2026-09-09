"""`cortex query search` and `cortex query related`: argparse in, terminal out.

The only IO in this package. Every write to a terminal is here, which is what
makes the sanitization rule auditable: an address is a store path and stays
byte-exact so it can be opened, and a snippet is doc content that `kb ingest`
may have extracted from a codebase nobody here wrote. `rank._snippet` is where
that sanitizing happens. See cortex/sanitize.py.
"""
from __future__ import annotations
import math
from pathlib import Path

from cortex import query as qmod
from cortex import store
from cortex.errors import CortexError
from cortex.model import DocId
from cortex.parser import parse_world
from cortex.search.rank import SearchResult, related, search


def _print_notes(notes) -> None:
    """Trailing `# ...` lines naming what the scope left out. After the hits,
    alongside `(+N more)`: both say what the ranking you just read excludes."""
    for note in notes:
        print(f"# {note}")


def _print_result(res: SearchResult, max_n: int) -> None:
    """No score column. Under `--kind all` the number is an RRF score, which is
    not comparable to a BM25 score and carries nothing a reader can act on;
    rank order is the signal."""
    if not res.hits:
        print("(no matches)")
        return
    kw = max(len(h.kind) for h in res.hits)
    aw = max(len(h.address) for h in res.hits)
    for rank, h in enumerate(res.hits, start=1):
        print(f"{rank:>3}  {h.kind:<{kw}}  {h.address:<{aw}}  {h.snippet}")
    if res.total > max_n:
        print(f"(+{res.total - max_n} more; raise --max)")


def cmd_search(args) -> int:
    max_n = qmod.parse_max(args.max)
    root, names, notes = store.resolve_scope(args.workspace,
                                             home=Path.home(), cwd=Path.cwd())
    # Always parse the archive; `--archive` gates what gets indexed, so the flag
    # stays a filter rather than a second walk of the store.
    world = parse_world(root, include_archive=True)
    res = search(world, args.terms, kind=args.kind, names=names,
                 include_archive=args.archive, max=max_n)
    _print_result(res, max_n)
    _print_notes(notes)
    return 0


def parse_min_score(raw: str) -> float:
    """`--min-score` is a raw BM25 score, so it is corpus-relative and has no
    defensible default above zero. It filters before truncation, so `(+N more)`
    counts what passed the threshold rather than what merely matched."""
    try:
        f = float(raw)
    except (TypeError, ValueError):
        raise CortexError(f"--min-score must be a number, got {raw!r}")
    # `nan` and `inf` parse as floats but are not thresholds: every `score >=
    # nan` is False, so a typo would silently print `(no candidates)` over a
    # store that has them.
    if not math.isfinite(f):
        raise CortexError(f"--min-score must be a finite number, got {raw!r}")
    if f < 0:
        raise CortexError("--min-score must be >= 0")
    return f


def _print_related(res: SearchResult, target: DocId, kind: str,
                   max_n: int) -> None:
    """One line per candidate: rank, score, address, summary, and the shared
    terms that earned the rank. No kind column, because a run ranks exactly one
    kind.

    `search` omits its score because under `--kind all` it is an RRF number on
    no meaningful scale. Here it is a raw BM25 score over one index, and it is
    printed because it is the only way to calibrate `--min-score`: a threshold
    flag whose values you cannot see is the decorative knob it was added to
    avoid. It is comparable within one run and not across two."""
    print(f"{target.canonical()}  (candidates: {kind})")
    if not res.hits:
        print("(no candidates)")
        return
    aw = max(len(h.address) for h in res.hits)
    sw = max(len(h.snippet) for h in res.hits)
    for rank, h in enumerate(res.hits, start=1):
        shared = ", ".join(h.terms) or "(none)"
        print(f"{rank:>3}  {h.score:>8.2f}  {h.address:<{aw}}  "
              f"{h.snippet:<{sw}}  shared: {shared}")
    if res.total > max_n:
        print(f"(+{res.total - max_n} more; raise --max)")


def cmd_related(args) -> int:
    max_n = qmod.parse_max(args.max)
    min_score = parse_min_score(args.min_score)
    root, names, notes = store.resolve_scope(args.workspace,
                                             home=Path.home(), cwd=Path.cwd())
    world = parse_world(root, include_archive=True)
    # Resolve the slug inside the scope that will be ranked. The parse root is a
    # whole store, so an unqualified slug would otherwise resolve against every
    # workspace in it: a doc from a workspace `names` excludes would be ranked
    # against a corpus it is not part of, and a slug reused in two workspaces
    # would report as ambiguous even when only one of them is in scope. Under
    # `all` the two scopes already coincide.
    scope_ws = "all" if args.workspace == "all" else names[0]
    doc = qmod.resolve_one(world, args.slug, workspace=scope_ws,
                           session=args.session, kind=args.kind)
    # No candidate-kind flag: candidates are always the resolved doc's own kind,
    # so `--kind` keeps the one meaning it has on `neighbors` (narrow an
    # ambiguous slug) instead of quietly meaning two things on one command.
    res = related(world, doc.id, names=names, include_archive=args.archive,
                  max=max_n, min_score=min_score)
    _print_related(res, doc.id, doc.id.kind, max_n)
    _print_notes(notes)
    return 0
