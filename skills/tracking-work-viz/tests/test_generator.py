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


def _payload(html_path):
    import re, json
    html = html_path.read_text()
    blob = re.search(r'<script id="__SCOPE__"[^>]*>([\s\S]*?)</script>', html).group(1)
    return json.loads(blob)


def test_root_payload_task_contentpath(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "index.html")
    by_id = {n["id"]: n for n in payload["nodes"]}
    n = by_id["demo-ws/alpha/task/task-a"]
    assert n["contentPath"] == "workspaces/demo-ws/sessions/alpha/tasks/task-a.md"


def test_workspace_payload_task_contentpath(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "workspaces" / "demo-ws" / "index.html")
    by_id = {n["id"]: n for n in payload["nodes"]}
    n = by_id["demo-ws/alpha/task/task-a"]
    # Root-relative; frontend prefixes by rootHref dirname at fetch time.
    assert n["contentPath"] == "workspaces/demo-ws/sessions/alpha/tasks/task-a.md"


def test_session_payload_task_contentpath(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "workspaces" / "demo-ws" / "sessions" / "alpha" / "index.html")
    by_id = {n["id"]: n for n in payload["nodes"]}
    n = by_id["demo-ws/alpha/task/task-a"]
    assert n["contentPath"] == "workspaces/demo-ws/sessions/alpha/tasks/task-a.md"


def test_payload_session_contentpath_points_to_summary(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "index.html")
    by_id = {n["id"]: n for n in payload["nodes"]}
    sess = by_id["demo-ws/alpha/"]
    assert sess["contentPath"] == "workspaces/demo-ws/sessions/alpha/SUMMARY.md"


def test_payload_workspace_contentpath_points_to_index(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "index.html")
    by_id = {n["id"]: n for n in payload["nodes"]}
    ws = by_id["demo-ws/"]
    assert ws["contentPath"] == "workspaces/demo-ws/index.md"


def test_no_ghost_nodes_in_any_payload(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    for html in [out / "index.html",
                 out / "workspaces" / "demo-ws" / "index.html",
                 out / "workspaces" / "demo-ws" / "sessions" / "alpha" / "index.html"]:
        payload = _payload(html)
        for n in payload["nodes"]:
            assert n.get("ghost") in (False, None), f"ghost node leaked: {n}"


def test_tree_task_entries_have_contentpath_root(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "index.html")
    root = payload["tree"][0]
    ws = next(c for c in root["children"] if c["id"] == "demo-ws/")
    sess = next(c for c in ws["children"] if c["id"] == "demo-ws/alpha/")
    task = next(c for c in sess["children"] if c["id"] == "demo-ws/alpha/task/task-a")
    assert task["scopeId"] == "demo-ws/alpha/task/task-a"
    assert task["contentPath"] == "workspaces/demo-ws/sessions/alpha/tasks/task-a.md"


def test_tree_task_entries_have_contentpath_session_scope(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "workspaces" / "demo-ws" / "sessions" / "alpha" / "index.html")
    root = payload["tree"][0]
    ws = next(c for c in root["children"] if c["id"] == "demo-ws/")
    sess = next(c for c in ws["children"] if c["id"] == "demo-ws/alpha/")
    task = next(c for c in sess["children"] if c["id"] == "demo-ws/alpha/task/task-a")
    # Tree contentPaths are root-relative; the frontend prepends rootHref dirname.
    assert task["contentPath"] == "workspaces/demo-ws/sessions/alpha/tasks/task-a.md"


def test_tree_session_entries_have_contentpath_to_summary(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "index.html")
    root = payload["tree"][0]
    ws = next(c for c in root["children"] if c["id"] == "demo-ws/")
    sess = next(c for c in ws["children"] if c["id"] == "demo-ws/alpha/")
    assert sess["contentPath"] == "workspaces/demo-ws/sessions/alpha/SUMMARY.md"


def test_build_does_not_stage_dagre(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    assert not (out / "vendor" / "dagre.min.js").exists()
    assert not (out / "vendor" / "cytoscape-dagre.min.js").exists()
