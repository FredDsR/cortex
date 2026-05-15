"""Tests for the static-site generator."""
from pathlib import Path
import json
import pytest
from work_viz.parser import parse_world
from work_viz.generator import build


def test_build_creates_output_dir(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    assert out.is_dir()


def test_build_stages_vendor(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    assert (out / "vendor" / "cytoscape.min.js").is_file()
    assert (out / "vendor" / "marked.min.js").is_file()
    assert (out / "vendor" / "app.js").is_file()
    assert (out / "vendor" / "app.css").is_file()


def test_build_copies_task_md(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    assert (out / "workspaces/demo-ws/sessions/alpha/tasks/task-a.md").is_file()
    assert (out / "workspaces/demo-ws/sessions/alpha/SUMMARY.md").is_file()


def test_build_skips_ghosts(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    # The ghost memory/architecture reference must not produce a file.
    assert not (out / "workspaces/demo-ws/memory/architecture.md").exists()


def test_build_emits_root_index(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    root_idx = (out / "index.md").read_text()
    assert "# Fred's Work Tracking" in root_idx
    assert "demo-ws" in root_idx
    assert "other-ws" in root_idx


def test_build_emits_workspace_index(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    idx = (out / "workspaces" / "demo-ws" / "index.md").read_text()
    assert "# demo-ws" in idx
    assert "alpha" in idx
    assert "beta" in idx


def test_build_emits_session_index(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    idx = (out / "workspaces" / "demo-ws" / "sessions" / "alpha" / "index.md").read_text()
    assert "alpha" in idx
    assert "task-a" in idx
    assert "Open" in idx


def test_build_emits_memory_index(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    idx = (out / "workspaces" / "demo-ws" / "memory" / "index.md").read_text()
    assert "memory" in idx.lower()


def test_build_emits_root_html(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    html = (out / "index.html").read_text()
    assert "<script id=\"__SCOPE__\"" in html
    assert "/vendor/cytoscape.min.js" in html or "vendor/cytoscape.min.js" in html


def test_root_payload_has_all_nodes(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    html = (out / "index.html").read_text()
    import re, json
    blob = re.search(r'<script id="__SCOPE__"[^>]*>([\s\S]*?)</script>', html).group(1)
    payload = json.loads(blob)
    assert payload["scope"] == "root"
    ids = {n["id"] for n in payload["nodes"]}
    assert "demo-ws/" in ids
    assert "demo-ws/alpha/" in ids
    assert "demo-ws/alpha/task/task-a" in ids


def test_workspace_payload_is_scoped(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    html = (out / "workspaces" / "demo-ws" / "index.html").read_text()
    import re, json
    blob = re.search(r'<script id="__SCOPE__"[^>]*>([\s\S]*?)</script>', html).group(1)
    payload = json.loads(blob)
    assert payload["scope"] == "workspace"
    ids = {n["id"] for n in payload["nodes"]}
    # in-scope
    assert "demo-ws/alpha/task/task-a" in ids
    # 1-hop neighbour (cross-workspace target of follows edge)
    assert "other-ws/zeta/task/task-z" in ids


def test_session_payload_is_scoped(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    html = (out / "workspaces" / "demo-ws" / "sessions" / "alpha" / "index.html").read_text()
    import re, json
    blob = re.search(r'<script id="__SCOPE__"[^>]*>([\s\S]*?)</script>', html).group(1)
    payload = json.loads(blob)
    assert payload["scope"] == "session"
    ids = {n["id"] for n in payload["nodes"]}
    assert "demo-ws/alpha/task/task-a" in ids
    # 1-hop neighbour (cross-session related-to)
    assert "demo-ws/beta/task/task-c" in ids
