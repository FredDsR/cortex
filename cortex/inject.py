"""cortex inject: strictly opt-in, off-by-default session-start injection.

Three independent pieces:
  * render_block / cmd_here  -- the harness-agnostic renderer (this file)
  * a per-workspace sentinel -- <ws_root>/.inject-enabled (the opt-in toggle)
  * an adapter registry      -- per-harness wiring + stdout envelope

`cortex inject here` never errors to the user: any unresolved gate or exception
yields exit 0 with empty stdout. See
docs/superpowers/specs/2026-07-14-optin-sessionstart-inject-design.md.
"""
from __future__ import annotations
import os
from pathlib import Path

from cortex import frontmatter as fm
from cortex import kb
from cortex import store

SENTINEL_NAME = ".inject-enabled"

_DEFAULT_MAX_BYTES = 8192
_TRUNCATE_NOTICE = "... truncated; run 'cortex kb index'"


def _max_bytes() -> int:
    raw = os.environ.get("CORTEX_INJECT_MAX_BYTES", "")
    if raw.isdigit():
        return int(raw)
    return _DEFAULT_MAX_BYTES


def _sentinel(ws_root: Path) -> Path:
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
    if not _sentinel(ws_root).is_file():
        return ""

    sess = ""
    try:
        sess = store.resolve_session(ws_root, session)
    except store.StoreError:
        sess = ""

    lines: list[str] = []
    lines.append("## knowledge")
    lines += kb._render_section(ws_root / "knowledge", max_n)
    if sess:
        wdir = ws_root / "sessions" / sess / "workbench"
        lines.append(f"## workbench ({sess})")
        lines += kb._render_section(wdir, max_n)
        tasks = _render_tasks(ws_root / "sessions" / sess / "tasks", max_n)
        if tasks:
            lines.append("## open tasks")
            lines += tasks

    attrs = f' workspace="{ws_root.name}"' + (f' session="{sess}"' if sess else "")
    open_tag = f"<tracking-work-index{attrs}>"
    close_tag = "</tracking-work-index>"

    ceiling = _max_bytes()
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
        kept.append(_TRUNCATE_NOTICE)
    body = "\n".join(kept)
    return f"{open_tag}\n{body}\n{close_tag}"


def cmd_here(args) -> int:
    try:
        block = render_block(
            home=kb._home(), cwd=Path.cwd(),
            workspace=args.workspace, session=args.session,
            max_n=kb.parse_max(args.max),
        )
    except Exception:
        return 0
    if block:
        print(block)
    return 0
