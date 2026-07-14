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
import json
import os
import shutil
from pathlib import Path

from cortex import frontmatter as fm
from cortex import kb
from cortex import store
from cortex.errors import CortexError

SENTINEL_NAME = ".inject-enabled"

_DEFAULT_MAX_BYTES = 8192
_TRUNCATE_NOTICE = "... truncated; run 'cortex kb index'"


def _max_bytes() -> int:
    raw = os.environ.get("CORTEX_INJECT_MAX_BYTES", "")
    if raw.isdigit():
        return int(raw)
    return _DEFAULT_MAX_BYTES


_CC_MATCHER = "startup|clear|compact"
_CC_MARK = "inject here --format=claude-code"


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


class Adapter:
    """Per-harness wiring + stdout envelope. Every adapter provides `format`;
    the config methods are filled in per harness."""
    name = ""

    def format(self, block: str) -> str:            # pragma: no cover - overridden
        raise NotImplementedError

    def wire(self, *, home: Path, project_path: Path | None = None) -> bool:      # pragma: no cover - overridden
        raise NotImplementedError

    def unwire(self, *, home: Path, project_path: Path | None = None) -> bool:    # pragma: no cover - overridden
        raise NotImplementedError

    def is_wired(self, *, home: Path, project_path: Path | None = None) -> bool:
        return False


class ClaudeCodeAdapter(Adapter):
    name = "claude-code"

    def format(self, block: str) -> str:
        payload = {"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": block,
        }}
        return json.dumps(payload)

    def _settings_path(self, home: Path, project_path: Path | None) -> Path:
        base = project_path if project_path is not None else home
        return Path(base) / ".claude" / "settings.json"

    def _cortex_command(self) -> str:
        exe = shutil.which("cortex") or str(Path.home() / ".work" / "bin" / "cortex")
        return f"{exe} {_CC_MARK}"

    def _load(self, path: Path) -> dict:
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, OSError):
            return {}

    def _entries(self, data: dict) -> list:
        return data.setdefault("hooks", {}).setdefault("SessionStart", [])

    def _is_ours(self, entry: dict) -> bool:
        return any(_CC_MARK in h.get("command", "")
                   for h in entry.get("hooks", []))

    def wire(self, *, home: Path, project_path: Path | None = None) -> bool:
        path = self._settings_path(home, project_path)
        data = self._load(path)
        entries = self._entries(data)
        if any(self._is_ours(e) for e in entries):
            return False
        entries.append({
            "matcher": _CC_MATCHER,
            "hooks": [{"type": "command", "command": self._cortex_command()}],
        })
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return True

    def unwire(self, *, home: Path, project_path: Path | None = None) -> bool:
        path = self._settings_path(home, project_path)
        if not path.is_file():
            return False
        data = self._load(path)
        entries = self._entries(data)
        kept = [e for e in entries if not self._is_ours(e)]
        if len(kept) == len(entries):
            return False
        data["hooks"]["SessionStart"] = kept
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return True

    def is_wired(self, *, home: Path, project_path: Path | None = None) -> bool:
        data = self._load(self._settings_path(home, project_path))
        entries = data.get("hooks", {}).get("SessionStart", [])
        return any(self._is_ours(e) for e in entries)


ADAPTERS: dict[str, Adapter] = {a.name: a for a in (ClaudeCodeAdapter(),)}


def get_adapter(name: str) -> Adapter:
    try:
        return ADAPTERS[name]
    except KeyError:
        known = ", ".join(sorted(ADAPTERS)) or "(none)"
        raise CortexError(f"unknown harness '{name}'; known: {known}")


def cmd_here(args) -> int:
    try:
        block = render_block(
            home=kb._home(), cwd=Path.cwd(),
            workspace=args.workspace, session=args.session,
            max_n=kb.parse_max(args.max),
        )
    except Exception:
        return 0
    if not block:
        return 0
    if args.format == "text":
        print(block)
    else:
        print(get_adapter(args.format).format(block))
    return 0


def cmd_enable(args) -> int:
    home, cwd = kb._home(), Path.cwd()
    wired_note = ""
    if args.wire_hook:
        get_adapter(args.wire_hook).wire(home=home)
        wired_note = f" hook wired for {args.wire_hook}."
    try:
        ws_root = store.resolve_workspace(args.workspace, home=home, cwd=cwd)
    except store.StoreError:
        if args.wire_hook:
            print(f"no workspace resolved; nothing opted in.{wired_note}")
            return 0
        raise
    _sentinel(ws_root).write_text("on\n", encoding="utf-8")
    print(f"injection enabled for workspace '{ws_root.name}'.{wired_note}")
    return 0


def cmd_disable(args) -> int:
    home, cwd = kb._home(), Path.cwd()
    unwired_note = ""
    if args.unwire_hook:
        get_adapter(args.unwire_hook).unwire(home=home)
        unwired_note = f" hook unwired for {args.unwire_hook}."
    ws_root = store.resolve_workspace(args.workspace, home=home, cwd=cwd)
    s = _sentinel(ws_root)
    if s.is_file():
        s.unlink()
    print(f"injection disabled for workspace '{ws_root.name}'.{unwired_note}")
    return 0


def cmd_status(args) -> int:
    home, cwd = kb._home(), Path.cwd()
    ws_root = store.resolve_workspace(args.workspace, home=home, cwd=cwd)
    state = "enabled" if _sentinel(ws_root).is_file() else "disabled"
    print(f"workspace '{ws_root.name}': injection {state}")
    wired = [name for name, a in sorted(ADAPTERS.items()) if a.is_wired(home=home)]
    print("wired hooks: " + (", ".join(wired) if wired else "(none)"))
    return 0
