"""Walk a `~/.work/workspaces/<slug>/` tree and produce a Workspace model."""
from pathlib import Path

from .model import Workspace, Session, Task, STATUS_UNKNOWN


_FRONTMATTER_DELIM = "---\n"


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith(_FRONTMATTER_DELIM):
        return {}, text
    end = text.find("\n" + _FRONTMATTER_DELIM, len(_FRONTMATTER_DELIM))
    if end == -1:
        return {}, text
    fm_block = text[len(_FRONTMATTER_DELIM):end]
    body = text[end + 1 + len(_FRONTMATTER_DELIM):]
    meta: dict = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body


def _parse_session(sess_dir: Path, slug: str | None = None) -> Session:
    sess = Session(slug=slug or sess_dir.name)
    summary_path = sess_dir / "SUMMARY.md"
    if summary_path.exists():
        raw = summary_path.read_text(encoding="utf-8")
        sess.summary_meta, sess.summary_text = _split_frontmatter(raw)
    tasks_dir = sess_dir / "tasks"
    if tasks_dir.exists():
        for task_path in sorted(tasks_dir.glob("*.md")):
            body = task_path.read_text(encoding="utf-8")
            sess.tasks.append(Task(slug=task_path.stem, body=body, status=STATUS_UNKNOWN))
    return sess


def parse_workspace(workspaces_root: Path, slug: str) -> Workspace:
    ws_dir = workspaces_root / slug
    if not ws_dir.is_dir():
        raise FileNotFoundError(f"workspace not found: {ws_dir}")
    ws = Workspace(slug=slug, has_meta=(ws_dir / ".meta").exists())
    sessions_dir = ws_dir / "sessions"
    if sessions_dir.exists():
        for sd in sorted(p for p in sessions_dir.iterdir() if p.is_dir()):
            ws.sessions.append(_parse_session(sd))
    return ws
