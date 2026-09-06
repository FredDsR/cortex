"""Where a doc lives: output paths, content hrefs, and the parent/child walk.

The vocabulary every builder shares. `pages` writes markdown to `doc_out_path`,
`graph` points the frontend at `content_path`, and both walk the store with
`children_of`.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from cortex import atomic
from cortex.model import World, Doc, DocId


def write_out(path: Path, data: str) -> None:
    """Build output is regenerated from source, so replace atomically (a partial
    page would break the served site) but skip the fsyncs: `viz serve --edit`
    rebuilds every page on every save."""
    atomic.write_text(path, data, encoding="utf-8", durable=False)


def doc_out_path(doc: Doc, out_dir: Path) -> Path:
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


def content_path(cid: DocId) -> Optional[str]:
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


def children_of(world: World, parent_canon: str, kind: str) -> list[Doc]:
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
