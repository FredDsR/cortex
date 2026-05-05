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

from .parser import parse_workspace


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


def generate_one_shot(workspaces_root: Path, slug: str, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    ws = parse_workspace(workspaces_root, slug)
    data = asdict(ws)
    # Embed sibling workspace slugs so the UI can render a switcher.
    data["available_workspaces"] = _list_workspace_slugs(workspaces_root)
    payload = _safe_json_for_script_tag(data)
    html = _render("index.html", {
        '"@@MODE@@"': '"static"',
        "@@DATA@@": payload,
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
    html = _render("dashboard.html", {"@@DATA@@": payload})
    out_path = out_dir / "dashboard.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
