"""Tests for the static-site generator."""
from pathlib import Path
import json
import pytest
from cortex.parser import parse_world
from cortex.viz.generator import build


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
    # The ghost knowledge/architecture reference must not produce a file.
    assert not (out / "workspaces/demo-ws/knowledge/architecture.md").exists()


def test_build_emits_root_index(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    root_idx = (out / "index.md").read_text()
    assert "# Your Cortex" in root_idx
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


def test_build_emits_knowledge_index(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    idx = (out / "workspaces" / "demo-ws" / "knowledge" / "index.md").read_text()
    assert "knowledge" in idx.lower()


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


def test_supplementary_md_copied_to_session_dir(workspaces_root, tmp_path):
    """Author-authored .md files (research notes, dated audit logs, etc.) that
    sit next to SUMMARY.md must be copied so that relative links in rendered
    markdown resolve."""
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    # Nested supplementary file
    assert (out / "workspaces/demo-ws/sessions/alpha/research/literature.md").is_file()
    # Top-level supplementary file at session root
    assert (out / "workspaces/demo-ws/sessions/alpha/audit-2026-04-29.md").is_file()


def test_build_does_not_stage_dagre(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    assert not (out / "vendor" / "dagre.min.js").exists()
    assert not (out / "vendor" / "cytoscape-dagre.min.js").exists()


def test_payload_includes_author_for_knowledge(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "index.html")
    by_id = {n["id"]: n for n in payload["nodes"]}
    assert by_id["authored-ws/knowledge/by-human"]["author"] == "human"
    assert by_id["authored-ws/knowledge/by-agent"]["author"] == "agent"


def test_payload_includes_author_for_workbench(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "index.html")
    by_id = {n["id"]: n for n in payload["nodes"]}
    assert by_id["authored-ws/s1/workbench/wb-agent"]["author"] == "agent"


def test_tree_includes_knowledge_with_author(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "index.html")
    root = payload["tree"][0]
    ws = next(c for c in root["children"] if c["id"] == "authored-ws/")
    k_ids = {c["id"]: c for c in ws["children"] if c["kind"] == "knowledge"}
    assert "authored-ws/knowledge/by-human" in k_ids
    assert k_ids["authored-ws/knowledge/by-human"]["author"] == "human"
    assert k_ids["authored-ws/knowledge/by-agent"]["author"] == "agent"


def test_tree_includes_workbench_with_author(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "index.html")
    root = payload["tree"][0]
    ws = next(c for c in root["children"] if c["id"] == "authored-ws/")
    sess = next(c for c in ws["children"] if c["id"] == "authored-ws/s1/")
    wb_children = [c for c in sess["children"] if c["kind"] == "workbench"]
    assert any(c["id"] == "authored-ws/s1/workbench/wb-agent" and c["author"] == "agent"
               for c in wb_children)


def test_payload_author_null_for_unauthored_kinds(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "index.html")
    by_id = {n["id"]: n for n in payload["nodes"]}
    # Tasks, sessions, workspaces always have author None.
    assert by_id["demo-ws/alpha/task/task-a"]["author"] is None
    assert by_id["demo-ws/alpha/"]["author"] is None
    assert by_id["demo-ws/"]["author"] is None


from cortex.viz import generator


def test_build_payload_matches_root_page(workspaces_root, tmp_path):
    world = parse_world(workspaces_root)
    payload = generator.build_payload(world, "root", "/")
    assert payload["scope"] == "root"
    assert payload["scopeId"] == "/"
    assert payload["rootHref"] == "index.html"
    assert payload["defaultContentPath"] == "index.md"
    assert isinstance(payload["tree"], list) and payload["tree"]
    assert isinstance(payload["nodes"], list) and payload["nodes"]
    assert isinstance(payload["wikilinks"], dict)


def test_build_payload_workspace_scope(workspaces_root):
    world = parse_world(workspaces_root)
    payload = generator.build_payload(world, "workspace", "demo-ws/")
    assert payload["scope"] == "workspace"
    assert payload["scopeId"] == "demo-ws/"
    assert payload["rootHref"] == "../../index.html"
    assert payload["defaultContentPath"] == "workspaces/demo-ws/index.md"


def test_build_writes_manifest(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    generator.build(world, out, workspaces_root=workspaces_root)
    manifest = out / generator.MANIFEST_NAME
    assert manifest.is_file()
    data = json.loads(manifest.read_text())
    assert data["workspacesRoot"] == str(workspaces_root)
    assert "builtAt" in data


def test_node_payload_includes_kb_fields(workspaces_root, tmp_path):
    out = tmp_path / "out"
    build(parse_world(workspaces_root), out)
    payload = _payload(out / "index.html")
    node = next(n for n in payload["nodes"] if n["id"] == "authored-ws/knowledge/typed")
    assert node["type"] == "Runbook"
    assert node["description"] == "a one-line description"
    assert node["updated"] == "2026-06-01"


def test_first_paragraph_skips_h1_and_blanks():
    from cortex.viz import generator as g
    body = "\n\n# Title Heading\n\nFirst real paragraph here.\nSecond line of it.\n\nLater section.\n"
    assert g._first_paragraph(body) == "First real paragraph here. Second line of it."
    assert g._first_paragraph("") == ""
    assert g._first_paragraph("# Only a heading\n") == ""
    assert g._first_paragraph("x" * 500) == "x" * 300  # capped


def test_search_page_href_per_kind():
    from cortex.viz import generator as g
    from cortex.model import DocId
    assert g._search_page_href(DocId(kind="root")) == "index.html"
    assert g._search_page_href(DocId(kind="workspace", workspace="w")) == "workspaces/w/index.html"
    assert g._search_page_href(DocId(kind="knowledge", workspace="w", slug="k")) == "workspaces/w/index.html"
    assert g._search_page_href(DocId(kind="session", workspace="w", session="s")) == "workspaces/w/sessions/s/index.html"
    assert g._search_page_href(DocId(kind="task", workspace="w", session="s", slug="t")) == "workspaces/w/sessions/s/index.html"
    assert g._search_page_href(DocId(kind="workbench", workspace="w", session="s", slug="b")) == "workspaces/w/sessions/s/index.html"


def test_build_writes_search_docs(workspaces_root, tmp_path):
    import json
    from cortex import parser
    from cortex.viz.generator import build
    out = tmp_path / "out"
    world = parser.parse_world(workspaces_root, include_archive=True)
    build(world, out, workspaces_root=workspaces_root)
    data = json.loads((out / "search-docs.json").read_text())
    assert isinstance(data, list) and data
    rec = next(r for r in data if r["id"] == "demo-ws/alpha/task/task-a")
    assert rec["kind"] == "task"
    assert rec["slug"] == "task-a"
    assert rec["title"] == "Task a"
    assert rec["pageHref"] == "workspaces/demo-ws/sessions/alpha/index.html"
    assert rec["contentPath"] == "workspaces/demo-ws/sessions/alpha/tasks/task-a.md"
    assert all(not r["id"].endswith("/task/does-not-exist") for r in data)


def test_build_stages_minisearch_vendor(workspaces_root, tmp_path):
    from cortex import parser
    from cortex.viz.generator import build
    out = tmp_path / "out"
    build(parser.parse_world(workspaces_root), out, workspaces_root=workspaces_root)
    assert (out / "vendor" / "minisearch.min.js").is_file()


def test_root_index_has_cross_workspace_knowledge_dictionary(workspaces_root, tmp_path):
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    root_idx = (out / "index.md").read_text()
    assert "## Knowledge" in root_idx
    assert "### Runbook" in root_idx                                   # authored-ws/typed.md
    assert "[typed (authored-ws)](workspaces/authored-ws/knowledge/typed.md)" in root_idx
    assert "a one-line description" in root_idx


def test_root_index_description_placeholder_matches_cli(workspaces_root, tmp_path):
    # authored-ws/by-agent.md has no type/description/title -> same placeholder
    # the CLI uses, so the two brain surfaces render description-less docs alike.
    out = tmp_path / "out"
    world = parse_world(workspaces_root)
    build(world, out)
    root_idx = (out / "index.md").read_text()
    assert "[by-agent (authored-ws)](workspaces/authored-ws/knowledge/by-agent.md) - (no description)" in root_idx
