"""Static-site generator: World -> filesystem under out_dir.

A build is a fixed order over three modules: `layout` answers where any doc
lives, `pages` mirrors the markdown and writes the index.md tree, and `graph`
writes the payload-bearing HTML shells and the search index. This module owns
the order and the build manifest, nothing else.
"""
from __future__ import annotations
import datetime
import json
from pathlib import Path
from typing import Optional

from cortex.model import World
from . import graph, pages
from .layout import write_out
# Re-exported: `viz serve --edit` rebuilds one page's payload on every save.
from .graph import build_payload

__all__ = ["MANIFEST_NAME", "build", "build_payload"]

MANIFEST_NAME = ".cortex-build.json"


def _write_manifest(out_dir: Path, workspaces_root: Optional[Path]) -> None:
    data = {
        "workspacesRoot": str(workspaces_root) if workspaces_root else "",
        "builtAt": datetime.datetime.now().astimezone().isoformat(),
    }
    write_out(out_dir / MANIFEST_NAME, json.dumps(data, ensure_ascii=False))


def build(world: World, out_dir: Path, workspaces_root: Optional[Path] = None) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages.stage_vendor(out_dir)
    pages.copy_markdown(world, out_dir)
    pages.copy_supplementary_md(world, out_dir)
    pages.emit_all_indices(world, out_dir)
    graph.emit_html_pages(world, out_dir)
    graph.write_search_index(world, out_dir)
    _write_manifest(out_dir, workspaces_root)
