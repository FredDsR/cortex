"""Tests for the multi-typed graph model."""
from work_viz.model import Doc, DocId, Edge, RawEdge, World, STATUS_OPEN


def test_docid_root_canonical():
    assert DocId(kind="root").canonical() == "/"


def test_docid_workspace_canonical():
    assert DocId(kind="workspace", workspace="foo").canonical() == "foo/"


def test_docid_session_canonical():
    assert DocId(kind="session", workspace="foo", session="bar").canonical() == "foo/bar/"


def test_docid_task_canonical():
    cid = DocId(kind="task", workspace="foo", session="bar", slug="task-baz").canonical()
    assert cid == "foo/bar/task/task-baz"


def test_docid_knowledge_canonical():
    cid = DocId(kind="knowledge", workspace="foo", slug="note").canonical()
    assert cid == "foo/knowledge/note"


def test_docid_workbench_canonical():
    cid = DocId(kind="workbench", workspace="foo", session="bar", slug="draft").canonical()
    assert cid == "foo/bar/workbench/draft"


def test_docid_equality_hashable():
    a = DocId(kind="task", workspace="w", session="s", slug="x")
    b = DocId(kind="task", workspace="w", session="s", slug="x")
    assert a == b
    assert hash(a) == hash(b)


def test_doc_defaults():
    doc = Doc(id=DocId(kind="root"), title="root", body="", frontmatter={}, rel_path=None,
              edges_out=[])
    assert doc.ghost is False
    assert doc.edges_out == []


def test_edge_basic():
    src = DocId(kind="task", workspace="w", session="s", slug="a")
    tgt = DocId(kind="task", workspace="w", session="s", slug="b")
    e = Edge(source=src, target=tgt, raw_target="task-b", kind="blocked", resolved=True)
    assert e.kind == "blocked"
    assert e.resolved is True


def test_world_empty():
    root = Doc(id=DocId(kind="root"), title="root", body="", frontmatter={}, rel_path=None,
               edges_out=[])
    w = World(root=root, docs={"/": root}, edges=[], ghosts=set())
    assert w.docs["/"] is root
    assert w.edges == []
