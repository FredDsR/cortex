import json
from pathlib import Path
from work_viz.generator import generate_one_shot
from work_viz.generator import generate_dashboard
from work_viz.generator import build_workspace_html, build_dashboard_html
from work_viz.parser import parse_world


def _extract_cy_data(html: str) -> dict:
    """Extract and parse the __CY_DATA__ JSON payload from an HTML string."""
    # Find the line containing window.__CY_DATA__ = ...;
    for line in html.splitlines():
        stripped = line.strip()
        if stripped.startswith("window.__CY_DATA__"):
            # Strip the variable assignment prefix and trailing semicolon
            after_eq = stripped.split("=", 1)[1].strip()
            json_str = after_eq.rstrip(";")
            # Unescape the <\/ back to </ for JSON parsing
            json_str = json_str.replace("<\\/", "</")
            return json.loads(json_str)
    raise ValueError("window.__CY_DATA__ not found in HTML")


def test_workspace_html_carries_cy_data(workspaces_root: Path):
    world = parse_world(workspaces_root)
    html = build_workspace_html(world, "demo")
    assert "window.__CY_DATA__ = " in html
    assert "@@CY_DATA@@" not in html
    payload = _extract_cy_data(html)
    assert "modes" in payload
    assert "ghosts" in payload
    assert "default_mode" in payload


def test_workspace_local_mode_excludes_other_ws_tasks(workspaces_root: Path):
    world = parse_world(workspaces_root)
    html = build_workspace_html(world, "demo")
    payload = _extract_cy_data(html)
    local = payload["modes"]["local"]
    node_ids = [n["id"] for n in local["nodes"]]
    # All real (non-ghost) nodes should belong to demo workspace
    real_nodes = [n for n in local["nodes"] if not n["ghost"]]
    assert all(n["id"].startswith("demo/") for n in real_nodes)
    # The cross-WS reference to other/sister/task-pinned appears as a ghost node
    ghost_nodes = [n for n in local["nodes"] if n["ghost"]]
    ghost_ids = [n["id"] for n in ghost_nodes]
    assert any("other/sister/task-pinned" in gid for gid in ghost_ids)


def test_workspace_global_mode_includes_cross_ws_neighbor(workspaces_root: Path):
    world = parse_world(workspaces_root)
    html = build_workspace_html(world, "demo")
    payload = _extract_cy_data(html)
    global_mode = payload["modes"]["global"]
    node_ids = [n["id"] for n in global_mode["nodes"]]
    # other/sister/task-pinned must appear as a real node (ghost: False)
    cross_ws = [n for n in global_mode["nodes"] if n["id"] == "other/sister/task-pinned"]
    assert cross_ws, f"other/sister/task-pinned not in global mode nodes: {node_ids}"
    assert cross_ws[0]["ghost"] is False


def test_workspace_edges_carry_kind_and_resolved(workspaces_root: Path):
    world = parse_world(workspaces_root)
    html = build_workspace_html(world, "demo")
    payload = _extract_cy_data(html)
    for mode_name, mode_data in payload["modes"].items():
        for edge in mode_data["edges"]:
            assert "kind" in edge, f"edge missing 'kind' in {mode_name}: {edge}"
            assert "resolved" in edge, f"edge missing 'resolved' in {mode_name}: {edge}"


def test_dashboard_global_contains_all_workspaces(workspaces_root: Path):
    world = parse_world(workspaces_root)
    html = build_dashboard_html(world)
    payload = _extract_cy_data(html)
    global_mode = payload["modes"]["global"]
    node_ids = [n["id"] for n in global_mode["nodes"]]
    has_demo = any(nid.startswith("demo/") for nid in node_ids)
    has_other = any(nid.startswith("other/") for nid in node_ids)
    assert has_demo, f"No demo nodes in dashboard global: {node_ids}"
    assert has_other, f"No other nodes in dashboard global: {node_ids}"


def test_one_shot_writes_self_contained_html(workspaces_root: Path, tmp_path: Path):
    out = generate_one_shot(workspaces_root, "demo", out_dir=tmp_path)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    # MODE marker is replaced
    assert "@@MODE@@" not in text
    assert '"static"' in text
    # DATA placeholder is replaced with valid JSON
    assert "@@DATA@@" not in text
    # The slug should appear in the embedded data
    assert '"slug": "demo"' in text or '"slug":"demo"' in text
    # Vendor links should be relative
    assert 'src="vendor/cytoscape.min.js"' in text


def test_dashboard_lists_workspaces(workspaces_root: Path, tmp_path: Path):
    out = generate_dashboard(workspaces_root, out_dir=tmp_path)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "@@DATA@@" not in text
    assert '"slug": "demo"' in text or '"slug":"demo"' in text


def test_one_shot_emits_cy_data_with_global_mode(workspaces_root: Path, tmp_path: Path):
    """generate_one_shot uses parse_world, so the global mode includes cross-WS nodes."""
    out = generate_one_shot(workspaces_root, "demo", out_dir=tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "window.__CY_DATA__" in text
    assert "@@CY_DATA@@" not in text
    payload = _extract_cy_data(text)
    # Global mode should contain nodes from the 'other' workspace (cross-WS neighbor)
    global_nodes = payload["modes"]["global"]["nodes"]
    has_other = any(n["id"].startswith("other/") for n in global_nodes)
    assert has_other, f"No 'other/' nodes in global mode: {[n['id'] for n in global_nodes]}"


def test_workspace_html_emits_chip_markup(workspaces_root: Path):
    world = parse_world(workspaces_root)
    html = build_workspace_html(world, "demo")
    assert 'id="chip-blocked"' in html
    assert 'id="chip-related"' in html
    assert 'id="chip-follows"' in html
    assert 'id="chip-mentions"' in html
    assert 'id="chip-global"' in html


def test_chip_default_classes(workspaces_root: Path):
    world = parse_world(workspaces_root)
    html = build_workspace_html(world, "demo")
    # First three chips should be 'chip on'; last two just 'chip'
    assert 'id="chip-blocked" class="chip on"' in html or 'class="chip on"' in html.split('id="chip-blocked"')[0].split('<')[-1] + 'id="chip-blocked"' in html
    # Use a more robust check: find the button tag for each chip
    import re
    def chip_classes(chip_id):
        m = re.search(r'<button[^>]*id="' + chip_id + r'"[^>]*class="([^"]*)"', html)
        if not m:
            m = re.search(r'<button[^>]*class="([^"]*)"[^>]*id="' + chip_id + r'"', html)
        return m.group(1) if m else None

    assert chip_classes("chip-blocked") == "chip on"
    assert chip_classes("chip-related") == "chip on"
    assert chip_classes("chip-follows") == "chip on"
    assert chip_classes("chip-mentions") == "chip"
    assert chip_classes("chip-global") == "chip"


def test_script_tag_injection_neutralized(workspaces_root: Path, tmp_path: Path):
    """A task body containing </script> must not break out of the inline <script> block."""
    # Inject a malicious task body into a writable copy of the fixture
    import shutil
    dest = tmp_path / "ws"
    shutil.copytree(workspaces_root, dest)
    task_path = dest / "demo" / "sessions" / "feature-x" / "tasks" / "task-foo.md"
    task_path.write_text(task_path.read_text() + "\n\n</script><script>window.PWNED=true</script>\n")
    from work_viz.generator import generate_one_shot
    out = generate_one_shot(dest, "demo", out_dir=tmp_path)
    text = out.read_text(encoding="utf-8")
    # The literal </script> in the body must be escaped in the inlined JSON.
    assert "</script><script>window.PWNED=true</script>" not in text
    # The escaped form should be present.
    assert "<\\/script>" in text or "<\\/" in text
