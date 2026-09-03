"""Filesystem walker: emits a World from a workspaces root."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Optional

import yaml

from .model import (
    Doc, DocId, Edge, RawEdge, World,
    AUTHORED_EDGE_KINDS,
)
from . import address


_FENCE_RE = re.compile(r"^\s*```")
_BODY_REL_RE = re.compile(r"^\s*(Blocked by|Related to|Follows):\s*(.+)$", re.IGNORECASE)
_FM_KEY_TO_KIND = {"blocked_by": "blocked", "related_to": "related", "follows": "follows"}
_LABEL_TO_KIND = {"blocked by": "blocked", "related to": "related", "follows": "follows"}
# `(?!\()` excludes a markdown link label: in `[label](path.md)` the bracketed
# text names the link, not a doc, so `[text](...)` used as prose syntax was
# producing `text` as a reference (a ghost node in the viz, and a broken-ref
# finding in `kb lint`).
_MENTION_BRACKET_RE = re.compile(r"\[([a-z0-9][a-z0-9/_\-]*)\](?!\()")
_MENTION_BARE_RE = re.compile(r"\btask-[a-z0-9\-]+\b")
# ...but a markdown link whose href is the local `.md` file the label names IS a
# reference, and the commonest way to write one: `[corpus-dedup](corpus-dedup.md)`,
# `[knowledge/foo](../knowledge/foo.md)`. Requiring the href's stem to equal the
# label's last segment is what separates those from `[label](some/path.md)`,
# where the label names the link text and nothing else. Without this, every
# reference not spelled `task-<slug>` (the bare form) silently lost its edge.
_MENTION_MD_LINK_RE = re.compile(
    r"\[([a-z0-9][a-z0-9/_\-]*)\]\(([^)\s]+\.md)\)")
# Inline code is an illustration, not a reference: `` `[label](path.md)` `` is
# prose about markdown syntax. Blanked before the md-link scan only, so a
# backticked `task-slug` keeps behaving as it always has.
_CODE_SPAN_RE = re.compile(r"`[^`\n]*`")
# GFM task-list checkbox at the start of a list item ("- [x] ", "* [ ] ").
# Stripped before mention scanning so a checked box's `[x]` marker is not
# mistaken for a `[slug]` reference.
_CHECKBOX_RE = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s?")


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


def _extract_raw_edges(fm: dict, body: str) -> list[RawEdge]:
    raw: list[RawEdge] = []
    seen: set[tuple[str, str]] = set()

    def _add(kind: str, target: str):
        target = target.strip()
        if not target:
            return
        key = (kind, target)
        if key in seen:
            return
        seen.add(key)
        raw.append(RawEdge(kind=kind, raw_target=target))

    # 1. frontmatter keys
    for fm_key, kind in _FM_KEY_TO_KIND.items():
        if fm_key in fm:
            val = fm[fm_key]
            items = val if isinstance(val, list) else [val]
            for item in items:
                if item is not None:
                    _add(kind, str(item))

    # 2. body lines, skipping fenced blocks
    in_fence = False
    typed_lines: set[int] = set()
    for i, line in enumerate(body.splitlines()):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _BODY_REL_RE.match(line)
        if m:
            label = m.group(1).strip().lower()
            kind = _LABEL_TO_KIND[label]
            rest = m.group(2)
            typed_lines.add(i)
            for tok in [t.strip() for t in rest.split(",")]:
                tok = tok.strip().lstrip("[").rstrip("]").strip()
                if tok:
                    _add(kind, tok)

    # 3. mentions (anything bracketed or bare that survived, skipping typed lines + fences)
    in_fence = False
    for i, line in enumerate(body.splitlines()):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or i in typed_lines:
            continue
        line = _CHECKBOX_RE.sub("", line)
        for label, href in _MENTION_MD_LINK_RE.findall(_CODE_SPAN_RE.sub(" ", line)):
            if "://" in href:
                continue
            if href.rsplit("/", 1)[-1][:-3] == label.rsplit("/", 1)[-1]:
                _add("mentions", label)
        for tok in _MENTION_BRACKET_RE.findall(line):
            _add("mentions", tok)
        for tok in _MENTION_BARE_RE.findall(line):
            _add("mentions", tok)

    return raw


def raw_refs(doc: Doc) -> list[RawEdge]:
    """Public: all authored references in a doc (frontmatter relations, typed
    body lines, and mentions), deduped, BEFORE address resolution. parse_world
    discards references that do not resolve to an on-disk doc, so ghost/unresolved
    detection (cortex.query) re-derives them from the doc here."""
    return _extract_raw_edges(doc.frontmatter, doc.body)


def _read_doc(path: Path, id: DocId) -> tuple[Doc, list[RawEdge]]:
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    is_kb = id.kind in ("knowledge", "workbench")
    fallback = id.slug or id.session or id.workspace or "(untitled)"
    if is_kb and fm.get("title"):
        title = str(fm["title"])
    else:
        title = _title_from_body(body, fallback)
    status = fm.get("status") if id.kind == "task" else None
    author = fm.get("author") if is_kb else None
    # Stringify: PyYAML coerces bare dates (updated: 2026-06-01) to datetime.date,
    # and any scalar must be JSON-serializable for the generator payload.
    def _str_field(key: str) -> Optional[str]:
        v = fm.get(key) if is_kb else None
        return None if v is None else str(v)
    doc_type = _str_field("type")
    description = _str_field("description")
    updated = _str_field("updated")
    doc = Doc(id=id, title=title, body=body, frontmatter=fm, rel_path=path,
              edges_out=[], status=status, author=author,
              type=doc_type, description=description, updated=updated)
    raw = _extract_raw_edges(fm, body)
    return doc, raw


def parse_world(workspaces_root: Path, *, include_archive: bool = False) -> World:
    workspaces_root = Path(workspaces_root)
    docs: dict[str, Doc] = {}
    edges: list[Edge] = []
    ghosts: set[str] = set()
    raw_edges: dict[str, list[RawEdge]] = {}

    # Root hub
    root = Doc(id=DocId(kind="root"), title="Your Cortex", body="",
               frontmatter={}, rel_path=None, edges_out=[])
    docs["/"] = root

    if not workspaces_root.is_dir():
        return World(root=root, docs=docs, edges=edges, ghosts=ghosts)

    # Pass 1: discovery + containment
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

        knowledge_dir = ws_dir / "knowledge"
        if knowledge_dir.is_dir():
            for kfile in sorted(knowledge_dir.glob("*.md")):
                if kfile.name.lower() == "index.md":
                    continue
                kid = DocId(kind="knowledge", workspace=ws_slug, slug=kfile.stem)
                doc, raw = _read_doc(kfile, kid)
                docs[kid.canonical()] = doc
                edges.append(Edge(source=ws_id, target=kid, raw_target=kfile.stem,
                                  kind="contains", resolved=True))
                raw_edges[kid.canonical()] = raw

        # Collect (sess_dir, sess_slug, archived) tuples for both live sessions
        # and (optionally) archived ones, then process them with the same body.
        sessions_dir = ws_dir / "sessions"
        session_sources: list[tuple[Path, str, bool]] = []
        if sessions_dir.is_dir():
            for sess_dir in sorted(p for p in sessions_dir.iterdir() if p.is_dir()):
                if sess_dir.name in address.RESERVED_WORDS:
                    continue
                session_sources.append((sess_dir, sess_dir.name, False))
        if include_archive:
            archive_dir = ws_dir / "archive"
            if archive_dir.is_dir():
                for sess_dir in sorted(p for p in archive_dir.iterdir() if p.is_dir()):
                    session_sources.append((sess_dir, sess_dir.name, True))

        for sess_dir, sess_slug, archived in session_sources:
            sess_id = DocId(kind="session", workspace=ws_slug, session=sess_slug)
            if sess_id.canonical() in docs:
                continue  # collision between live and archived; live wins
            summary = sess_dir / "SUMMARY.md"
            if summary.is_file():
                sess_doc, raw = _read_doc(summary, sess_id)
                raw_edges[sess_id.canonical()] = raw
            else:
                sess_doc = Doc(id=sess_id, title=sess_slug, body="", frontmatter={},
                               rel_path=sess_dir, edges_out=[])
            sess_doc.archived = archived
            docs[sess_id.canonical()] = sess_doc
            edges.append(Edge(source=ws_id, target=sess_id, raw_target=sess_slug,
                              kind="contains", resolved=True))

            tasks_dir = sess_dir / "tasks"
            if tasks_dir.is_dir():
                for tfile in sorted(tasks_dir.glob("*.md")):
                    if tfile.name.lower() == "index.md":
                        continue
                    tid = DocId(kind="task", workspace=ws_slug,
                                session=sess_slug, slug=tfile.stem)
                    doc, raw = _read_doc(tfile, tid)
                    doc.archived = archived
                    docs[tid.canonical()] = doc
                    edges.append(Edge(source=sess_id, target=tid,
                                      raw_target=tfile.stem,
                                      kind="contains", resolved=True))
                    raw_edges[tid.canonical()] = raw

            wb_dir = sess_dir / "workbench"
            if wb_dir.is_dir():
                for wfile in sorted(wb_dir.glob("*.md")):
                    if wfile.name.lower() == "index.md":
                        continue
                    wid = DocId(kind="workbench", workspace=ws_slug,
                                session=sess_slug, slug=wfile.stem)
                    doc, raw = _read_doc(wfile, wid)
                    doc.archived = archived
                    docs[wid.canonical()] = doc
                    edges.append(Edge(source=sess_id, target=wid,
                                      raw_target=wfile.stem,
                                      kind="contains", resolved=True))
                    raw_edges[wid.canonical()] = raw

    # Pass 2: resolve raw edges. Unresolved targets and dangling-after-resolution
    # targets are dropped; no ghost docs are synthesized.
    edge_keys: set[tuple[str, str, str]] = {
        (e.source.canonical(), e.target.canonical(), e.kind) for e in edges
    }
    for src_canon, raws in raw_edges.items():
        src_doc = docs[src_canon]
        for raw in raws:
            res = address.resolve(raw.raw_target, referencing=src_doc.id)
            if not res.resolved:
                continue
            tgt = res.doc_id
            if tgt.canonical() not in docs:
                continue
            key = (src_doc.id.canonical(), tgt.canonical(), raw.kind)
            if key in edge_keys:
                continue
            edge_keys.add(key)
            edge = Edge(source=src_doc.id, target=tgt,
                        raw_target=raw.raw_target, kind=raw.kind, resolved=True)
            edges.append(edge)
            src_doc.edges_out.append(edge)

    return World(root=root, docs=docs, edges=edges, ghosts=ghosts)
