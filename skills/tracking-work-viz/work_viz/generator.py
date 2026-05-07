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

from .parser import parse_workspace, parse_world
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


def _list_workspace_slugs(workspaces_root: Path) -> list:
    if not workspaces_root.is_dir():
        return []
    return sorted(p.name for p in workspaces_root.iterdir() if p.is_dir())


# ---------------------------------------------------------------------------
# Per-edge-class data builders (Step 6)
# ---------------------------------------------------------------------------

# Transitional: generate_one_shot / generate_dashboard will be rewired in Step 7
# to call build_workspace_html / build_dashboard_html. Until then they emit an
# empty graph payload so the @@CY_DATA@@ placeholder is satisfied.
_EMPTY_CY_DATA: dict = {
    "modes": {
        "local": {"nodes": [], "edges": []},
        "global": {"nodes": [], "edges": []},
    },
    "ghosts": [],
    "default_mode": "local",
}


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
        # If the target is outside this WS and not already a real node, add ghost
        if not edge.target.startswith(ws_prefix) and edge.target not in real_ids:
            if edge.target not in ghost_ids_seen:
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

    # Collect edges touching this WS (source or target in WS)
    touching_edges: list = []
    neighbor_ids: set = set()
    for edge in world.edges:
        src_in = edge.source.startswith(ws_prefix)
        tgt_in = edge.target.startswith(ws_prefix)
        if src_in or tgt_in:
            touching_edges.append(_serialize_edge(edge))
            if src_in and not tgt_in:
                neighbor_ids.add(edge.target)
            if tgt_in and not src_in:
                neighbor_ids.add(edge.source)

    # Build a lookup of all world nodes by id
    world_node_lookup: dict = {n["id"]: n for n in _collect_nodes(world)}

    # Add neighbor nodes that are real (exist in world) and not already in WS
    extra_nodes: list = []
    for nid in neighbor_ids:
        if nid in ws_node_ids:
            continue
        if nid in world_node_lookup:
            extra_nodes.append(world_node_lookup[nid])
        # Unresolvable (ghost) neighbors are not added as real nodes in global mode

    return {"nodes": ws_nodes + extra_nodes, "edges": touching_edges}


def _build_dashboard_global(world: World) -> dict:
    """Return all nodes and all edges in the world."""
    return {
        "nodes": _collect_nodes(world),
        "edges": [_serialize_edge(edge) for edge in world.edges],
    }


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
        raise ValueError(f"Workspace '{slug}' not found in world")

    data = asdict(ws_obj)
    data["available_workspaces"] = [ws.slug for ws in world.workspaces]

    payload = _safe_json_for_script_tag(data)
    cy_payload = _safe_json_for_script_tag(cy_data)

    return _render("index.html", {
        '"@@MODE@@"': '"static"',
        "@@DATA@@": payload,
        "@@CY_DATA@@": cy_payload,
    })


def build_dashboard_html(world: World) -> str:
    """Return the full HTML string for the dashboard page (pure, no I/O)."""
    # Dashboard has no per-workspace local view; local is intentionally empty.
    cy_data = {
        "modes": {
            "local": {"nodes": [], "edges": []},
            "global": _build_dashboard_global(world),
        },
        "ghosts": list(world.ghosts),
        "default_mode": "global",
    }

    # Build the existing summary data dict from the world workspaces
    # (replicated logic from _summarize_one but without filesystem I/O)
    # For dashboard HTML built from World, we emit a minimal summary.
    # The full filesystem-based summary is only needed for generate_dashboard.
    summary = {"workspaces": [ws.slug for ws in world.workspaces]}
    payload = _safe_json_for_script_tag(summary)
    cy_payload = _safe_json_for_script_tag(cy_data)

    return _render("dashboard.html", {
        "@@DATA@@": payload,
        "@@CY_DATA@@": cy_payload,
    })


def generate_one_shot(workspaces_root: Path, slug: str, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    ws = parse_workspace(workspaces_root, slug)
    data = asdict(ws)
    # Embed sibling workspace slugs so the UI can render a switcher.
    data["available_workspaces"] = _list_workspace_slugs(workspaces_root)
    payload = _safe_json_for_script_tag(data)
    cy_payload = _safe_json_for_script_tag(_EMPTY_CY_DATA)
    html = _render("index.html", {
        '"@@MODE@@"': '"static"',
        "@@DATA@@": payload,
        "@@CY_DATA@@": cy_payload,
    })
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _summarize_one(workspaces_root: Path, ws_dir: Path) -> dict:
    """Build the dashboard row for a single workspace. Raises on parse failure."""
    slug = ws_dir.name
    ws = parse_workspace(workspaces_root, slug)
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
        "slug": slug,
        "session_count": session_count,
        "task_count": task_count,
        "last_updated": last_iso,
        "last_mtime": last_mtime,
        "agent_count": len(ws.active_session_slugs),
        "status_counts": status_counts,
    }


def _summarize(workspaces_root: Path) -> dict:
    out: dict = {"workspaces": []}
    if not workspaces_root.is_dir():
        return out
    for ws_dir in sorted(p for p in workspaces_root.iterdir() if p.is_dir()):
        try:
            out["workspaces"].append(_summarize_one(workspaces_root, ws_dir))
        except Exception as exc:
            # Don't let one corrupt workspace blow up the whole dashboard;
            # surface it as a placeholder row so the user notices.
            print(f"warning: failed to summarize {ws_dir.name}: {exc}", file=sys.stderr)
            out["workspaces"].append({
                "slug": ws_dir.name,
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
    summary = _summarize(workspaces_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Also generate per-workspace pages so dashboard links resolve.
    for entry in summary["workspaces"]:
        if entry.get("error"):
            continue  # parse already failed; don't try to render the per-workspace page
        try:
            generate_one_shot(workspaces_root, entry["slug"], out_dir=out_dir)
        except Exception as exc:
            print(f"warning: failed to generate {entry['slug']}.html: {exc}", file=sys.stderr)
    payload = _safe_json_for_script_tag(summary)
    empty_cy = dict(_EMPTY_CY_DATA)
    cy_payload = _safe_json_for_script_tag(empty_cy)
    html = _render("dashboard.html", {
        "@@DATA@@": payload,
        "@@CY_DATA@@": cy_payload,
    })
    out_path = out_dir / "dashboard.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
