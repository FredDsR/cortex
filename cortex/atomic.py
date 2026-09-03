"""Crash-safe file writes.

Every file write cortex's Python performs into `~/.cortex` or the harness
settings goes through `write_text`. A bare `Path.write_text` truncates the
target and then streams into it, so an interruption anywhere in the middle
leaves a half-written file at the real path. That matters more here than
usual: `cortex.kb` follows each write with `sync_after()`, which commits and
pushes, and `cortex.inject` writes the harness settings file that every
session parses at startup.

The sequence is the standard one: write to a temp file in the target's own
directory (same filesystem, so the rename is atomic), fsync it, rename over
the target, then fsync the directory so the rename itself is durable.

Two things this does not cover, deliberately: files agents author through the
harness (`SUMMARY.md`, `tasks/*.md`, `workbench/*.md`), and the
`shutil.copy`/`shutil.move` paths in `cortex.viz.generator` and
`cortex.migrate_store`.
"""
from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

# The temp name is the target's name plus mkstemp's random suffix. Cap the
# borrowed part so a long-but-legal filename cannot push the temp past the
# 255-byte limit and fail a write that a bare write_text would have made.
_PREFIX_CAP = 40


def write_text(path, data: str, encoding: str = "utf-8", *, durable: bool = True) -> None:
    """Write `data` to `path` atomically. Readers see the old file or the new
    one, never a partial one.

    `durable=False` keeps the atomic replace but skips the fsyncs, for output
    that is regenerated from source rather than being the source.
    """
    target = _resolve_link(Path(path))
    directory = target.parent
    fd, tmp = tempfile.mkstemp(
        dir=str(directory), prefix=f".{target.name[:_PREFIX_CAP]}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(data)
            if durable:
                f.flush()
                os.fsync(f.fileno())
        os.chmod(tmp, _target_mode(target))
        os.replace(tmp, str(target))
    except BaseException:
        _unlink_quietly(tmp)
        raise
    if durable:
        _fsync_dir(directory)


def _resolve_link(target: Path) -> Path:
    """Write to what a symlink points at, not over the symlink. `os.replace`
    would otherwise turn a dotfiles-managed `~/.claude/settings.json` into a
    plain file and detach it from its repo."""
    if target.is_symlink():
        return Path(os.path.realpath(target))
    return target


def _target_mode(target: Path) -> int:
    """mkstemp creates 0600. Keep an existing file's mode; give a new one the
    permissions an ordinary create would have produced."""
    try:
        return stat.S_IMODE(target.stat().st_mode)
    except OSError:
        return 0o666 & ~_umask()


_UMASK: int | None = None


def _umask() -> int:
    """Reading the umask means setting it, so do that once per process rather
    than on every write."""
    global _UMASK
    if _UMASK is None:
        current = os.umask(0o022)
        os.umask(current)
        _UMASK = current
    return _UMASK


def _fsync_dir(directory: Path) -> None:
    """Best-effort: by the time this runs `os.replace` has already returned, so
    the new content is live. Failing here would report a successful write as a
    failed one, and some filesystems (CIFS) simply refuse a directory fsync."""
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _unlink_quietly(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass
