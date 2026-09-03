import math

import pytest

from cortex import search
from cortex.model import Doc, DocId, World


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


# --- World-level search ---

def _doc(kind, slug, *, body="", title="", description=None, type=None,
         status=None, workspace="ws", session="s1", archived=False):
    did = DocId(kind=kind, workspace=workspace,
                session=None if kind == "knowledge" else session, slug=slug)
    return Doc(id=did, title=title or slug, body=body, frontmatter={},
               rel_path=None, status=status, archived=archived,
               type=type, description=description)


def _world(*docs):
    root = Doc(id=DocId(kind="root"), title="/", body="", frontmatter={},
               rel_path=None)
    return World(root=root, docs={d.id.canonical(): d for d in docs})


def test_search_finds_a_term_in_a_knowledge_body():
    w = _world(_doc("knowledge", "retry-policy",
                    body="Exponential backoff on 5xx retries."))
    res = search.search(w, "backoff")
    assert [h.address for h in res.hits] == ["ws/knowledge/retry-policy"]
    assert res.hits[0].kind == "knowledge"
    assert res.total == 1


def test_slug_match_outranks_a_body_only_match():
    w = _world(
        _doc("knowledge", "atomic-writes", body="Unrelated prose entirely."),
        _doc("knowledge", "other-note", body="atomic " * 3),
    )
    ranked = [h.address for h in search.search(w, "atomic writes").hits]
    assert ranked[0] == "ws/knowledge/atomic-writes"


def test_description_and_type_are_searchable():
    w = _world(_doc("knowledge", "n1", description="mkstemp mode pitfalls",
                    type="Gotcha"))
    assert search.search(w, "mkstemp").hits
    assert search.search(w, "gotcha").hits


def test_task_status_is_searchable():
    w = _world(_doc("task", "t1", status="Blocked", body="waiting"))
    hits = search.search(w, "blocked").hits
    assert [h.address for h in hits] == ["ws/s1/task/t1"]


def test_kind_filter_selects_one_kind():
    w = _world(
        _doc("knowledge", "k1", body="retry"),
        _doc("workbench", "wb1", body="retry"),
        _doc("task", "t1", body="retry"),
    )

    def kinds(kind):
        return {h.kind for h in search.search(w, "retry", kind=kind).hits}

    assert kinds("knowledge") == {"knowledge"}
    assert kinds("workbench") == {"workbench"}
    assert kinds("task") == {"task"}
    assert kinds("all") == {"knowledge", "workbench", "task"}


def test_kind_filter_reports_its_own_total():
    # `total` must count the filtered list, not the whole prose index, or the
    # "(+N more)" line would promise hits the filter already removed.
    w = _world(
        _doc("knowledge", "k1", body="retry"),
        _doc("workbench", "wb1", body="retry"),
    )
    assert search.search(w, "retry", kind="knowledge").total == 1


def test_all_kind_fuses_so_each_index_winner_surfaces():
    # One long task and one short knowledge doc: whichever corpus produces the
    # larger raw BM25 magnitude must not monopolize the top of the fused list.
    w = _world(
        _doc("knowledge", "k1", body="retry"),
        _doc("task", "t1", body="retry " + "filler " * 40),
        _doc("task", "t2", body="retry"),
    )
    kinds = [h.kind for h in search.search(w, "retry", kind="all").hits][:2]
    assert set(kinds) == {"knowledge", "task"}


def test_archived_docs_are_excluded_by_default():
    w = _world(
        _doc("knowledge", "live", body="retry"),
        _doc("knowledge", "dead", body="retry", archived=True),
    )
    assert [h.address for h in search.search(w, "retry").hits] == [
        "ws/knowledge/live"]
    both = {h.address
            for h in search.search(w, "retry", include_archive=True).hits}
    assert both == {"ws/knowledge/live", "ws/knowledge/dead"}


def test_names_filter_scopes_to_named_workspaces():
    w = _world(
        _doc("knowledge", "k1", body="retry", workspace="wsa"),
        _doc("knowledge", "k2", body="retry", workspace="wsb"),
    )
    hits = search.search(w, "retry", names=["wsa"]).hits
    assert [h.address for h in hits] == ["wsa/knowledge/k1"]


def test_ghost_docs_are_never_indexed():
    # A ghost is an unwritten target of a [[...]] link, not a document.
    w = _world(_doc("knowledge", "real", body="retry"))
    ghost = _doc("knowledge", "ghosted", body="")
    ghost.ghost = True
    w.docs[ghost.id.canonical()] = ghost
    assert [h.address for h in search.search(w, "ghosted").hits] == []


def test_non_linkable_kinds_are_never_indexed():
    # A session's SUMMARY.md is a container, not a searchable document.
    root = Doc(id=DocId(kind="root"), title="/", body="", frontmatter={},
               rel_path=None)
    sess = Doc(id=DocId(kind="session", workspace="ws", session="s1"),
               title="s1", body="retry retry retry", frontmatter={},
               rel_path=None)
    w = World(root=root, docs={sess.id.canonical(): sess})
    assert search.search(w, "retry").hits == []


def test_snippet_is_the_first_matching_body_line():
    w = _world(_doc("knowledge", "k1",
                    body="# Heading\n\nUnrelated opening line.\n\n"
                         "The retry path fsyncs the directory.\n"))
    assert search.search(w, "retry").hits[0].snippet == (
        "The retry path fsyncs the directory.")


def test_snippet_falls_back_to_description_then_title():
    w = _world(_doc("knowledge", "retry-note", description="Retry semantics"))
    assert search.search(w, "retry").hits[0].snippet == "Retry semantics"
    w2 = _world(_doc("knowledge", "retry-note", title="Retry Note"))
    assert search.search(w2, "retry").hits[0].snippet == "Retry Note"


def test_snippet_is_sanitized_and_whitespace_collapsed():
    w = _world(_doc("knowledge", "k1",
                    body="retry‮ reversed​ text\t\tspaced"))
    snippet = search.search(w, "retry").hits[0].snippet
    assert "‮" not in snippet and "​" not in snippet
    assert "\t" not in snippet
    assert snippet == "retry reversed text spaced"


def test_snippet_is_truncated():
    w = _world(_doc("knowledge", "k1", body="retry " + "x" * 400))
    snippet = search.search(w, "retry").hits[0].snippet
    assert len(snippet) == search.SNIPPET_WIDTH + 3
    assert snippet.endswith("...")


def test_max_bounds_the_hits_but_not_the_total():
    w = _world(*[_doc("knowledge", f"k{i}", body="retry") for i in range(5)])
    res = search.search(w, "retry", max=2)
    assert len(res.hits) == 2
    assert res.total == 5


def test_no_match_returns_an_empty_result():
    w = _world(_doc("knowledge", "k1", body="retry"))
    res = search.search(w, "nonexistent")
    assert res.hits == [] and res.total == 0


def test_punctuation_only_query_returns_an_empty_result():
    w = _world(_doc("knowledge", "k1", body="retry"))
    assert search.search(w, "...").total == 0


def test_terms_accept_a_list_as_well_as_a_string():
    w = _world(_doc("knowledge", "k1", body="exponential backoff"))
    assert search.search(w, ["exponential", "backoff"]).total == 1


def test_unknown_kind_raises_rather_than_returning_task_hits():
    # Argparse `choices` shields the CLI, so this guards a library caller: a
    # plausible-looking task ranking is worse than an error.
    w = _world(_doc("task", "t1", body="retry"))
    with pytest.raises(ValueError, match="unknown search kind"):
        search.search(w, "retry", kind="Task")


def test_build_indexes_partitions_prose_from_tasks():
    w = _world(
        _doc("knowledge", "k1", body="retry"),
        _doc("workbench", "wb1", body="retry"),
        _doc("task", "t1", body="retry"),
    )
    prose, tasks = search.build_indexes(w)
    assert len(prose) == 2
    assert len(tasks) == 1
