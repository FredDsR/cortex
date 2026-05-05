"""Walk a `~/.work/workspaces/<slug>/` tree and produce a Workspace model."""
from pathlib import Path
import re

from .model import (
    Workspace, Session, Task,
    STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_BLOCKED, STATUS_RESOLVED, STATUS_UNKNOWN,
)


_FRONTMATTER_DELIM = "---\n"
_INLINE_FIELD_RE = re.compile(r"^\*\*([^*:]+):\*\*\s*(.*)$")
_HEADING_RE = re.compile(r"^###\s+(.+?)\s*$")
_LINK_TASK_RE = re.compile(r"\[[^\]]+\]\(tasks/([a-z0-9-]+)\.md\)")
_BARE_TASK_RE = re.compile(r"\b(task-[a-z0-9-]+)\b")
_BLOCKED_BY_RE = re.compile(r"^\s*\*?\*?\s*Blocked by:?\s*\*?\*?\s*(.+)$", re.IGNORECASE)

_HEADING_TO_STATUS = {
    "in progress": STATUS_IN_PROGRESS,
    "open": STATUS_OPEN,
    "blocked": STATUS_BLOCKED,
    "resolved": STATUS_RESOLVED,
}


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


def _parse_inline_fields(body: str) -> dict:
    fields: dict = {}
    for line in body.splitlines():
        m = _INLINE_FIELD_RE.match(line)
        if m:
            key = m.group(1).strip()
            if key not in fields:
                fields[key] = m.group(2).strip()
    return fields


def _parse_blocked_by(body: str) -> list:
    out: list = []
    for line in body.splitlines():
        m = _BLOCKED_BY_RE.match(line.strip())
        if not m:
            continue
        rest = m.group(1)
        for slug in _LINK_TASK_RE.findall(rest):
            if slug not in out:
                out.append(slug)
        for slug in _BARE_TASK_RE.findall(rest):
            if slug not in out:
                out.append(slug)
    return out


def _parse_summary_status_map(summary_text: str) -> dict:
    status_map: dict = {}
    current: str | None = None
    for line in summary_text.splitlines():
        h = _HEADING_RE.match(line)
        if h:
            current = _HEADING_TO_STATUS.get(h.group(1).strip().lower())
            continue
        if current is None:
            continue
        for slug in _LINK_TASK_RE.findall(line):
            status_map[slug] = current
        for slug in _BARE_TASK_RE.findall(line):
            status_map.setdefault(slug, current)
    return status_map


def _fallback_status_from_inline(value: str) -> str:
    v = value.lower()
    if "resolved" in v or "closed" in v:
        return STATUS_RESOLVED
    if "in progress" in v:
        return STATUS_IN_PROGRESS
    if "blocked" in v:
        return STATUS_BLOCKED
    if v.strip():
        return STATUS_OPEN
    return STATUS_UNKNOWN


def _count_active(dir_path: Path) -> int:
    return sum(1 for f in dir_path.iterdir() if f.name.startswith(".active."))


def _read_active_session_slugs(ws_dir: Path) -> list:
    slugs: list = []
    for f in sorted(ws_dir.iterdir()):
        if not f.name.startswith(".active."):
            continue
        try:
            text = f.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            slugs.append(text)
    return slugs


def _parse_session(sess_dir: Path, slug: str | None = None) -> Session:
    sess = Session(slug=slug or sess_dir.name)
    summary_path = sess_dir / "SUMMARY.md"
    if summary_path.exists():
        raw = summary_path.read_text(encoding="utf-8")
        sess.summary_meta, sess.summary_text = _split_frontmatter(raw)
    sess.active_agent_count = _count_active(sess_dir)
    status_map = _parse_summary_status_map(sess.summary_text)
    tasks_dir = sess_dir / "tasks"
    if tasks_dir.exists():
        for task_path in sorted(tasks_dir.glob("*.md")):
            body = task_path.read_text(encoding="utf-8")
            t_slug = task_path.stem
            inline = _parse_inline_fields(body)
            status = status_map.get(t_slug)
            if not status:
                status = _fallback_status_from_inline(inline.get("Status", ""))
            sess.tasks.append(Task(
                slug=t_slug,
                body=body,
                inline_fields=inline,
                blocked_by=_parse_blocked_by(body),
                status=status,
            ))
    return sess


def parse_workspace(workspaces_root: Path, slug: str) -> Workspace:
    ws_dir = workspaces_root / slug
    if not ws_dir.is_dir():
        raise FileNotFoundError(f"workspace not found: {ws_dir}")
    ws = Workspace(slug=slug, has_meta=(ws_dir / ".meta").exists())
    ws.active_session_slugs = _read_active_session_slugs(ws_dir)
    sessions_dir = ws_dir / "sessions"
    if sessions_dir.exists():
        for sd in sorted(p for p in sessions_dir.iterdir() if p.is_dir()):
            ws.sessions.append(_parse_session(sd))
    return ws
