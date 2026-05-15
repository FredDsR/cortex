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
