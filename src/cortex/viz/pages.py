"""The markdown half of the site: mirror the store's .md files into out_dir and
emit one index.md per level.

Nothing here knows about the graph payload; the only shared vocabulary is
`layout`.
"""
from __future__ import annotations
import shutil
from pathlib import Path

from cortex import model
from cortex.model import World, Doc, is_reserved
from .layout import children_of, content_path, doc_out_path, write_out

_VENDOR_SRC = Path(__file__).parent / "templates" / "vendor"


def stage_vendor(out_dir: Path) -> None:
    vendor_out = out_dir / "vendor"
    if vendor_out.exists():
        shutil.rmtree(vendor_out)
    shutil.copytree(_VENDOR_SRC, vendor_out)


def copy_markdown(world: World, out_dir: Path) -> None:
    for doc in world.docs.values():
        if doc.ghost or doc.rel_path is None or doc.id.kind in ("root", "workspace"):
            continue
        # Sessions without a SUMMARY.md keep rel_path = session dir; skip those.
        if not doc.rel_path.is_file():
            continue
        dest = doc_out_path(doc, out_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(doc.rel_path, dest)


def copy_supplementary_md(world: World, out_dir: Path) -> None:
    """Mirror any unindexed .md files inside session and knowledge directories so
    relative links in author-authored markdown resolve. Indexed docs (SUMMARY,
    tasks/*.md, workbench/*.md, knowledge/*.md) are already copied by
    copy_markdown; this pass picks up siblings like research/notes.md and
    dated audit files."""
    for doc in world.docs.values():
        if doc.id.kind != "session" or doc.rel_path is None:
            continue
        sess_dir = doc.rel_path if doc.rel_path.is_dir() else doc.rel_path.parent
        if not sess_dir.is_dir():
            continue
        out_sess = (out_dir / "workspaces" / doc.id.workspace
                    / "sessions" / doc.id.session)
        for md in sess_dir.rglob("*.md"):
            rel = md.relative_to(sess_dir)
            # Skip already-indexed flat children (SUMMARY, tasks/*.md, workbench/*.md).
            if rel.name == "SUMMARY.md" and len(rel.parts) == 1:
                continue
            if rel.parts[0] in ("tasks", "workbench") and len(rel.parts) == 2:
                continue
            if is_reserved(rel.name):
                continue
            dest = out_sess / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(md, dest)

    for doc in world.docs.values():
        if doc.id.kind != "workspace" or doc.rel_path is None:
            continue
        k_dir = doc.rel_path / "knowledge"
        if not k_dir.is_dir():
            continue
        out_k = out_dir / "workspaces" / doc.id.workspace / "knowledge"
        for md in k_dir.rglob("*.md"):
            rel = md.relative_to(k_dir)
            if is_reserved(rel.name):
                continue
            if len(rel.parts) == 1:
                continue  # already copied by copy_markdown
            dest = out_k / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(md, dest)


def _emit_root_index(world: World, out_dir: Path) -> None:
    workspaces = children_of(world, "/", "workspace")
    lines = ["# Your Cortex", "", "## Workspaces", ""]
    for ws in workspaces:
        lines.append(f"- [{ws.id.workspace}](workspaces/{ws.id.workspace}/index.html)")

    # The brain: a derived cross-workspace knowledge dictionary, grouped by type.
    # Grouping/ordering and the description fallback are shared with the
    # `cortex kb index --workspace=all` CLI (cortex.model) so the two brain
    # surfaces stay consistent.
    kdocs = [d for d in world.docs.values()
             if d.id.kind == "knowledge" and not d.ghost]
    lines += ["", f"## Knowledge ({len(kdocs)})", ""]
    if not kdocs:
        lines.append("_No knowledge docs yet._")
    else:
        for display_ty, group in model.group_by_type(kdocs, lambda d: d.type):
            lines += ["", f"### {display_ty if display_ty else '(untyped)'}", ""]
            for d in sorted(group,
                            key=lambda d: (d.id.slug or "", d.id.workspace or "")):
                href = content_path(d.id) or ""
                # Raw frontmatter title (not the slug-fallback Doc.title) so the
                # description fallback matches the CLI's `kb index` exactly.
                raw_title = d.frontmatter.get("title") if d.frontmatter else None
                desc = model.format_description(d.description, raw_title)
                lines.append(f"- [{d.id.slug} ({d.id.workspace})]({href}) - {desc}")
    lines.append("")
    write_out(out_dir / "index.md", "\n".join(lines))


def _emit_workspace_index(world: World, ws: Doc, out_dir: Path) -> None:
    ws_dir = out_dir / "workspaces" / ws.id.workspace
    ws_dir.mkdir(parents=True, exist_ok=True)
    sessions = children_of(world, ws.id.canonical(), "session")
    knowledge_docs = children_of(world, ws.id.canonical(), "knowledge")
    lines = [f"# {ws.id.workspace}", "",
             "[<- Dashboard](../../index.html)", "",
             f"## Sessions ({len(sessions)})", ""]
    for s in sessions:
        lines.append(f"- [{s.id.session}](sessions/{s.id.session}/index.html)")
    lines.extend(["", f"## Knowledge ({len(knowledge_docs)})", "",
                  "[Open knowledge folder](knowledge/index.md)", ""])
    write_out(ws_dir / "index.md", "\n".join(lines))


def _emit_knowledge_index(world: World, ws: Doc, out_dir: Path) -> None:
    k_dir = out_dir / "workspaces" / ws.id.workspace / "knowledge"
    k_dir.mkdir(parents=True, exist_ok=True)
    docs = children_of(world, ws.id.canonical(), "knowledge")
    lines = [f"# {ws.id.workspace} / knowledge", "",
             "[<- Workspace](../index.html)", "",
             f"## Knowledge docs ({len(docs)})", ""]
    if not docs:
        lines.append("_No knowledge docs yet._")
    else:
        for d in docs:
            lines.append(f"- [{d.id.slug}]({d.id.slug}.md)")
    write_out(k_dir / "index.md", "\n".join(lines))


def _emit_session_index(world: World, sess: Doc, out_dir: Path) -> None:
    sess_dir = out_dir / "workspaces" / sess.id.workspace / "sessions" / sess.id.session
    sess_dir.mkdir(parents=True, exist_ok=True)
    parent_canon = sess.id.canonical()
    tasks = children_of(world, parent_canon, "task")
    workbenches = children_of(world, parent_canon, "workbench")
    lines = [f"# {sess.id.session}", "",
             f"_In workspace `{sess.id.workspace}`_", "",
             "[<- Workspace](../../index.html)", "",
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
    write_out(sess_dir / "index.md", "\n".join(lines))


def _emit_workbench_index(world: World, sess: Doc, out_dir: Path) -> None:
    wb_dir = out_dir / "workspaces" / sess.id.workspace / "sessions" / sess.id.session / "workbench"
    wb_dir.mkdir(parents=True, exist_ok=True)
    docs = children_of(world, sess.id.canonical(), "workbench")
    lines = [f"# {sess.id.session} / workbench", "",
             "[<- Session](../index.html)", "",
             f"## Workbench docs ({len(docs)})", ""]
    if not docs:
        lines.append("_No workbench docs yet._")
    else:
        for d in docs:
            lines.append(f"- [{d.id.slug}]({d.id.slug}.md)")
    write_out(wb_dir / "index.md", "\n".join(lines))


def _emit_tasks_index(world: World, sess: Doc, out_dir: Path) -> None:
    tasks_dir = out_dir / "workspaces" / sess.id.workspace / "sessions" / sess.id.session / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    docs = children_of(world, sess.id.canonical(), "task")
    lines = [f"# {sess.id.session} / tasks", "",
             "[<- Session](../index.html)", "",
             f"## Tasks ({len(docs)})", ""]
    if not docs:
        lines.append("_No tasks yet._")
    else:
        for d in docs:
            lines.append(f"- [{d.id.slug}]({d.id.slug}.md) - {d.status or '(unstated)'}")
    write_out(tasks_dir / "index.md", "\n".join(lines))


def emit_all_indices(world: World, out_dir: Path) -> None:
    _emit_root_index(world, out_dir)
    for ws in children_of(world, "/", "workspace"):
        _emit_workspace_index(world, ws, out_dir)
        _emit_knowledge_index(world, ws, out_dir)
        for sess in children_of(world, ws.id.canonical(), "session"):
            _emit_session_index(world, sess, out_dir)
            _emit_workbench_index(world, sess, out_dir)
            _emit_tasks_index(world, sess, out_dir)
