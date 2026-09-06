"""Ranking cortex documents: a `World` in, a `SearchResult` out.

Two indexes rather than one, because knowledge prose and task files are
different retrieval problems: different lengths, different fields, and
different intent. BM25's length normalization on a merged corpus would
systematically favour one kind over the other. When a query spans both, the two
ranked lists fuse with Reciprocal Rank Fusion, which uses only rank position
and so needs no score calibration between two incomparable corpora.

Pure: this module decides what is indexable and what a hit looks like, and
`cli.py` decides how it prints.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

from cortex import query as qmod
from cortex.model import Doc, DocId, World
from cortex.sanitize import sanitize
from cortex.search.index import Index, rrf, tokenize


PROSE_KINDS = ("knowledge", "workbench")
TASK_KINDS = ("task",)
_INDEXED_KINDS = PROSE_KINDS + TASK_KINDS

# Fields are concatenated with repetition rather than scored per-field BM25F.
# Repetition is the standard cheap approximation, and BM25's own `b` length
# normalization absorbs the length inflation it causes. The slug is weighted
# because it is how a doc is addressed and cited, so a search for
# `atomic-write-port-pitfalls` should return that doc rather than its citers.
_PROSE_WEIGHTS = (("slug", 3), ("title", 3), ("description", 2), ("type", 2))
_TASK_WEIGHTS = (("slug", 3), ("title", 3), ("description", 2), ("status", 1))

SNIPPET_WIDTH = 96
_WS_RE = re.compile(r"\s+")


@dataclass
class Hit:
    doc_id: DocId
    kind: str
    address: str
    snippet: str
    score: float
    # Only `related` fills this in; `search` leaves it empty, because a hit for
    # terms the user typed already names its own reason.
    terms: list = field(default_factory=list)


@dataclass
class SearchResult:
    """`hits` is bounded by the caller's `max`; `total` is how many matched.
    Same pair as `query.NeighborResult`'s `outgoing` / `outgoing_total`, and for
    the same reason: the CLI needs to say how many results it did not print."""
    hits: list
    total: int


def _field(doc: Doc, name: str):
    return doc.id.slug if name == "slug" else getattr(doc, name, None)


def _doc_tokens(doc: Doc, weights) -> list:
    tokens = []
    for name, weight in weights:
        tokens.extend(tokenize(_field(doc, name)) * weight)
    tokens.extend(tokenize(doc.body))
    return tokens


def _clip(text: str, width: int = SNIPPET_WIDTH) -> str:
    flat = _WS_RE.sub(" ", sanitize(text)).strip()
    return flat if len(flat) <= width else flat[:width] + "..."


def _snippet(doc: Doc, query_tokens) -> str:
    """The first body line sharing a token with the query, else the
    description, else the title.

    Sanitized because a knowledge body can carry ingested text from a codebase
    nobody here wrote, and this line prints straight to a terminal. That is the
    same exposure `cortex/sanitize.py` was added for."""
    wanted = set(query_tokens)
    for line in doc.body.splitlines():
        if wanted & set(tokenize(line)):
            return _clip(line)
    return _clip(doc.description or doc.title or "(no summary)")


def _indexable(world: World, *, names, include_archive) -> dict:
    """Canonical id -> Doc for every in-scope searchable doc. Workspaces and
    sessions are containers rather than documents, and a ghost is the unwritten
    target of a link, so neither is indexed."""
    out = {}
    for key, doc in world.docs.items():
        if doc.id.kind not in _INDEXED_KINDS or doc.ghost:
            continue
        if not include_archive and doc.archived:
            continue
        if names is not None and doc.id.workspace not in names:
            continue
        out[key] = doc
    return out


def _build(docs: dict):
    prose, tasks = Index(), Index()
    for key, doc in docs.items():
        if doc.id.kind in PROSE_KINDS:
            prose.add(key, _doc_tokens(doc, _PROSE_WEIGHTS))
        else:
            tasks.add(key, _doc_tokens(doc, _TASK_WEIGHTS))
    return prose, tasks


def build_indexes(world: World, *, names=None, include_archive: bool = False):
    """`(prose, tasks)`. Two indexes, not one: knowledge prose and task files
    differ in length, in fields, and in what a query about them means, so a
    merged corpus would let BM25's length normalization systematically favour
    one kind over the other."""
    return _build(_indexable(world, names=names,
                             include_archive=include_archive))


def search(world: World, terms, *, kind: str = "all", names=None,
           include_archive: bool = False, max: int = 10) -> SearchResult:
    """Ranked hits for TERMS. `kind` is one of knowledge / workbench / task /
    all; `all` runs both indexes and fuses them with RRF."""
    query_tokens = tokenize(terms if isinstance(terms, str) else " ".join(terms))
    if not query_tokens:
        return SearchResult(hits=[], total=0)
    docs = _indexable(world, names=names, include_archive=include_archive)
    prose, tasks = _build(docs)
    if kind == "all":
        ranked = rrf([prose.search(query_tokens), tasks.search(query_tokens)])
    elif kind in PROSE_KINDS:
        # knowledge and workbench share one index on purpose (same length
        # profile, same fields, same intent), so a single kind is a filter over
        # its results rather than an index of its own.
        ranked = [(key, score) for key, score in prose.search(query_tokens)
                  if docs[key].id.kind == kind]
    elif kind in TASK_KINDS:
        ranked = tasks.search(query_tokens)
    else:
        # Named explicitly rather than falling through to the task index: an
        # unrecognized kind returning task hits reads as a working search.
        raise ValueError(f"unknown search kind: {kind!r}")
    hits = [Hit(doc_id=docs[key].id, kind=docs[key].id.kind, address=key,
                snippet=_snippet(docs[key], query_tokens), score=score)
            for key, score in ranked[:max]]
    return SearchResult(hits=hits, total=len(ranked))


# How many shared terms `related` names per candidate, and how wide its summary
# column runs. Both are narrow so a candidate stays one readable line.
RELATED_TERMS = 5
RELATED_SUMMARY_WIDTH = 56


def _query_tokens(doc: Doc) -> list:
    """The doc-as-query token list: an ordered dedup over title, description,
    and body.

    Deduplicated because `Index.search` scores a repeated query term once per
    occurrence. Handing it a body's raw token list would weight every term by
    its frequency in the *source* doc, so a word the author happened to repeat
    would outweigh the rare term that actually makes two notes related."""
    seen, out = set(), []
    for text in (doc.title, doc.description, doc.body):
        for tok in tokenize(text):
            if tok not in seen:
                seen.add(tok)
                out.append(tok)
    return out


def related(world: World, target_id: DocId, *, names=None,
            include_archive: bool = False, max: int = 5,
            min_score: float = 0.0) -> SearchResult:
    """Link candidates for TARGET: BM25 with the document itself as the query.

    Deriving the query from the doc rather than from terms an agent picks is
    the whole point. A sweep that re-chooses its own search terms per document
    gives different candidates on a second run over an unchanged store, and
    nothing about it is testable.

    Candidates are always TARGET's own kind, so knowledge ranks against
    knowledge. There is no kind selector and deliberately no `all`: fusing two
    corpora with RRF would put `min_score` on a scale where 0.016 is a good
    result, and a threshold nobody can reason about is the same as no
    threshold. One index also keeps the score a raw BM25 number, so
    `min_score` compares like with like across the docs of one sweep."""
    target = world.docs.get(target_id.canonical())
    if target is None:
        raise ValueError(f"no such doc: {target_id.canonical()}")
    kind = target_id.kind
    if kind not in _INDEXED_KINDS:
        # A workspace or session is a container, not a document, so it has no
        # text to query with and no index to rank against.
        raise ValueError(f"cannot rank candidates for kind {kind!r}")
    query_tokens = _query_tokens(target)
    if not query_tokens:
        return SearchResult(hits=[], total=0)
    docs = _indexable(world, names=names, include_archive=include_archive)
    prose, tasks = _build(docs)
    index = prose if kind in PROSE_KINDS else tasks
    excluded = qmod.linked_ids(world, target_id)
    ranked = [(key, score) for key, score in index.search(query_tokens)
              if key not in excluded
              and docs[key].id.kind == kind
              and score >= min_score]
    hits = [Hit(doc_id=docs[key].id, kind=kind, address=key,
                snippet=_clip(docs[key].description or docs[key].title
                              or "(no summary)", RELATED_SUMMARY_WIDTH),
                score=score,
                terms=index.top_terms(query_tokens, key, RELATED_TERMS))
            for key, score in ranked[:max]]
    return SearchResult(hits=hits, total=len(ranked))
