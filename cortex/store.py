"""Filesystem resolution for the cortex engine: locate the ~/.cortex store, the
target workspace, and the active session. Ports work-kb's resolve_workspace /
resolve_session / find_local_store, including their die-on-ambiguity semantics
(raised here as StoreError, exit code 1)."""
from __future__ import annotations
import re
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


def _meta_cwd(ws_root: Path) -> str | None:
    """Read the `cwd:` field from a workspace's .meta, or None. Mirrors the bash
    resolver's `awk -F': ' '$1=="cwd"{print $2}' | head -n1`: first match wins."""
    try:
        text = (ws_root / ".meta").read_text()
    except OSError:
        return None
    for line in text.splitlines():
        key, sep, value = line.partition(": ")
        if sep and key == "cwd":
            return value
    return None


# Separators (both flavours), NUL and other control bytes. A newline matters on
# its own: `.active.*` pointers are one session per line, so a name holding one
# would round-trip as two sessions.
_BAD_IN_NAME = re.compile(r"[/\\\x00-\x1f]")


def _validate_name(kind: str, name: str) -> None:
    """A workspace or session token is agent-supplied and gets joined onto the
    store root, so it must be one plain path segment. Rejects `.` and `..`,
    anything holding a separator or a control byte, and absolute paths -- which
    matter most, since `root / "/etc"` is `/etc`.

    Deliberately not an allowlist of "slug-shaped" characters: slugs come from
    `basename "$cwd"` (see skills/cortex-tracking/scripts/resolve_workspace.sh),
    so a real workspace can legitimately be named `My Project`, `_scratch` or
    `.dotfiles`. Every name a store realistically holds stays addressable; only
    what can leave the segment is refused."""
    if name in (".", "..") or _BAD_IN_NAME.search(name) or Path(name).is_absolute():
        raise StoreError(
            f"invalid {kind} name: {name!r} "
            f"(must be a single path segment, not '.' or '..')")


def _assert_under(root: Path, path: Path, kind: str, name: str) -> None:
    """Second, independent gate: the target must resolve to a direct child of
    `root`. Catches what the name check cannot, namely an entry under the
    store that is a symlink pointing outside it. Same containment intent as
    cortex/viz/edit_backend.py::source_path_for, tightened to a direct child
    because the store layout has no nesting below the root."""
    if path.resolve().parent != root.resolve():
        raise StoreError(f"{kind} '{name}' escapes the store root")


def resolve_workspace(explicit_ws: str, *, home: Path, cwd: Path) -> Path:
    home = Path(home)
    root = home / ".cortex" / "workspaces"
    if explicit_ws:
        _validate_name("workspace", explicit_ws)
        ws = root / explicit_ws
        _assert_under(root, ws, "workspace", explicit_ws)
        if not ws.is_dir():
            raise StoreError(f"workspace '{explicit_ws}' not found")
        return ws
    local = find_local_store(cwd, home)
    if local is not None:
        return local
    # Step 2 of the bash resolver: an exact .meta cwd match. Without this, a cwd
    # that names a workspace unambiguously still lost to the active-pointer scan
    # below, which dies whenever any two workspaces hold stale .active.* files.
    target = Path(cwd).resolve()
    if root.is_dir():
        for ws in sorted(p for p in root.iterdir() if p.is_dir()):
            mcwd = _meta_cwd(ws)
            if mcwd and Path(mcwd).resolve() == target:
                return ws
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
    sessions = ws_root / "sessions"
    if explicit_sess:
        _validate_name("session", explicit_sess)
        sess_dir = sessions / explicit_sess
        _assert_under(sessions, sess_dir, "session", explicit_sess)
        if not sess_dir.is_dir():
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
    # The pointer file is written by an agent too, and callers join the returned
    # name onto `<ws>/sessions/`, so it gets the same two gates as a token.
    sess = unique[0]
    if not sess:                        # a blank pointer names no session
        raise StoreError(f"no active session in '{ws_root.name}'; pass --session <sess>")
    _validate_name("session", sess)
    _assert_under(sessions, sessions / sess, "session", sess)
    return sess
