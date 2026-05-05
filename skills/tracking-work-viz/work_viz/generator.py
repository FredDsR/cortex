"""Render a one-shot self-contained HTML viewer for a workspace."""
from __future__ import annotations
import json
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


def generate_one_shot(workspaces_root: Path, slug: str, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    ws = parse_workspace(workspaces_root, slug)
    payload = json.dumps(asdict(ws), ensure_ascii=False)
    html = _render("index.html", {
        '"@@MODE@@"': '"static"',
        "@@DATA@@": payload,
    })
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
