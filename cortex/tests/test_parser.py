"""Tests for the multi-typed parser."""
from pathlib import Path
import pytest
from cortex.parser import parse_world
from cortex.model import DocId


def test_parse_world_discovers_root(workspaces_root):
    world = parse_world(workspaces_root)
    assert world.root.id.kind == "root"
    assert "/" in world.docs


def test_parse_world_discovers_workspaces(workspaces_root):
    world = parse_world(workspaces_root)
    assert "demo-ws/" in world.docs
    assert "other-ws/" in world.docs
    assert "kb-ghosts-ws/" in world.docs
    assert world.docs["demo-ws/"].id.kind == "workspace"


def test_parse_world_discovers_sessions(workspaces_root):
    world = parse_world(workspaces_root)
    assert "demo-ws/alpha/" in world.docs
    assert "demo-ws/beta/" in world.docs
    assert "other-ws/zeta/" in world.docs


def test_parse_world_discovers_tasks(workspaces_root):
    world = parse_world(workspaces_root)
    assert "demo-ws/alpha/task/task-a" in world.docs
    assert world.docs["demo-ws/alpha/task/task-a"].status == "Open"


def test_parse_world_contains_edges(workspaces_root):
    world = parse_world(workspaces_root)
    contains = [e for e in world.edges if e.kind == "contains"]
    sources = {e.source.canonical() for e in contains}
    assert "/" in sources
    assert "demo-ws/" in sources
    assert "demo-ws/alpha/" in sources


def test_typed_relations_from_body(workspaces_root):
    world = parse_world(workspaces_root)
    blocked = [e for e in world.edges if e.kind == "blocked"]
    assert any(e.source.slug == "task-a" and e.target.slug == "task-b" for e in blocked)


def test_related_to_cross_session(workspaces_root):
    world = parse_world(workspaces_root)
    related = [e for e in world.edges if e.kind == "related"]
    assert any(
        e.source.slug == "task-a" and e.target.session == "beta" and e.target.slug == "task-c"
        for e in related
    )


def test_follows_cross_workspace(workspaces_root):
    world = parse_world(workspaces_root)
    follows = [e for e in world.edges if e.kind == "follows"]
    assert any(
        e.source.workspace == "demo-ws" and e.target.workspace == "other-ws"
        and e.target.slug == "task-z"
        for e in follows
    )


def test_mention_to_knowledge_does_not_create_ghost(workspaces_root):
    world = parse_world(workspaces_root)
    # No ghost docs are synthesized for unresolved targets.
    assert "demo-ws/knowledge/architecture" not in world.docs
    assert world.ghosts == set()


def test_kb_ghosts_workspace_emits_no_ghost_nodes(workspaces_root):
    world = parse_world(workspaces_root)
    # The workspace and its session exist; the missing knowledge/workbench refs do not.
    assert "kb-ghosts-ws/" in world.docs
    assert "kb-ghosts-ws/solo/" in world.docs
    assert "kb-ghosts-ws/knowledge/missing-note" not in world.docs
    assert "kb-ghosts-ws/solo/workbench/draft-x" not in world.docs


def test_unresolved_edges_are_dropped(workspaces_root):
    world = parse_world(workspaces_root)
    assert all(e.resolved for e in world.edges)
    doc_ids = set(world.docs.keys())
    for e in world.edges:
        assert e.target.canonical() in doc_ids


def test_no_duplicate_edges(workspaces_root):
    world = parse_world(workspaces_root)
    seen = set()
    for e in world.edges:
        key = (e.source.canonical(), e.target.canonical(), e.kind)
        assert key not in seen
        seen.add(key)


def test_parser_extracts_author_on_knowledge(workspaces_root):
    world = parse_world(workspaces_root)
    human = world.docs.get("authored-ws/knowledge/by-human")
    agent = world.docs.get("authored-ws/knowledge/by-agent")
    assert human is not None and human.author == "human"
    assert agent is not None and agent.author == "agent"


def test_parser_extracts_author_on_workbench(workspaces_root):
    world = parse_world(workspaces_root)
    wb = world.docs.get("authored-ws/s1/workbench/wb-agent")
    assert wb is not None and wb.author == "agent"


def test_parser_ignores_author_on_task(tmp_path):
    """Author is only meaningful on knowledge/workbench; tasks ignore the field."""
    import textwrap
    ws = tmp_path / "workspaces" / "tmp-ws"
    sess = ws / "sessions" / "s1"
    (sess / "tasks").mkdir(parents=True)
    (sess / "SUMMARY.md").write_text("---\nslug: s1\n---\n# s1\n")
    (sess / "tasks" / "task-x.md").write_text(textwrap.dedent("""\
        ---
        status: Open
        author: agent
        ---

        Body
    """))
    world = parse_world(tmp_path / "workspaces")
    task = world.docs.get("tmp-ws/s1/task/task-x")
    assert task is not None
    assert task.author is None


def test_knowledge_reads_new_frontmatter_fields(workspaces_root):
    world = parse_world(workspaces_root)
    doc = world.docs["authored-ws/knowledge/typed"]
    assert doc.type == "Runbook"
    assert doc.description == "a one-line description"
    assert doc.updated == "2026-06-01"


def test_frontmatter_title_beats_body_heading(workspaces_root):
    world = parse_world(workspaces_root)
    doc = world.docs["authored-ws/knowledge/typed"]
    assert doc.title == "Frontmatter Title Wins"


def test_uppercase_index_excluded_from_graph(workspaces_root):
    world = parse_world(workspaces_root)
    assert "authored-ws/knowledge/INDEX" not in world.docs
    assert "authored-ws/knowledge/index" not in world.docs
