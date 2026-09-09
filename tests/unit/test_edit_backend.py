"""Tests for edit_backend: source-path mapping + hashing."""
import hashlib
import pytest
from cortex.parser import parse_world
from cortex.viz import edit_backend as eb


def test_source_path_for_task(workspaces_root):
    world = parse_world(workspaces_root)
    cid = "demo-ws/alpha/task/task-a"
    p = eb.source_path_for(world, cid, workspaces_root)
    assert p.name == "task-a.md"
    assert p.is_file()


def test_source_path_for_session_summary(workspaces_root):
    world = parse_world(workspaces_root)
    p = eb.source_path_for(world, "demo-ws/alpha/", workspaces_root)
    assert p.name == "SUMMARY.md"


def test_source_path_rejects_workspace(workspaces_root):
    world = parse_world(workspaces_root)
    with pytest.raises(PermissionError):
        eb.source_path_for(world, "demo-ws/", workspaces_root)


def test_source_path_rejects_root(workspaces_root):
    world = parse_world(workspaces_root)
    with pytest.raises(PermissionError):
        eb.source_path_for(world, "/", workspaces_root)


def test_source_path_unknown_id(workspaces_root):
    world = parse_world(workspaces_root)
    with pytest.raises(LookupError):
        eb.source_path_for(world, "demo-ws/alpha/task/nope", workspaces_root)


def test_file_hash_matches_sha256(workspaces_root):
    world = parse_world(workspaces_root)
    p = eb.source_path_for(world, "demo-ws/alpha/task/task-a", workspaces_root)
    expected = hashlib.sha256(p.read_bytes()).hexdigest()
    assert eb.file_hash(p) == expected
