"""Pure-grammar tests for address.resolve."""
import pytest
from work_viz.address import resolve, ResolveResult, RESERVED_WORDS
from work_viz.model import DocId


def _src(workspace="w", session="s"):
    return DocId(kind="task", workspace=workspace, session=session, slug="src")


@pytest.mark.parametrize("token,expected_kind,expected_ws,expected_sess,expected_slug", [
    ("task-foo",                "task",      "w",       "s",       "task-foo"),
    ("other-sess/task-bar",     "task",      "w",       "other-sess", "task-bar"),
    ("other-ws/sess/task-baz",  "task",      "other-ws", "sess",   "task-baz"),
    ("memory/note",             "memory",    "w",       None,      "note"),
    ("other-ws/memory/note",    "memory",    "other-ws", None,     "note"),
    ("workbench/draft",         "workbench", "w",       "s",       "draft"),
    ("sess2/workbench/draft",   "workbench", "w",       "sess2",   "draft"),
    ("other-ws/sess/workbench/draft", "workbench", "other-ws", "sess", "draft"),
])
def test_resolve_happy(token, expected_kind, expected_ws, expected_sess, expected_slug):
    r = resolve(token, referencing=_src())
    assert r.resolved is True
    assert r.doc_id.kind == expected_kind
    assert r.doc_id.workspace == expected_ws
    assert r.doc_id.session == expected_sess
    assert r.doc_id.slug == expected_slug


@pytest.mark.parametrize("token", [
    "",                                # empty
    "a/b/c/d",                         # too many components, no keyword
    "a/b/c/d/e",                       # really too many
    "a/memory",                        # memory at position 1 but no slug
    "a/b/memory/note",                 # memory at position >= 2
    "a/b/c/workbench/d",               # workbench at position 3, 5 tokens, invalid
])
def test_resolve_grammar_rejects(token):
    r = resolve(token, referencing=_src())
    assert r.resolved is False


def test_reserved_words_constant():
    assert "memory" in RESERVED_WORDS
    assert "workbench" in RESERVED_WORDS


def test_resolve_strips_brackets():
    r = resolve("[task-foo]", referencing=_src())
    assert r.resolved is True
    assert r.doc_id.slug == "task-foo"


def test_resolve_strips_whitespace():
    r = resolve("  task-foo  ", referencing=_src())
    assert r.resolved is True
    assert r.doc_id.slug == "task-foo"
