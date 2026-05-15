"""Filesystem walker: emits a World from a workspaces root."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

import yaml

from .model import (
    Doc, DocId, Edge, RawEdge, World,
    AUTHORED_EDGE_KINDS, STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_BLOCKED, STATUS_RESOLVED,
)
from . import address


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_block = text[4:end]
    body = text[end + 5:].lstrip("\n")
    try:
        fm = yaml.safe_load(fm_block) or {}
    except yaml.YAMLError:
        return {}, text
    return fm if isinstance(fm, dict) else {}, body


def _title_from_body(body: str, fallback: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _read_doc(path: Path, id: DocId) -> Doc:
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    title = _title_from_body(body, id.slug or id.session or id.workspace or "(untitled)")
    status = fm.get("status") if id.kind == "task" else None
    return Doc(id=id, title=title, body=body, frontmatter=fm, rel_path=path,
               edges_out=[], status=status)


def parse_world(workspaces_root: Path, *, include_archive: bool = False) -> World:
    workspaces_root = Path(workspaces_root)
    docs: dict[str, Doc] = {}
    edges: list[Edge] = []
    ghosts: set[str] = set()
    raw_edges_by_canonical: dict[str, list[RawEdge]] = {}

    # Root hub
    root = Doc(id=DocId(kind="root"), title="Fred's Work Tracking", body="",
               frontmatter={}, rel_path=None, edges_out=[])
    docs["/"] = root

    if not workspaces_root.is_dir():
        return World(root=root, docs=docs, edges=edges, ghosts=ghosts)

    for ws_dir in sorted(p for p in workspaces_root.iterdir() if p.is_dir()):
        ws_slug = ws_dir.name
        if ws_slug in address.RESERVED_WORDS:
            continue
        ws_id = DocId(kind="workspace", workspace=ws_slug)
        ws_doc = Doc(id=ws_id, title=ws_slug, body="", frontmatter={},
                     rel_path=ws_dir, edges_out=[])
        docs[ws_id.canonical()] = ws_doc
        edges.append(Edge(source=root.id, target=ws_id, raw_target=ws_slug,
                          kind="contains", resolved=True))

        # memory/*.md
        memory_dir = ws_dir / "memory"
        if memory_dir.is_dir():
            for mfile in sorted(memory_dir.glob("*.md")):
                mid = DocId(kind="memory", workspace=ws_slug, slug=mfile.stem)
                doc = _read_doc(mfile, mid)
                docs[mid.canonical()] = doc
                edges.append(Edge(source=ws_id, target=mid, raw_target=mfile.stem,
                                  kind="contains", resolved=True))
                raw_edges_by_canonical[mid.canonical()] = []

        # sessions/<sess>/...
        sessions_dir = ws_dir / "sessions"
        if sessions_dir.is_dir():
            for sess_dir in sorted(p for p in sessions_dir.iterdir() if p.is_dir()):
                sess_slug = sess_dir.name
                if sess_slug in address.RESERVED_WORDS:
                    continue
                sess_id = DocId(kind="session", workspace=ws_slug, session=sess_slug)
                summary = sess_dir / "SUMMARY.md"
                if summary.is_file():
                    sess_doc = _read_doc(summary, sess_id)
                else:
                    sess_doc = Doc(id=sess_id, title=sess_slug, body="", frontmatter={},
                                   rel_path=sess_dir, edges_out=[])
                docs[sess_id.canonical()] = sess_doc
                edges.append(Edge(source=ws_id, target=sess_id, raw_target=sess_slug,
                                  kind="contains", resolved=True))

                tasks_dir = sess_dir / "tasks"
                if tasks_dir.is_dir():
                    for tfile in sorted(tasks_dir.glob("*.md")):
                        if tfile.name == "index.md":
                            continue
                        tid = DocId(kind="task", workspace=ws_slug,
                                    session=sess_slug, slug=tfile.stem)
                        doc = _read_doc(tfile, tid)
                        docs[tid.canonical()] = doc
                        edges.append(Edge(source=sess_id, target=tid,
                                          raw_target=tfile.stem,
                                          kind="contains", resolved=True))
                        raw_edges_by_canonical[tid.canonical()] = []

                wb_dir = sess_dir / "workbench"
                if wb_dir.is_dir():
                    for wfile in sorted(wb_dir.glob("*.md")):
                        if wfile.name == "index.md":
                            continue
                        wid = DocId(kind="workbench", workspace=ws_slug,
                                    session=sess_slug, slug=wfile.stem)
                        doc = _read_doc(wfile, wid)
                        docs[wid.canonical()] = doc
                        edges.append(Edge(source=sess_id, target=wid,
                                          raw_target=wfile.stem,
                                          kind="contains", resolved=True))
                        raw_edges_by_canonical[wid.canonical()] = []

    return World(root=root, docs=docs, edges=edges, ghosts=ghosts)
