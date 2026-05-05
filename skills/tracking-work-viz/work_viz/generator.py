"""Render a one-shot self-contained HTML viewer for a workspace."""
from __future__ import annotations
import datetime as _dt
import json
import os
from dataclasses import asdict
from pathlib import Path

from .parser import parse_workspace


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
    payload = json.dumps(data, ensure_ascii=False)
    html = _render("index.html", {
        '"@@MODE@@"': '"static"',
        "@@DATA@@": payload,
    })
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _summarize(workspaces_root: Path) -> dict:
    out: dict = {"workspaces": []}
    if not workspaces_root.is_dir():
        return out
    for ws_dir in sorted(p for p in workspaces_root.iterdir() if p.is_dir()):
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
        out["workspaces"].append({
            "slug": slug,
            "session_count": session_count,
            "task_count": task_count,
            "last_updated": last_iso,
            "last_mtime": last_mtime,
            "agent_count": len(ws.active_session_slugs),
            "status_counts": status_counts,
        })
    return out


def generate_dashboard(workspaces_root: Path, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    summary = _summarize(workspaces_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Also generate per-workspace pages so dashboard links resolve.
    for entry in summary["workspaces"]:
        try:
            generate_one_shot(workspaces_root, entry["slug"], out_dir=out_dir)
        except Exception as exc:
            print(f"warning: failed to generate {entry['slug']}.html: {exc}", file=__import__("sys").stderr)
    payload = json.dumps(summary, ensure_ascii=False)
    html = _render("dashboard.html", {"@@DATA@@": payload})
    out_path = out_dir / "dashboard.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
