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

`related` powers `cortex query related <slug>`: the same ranking with a
document as the query instead of terms, so link discovery is deterministic
rather than a per-run judgment call about which words to search for.

The index is derived and disposable, rebuilt on every invocation, matching how
`SUMMARY.md` and `INDEX.md` are already derived rather than stored.

Pure (stdlib only); the CLI at the bottom is this module's only IO.
"""
from __future__ import annotations
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from cortex import query as qmod
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

    def _avgdl(self) -> float:
        return sum(self._lengths.values()) / len(self._lengths)

    def _term_score(self, idf: float, freq: int, dl: int, avgdl: float) -> float:
        """One term's BM25 contribution to one document."""
        denom = freq + self.k1 * (1 - self.b + self.b * dl / avgdl)
        return idf * freq * (self.k1 + 1) / denom

    def search(self, query_tokens: list, max: int | None = None) -> list:
        """Ranked `(key, score)`, descending by score then ascending by key.
        Only documents matching at least one query term appear."""
        if not self._lengths or not query_tokens:
            return []
        avgdl = self._avgdl()
        scores: dict = {}
        for term in query_tokens:
            postings = self._postings.get(term)
            if not postings:
                continue
            idf = self._idf(term)
            for key, freq in postings.items():
                scores[key] = scores.get(key, 0.0) + self._term_score(
                    idf, freq, self._lengths[key], avgdl)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked if max is None else ranked[:max]

    def top_terms(self, query_tokens: list, key: str, max_terms: int) -> list:
        """The query terms that actually earned KEY its score, highest
        contribution first, then alphabetically.

        `query related` prints these so a candidate's rank is explainable. A
        ranked list nobody can interrogate gets either trusted blindly or
        ignored, and both are worse than a short list of the shared words."""
        if key not in self._lengths or not query_tokens:
            return []
        avgdl, dl = self._avgdl(), self._lengths[key]
        scored = []
        for term in dict.fromkeys(query_tokens):
            freq = self._postings.get(term, {}).get(key)
            if not freq:
                continue
            scored.append((self._term_score(self._idf(term), freq, dl, avgdl), term))
        scored.sort(key=lambda st: (-st[0], st[1]))
        return [term for _score, term in scored[:max_terms]]


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


# --- CLI (the only IO in this module) ---
from pathlib import Path

from cortex import store
from cortex.errors import CortexError
from cortex.parser import parse_world


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
    doc = qmod.resolve_one(world, args.slug, workspace=args.workspace,
                           session=args.session, kind=args.kind)
    # No candidate-kind flag: candidates are always the resolved doc's own kind,
    # so `--kind` keeps the one meaning it has on `neighbors` (narrow an
    # ambiguous slug) instead of quietly meaning two things on one command.
    res = related(world, doc.id, names=names, include_archive=args.archive,
                  max=max_n, min_score=min_score)
    _print_related(res, doc.id, doc.id.kind, max_n)
    _print_notes(notes)
    return 0
