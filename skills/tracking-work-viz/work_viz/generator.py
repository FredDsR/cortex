"""Static-site generator: World -> filesystem under out_dir."""
from __future__ import annotations
import json
import re
import shutil
import sys
from pathlib import Path

from .model import World, Doc, DocId, Edge

_PACKAGE_DIR = Path(__file__).parent.parent
_VENDOR_SRC = _PACKAGE_DIR / "templates" / "vendor"
_SHELL_TEMPLATE = (_PACKAGE_DIR / "templates" / "shell.html").read_text(encoding="utf-8")


def _stage_vendor(out_dir: Path) -> None:
    vendor_out = out_dir / "vendor"
    if vendor_out.exists():
        shutil.rmtree(vendor_out)
    shutil.copytree(_VENDOR_SRC, vendor_out)


def _doc_out_path(doc: Doc, out_dir: Path) -> Path:
    cid = doc.id
    base = out_dir / "workspaces" / cid.workspace if cid.workspace else out_dir
    if cid.kind == "workspace":
        return base / "index.md"
    if cid.kind == "session":
        return base / "sessions" / cid.session / "SUMMARY.md"
    if cid.kind == "task":
        return base / "sessions" / cid.session / "tasks" / f"{cid.slug}.md"
    if cid.kind == "memory":
        return base / "memory" / f"{cid.slug}.md"
    if cid.kind == "workbench":
        return base / "sessions" / cid.session / "workbench" / f"{cid.slug}.md"
    if cid.kind == "root":
        return out_dir / "index.md"
    raise ValueError(f"unknown doc kind: {cid.kind!r}")


def _copy_markdown(world: World, out_dir: Path) -> None:
    for doc in world.docs.values():
        if doc.ghost or doc.rel_path is None or doc.id.kind in ("root", "workspace"):
            continue
        # Sessions without a SUMMARY.md keep rel_path = session dir; skip those.
        if not doc.rel_path.is_file():
            continue
        dest = _doc_out_path(doc, out_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(doc.rel_path, dest)


def _children_of(world: World, parent_canon: str, kind: str) -> list[Doc]:
    out = []
    for doc in world.docs.values():
        if doc.ghost or doc.id.kind != kind:
            continue
        # Filter by parent
        if kind == "workspace" and parent_canon == "/":
            out.append(doc)
        elif kind == "session" and doc.id.workspace and f"{doc.id.workspace}/" == parent_canon:
            out.append(doc)
        elif kind == "memory" and doc.id.workspace and f"{doc.id.workspace}/" == parent_canon:
            out.append(doc)
        elif kind == "task" and doc.id.workspace and doc.id.session and \
             f"{doc.id.workspace}/{doc.id.session}/" == parent_canon:
            out.append(doc)
        elif kind == "workbench" and doc.id.workspace and doc.id.session and \
             f"{doc.id.workspace}/{doc.id.session}/" == parent_canon:
            out.append(doc)
    return sorted(out, key=lambda d: d.id.canonical())


def _emit_root_index(world: World, out_dir: Path) -> None:
    workspaces = _children_of(world, "/", "workspace")
    lines = ["# Fred's Work Tracking", "", "## Workspaces", ""]
    for ws in workspaces:
        lines.append(f"- [{ws.id.workspace}](workspaces/{ws.id.workspace}/index.md)")
    lines.append("")
    (out_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_workspace_index(world: World, ws: Doc, out_dir: Path) -> None:
    ws_dir = out_dir / "workspaces" / ws.id.workspace
    ws_dir.mkdir(parents=True, exist_ok=True)
    sessions = _children_of(world, ws.id.canonical(), "session")
    memories = _children_of(world, ws.id.canonical(), "memory")
    lines = [f"# {ws.id.workspace}", "",
             "[<- Dashboard](../../index.md)", "",
             f"## Sessions ({len(sessions)})", ""]
    for s in sessions:
        lines.append(f"- [{s.id.session}](sessions/{s.id.session}/index.md)")
    lines.extend(["", f"## Memory ({len(memories)})", "",
                  "[Open memory folder](memory/index.md)", ""])
    (ws_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_memory_index(world: World, ws: Doc, out_dir: Path) -> None:
    mem_dir = out_dir / "workspaces" / ws.id.workspace / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    docs = _children_of(world, ws.id.canonical(), "memory")
    lines = [f"# {ws.id.workspace} / memory", "",
             "[<- Workspace](../index.md)", "",
             f"## Memory docs ({len(docs)})", ""]
    if not docs:
        lines.append("_No memory docs yet._")
    else:
        for d in docs:
            lines.append(f"- [{d.id.slug}]({d.id.slug}.md)")
    (mem_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_session_index(world: World, sess: Doc, out_dir: Path) -> None:
    sess_dir = out_dir / "workspaces" / sess.id.workspace / "sessions" / sess.id.session
    sess_dir.mkdir(parents=True, exist_ok=True)
    parent_canon = sess.id.canonical()
    tasks = _children_of(world, parent_canon, "task")
    workbenches = _children_of(world, parent_canon, "workbench")
    lines = [f"# {sess.id.session}", "",
             f"_In workspace `{sess.id.workspace}`_", "",
             "[<- Workspace](../../index.md)", "",
             f"## Tasks ({len(tasks)})", ""]
    if not tasks:
        lines.append("_No tasks yet._")
    else:
        for t in tasks:
            status = t.status or "(unstated)"
            lines.append(f"- [{t.id.slug}](tasks/{t.id.slug}.md) - {status}")
    lines.extend(["", f"## Workbench ({len(workbenches)})", ""])
    if not workbenches:
        lines.append("_No workbench docs yet._")
    else:
        for w in workbenches:
            lines.append(f"- [{w.id.slug}](workbench/{w.id.slug}.md)")
    if sess.body:
        excerpt = sess.body.strip()[:400]
        lines.extend(["", "## Summary excerpt", "", excerpt])
    (sess_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_workbench_index(world: World, sess: Doc, out_dir: Path) -> None:
    wb_dir = out_dir / "workspaces" / sess.id.workspace / "sessions" / sess.id.session / "workbench"
    wb_dir.mkdir(parents=True, exist_ok=True)
    docs = _children_of(world, sess.id.canonical(), "workbench")
    lines = [f"# {sess.id.session} / workbench", "",
             "[<- Session](../index.md)", "",
             f"## Workbench docs ({len(docs)})", ""]
    if not docs:
        lines.append("_No workbench docs yet._")
    else:
        for d in docs:
            lines.append(f"- [{d.id.slug}]({d.id.slug}.md)")
    (wb_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_tasks_index(world: World, sess: Doc, out_dir: Path) -> None:
    tasks_dir = out_dir / "workspaces" / sess.id.workspace / "sessions" / sess.id.session / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    docs = _children_of(world, sess.id.canonical(), "task")
    lines = [f"# {sess.id.session} / tasks", "",
             "[<- Session](../index.md)", "",
             f"## Tasks ({len(docs)})", ""]
    if not docs:
        lines.append("_No tasks yet._")
    else:
        for d in docs:
            lines.append(f"- [{d.id.slug}]({d.id.slug}.md) - {d.status or '(unstated)'}")
    (tasks_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_all_indices(world: World, out_dir: Path) -> None:
    _emit_root_index(world, out_dir)
    for ws in _children_of(world, "/", "workspace"):
        _emit_workspace_index(world, ws, out_dir)
        _emit_memory_index(world, ws, out_dir)
        for sess in _children_of(world, ws.id.canonical(), "session"):
            _emit_session_index(world, sess, out_dir)
            _emit_workbench_index(world, sess, out_dir)
            _emit_tasks_index(world, sess, out_dir)


def _node_dict(world: World, doc: Doc) -> dict:
    parent = None
    cid = doc.id
    if cid.kind == "workspace":
        parent = "/"
    elif cid.kind == "session":
        parent = f"{cid.workspace}/"
    elif cid.kind in ("task", "workbench"):
        parent = f"{cid.workspace}/{cid.session}/"
    elif cid.kind == "memory":
        parent = f"{cid.workspace}/"
    label = cid.slug or cid.session or cid.workspace or "root"
    content_path = None
    if not doc.ghost and cid.kind == "task":
        content_path = f"sessions/{cid.session}/tasks/{cid.slug}.md"
    elif not doc.ghost and cid.kind == "memory":
        content_path = f"memory/{cid.slug}.md"
    elif not doc.ghost and cid.kind == "workbench":
        content_path = f"sessions/{cid.session}/workbench/{cid.slug}.md"
    return {
        "id": cid.canonical(),
        "label": label,
        "kind": cid.kind,
        "parent": parent,
        "status": doc.status,
        "ghost": doc.ghost,
        "contentPath": content_path,
    }


def _edge_dict(e: Edge) -> dict:
    return {
        "source": e.source.canonical(),
        "target": e.target.canonical(),
        "kind": e.kind,
        "resolved": e.resolved,
    }


def _scope_filter(world: World, scope: str, scope_id: str) -> tuple[list[dict], list[dict]]:
    if scope == "root":
        nodes = [_node_dict(world, d) for d in world.docs.values()]
        edges = [_edge_dict(e) for e in world.edges]
        return nodes, edges
    if scope == "workspace":
        ws = scope_id.rstrip("/")
        in_scope = {cid for cid, d in world.docs.items()
                    if d.id.workspace == ws or cid == "/"}
    else:  # session
        ws, sess = scope_id.rstrip("/").split("/", 1)
        in_scope = {cid for cid, d in world.docs.items()
                    if d.id.workspace == ws and d.id.session == sess}
        in_scope.add(f"{ws}/")
        in_scope.add("/")
    # 1-hop expansion
    neighbours: set[str] = set()
    keep_edges = []
    for e in world.edges:
        s, t = e.source.canonical(), e.target.canonical()
        if s in in_scope or t in in_scope:
            keep_edges.append(e)
            neighbours.add(s)
            neighbours.add(t)
    keep_ids = in_scope | neighbours
    nodes = [_node_dict(world, world.docs[cid]) for cid in keep_ids if cid in world.docs]
    edges = [_edge_dict(e) for e in keep_edges]
    return nodes, edges


def _build_tree(world: World) -> list[dict]:
    root_node = {"id": "/", "label": "Fred's Work Tracking", "kind": "root",
                 "href": "/index.html", "children": []}
    for ws in _children_of(world, "/", "workspace"):
        ws_node = {"id": ws.id.canonical(), "label": ws.id.workspace, "kind": "workspace",
                   "href": f"workspaces/{ws.id.workspace}/index.html", "children": []}
        for sess in _children_of(world, ws.id.canonical(), "session"):
            sess_node = {"id": sess.id.canonical(), "label": sess.id.session,
                         "kind": "session",
                         "href": f"workspaces/{ws.id.workspace}/sessions/{sess.id.session}/index.html",
                         "children": []}
            for t in _children_of(world, sess.id.canonical(), "task"):
                sess_node["children"].append({
                    "id": t.id.canonical(), "label": t.id.slug,
                    "kind": "task", "href": None, "children": []})
            ws_node["children"].append(sess_node)
        root_node["children"].append(ws_node)
    return [root_node]


def _render_shell(scope: str, scope_id: str, payload: dict, vendor_rel: str, title: str) -> str:
    blob = json.dumps(payload, ensure_ascii=False)
    html = _SHELL_TEMPLATE
    html = html.replace("__TITLE__", title)
    html = html.replace("__VENDOR__", vendor_rel)
    html = html.replace("__SCOPE_JSON__", blob)
    return html


def _vendor_rel(scope: str, scope_id: str) -> str:
    if scope == "root":
        return "vendor"
    if scope == "workspace":
        return "../../vendor"
    return "../../../../vendor"  # session


def _default_content_path(scope: str) -> str:
    return "index.md"


def _emit_html_pages(world: World, out_dir: Path) -> None:
    tree = _build_tree(world)

    nodes, edges = _scope_filter(world, "root", "/")
    payload = {
        "scope": "root", "scopeId": "/", "rootHref": "index.html",
        "tree": tree, "nodes": nodes, "edges": edges,
        "defaultContentPath": "index.md",
    }
    (out_dir / "index.html").write_text(
        _render_shell("root", "/", payload, _vendor_rel("root", "/"), "Fred's Work Tracking"),
        encoding="utf-8")

    for ws in _children_of(world, "/", "workspace"):
        nodes, edges = _scope_filter(world, "workspace", ws.id.canonical())
        payload = {
            "scope": "workspace", "scopeId": ws.id.canonical(),
            "rootHref": "../../index.html",
            "tree": tree, "nodes": nodes, "edges": edges,
            "defaultContentPath": "index.md",
        }
        ws_html = out_dir / "workspaces" / ws.id.workspace / "index.html"
        ws_html.write_text(
            _render_shell("workspace", ws.id.canonical(), payload,
                          _vendor_rel("workspace", ws.id.canonical()), ws.id.workspace),
            encoding="utf-8")
        for sess in _children_of(world, ws.id.canonical(), "session"):
            nodes, edges = _scope_filter(world, "session", sess.id.canonical())
            payload = {
                "scope": "session", "scopeId": sess.id.canonical(),
                "rootHref": "../../../../index.html",
                "tree": tree, "nodes": nodes, "edges": edges,
                "defaultContentPath": "index.md",
            }
            sess_html = ws_html.parent / "sessions" / sess.id.session / "index.html"
            sess_html.write_text(
                _render_shell("session", sess.id.canonical(), payload,
                              _vendor_rel("session", sess.id.canonical()),
                              f"{sess.id.session} - {ws.id.workspace}"),
                encoding="utf-8")


def build(world: World, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _stage_vendor(out_dir)
    _copy_markdown(world, out_dir)
    _emit_all_indices(world, out_dir)
    _emit_html_pages(world, out_dir)
