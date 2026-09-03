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
