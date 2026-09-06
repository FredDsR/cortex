"""The data half of the site: the per-scope payload the frontend renders (nodes,
edges, tree, wikilinks), the HTML shells that carry it to the browser, and the
search index.

`build_payload` is the single source of truth for both the static build and the
live refresh `viz serve --edit` performs on save.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

from cortex.model import World, Doc, DocId, Edge
from .layout import children_of, content_path, write_out

_SHELL_TEMPLATE = (Path(__file__).parent / "templates" / "shell.html").read_text(encoding="utf-8")


# ---- graph payload ----

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
        label = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", label)
    node_content = None if doc.ghost else content_path(cid)
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
        "contentPath": node_content,
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
    out: dict[str, str] = {}
    def _index_pass(predicate):
        for doc in world.docs.values():
            if doc.ghost or not predicate(doc):
                continue
            path = content_path(doc.id)
            if not path:
                continue
            cid = doc.id
            slug = cid.slug or cid.session or cid.workspace
            if slug and slug not in out:
                out[slug] = path
            if doc.archived and cid.kind == "session":
                alias = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug or "")
                if alias and alias != slug and alias not in out:
                    out[alias] = path
    _index_pass(lambda d: not d.archived)
    _index_pass(lambda d: d.archived)
    return out


def _build_tree(world: World) -> list[dict]:
    root_doc = world.docs.get("/")
    root_node = {"id": "/", "label": "Your Cortex", "kind": "root",
                 "scopeId": "/", "href": "index.html",
                 "contentPath": content_path(root_doc.id) if root_doc else "index.md",
                 "archived": False,
                 "children": []}
    for ws in children_of(world, "/", "workspace"):
        ws_node = {
            "id": ws.id.canonical(),
            "scopeId": ws.id.canonical(),
            "label": ws.id.workspace, "kind": "workspace",
            "href": f"workspaces/{ws.id.workspace}/index.html",
            "contentPath": content_path(ws.id),
            "archived": False,
            "children": [],
        }
        for sess in children_of(world, ws.id.canonical(), "session"):
            sess_label = sess.id.session or ""
            if sess.archived:
                sess_label = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", sess_label)
            sess_node = {
                "id": sess.id.canonical(),
                "scopeId": sess.id.canonical(),
                "label": sess_label, "kind": "session",
                "href": f"workspaces/{ws.id.workspace}/sessions/{sess.id.session}/index.html",
                "contentPath": content_path(sess.id),
                "archived": sess.archived,
                "children": [],
            }
            for t in children_of(world, sess.id.canonical(), "task"):
                sess_node["children"].append({
                    "id": t.id.canonical(),
                    "scopeId": t.id.canonical(),
                    "label": t.id.slug, "kind": "task", "href": None,
                    "contentPath": content_path(t.id),
                    "archived": t.archived,
                    "status": t.status,
                    "children": [],
                })
            for wb in children_of(world, sess.id.canonical(), "workbench"):
                sess_node["children"].append({
                    "id": wb.id.canonical(),
                    "scopeId": wb.id.canonical(),
                    "label": wb.id.slug, "kind": "workbench", "href": None,
                    "contentPath": content_path(wb.id),
                    "archived": wb.archived,
                    "author": wb.author,
                    "type": wb.type,
                    "description": wb.description,
                    "updated": wb.updated,
                    "children": [],
                })
            ws_node["children"].append(sess_node)
        for k in children_of(world, ws.id.canonical(), "knowledge"):
            ws_node["children"].append({
                "id": k.id.canonical(),
                "scopeId": k.id.canonical(),
                "label": k.id.slug, "kind": "knowledge", "href": None,
                "contentPath": content_path(k.id),
                "archived": False,
                "author": k.author,
                "type": k.type,
                "description": k.description,
                "updated": k.updated,
                "children": [],
            })
        root_node["children"].append(ws_node)
    return [root_node]


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


# ---- html shells ----

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


def emit_html_pages(world: World, out_dir: Path) -> None:
    payload = build_payload(world, "root", "/")
    write_out(out_dir / "index.html",
               _render_shell("root", "/", payload, _vendor_rel("root", "/"),
                             "Your Cortex",
                             title_line="Your Cortex",
                             subtitle_line="all workspaces"))

    for ws in children_of(world, "/", "workspace"):
        ws_scope_id = ws.id.canonical()
        payload = build_payload(world, "workspace", ws_scope_id)
        ws_html = out_dir / "workspaces" / ws.id.workspace / "index.html"
        write_out(ws_html,
                   _render_shell("workspace", ws_scope_id, payload,
                                 _vendor_rel("workspace", ws_scope_id),
                                 ws.id.workspace,
                                 title_line=ws.id.workspace,
                                 subtitle_line="workspace"))
        for sess in children_of(world, ws_scope_id, "session"):
            sess_scope_id = sess.id.canonical()
            payload = build_payload(world, "session", sess_scope_id)
            sess_html = ws_html.parent / "sessions" / sess.id.session / "index.html"
            write_out(
                sess_html,
                _render_shell("session", sess_scope_id, payload,
                              _vendor_rel("session", sess_scope_id),
                              f"{sess.id.session} - {ws.id.workspace}",
                              title_line=sess.id.session,
                              subtitle_line=f"session in workspace {ws.id.workspace}"))


# ---- search index ----

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
            "contentPath": content_path(cid),
        })
    out.sort(key=lambda r: r["id"])
    return out


def write_search_index(world: World, out_dir: Path) -> None:
    write_out(out_dir / "search-docs.json",
               json.dumps(_search_docs(world), ensure_ascii=False))
