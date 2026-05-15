"""Tests for the multi-typed parser."""
from pathlib import Path
import pytest
from work_viz.parser import parse_world
from work_viz.model import DocId


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


def test_mention_to_memory_creates_ghost(workspaces_root):
    world = parse_world(workspaces_root)
    ghost_id = "demo-ws/memory/architecture"
    assert ghost_id in world.docs
    assert world.docs[ghost_id].ghost is True
    assert ghost_id in world.ghosts


def test_kb_ghosts_workspace(workspaces_root):
    world = parse_world(workspaces_root)
    assert "kb-ghosts-ws/memory/missing-note" in world.docs
    assert "kb-ghosts-ws/solo/workbench/draft-x" in world.docs


def test_no_duplicate_edges(workspaces_root):
    world = parse_world(workspaces_root)
    seen = set()
    for e in world.edges:
        key = (e.source.canonical(), e.target.canonical(), e.kind)
        assert key not in seen
        seen.add(key)
