import math

import pytest

from cortex import search


def _approx(value):
    return pytest.approx(value, rel=1e-9)


# --- tokenize ---

def test_tokenize_casefolds_and_splits_on_punctuation():
    assert search.tokenize("Atomic Writes, Ported!") == ["atomic", "writes", "ported"]


def test_tokenize_splits_hyphens_and_underscores():
    # This is what makes a search for "active pointer" find
    # close-day-active-pointer, and "parse world" find parse_world.
    assert search.tokenize("close-day-active-pointer") == [
        "close", "day", "active", "pointer"]
    assert search.tokenize("parse_world") == ["parse", "world"]


def test_tokenize_keeps_digits_and_unicode_letters():
    assert search.tokenize("BM25 café") == ["bm25", "café"]


def test_tokenize_on_empty_and_punctuation_only():
    assert search.tokenize("") == []
    assert search.tokenize("... --- ...") == []


def test_tokenize_accepts_none_as_empty():
    assert search.tokenize(None) == []


# --- BM25 ---

def test_idf_stays_positive_for_a_term_in_every_document():
    # The textbook idf goes negative once df > N/2, which would make a common
    # term actively demote the documents holding it.
    idx = search.Index()
    for i in range(5):
        idx.add(f"d{i}", ["cortex", f"other{i}"])
    hits = idx.search(["cortex"])
    assert len(hits) == 5
    assert all(score > 0 for _, score in hits)


def test_bm25_score_matches_hand_computation():
    # Corpus: 3 docs, "retry" in d1 twice and d2 once, absent from d3.
    idx = search.Index()
    idx.add("d1", ["retry", "retry", "backoff", "sync"])       # dl 4, f 2
    idx.add("d2", ["retry", "push"])                           # dl 2, f 1
    idx.add("d3", ["unrelated", "words", "here", "entirely"])  # dl 4, f 0
    hits = dict(idx.search(["retry"]))

    n, df = 3, 2
    avgdl = (4 + 2 + 4) / 3
    idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
    k1, b = 1.5, 0.75

    def expected(f, dl):
        return idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))

    assert hits["d1"] == _approx(expected(2, 4))
    assert hits["d2"] == _approx(expected(1, 2))
    assert "d3" not in hits


def test_shorter_document_outranks_longer_at_equal_frequency():
    idx = search.Index()
    idx.add("short", ["retry", "sync"])
    idx.add("long", ["retry"] + [f"filler{i}" for i in range(50)])
    assert [key for key, _ in idx.search(["retry"])] == ["short", "long"]


def test_repeated_term_outranks_single_occurrence_at_equal_length():
    idx = search.Index()
    idx.add("twice", ["retry", "retry"])
    idx.add("once", ["retry", "filler"])
    assert [key for key, _ in idx.search(["retry"])] == ["twice", "once"]


def test_multi_term_query_sums_contributions():
    idx = search.Index()
    idx.add("both", ["retry", "backoff"])
    idx.add("one", ["retry", "unrelated"])
    idx.add("neither", ["nothing", "relevant"])
    assert [key for key, _ in idx.search(["retry", "backoff"])] == ["both", "one"]


def test_unknown_term_returns_nothing():
    idx = search.Index()
    idx.add("d1", ["retry"])
    assert idx.search(["nonexistent"]) == []


def test_search_on_empty_index_returns_nothing():
    assert search.Index().search(["retry"]) == []


def test_empty_query_returns_nothing():
    idx = search.Index()
    idx.add("d1", ["retry"])
    assert idx.search([]) == []


def test_max_truncates_without_reordering():
    idx = search.Index()
    idx.add("short", ["retry"])
    idx.add("long", ["retry"] + [f"f{i}" for i in range(20)])
    assert [k for k, _ in idx.search(["retry"], max=1)] == ["short"]


def test_equal_scores_break_ties_on_key():
    idx = search.Index()
    idx.add("zeta", ["retry", "x"])
    idx.add("alpha", ["retry", "y"])
    assert [k for k, _ in idx.search(["retry"])] == ["alpha", "zeta"]


def test_len_counts_added_documents():
    idx = search.Index()
    idx.add("d1", ["a"])
    idx.add("d2", ["b"])
    assert len(idx) == 2


# --- RRF ---

def test_rrf_beats_a_naive_score_merge():
    # `big` tops a corpus whose scores run large; `small` tops a corpus whose
    # scores run tiny. A naive merge on raw score would rank `runner_up`
    # (40.0, second place) above `small` (0.9, first place). RRF sees only rank,
    # so both list winners come first.
    loud = [("big", 100.0), ("runner_up", 40.0)]
    quiet = [("small", 0.9), ("small_2", 0.4)]
    fused = [key for key, _ in search.rrf([loud, quiet])]
    assert set(fused[:2]) == {"big", "small"}
    assert set(fused[2:]) == {"runner_up", "small_2"}


def test_rrf_score_is_the_sum_of_reciprocal_ranks():
    a = [("shared", 9.0), ("only_a", 1.0)]
    b = [("only_b", 5.0), ("shared", 2.0)]
    fused = dict(search.rrf([a, b], k=60))
    assert fused["shared"] == _approx(1 / 61 + 1 / 62)
    assert fused["only_a"] == _approx(1 / 62)
    assert fused["only_b"] == _approx(1 / 61)


def test_rrf_promotes_a_document_ranked_by_both_lists():
    a = [("x", 9.0), ("shared", 8.0)]
    b = [("y", 9.0), ("shared", 8.0)]
    assert [key for key, _ in search.rrf([a, b])][0] == "shared"


def test_rrf_degrades_when_one_list_is_empty():
    a = [("x", 1.0), ("y", 0.5)]
    assert [key for key, _ in search.rrf([a, []])] == ["x", "y"]


def test_rrf_of_nothing_is_nothing():
    assert search.rrf([]) == []
    assert search.rrf([[], []]) == []


def test_rrf_breaks_ties_on_key():
    a = [("zeta", 1.0)]
    b = [("alpha", 1.0)]
    assert [key for key, _ in search.rrf([a, b])] == ["alpha", "zeta"]
