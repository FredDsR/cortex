"""Render an HTML viewer for a workspace.

The output HTML inlines the parsed workspace data as JSON but loads
Cytoscape, dagre, marked, and the first-party `app.js` / `app.css` from
relative `vendor/` paths. `install.sh` populates `~/.work/viz/vendor/`
with the third-party JS and copies the first-party assets there.
"""
from __future__ import annotations
import datetime as _dt
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from .parser import parse_world
from .model import World


def _safe_json_for_script_tag(obj) -> str:
    """JSON-encode `obj` and escape sequences that could close a <script> tag.

    A task body or workspace slug containing the literal `</script>` would
    otherwise terminate the inline `<script>` block early and inject the
    remaining content into the document. Replacing `</` with `<\\/` keeps
    the value JSON-string-equivalent (JS unescapes `\\/` to `/`) while
    preventing the parser from seeing a closing tag. We also escape U+2028
    / U+2029 which are valid in JSON but illegal as raw characters in JS
    string literals.
    """
    raw = json.dumps(obj, ensure_ascii=False)
    return (raw
            .replace("</", "<\\/")
            .replace(" ", "\\u2028")
            .replace(" ", "\\u2029"))


_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
DEFAULT_OUT_DIR = Path.home() / ".work" / "viz"


def _render(template_name: str, replacements: dict) -> str:
    raw = (_TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
    out = raw
    for key, value in replacements.items():
        out = out.replace(key, value)
    return out


# ---------------------------------------------------------------------------
# Per-edge-class data builders (Step 6)
# ---------------------------------------------------------------------------


def _serialize_edge(edge) -> dict:
    """Convert a parsed Edge to a JSON-friendly dict.

    Both edge.source and edge.target are already canonicalized by parse_world.
    """
    return {
        "source": edge.source,
        "target": edge.target,
        "kind": edge.kind,
        "resolved": edge.resolved,
    }


def _collect_nodes(world: World, slug: str | None = None) -> list:
    """Collect node dicts. If slug is provided, restrict to that workspace.
    Otherwise return nodes for all workspaces. Skips archived sessions."""
    nodes: list = []
    for ws in world.workspaces:
        if slug is not None and ws.slug != slug:
            continue
        for sess in ws.sessions:
            if sess.archived:
                continue
            for task in sess.tasks:
                nodes.append({
                    "id": f"{ws.slug}/{sess.slug}/{task.slug}",
                    "label": task.slug,
                    "ws": ws.slug,
                    "session": sess.slug,
                    "status": task.status,
                    "ghost": False,
                })
    return nodes


def _build_local_mode(world: World, slug: str) -> dict:
    """Return nodes+edges for a workspace in Local mode.

    Nodes: all tasks in this WS plus ghost nodes for cross-WS edge targets.
    Edges: all edges whose source is in this WS.
    """
    ws_prefix = slug + "/"
    real_nodes = _collect_nodes(world, slug)
    real_ids = {n["id"] for n in real_nodes}

    # Collect cross-WS edge targets that are not in this WS
    ghost_ids_seen: set = set()
    ghost_nodes: list = []
    local_edges: list = []

    for edge in world.edges:
        if not edge.source.startswith(ws_prefix):
            continue
        local_edges.append(_serialize_edge(edge))
        # Add a ghost for any target that isn't a real node in this WS.
        # Covers both cross-WS targets and same-WS targets that didn't
        # resolve (e.g., a typo or a stale slug). Cytoscape rejects edges
        # whose endpoints aren't in the elements list, so dangling targets
        # MUST be represented somehow.
        if edge.target not in real_ids and edge.target not in ghost_ids_seen:
            ghost_ids_seen.add(edge.target)
            parts = edge.target.split("/")
            ghost_ws = parts[0] if len(parts) >= 1 else ""
            ghost_sess = parts[1] if len(parts) >= 2 else ""
            ghost_task = parts[2] if len(parts) >= 3 else edge.target
            ghost_nodes.append({
                "id": edge.target,
                "label": ghost_task,
                "ws": ghost_ws,
                "session": ghost_sess,
                "status": "unknown",
                "ghost": True,
            })

    return {"nodes": real_nodes + ghost_nodes, "edges": local_edges}


def _build_global_mode_for_workspace(world: World, slug: str) -> dict:
    """Return nodes+edges for a workspace in Global mode.

    Nodes: all tasks in this WS plus 1-hop neighbors in other workspaces.
    Edges: all edges where source or target is in this WS.
    """
    ws_prefix = slug + "/"
    ws_nodes = _collect_nodes(world, slug)
    ws_node_ids = {n["id"] for n in ws_nodes}

    # Collect edges touching this WS and every endpoint they reference.
    touching_edges: list = []
    referenced_ids: set = set()
    for edge in world.edges:
        src_in = edge.source.startswith(ws_prefix)
        tgt_in = edge.target.startswith(ws_prefix)
        if src_in or tgt_in:
            touching_edges.append(_serialize_edge(edge))
            referenced_ids.add(edge.source)
            referenced_ids.add(edge.target)

    world_node_lookup: dict = {n["id"]: n for n in _collect_nodes(world)}

    # For every endpoint not already in this WS's real nodes, add either
    # a real (cross-WS resolved) node or a ghost node. Cytoscape rejects
    # edges whose endpoints aren't in the elements list, so we must
    # represent every endpoint somehow.
    extra_nodes: list = []
    for nid in referenced_ids:
        if nid in ws_node_ids:
            continue
        if nid in world_node_lookup:
            extra_nodes.append(world_node_lookup[nid])
        else:
            parts = nid.split("/")
            extra_nodes.append({
                "id": nid,
                "label": parts[2] if len(parts) >= 3 else nid,
                "ws": parts[0] if len(parts) >= 1 else "",
                "session": parts[1] if len(parts) >= 2 else "",
                "status": "unknown",
                "ghost": True,
            })

    return {"nodes": ws_nodes + extra_nodes, "edges": touching_edges}


def _build_dashboard_global(world: World) -> dict:
    """Return all nodes and all edges in the world.

    Includes ghost nodes for any edge endpoint that didn't resolve to a
    real task, so consumers can render every edge without filtering.
    """
    real_nodes = _collect_nodes(world)
    real_ids = {n["id"] for n in real_nodes}
    edges = [_serialize_edge(edge) for edge in world.edges]
    ghost_seen: set = set()
    ghost_nodes: list = []
    for edge in world.edges:
        for endpoint in (edge.source, edge.target):
            if endpoint in real_ids or endpoint in ghost_seen:
                continue
            ghost_seen.add(endpoint)
            parts = endpoint.split("/")
            ghost_nodes.append({
                "id": endpoint,
                "label": parts[2] if len(parts) >= 3 else endpoint,
                "ws": parts[0] if len(parts) >= 1 else "",
                "session": parts[1] if len(parts) >= 2 else "",
                "status": "unknown",
                "ghost": True,
            })
    return {"nodes": real_nodes + ghost_nodes, "edges": edges}


def build_workspace_html(world: World, slug: str) -> str:
    """Return the full HTML string for a workspace page (pure, no I/O)."""
    cy_data = {
        "modes": {
            "local": _build_local_mode(world, slug),
            "global": _build_global_mode_for_workspace(world, slug),
        },
        "ghosts": list(world.ghosts),
        "default_mode": "local",
    }

    ws_obj = next((ws for ws in world.workspaces if ws.slug == slug), None)
    if ws_obj is None:
        raise FileNotFoundError(f"workspace not found: {slug}")

    data = asdict(ws_obj)
    data["available_workspaces"] = [ws.slug for ws in world.workspaces]

    payload = _safe_json_for_script_tag(data)
    cy_payload = _safe_json_for_script_tag(cy_data)

    return _render("index.html", {
        '"@@MODE@@"': '"static"',
        "@@DATA@@": payload,
        "@@CY_DATA@@": cy_payload,
    })


def _dashboard_cy_data(world: World) -> dict:
    """Return the cy_data dict shared by the dashboard page builders."""
    return {
        "modes": {
            "local": {"nodes": [], "edges": []},
            "global": _build_dashboard_global(world),
        },
        "ghosts": list(world.ghosts),
        "default_mode": "global",
    }


def build_dashboard_html(world: World) -> str:
    """Return the full HTML string for the dashboard page (pure, no I/O)."""
    # For dashboard HTML built from World alone, emit a minimal summary.
    # The full filesystem-based summary is only needed for generate_dashboard.
    summary = {"workspaces": [ws.slug for ws in world.workspaces]}
    payload = _safe_json_for_script_tag(summary)
    cy_payload = _safe_json_for_script_tag(_dashboard_cy_data(world))

    return _render("dashboard.html", {
        "@@DATA@@": payload,
        "@@CY_DATA@@": cy_payload,
    })


def generate_one_shot(workspaces_root: Path, slug: str, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    world = parse_world(workspaces_root)
    html = build_workspace_html(world, slug)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _summarize_one(workspaces_root: Path, ws) -> dict:
    """Build the dashboard row for a single workspace from a parsed Workspace object.

    The last_mtime is still computed from the filesystem because it reflects
    file modification times that are not captured in the parsed model.
    """
    ws_dir = workspaces_root / ws.slug
    active_sessions = [s for s in ws.sessions if not s.archived]
    session_count = len(active_sessions)
    all_tasks = [t for s in active_sessions for t in s.tasks]
    task_count = len(all_tasks)
    status_counts = {"in_progress": 0, "open": 0, "blocked": 0, "resolved": 0, "unknown": 0}
    for t in all_tasks:
        status_counts[t.status] = status_counts.get(t.status, 0) + 1
    last_mtime = 0.0
    for dp, _, fns in os.walk(ws_dir):
        for fn in fns:
            try:
                mt = (Path(dp) / fn).stat().st_mtime
                if mt > last_mtime:
                    last_mtime = mt
            except OSError:
                pass
    last_iso = (
        _dt.datetime.fromtimestamp(last_mtime).strftime("%Y-%m-%d %H:%M")
        if last_mtime else ""
    )
    return {
        "slug": ws.slug,
        "session_count": session_count,
        "task_count": task_count,
        "last_updated": last_iso,
        "last_mtime": last_mtime,
        "agent_count": len(ws.active_session_slugs),
        "status_counts": status_counts,
    }


def _summarize(workspaces_root: Path, world: World) -> dict:
    """Build the dashboard summary from an already-parsed World.

    Falls back to a placeholder row for any workspace that cannot be summarized
    (e.g., filesystem disappeared between parse and summary).
    """
    out: dict = {"workspaces": []}
    for ws in world.workspaces:
        try:
            out["workspaces"].append(_summarize_one(workspaces_root, ws))
        except Exception as exc:
            # Don't let one corrupt workspace blow up the whole dashboard;
            # surface it as a placeholder row so the user notices.
            print(f"warning: failed to summarize {ws.slug}: {exc}", file=sys.stderr)
            out["workspaces"].append({
                "slug": ws.slug,
                "session_count": 0,
                "task_count": 0,
                "last_updated": "",
                "last_mtime": 0,
                "agent_count": 0,
                "status_counts": {"in_progress": 0, "open": 0, "blocked": 0, "resolved": 0, "unknown": 0},
                "error": str(exc),
            })
    return out


def generate_dashboard(workspaces_root: Path, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    world = parse_world(workspaces_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Generate per-workspace pages so dashboard links resolve.
    for ws in world.workspaces:
        try:
            html = build_workspace_html(world, ws.slug)
            (out_dir / f"{ws.slug}.html").write_text(html, encoding="utf-8")
        except Exception as exc:
            print(f"warning: failed to generate {ws.slug}.html: {exc}", file=sys.stderr)
    # Build the filesystem-based summary (status counts, last_mtime, etc.)
    summary = _summarize(workspaces_root, world)
    # Re-render with the richer filesystem summary and the shared cy_data helper.
    payload = _safe_json_for_script_tag(summary)
    cy_payload = _safe_json_for_script_tag(_dashboard_cy_data(world))
    html = _render("dashboard.html", {
        "@@DATA@@": payload,
        "@@CY_DATA@@": cy_payload,
    })
    out_path = out_dir / "dashboard.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
