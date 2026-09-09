"""The injection payload, and the sentinel that gates it.

Harness-agnostic: this builds the `<cortex-index>` block and knows nothing
about how any particular harness wants it delivered, which is `adapters.py`.
Prints nothing.

The byte ceiling is enforced here rather than by the caller, because a block
truncated after the fact would lose its closing tag.
"""
from __future__ import annotations
import os
from pathlib import Path

from cortex import frontmatter as fm
from cortex import store
from cortex.kb import index as kb_index

SENTINEL_NAME = ".inject-enabled"

_DEFAULT_MAX_BYTES = 8192
_TRUNCATE_NOTICE = "... truncated; run 'cortex kb index'"


def _max_bytes() -> int:
    raw = os.environ.get("CORTEX_INJECT_MAX_BYTES", "")
    if raw.isdigit():
        return int(raw)
    return _DEFAULT_MAX_BYTES


def sentinel(ws_root: Path) -> Path:
    return ws_root / SENTINEL_NAME


# Order: In Progress before Open; unmatched statuses are dropped.
_TASK_ORDER = {"In Progress": 0, "Open": 1}


def _render_tasks(tasks_dir: Path, max_n: int) -> list[str]:
    """One line per open/in-progress task `[<status>] <slug> - <title>`, ordered
    In Progress then Open then slug, capped at max_n. Title is the first H1 or the
    slug. Mirrors manifest.sh's status/title parsing."""
    if not tasks_dir.is_dir():
        return []
    rows = []
    for f in sorted(tasks_dir.glob("*.md")):
        block, body = fm.split(f.read_text(encoding="utf-8"))
        status = fm.read_field(block or "", "status")
        if status not in _TASK_ORDER:
            continue
        title = f.stem
        for line in (body or "").splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        rows.append((_TASK_ORDER[status], f.stem,
                     f"[{status}] {f.stem} - {title}"))
    if not rows:
        return []
    total = len(rows)
    rows.sort(key=lambda r: (r[0], r[1]))
    out = [r[2] for r in rows[:max_n]]
    if total > max_n:
        out.append(f"... {total - max_n} more (raise --max)")
    return out


def render_block(*, home: Path, cwd: Path, workspace: str, session: str,
                 max_n: int) -> str:
    """Return the injection block, or "" when no workspace resolves or the
    workspace is not opted in."""
    try:
        ws_root = store.resolve_workspace(workspace, home=home, cwd=cwd)
    except store.StoreError:
        return ""
    if not sentinel(ws_root).is_file():
        return ""

    sess = ""
    try:
        sess = store.resolve_session(ws_root, session)
    except store.StoreError:
        sess = ""

    lines: list[str] = []
    lines.append("## knowledge")
    lines += kb_index.render_section(ws_root / "knowledge", max_n)
    if sess:
        wdir = ws_root / "sessions" / sess / "workbench"
        lines.append(f"## workbench ({sess})")
        lines += kb_index.render_section(wdir, max_n)
        tasks = _render_tasks(ws_root / "sessions" / sess / "tasks", max_n)
        if tasks:
            lines.append("## open tasks")
            lines += tasks

    attrs = f' workspace="{ws_root.name}"' + (f' session="{sess}"' if sess else "")
    open_tag = f"<cortex-index{attrs}>"
    close_tag = "</cortex-index>"

    ceiling = _max_bytes()
    notice_cost = len((_TRUNCATE_NOTICE + "\n").encode("utf-8"))
    kept: list[str] = []
    used = len((open_tag + "\n" + close_tag).encode("utf-8"))
    truncated = False
    for ln in lines:
        cost = len((ln + "\n").encode("utf-8"))
        if used + cost > ceiling and kept:
            truncated = True
            break
        kept.append(ln)
        used += cost
    if truncated:
        # Reserve room for the notice inside the ceiling: drop kept lines until
        # the notice fits, so the final block honors CORTEX_INJECT_MAX_BYTES.
        while kept and used + notice_cost > ceiling:
            used -= len((kept.pop() + "\n").encode("utf-8"))
        kept.append(_TRUNCATE_NOTICE)
    body = "\n".join(kept)
    return f"{open_tag}\n{body}\n{close_tag}"

