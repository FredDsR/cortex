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


def test_raw_refs_exposes_authored_references(workspaces_root):
    from cortex import parser
    from cortex.model import DocId
    world = parser.parse_world(workspaces_root, include_archive=True)
    task_a = world.docs["demo-ws/alpha/task/task-a"]
    refs = {(r.kind, r.raw_target) for r in parser.raw_refs(task_a)}
    assert ("blocked", "task-b") in refs
    assert ("related", "beta/task-c") in refs
    assert ("follows", "other-ws/zeta/task-z") in refs


def test_markdown_link_label_is_not_a_reference():
    """`[label](path.md)` names a link, not a doc. Treating the label as a
    reference turned prose about markdown syntax into ghost nodes."""
    from cortex.parser import _extract_raw_edges
    refs = {(r.kind, r.raw_target) for r in
            _extract_raw_edges({}, "Write `[label](path.md)` to link.\n"
                                   "But [real-note] is a reference.\n")}
    assert ("mentions", "label") not in refs
    assert ("mentions", "real-note") in refs


def test_markdown_link_to_a_task_still_resolves(workspaces_root):
    """A SUMMARY.md task list is written as markdown links; the bare `task-`
    slug inside the label keeps the mention edge alive."""
    from cortex.parser import _extract_raw_edges
    refs = {(r.kind, r.raw_target) for r in
            _extract_raw_edges({}, "- [task-foo](tasks/task-foo.md) - doing it\n")}
    assert ("mentions", "task-foo") in refs


def test_raw_refs_includes_unresolved_ghost_tokens(workspaces_root):
    from cortex import parser
    world = parser.parse_world(workspaces_root, include_archive=True)
    ghosted = world.docs["kb-ghosts-ws/solo/task/task-ghosted"]
    refs = {(r.kind, r.raw_target) for r in parser.raw_refs(ghosted)}
    assert ("related", "knowledge/missing-note") in refs
    assert ("related", "workbench/draft-x") in refs
