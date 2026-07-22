"""Filesystem resolution for the cortex engine: locate the ~/.cortex store, the
target workspace, and the active session. Ports work-kb's resolve_workspace /
resolve_session / find_local_store, including their die-on-ambiguity semantics
(raised here as StoreError, exit code 1)."""
from __future__ import annotations
from pathlib import Path


class StoreError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


def find_local_store(cwd: Path, home: Path) -> Path | None:
    """Walk up from cwd (only within home) for a `.cortex/` dir. Returns None if
    cwd is not inside home or none is found."""
    cwd = Path(cwd).resolve()
    home = Path(home).resolve()
    if home not in cwd.parents and cwd != home:
        return None
    d = cwd
    while d != d.parent and d != home:
        candidate = d / ".cortex"
        if candidate.is_dir():
            return candidate
        d = d.parent
    return None


def _active_targets(ws_root: Path) -> list[str]:
    # `$(cat)` in bash strips only trailing newlines (not surrounding spaces,
    # and does not split embedded newlines into separate entries).
    out = []
    for f in sorted(ws_root.glob(".active.*")):
        try:
            out.append(f.read_text().rstrip("\n"))
        except OSError:
            pass
    return out


def resolve_workspace(explicit_ws: str, *, home: Path, cwd: Path) -> Path:
    home = Path(home)
    if explicit_ws:
        ws = home / ".cortex" / "workspaces" / explicit_ws
        if not ws.is_dir():
            raise StoreError(f"workspace '{explicit_ws}' not found")
        return ws
    local = find_local_store(cwd, home)
    if local is not None:
        return local
    root = home / ".cortex" / "workspaces"
    matches = []
    if root.is_dir():
        for ws in sorted(p for p in root.iterdir() if p.is_dir()):
            if any(ws.glob(".active.*")):
                matches.append(ws)
    if not matches:
        raise StoreError("no workspace context; pass --workspace <ws>")
    if len(matches) > 1:
        names = " ".join(p.name for p in matches)
        raise StoreError(f"multiple active workspaces ({names}); pass --workspace <ws>")
    return matches[0]


def resolve_session(ws_root: Path, explicit_sess: str) -> str:
    ws_root = Path(ws_root)
    if explicit_sess:
        if not (ws_root / "sessions" / explicit_sess).is_dir():
            raise StoreError(
                f"session '{explicit_sess}' not found in workspace '{ws_root.name}'")
        return explicit_sess
    targets = _active_targets(ws_root)
    if not targets:
        raise StoreError(f"no active session in '{ws_root.name}'; pass --session <sess>")
    # Bash counts UNIQUE LINES across all pointer contents (printf '%s\n' ... |
    # sort -u | wc -l), so a multi-line pointer is treated as multiple sessions.
    lines = [ln for t in targets for ln in t.split("\n")]
    unique = sorted(set(lines))
    if len(unique) != 1:
        raise StoreError(f"multiple sessions active in '{ws_root.name}'; pass --session <sess>")
    return unique[0]
