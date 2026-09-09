"""Filesystem resolution for the cortex engine: locate the ~/.cortex store, the
target workspace, and the active session. Ports work-kb's resolve_workspace /
resolve_session / find_local_store, including their die-on-ambiguity semantics
(raised here as StoreError, exit code 1)."""
from __future__ import annotations
import re
from pathlib import Path
from typing import NamedTuple


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


class Scope(NamedTuple):
    """What a verb operating over workspaces needs: the root to parse, the
    workspace names to act on, and any note about what the scope left out.

    A three-field tuple rather than a return value plus a lookup, because the
    note is only derivable from the same three inputs the scope came from and
    would otherwise be recomputed per verb."""
    root: Path
    names: list[str]
    notes: list[str]


def _tilde(path: Path, home: Path) -> str:
    """Render a path home-relative when it is under home. `~/.cortex/workspaces`
    is how the docs spell the global store, so a note that says the same thing
    reads as the same place; a long absolute path reads as a different one."""
    try:
        return "~/" + str(Path(path).resolve().relative_to(Path(home).resolve()))
    except ValueError:
        return str(path)


def _all_notes(root: Path, names: list[str], *, home: Path, cwd: Path) -> list[str]:
    """What `--workspace all` did not cover, in words.

    `all` means every workspace in the global store, which is not every store: a
    repo-local `<repo>/.cortex` is deliberately excluded, because
    `kb index --workspace=all --write` derives a cross-workspace brain and a
    per-repo store is not part of anybody's brain (skills/cortex-kb/SKILL.md).

    Excluding it silently is the defect. `names=[]` prints exactly what
    "searched everything, found nothing" prints, and a populated global store
    prints a complete-looking answer over a corpus that omits the store the user
    is standing in. Neither case is fixed by widening the scope; both are fixed
    by the scope saying what it covered."""
    local = find_local_store(Path(cwd), Path(home))
    where = _tilde(root, home)
    if not names:
        if local is not None:
            return [f"--workspace all found no workspaces in the global store "
                    f"({where}), and does not cover the repo-local store at "
                    f"{_tilde(local, home)}; omit --workspace to use that store"]
        return [f"--workspace all found no workspaces in the global "
                f"store ({where})"]
    if local is not None:
        return [f"--workspace all covers the global store ({where}) only; the "
                f"repo-local store at {_tilde(local, home)} was not included. "
                f"Omit --workspace to use that store"]
    return []


def resolve_scope(explicit_ws: str, *, home: Path, cwd: Path) -> Scope:
    """(workspaces root to parse, workspace names to act on, notes to surface).

    The root is the resolved workspace's parent so one expression covers both
    stores: the global `~/.cortex/workspaces`, and a repo-local `<repo>/.cortex`
    whose parent is the repo. Names filter what gets acted on, so the extra
    workspaces a global parse pulls in are only used for link resolution, which
    is what makes a cross-workspace reference resolvable at all.

    Notes are non-fatal and only ever produced by `all`; see `_all_notes`. They
    belong here rather than in a verb because one scoping rule backs three, so a
    per-verb explanation would be the same sentence written three times and kept
    in sync by hand."""
    if explicit_ws == "all":
        root = Path(home) / ".cortex" / "workspaces"
        names = (sorted(p.name for p in root.iterdir() if p.is_dir())
                 if root.is_dir() else [])
        return Scope(root, names, _all_notes(root, names, home=home, cwd=cwd))
    ws_root = resolve_workspace(explicit_ws, home=home, cwd=cwd)
    return Scope(ws_root.parent, [ws_root.name], [])
