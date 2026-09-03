"""BM25 keyword search over a parsed World, fused with RRF.

`search` powers `cortex query search <terms>`: the headless counterpart to the
viz's client-side MiniSearch. Before this, the only search in the family ran in
a browser, so an agent could not answer "do we already know something about X"
without a human opening a tab. `cortex kb index` is a table of contents over
`description:` fields, which answers a different question.

Two indexes rather than one, because knowledge prose and task files are
different retrieval problems: different lengths, different fields, and
different intent. BM25's length normalization on a merged corpus would
systematically favour one kind over the other. When a query spans both, the two
ranked lists fuse with Reciprocal Rank Fusion, which uses only rank position
and so needs no score calibration between two incomparable corpora.

The index is derived and disposable, rebuilt on every invocation, matching how
`SUMMARY.md` and `INDEX.md` are already derived rather than stored.

Pure (stdlib only); the CLI at the bottom is this module's only IO.
"""
from __future__ import annotations
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from cortex.model import Doc, DocId, World
from cortex.sanitize import sanitize

# Okapi BM25's conventional defaults. k1 controls term-frequency saturation,
# b how strongly document length normalizes.
K1 = 1.5
B = 0.75

# Unicode word characters with underscore excluded, so `snake_case` splits and
# a hyphenated slug splits too. The latter is what makes a search for "active
# pointer" reach `close-day-active-pointer`, which is how these docs are named.
_TOKEN_RE = re.compile(r"[^\W_]+")


def tokenize(text) -> list:
    """Lowercased word tokens. No stemming: `retries` will not match `retry`.
    A stdlib stemmer carries its own false-positive surface, and a missed hit is
    a more honest failure than a subtly wrong ranking."""
    if not text:
        return []
    return _TOKEN_RE.findall(str(text).casefold())


@dataclass
class Index:
    """An in-memory BM25 index over string keys.

    Keys are canonical doc ids, which double as the tie-break, so a query over
    an unchanged store always prints the same order."""
    k1: float = K1
    b: float = B
    _postings: dict = field(default_factory=dict)   # term -> {key: freq}
    _lengths: dict = field(default_factory=dict)    # key -> token count

    def __len__(self) -> int:
        return len(self._lengths)

    def add(self, key: str, tokens: list) -> None:
        self._lengths[key] = len(tokens)
        for term, freq in Counter(tokens).items():
            self._postings.setdefault(term, {})[key] = freq

    def _idf(self, term: str) -> float:
        """`ln(1 + (N - df + 0.5) / (df + 0.5))`. The `1 +` is what keeps this
        positive when df > N/2; the textbook form goes negative there, so a
        term appearing in most documents would demote the ones holding it."""
        n = len(self._lengths)
        df = len(self._postings.get(term, ()))
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(self, query_tokens: list, max: int | None = None) -> list:
        """Ranked `(key, score)`, descending by score then ascending by key.
        Only documents matching at least one query term appear."""
        if not self._lengths or not query_tokens:
            return []
        avgdl = sum(self._lengths.values()) / len(self._lengths)
        scores: dict = {}
        for term in query_tokens:
            postings = self._postings.get(term)
            if not postings:
                continue
            idf = self._idf(term)
            for key, freq in postings.items():
                dl = self._lengths[key]
                denom = freq + self.k1 * (1 - self.b + self.b * dl / avgdl)
                scores[key] = scores.get(key, 0.0) + idf * freq * (self.k1 + 1) / denom
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked if max is None else ranked[:max]


# Reciprocal Rank Fusion's conventional constant. It damps the gap between the
# top ranks, so a first place is worth meaningfully more than a second but not
# so much that a document ranked well by both lists cannot overtake it.
RRF_K = 60


def rrf(ranked_lists: list, k: int = RRF_K) -> list:
    """Fuse ranked `(key, score)` lists by Reciprocal Rank Fusion:
    `score(d) = sum over lists of 1 / (k + rank(d))`, rank 1-based.

    Only rank position is used. BM25 scores from two different corpora are not
    on a common scale, so a naive merge would let whichever index happens to
    produce larger magnitudes dominate regardless of relevance. This also
    degrades gracefully: a list that returns nothing contributes nothing."""
    scores: dict = {}
    for ranked in ranked_lists:
        for rank, (key, _score) in enumerate(ranked, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


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


def _clip(text: str) -> str:
    flat = _WS_RE.sub(" ", sanitize(text)).strip()
    return flat if len(flat) <= SNIPPET_WIDTH else flat[:SNIPPET_WIDTH] + "..."


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
    else:
        ranked = tasks.search(query_tokens)
    hits = [Hit(doc_id=docs[key].id, kind=docs[key].id.kind, address=key,
                snippet=_snippet(docs[key], query_tokens), score=score)
            for key, score in ranked[:max]]
    return SearchResult(hits=hits, total=len(ranked))
