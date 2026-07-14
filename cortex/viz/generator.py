"""Static-site generator: World -> filesystem under out_dir."""
from __future__ import annotations
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

from cortex import model
from cortex.model import World, Doc, DocId, Edge

_PACKAGE_DIR = Path(__file__).parent
_VENDOR_SRC = _PACKAGE_DIR / "templates" / "vendor"
_SHELL_TEMPLATE = (_PACKAGE_DIR / "templates" / "shell.html").read_text(encoding="utf-8")

MANIFEST_NAME = ".work-viz-build.json"


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
    if cid.kind == "knowledge":
        return base / "knowledge" / f"{cid.slug}.md"
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


def _copy_supplementary_md(world: World, out_dir: Path) -> None:
    """Mirror any unindexed .md files inside session and knowledge directories so
    relative links in author-authored markdown resolve. Indexed docs (SUMMARY,
    tasks/*.md, workbench/*.md, knowledge/*.md) are already copied by
    _copy_markdown; this pass picks up siblings like research/notes.md and
    dated audit files."""
    for doc in world.docs.values():
        if doc.id.kind != "session" or doc.rel_path is None:
            continue
        sess_dir = doc.rel_path if doc.rel_path.is_dir() else doc.rel_path.parent
        if not sess_dir.is_dir():
            continue
        out_sess = (out_dir / "workspaces" / doc.id.workspace
                    / "sessions" / doc.id.session)
        for md in sess_dir.rglob("*.md"):
            rel = md.relative_to(sess_dir)
            # Skip already-indexed flat children (SUMMARY, tasks/*.md, workbench/*.md).
            if rel.name == "SUMMARY.md" and len(rel.parts) == 1:
                continue
            if rel.parts[0] in ("tasks", "workbench") and len(rel.parts) == 2:
                continue
            if rel.name == "index.md":
                continue
            dest = out_sess / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(md, dest)

    for doc in world.docs.values():
        if doc.id.kind != "workspace" or doc.rel_path is None:
            continue
        k_dir = doc.rel_path / "knowledge"
        if not k_dir.is_dir():
            continue
        out_k = out_dir / "workspaces" / doc.id.workspace / "knowledge"
        for md in k_dir.rglob("*.md"):
            rel = md.relative_to(k_dir)
            if rel.name == "index.md":
                continue
            if len(rel.parts) == 1:
                continue  # already copied by _copy_markdown
            dest = out_k / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(md, dest)


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
        elif kind == "knowledge" and doc.id.workspace and f"{doc.id.workspace}/" == parent_canon:
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
        lines.append(f"- [{ws.id.workspace}](workspaces/{ws.id.workspace}/index.html)")

    # The brain: a derived cross-workspace knowledge dictionary, grouped by type.
    # Grouping/ordering and the description fallback are shared with the
    # `cortex kb index --workspace=all` CLI (cortex.model) so the two brain
    # surfaces stay consistent.
    kdocs = [d for d in world.docs.values()
             if d.id.kind == "knowledge" and not d.ghost]
    lines += ["", f"## Knowledge ({len(kdocs)})", ""]
    if not kdocs:
        lines.append("_No knowledge docs yet._")
    else:
        for display_ty, group in model.group_by_type(kdocs, lambda d: d.type):
            lines += ["", f"### {display_ty if display_ty else '(untyped)'}", ""]
            for d in sorted(group,
                            key=lambda d: (d.id.slug or "", d.id.workspace or "")):
                href = _content_path(d.id) or ""
                # Raw frontmatter title (not the slug-fallback Doc.title) so the
                # description fallback matches the CLI's `kb index` exactly.
                raw_title = d.frontmatter.get("title") if d.frontmatter else None
                desc = model.format_description(d.description, raw_title)
                lines.append(f"- [{d.id.slug} ({d.id.workspace})]({href}) - {desc}")
    lines.append("")
    (out_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_workspace_index(world: World, ws: Doc, out_dir: Path) -> None:
    ws_dir = out_dir / "workspaces" / ws.id.workspace
    ws_dir.mkdir(parents=True, exist_ok=True)
    sessions = _children_of(world, ws.id.canonical(), "session")
    knowledge_docs = _children_of(world, ws.id.canonical(), "knowledge")
    lines = [f"# {ws.id.workspace}", "",
             "[<- Dashboard](../../index.html)", "",
             f"## Sessions ({len(sessions)})", ""]
    for s in sessions:
        lines.append(f"- [{s.id.session}](sessions/{s.id.session}/index.html)")
    lines.extend(["", f"## Knowledge ({len(knowledge_docs)})", "",
                  "[Open knowledge folder](knowledge/index.md)", ""])
    (ws_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_knowledge_index(world: World, ws: Doc, out_dir: Path) -> None:
    k_dir = out_dir / "workspaces" / ws.id.workspace / "knowledge"
    k_dir.mkdir(parents=True, exist_ok=True)
    docs = _children_of(world, ws.id.canonical(), "knowledge")
    lines = [f"# {ws.id.workspace} / knowledge", "",
             "[<- Workspace](../index.html)", "",
             f"## Knowledge docs ({len(docs)})", ""]
    if not docs:
        lines.append("_No knowledge docs yet._")
    else:
        for d in docs:
            lines.append(f"- [{d.id.slug}]({d.id.slug}.md)")
    (k_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_session_index(world: World, sess: Doc, out_dir: Path) -> None:
    sess_dir = out_dir / "workspaces" / sess.id.workspace / "sessions" / sess.id.session
    sess_dir.mkdir(parents=True, exist_ok=True)
    parent_canon = sess.id.canonical()
    tasks = _children_of(world, parent_canon, "task")
    workbenches = _children_of(world, parent_canon, "workbench")
    lines = [f"# {sess.id.session}", "",
             f"_In workspace `{sess.id.workspace}`_", "",
             "[<- Workspace](../../index.html)", "",
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
             "[<- Session](../index.html)", "",
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
             "[<- Session](../index.html)", "",
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
        _emit_knowledge_index(world, ws, out_dir)
        for sess in _children_of(world, ws.id.canonical(), "session"):
            _emit_session_index(world, sess, out_dir)
            _emit_workbench_index(world, sess, out_dir)
            _emit_tasks_index(world, sess, out_dir)


def _content_path(cid: DocId) -> Optional[str]:
    """Root-relative path to a doc's markdown content. The frontend prepends a
    page-scope prefix derived from payload.rootHref before fetching."""
    if cid.kind == "root":
        return "index.md"
    if cid.kind == "workspace":
        return f"workspaces/{cid.workspace}/index.md"
    if cid.kind == "session":
        return f"workspaces/{cid.workspace}/sessions/{cid.session}/SUMMARY.md"
    if cid.kind == "task":
        return f"workspaces/{cid.workspace}/sessions/{cid.session}/tasks/{cid.slug}.md"
    if cid.kind == "knowledge":
        return f"workspaces/{cid.workspace}/knowledge/{cid.slug}.md"
    if cid.kind == "workbench":
        return f"workspaces/{cid.workspace}/sessions/{cid.session}/workbench/{cid.slug}.md"
    return None


def _first_paragraph(body: str, limit: int = 300) -> str:
    """First prose paragraph of a body: skip leading blank lines and a single
    leading `# ` H1, then take consecutive non-blank lines up to the next blank.
    Joined with spaces and capped. Empty when there is no prose."""
    lines = (body or "").split("\n")
    n = len(lines)
    i = 0
    while i < n and not lines[i].strip():
        i += 1
    if i < n and lines[i].lstrip().startswith("# "):
        i += 1
        while i < n and not lines[i].strip():
            i += 1
    para = []
    while i < n and lines[i].strip():
        para.append(lines[i].strip())
        i += 1
    return " ".join(para).strip()[:limit]


def _search_page_href(cid: DocId) -> str:
    """Root-relative href of the page whose scope shows this doc (its home)."""
    if cid.kind == "root":
        return "index.html"
    if cid.kind in ("workspace", "knowledge"):
        return f"workspaces/{cid.workspace}/index.html"
    # task, workbench, session render on the session page
    return f"workspaces/{cid.workspace}/sessions/{cid.session}/index.html"


def _search_docs(world: World) -> list:
    """One search record per non-ghost doc, sorted by id for deterministic output."""
    out = []
    for doc in world.docs.values():
        if doc.ghost:
            continue
        cid = doc.id
        out.append({
            "id": cid.canonical(),
            "kind": cid.kind,
            "slug": cid.slug or cid.session or cid.workspace or "root",
            "title": doc.title or "",
            "type": doc.type or "",
            "description": doc.description or "",
            "text": _first_paragraph(doc.body or ""),
            "ws": cid.workspace or "",
            "sess": cid.session or "",
            "pageHref": _search_page_href(cid),
            "contentPath": _content_path(cid),
        })
    out.sort(key=lambda r: r["id"])
    return out


def _write_search_index(world: World, out_dir: Path) -> None:
    (out_dir / "search-docs.json").write_text(
        json.dumps(_search_docs(world), ensure_ascii=False), encoding="utf-8")


def _node_dict(world: World, doc: Doc) -> dict:
    cid = doc.id
    if cid.kind == "workspace":
        parent = "/"
    elif cid.kind == "session":
        parent = f"{cid.workspace}/"
    elif cid.kind in ("task", "workbench"):
        parent = f"{cid.workspace}/{cid.session}/"
    elif cid.kind == "knowledge":
        parent = f"{cid.workspace}/"
    else:
        parent = None
    label = cid.slug or cid.session or cid.workspace or "root"
    # Strip the YYYY-MM-DD- prefix that archived session dirs use, so the
    # tree shows a readable name; the canonical id still embeds the prefix.
    if doc.archived and cid.kind == "session" and label:
        import re as _re
        label = _re.sub(r"^\d{4}-\d{2}-\d{2}-", "", label)
    content_path = None if doc.ghost else _content_path(cid)
    return {
        "id": cid.canonical(),
        "label": label,
        "kind": cid.kind,
        "parent": parent,
        "status": doc.status,
        "ghost": doc.ghost,
        "archived": doc.archived,
        "author": doc.author,
        "type": doc.type,
        "description": doc.description,
        "updated": doc.updated,
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
    neighbours: set[str] = set()
    keep_edges = []
    for e in world.edges:
        s, t = e.source.canonical(), e.target.canonical()
        if s in in_scope or t in in_scope:
            keep_edges.append(e)
            neighbours.add(s)
            neighbours.add(t)
    keep_ids = in_scope | neighbours
    # Sort the keep_ids so payload node order is deterministic across builds
    # (Python sets iterate in hash-randomized order otherwise).
    nodes = [_node_dict(world, world.docs[cid]) for cid in sorted(keep_ids) if cid in world.docs]
    edges = [_edge_dict(e) for e in keep_edges]
    return nodes, edges


def _global_wikilink_index(world: World) -> dict[str, str]:
    """Map slug -> root-relative contentPath for every non-ghost doc with
    content. Live docs are indexed first so they win on slug collisions with
    archived ones; archived sessions also get an alias under their
    stripped-date slug so [[task-graph]] still resolves to the closed session
    when no live one exists by that name."""
    import re as _re
    out: dict[str, str] = {}
    def _index_pass(predicate):
        for doc in world.docs.values():
            if doc.ghost or not predicate(doc):
                continue
            path = _content_path(doc.id)
            if not path:
                continue
            cid = doc.id
            slug = cid.slug or cid.session or cid.workspace
            if slug and slug not in out:
                out[slug] = path
            if doc.archived and cid.kind == "session":
                alias = _re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug or "")
                if alias and alias != slug and alias not in out:
                    out[alias] = path
    _index_pass(lambda d: not d.archived)
    _index_pass(lambda d: d.archived)
    return out


def _build_tree(world: World) -> list[dict]:
    import re as _re
    root_doc = world.docs.get("/")
    root_node = {"id": "/", "label": "Fred's Work Tracking", "kind": "root",
                 "scopeId": "/", "href": "index.html",
                 "contentPath": _content_path(root_doc.id) if root_doc else "index.md",
                 "archived": False,
                 "children": []}
    for ws in _children_of(world, "/", "workspace"):
        ws_node = {
            "id": ws.id.canonical(),
            "scopeId": ws.id.canonical(),
            "label": ws.id.workspace, "kind": "workspace",
            "href": f"workspaces/{ws.id.workspace}/index.html",
            "contentPath": _content_path(ws.id),
            "archived": False,
            "children": [],
        }
        for sess in _children_of(world, ws.id.canonical(), "session"):
            sess_label = sess.id.session or ""
            if sess.archived:
                sess_label = _re.sub(r"^\d{4}-\d{2}-\d{2}-", "", sess_label)
            sess_node = {
                "id": sess.id.canonical(),
                "scopeId": sess.id.canonical(),
                "label": sess_label, "kind": "session",
                "href": f"workspaces/{ws.id.workspace}/sessions/{sess.id.session}/index.html",
                "contentPath": _content_path(sess.id),
                "archived": sess.archived,
                "children": [],
            }
            for t in _children_of(world, sess.id.canonical(), "task"):
                sess_node["children"].append({
                    "id": t.id.canonical(),
                    "scopeId": t.id.canonical(),
                    "label": t.id.slug, "kind": "task", "href": None,
                    "contentPath": _content_path(t.id),
                    "archived": t.archived,
                    "status": t.status,
                    "children": [],
                })
            for wb in _children_of(world, sess.id.canonical(), "workbench"):
                sess_node["children"].append({
                    "id": wb.id.canonical(),
                    "scopeId": wb.id.canonical(),
                    "label": wb.id.slug, "kind": "workbench", "href": None,
                    "contentPath": _content_path(wb.id),
                    "archived": wb.archived,
                    "author": wb.author,
                    "type": wb.type,
                    "description": wb.description,
                    "updated": wb.updated,
                    "children": [],
                })
            ws_node["children"].append(sess_node)
        for k in _children_of(world, ws.id.canonical(), "knowledge"):
            ws_node["children"].append({
                "id": k.id.canonical(),
                "scopeId": k.id.canonical(),
                "label": k.id.slug, "kind": "knowledge", "href": None,
                "contentPath": _content_path(k.id),
                "archived": False,
                "author": k.author,
                "type": k.type,
                "description": k.description,
                "updated": k.updated,
                "children": [],
            })
        root_node["children"].append(ws_node)
    return [root_node]


def _render_shell(scope: str, scope_id: str, payload: dict, vendor_rel: str,
                  title: str, title_line: str, subtitle_line: str) -> str:
    blob = json.dumps(payload, ensure_ascii=False)
    html = _SHELL_TEMPLATE
    html = html.replace("__TITLE__", title)
    html = html.replace("__TITLE_LINE__", title_line)
    html = html.replace("__SUBTITLE_LINE__", subtitle_line)
    html = html.replace("__VENDOR__", vendor_rel)
    html = html.replace("__ROOT_HREF__", payload.get("rootHref", "index.html"))
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


def build_payload(world: World, scope: str, scope_id: str) -> dict:
    """Per-scope payload embedded in a page and returned by the save API.
    Single source of truth for both the static build and live edit refresh."""
    wikilinks = _global_wikilink_index(world)
    tree = _build_tree(world)
    nodes, edges = _scope_filter(world, scope, scope_id)
    if scope == "root":
        root_href = "index.html"
        default_cp = "index.md"
    elif scope == "workspace":
        ws = scope_id.rstrip("/")
        root_href = "../../index.html"
        default_cp = f"workspaces/{ws}/index.md"
    else:  # session
        ws, sess = scope_id.rstrip("/").split("/", 1)
        root_href = "../../../../index.html"
        default_cp = f"workspaces/{ws}/sessions/{sess}/SUMMARY.md"
    return {
        "scope": scope, "scopeId": scope_id, "rootHref": root_href,
        "tree": tree, "nodes": nodes, "edges": edges,
        "defaultContentPath": default_cp, "wikilinks": wikilinks,
    }


def _emit_html_pages(world: World, out_dir: Path) -> None:
    payload = build_payload(world, "root", "/")
    (out_dir / "index.html").write_text(
        _render_shell("root", "/", payload, _vendor_rel("root", "/"),
                      "Fred's Work Tracking",
                      title_line="Fred's Work Tracking",
                      subtitle_line="all workspaces"),
        encoding="utf-8")

    for ws in _children_of(world, "/", "workspace"):
        ws_scope_id = ws.id.canonical()
        payload = build_payload(world, "workspace", ws_scope_id)
        ws_html = out_dir / "workspaces" / ws.id.workspace / "index.html"
        ws_html.write_text(
            _render_shell("workspace", ws_scope_id, payload,
                          _vendor_rel("workspace", ws_scope_id),
                          ws.id.workspace,
                          title_line=ws.id.workspace,
                          subtitle_line="workspace"),
            encoding="utf-8")
        for sess in _children_of(world, ws_scope_id, "session"):
            sess_scope_id = sess.id.canonical()
            payload = build_payload(world, "session", sess_scope_id)
            sess_html = ws_html.parent / "sessions" / sess.id.session / "index.html"
            sess_html.write_text(
                _render_shell("session", sess_scope_id, payload,
                              _vendor_rel("session", sess_scope_id),
                              f"{sess.id.session} - {ws.id.workspace}",
                              title_line=sess.id.session,
                              subtitle_line=f"session in workspace {ws.id.workspace}"),
                encoding="utf-8")


def _write_manifest(out_dir: Path, workspaces_root: Optional[Path]) -> None:
    import datetime
    data = {
        "workspacesRoot": str(workspaces_root) if workspaces_root else "",
        "builtAt": datetime.datetime.now().astimezone().isoformat(),
    }
    (out_dir / MANIFEST_NAME).write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")


def build(world: World, out_dir: Path, workspaces_root: Optional[Path] = None) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _stage_vendor(out_dir)
    _copy_markdown(world, out_dir)
    _copy_supplementary_md(world, out_dir)
    _emit_all_indices(world, out_dir)
    _emit_html_pages(world, out_dir)
    _write_search_index(world, out_dir)
    _write_manifest(out_dir, workspaces_root)
