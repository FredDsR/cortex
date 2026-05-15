"""Static-site generator: World -> filesystem under out_dir."""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

from .model import World, Doc, DocId

_PACKAGE_DIR = Path(__file__).parent.parent
_VENDOR_SRC = _PACKAGE_DIR / "templates" / "vendor"


def _stage_vendor(out_dir: Path) -> None:
    vendor_out = out_dir / "vendor"
    if vendor_out.exists():
        shutil.rmtree(vendor_out)
    shutil.copytree(_VENDOR_SRC, vendor_out)


def _doc_out_path(doc: Doc, out_dir: Path) -> Path:
    cid = doc.id
    base = out_dir / "workspaces" / cid.workspace if cid.workspace else out_dir
    if cid.kind == "workspace":
        return base / "index.md"
    if cid.kind == "session":
        return base / "sessions" / cid.session / "SUMMARY.md"
    if cid.kind == "task":
        return base / "sessions" / cid.session / "tasks" / f"{cid.slug}.md"
    if cid.kind == "memory":
        return base / "memory" / f"{cid.slug}.md"
    if cid.kind == "workbench":
        return base / "sessions" / cid.session / "workbench" / f"{cid.slug}.md"
    if cid.kind == "root":
        return out_dir / "index.md"
    raise ValueError(f"unknown doc kind: {cid.kind!r}")


def _copy_markdown(world: World, out_dir: Path) -> None:
    for doc in world.docs.values():
        if doc.ghost or doc.rel_path is None or doc.id.kind in ("root", "workspace"):
            continue
        # Sessions without a SUMMARY.md keep rel_path = session dir; skip those.
        if not doc.rel_path.is_file():
            continue
        dest = _doc_out_path(doc, out_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(doc.rel_path, dest)


def _children_of(world: World, parent_canon: str, kind: str) -> list[Doc]:
    out = []
    for doc in world.docs.values():
        if doc.ghost or doc.id.kind != kind:
            continue
        # Filter by parent
        if kind == "workspace" and parent_canon == "/":
            out.append(doc)
        elif kind == "session" and doc.id.workspace and f"{doc.id.workspace}/" == parent_canon:
            out.append(doc)
        elif kind == "memory" and doc.id.workspace and f"{doc.id.workspace}/" == parent_canon:
            out.append(doc)
        elif kind == "task" and doc.id.workspace and doc.id.session and \
             f"{doc.id.workspace}/{doc.id.session}/" == parent_canon:
            out.append(doc)
        elif kind == "workbench" and doc.id.workspace and doc.id.session and \
             f"{doc.id.workspace}/{doc.id.session}/" == parent_canon:
            out.append(doc)
    return sorted(out, key=lambda d: d.id.canonical())


def _emit_root_index(world: World, out_dir: Path) -> None:
    workspaces = _children_of(world, "/", "workspace")
    lines = ["# Fred's Work Tracking", "", "## Workspaces", ""]
    for ws in workspaces:
        lines.append(f"- [{ws.id.workspace}](workspaces/{ws.id.workspace}/index.md)")
    lines.append("")
    (out_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_workspace_index(world: World, ws: Doc, out_dir: Path) -> None:
    ws_dir = out_dir / "workspaces" / ws.id.workspace
    ws_dir.mkdir(parents=True, exist_ok=True)
    sessions = _children_of(world, ws.id.canonical(), "session")
    memories = _children_of(world, ws.id.canonical(), "memory")
    lines = [f"# {ws.id.workspace}", "",
             "[<- Dashboard](../../index.md)", "",
             f"## Sessions ({len(sessions)})", ""]
    for s in sessions:
        lines.append(f"- [{s.id.session}](sessions/{s.id.session}/index.md)")
    lines.extend(["", f"## Memory ({len(memories)})", "",
                  "[Open memory folder](memory/index.md)", ""])
    (ws_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_memory_index(world: World, ws: Doc, out_dir: Path) -> None:
    mem_dir = out_dir / "workspaces" / ws.id.workspace / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    docs = _children_of(world, ws.id.canonical(), "memory")
    lines = [f"# {ws.id.workspace} / memory", "",
             "[<- Workspace](../index.md)", "",
             f"## Memory docs ({len(docs)})", ""]
    if not docs:
        lines.append("_No memory docs yet._")
    else:
        for d in docs:
            lines.append(f"- [{d.id.slug}]({d.id.slug}.md)")
    (mem_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_session_index(world: World, sess: Doc, out_dir: Path) -> None:
    sess_dir = out_dir / "workspaces" / sess.id.workspace / "sessions" / sess.id.session
    sess_dir.mkdir(parents=True, exist_ok=True)
    parent_canon = sess.id.canonical()
    tasks = _children_of(world, parent_canon, "task")
    workbenches = _children_of(world, parent_canon, "workbench")
    lines = [f"# {sess.id.session}", "",
             f"_In workspace `{sess.id.workspace}`_", "",
             "[<- Workspace](../../index.md)", "",
             f"## Tasks ({len(tasks)})", ""]
    if not tasks:
        lines.append("_No tasks yet._")
    else:
        for t in tasks:
            status = t.status or "(unstated)"
            lines.append(f"- [{t.id.slug}](tasks/{t.id.slug}.md) - {status}")
    lines.extend(["", f"## Workbench ({len(workbenches)})", ""])
    if not workbenches:
        lines.append("_No workbench docs yet._")
    else:
        for w in workbenches:
            lines.append(f"- [{w.id.slug}](workbench/{w.id.slug}.md)")
    if sess.body:
        excerpt = sess.body.strip()[:400]
        lines.extend(["", "## Summary excerpt", "", excerpt])
    (sess_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_workbench_index(world: World, sess: Doc, out_dir: Path) -> None:
    wb_dir = out_dir / "workspaces" / sess.id.workspace / "sessions" / sess.id.session / "workbench"
    wb_dir.mkdir(parents=True, exist_ok=True)
    docs = _children_of(world, sess.id.canonical(), "workbench")
    lines = [f"# {sess.id.session} / workbench", "",
             "[<- Session](../index.md)", "",
             f"## Workbench docs ({len(docs)})", ""]
    if not docs:
        lines.append("_No workbench docs yet._")
    else:
        for d in docs:
            lines.append(f"- [{d.id.slug}]({d.id.slug}.md)")
    (wb_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_tasks_index(world: World, sess: Doc, out_dir: Path) -> None:
    tasks_dir = out_dir / "workspaces" / sess.id.workspace / "sessions" / sess.id.session / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    docs = _children_of(world, sess.id.canonical(), "task")
    lines = [f"# {sess.id.session} / tasks", "",
             "[<- Session](../index.md)", "",
             f"## Tasks ({len(docs)})", ""]
    if not docs:
        lines.append("_No tasks yet._")
    else:
        for d in docs:
            lines.append(f"- [{d.id.slug}]({d.id.slug}.md) - {d.status or '(unstated)'}")
    (tasks_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _emit_all_indices(world: World, out_dir: Path) -> None:
    _emit_root_index(world, out_dir)
    for ws in _children_of(world, "/", "workspace"):
        _emit_workspace_index(world, ws, out_dir)
        _emit_memory_index(world, ws, out_dir)
        for sess in _children_of(world, ws.id.canonical(), "session"):
            _emit_session_index(world, sess, out_dir)
            _emit_workbench_index(world, sess, out_dir)
            _emit_tasks_index(world, sess, out_dir)


def build(world: World, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _stage_vendor(out_dir)
    _copy_markdown(world, out_dir)
    _emit_all_indices(world, out_dir)
