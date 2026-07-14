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
from pathlib import Path

from cortex import frontmatter as fm
from cortex import kb
from cortex import store

SENTINEL_NAME = ".inject-enabled"


def _sentinel(ws_root: Path) -> Path:
    return ws_root / SENTINEL_NAME


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

    attrs = f' workspace="{ws_root.name}"' + (f' session="{sess}"' if sess else "")
    body = "\n".join(lines)
    return f"<tracking-work-index{attrs}>\n{body}\n</tracking-work-index>"


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
