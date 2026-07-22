"""One-shot migrator: move ~/.work -> ~/.cortex for existing installs.
Dry-run by default; idempotent; never destroys data on conflict.

install.sh always creates ~/.cortex/bin (that is where the `cortex` bin lives,
so it must exist for the CLI to run at all). A bin-only ~/.cortex is therefore
just the install scaffold, NOT a real store, and we merge the old store into it.
Only a ~/.cortex that already holds real data (anything other than `bin/`) is a
genuine conflict we refuse to touch."""
from __future__ import annotations
import os
import shutil
from pathlib import Path


def _is_scaffold(new: Path) -> bool:
    """True if `new` is absent or contains nothing but the install `bin/` dir
    (i.e. it holds no migrated store data yet, so merging into it is safe)."""
    if not new.exists():
        return True
    return all(child.name == "bin" for child in new.iterdir())


def migrate(home: Path, *, write: bool) -> dict:
    home = Path(home)
    old = home / ".work"
    new = home / ".cortex"
    notes: list[str] = []
    if not old.exists():
        return {"action": "noop", "from": str(old), "to": str(new),
                "notes": ["no ~/.work store"]}
    if not _is_scaffold(new):
        return {"action": "conflict", "from": str(old), "to": str(new),
                "notes": [f"{new} already holds store data; move/merge manually"]}
    if not write:
        notes.append("dry-run: would merge ~/.work into ~/.cortex; "
                     "re-run with --write to apply")
        return {"action": "moved", "from": str(old), "to": str(new), "notes": notes}

    # Merge child-by-child so an install-created bin/ (and its fresh cortex
    # symlink) survives; move everything else (workspaces, knowledge, .git, ...).
    new.mkdir(parents=True, exist_ok=True)
    for child in sorted(old.iterdir()):
        dest = new / child.name
        if child.name == "bin" and dest.exists():
            # Keep the freshly-installed bin; discard the legacy one.
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
            continue
        if dest.exists():
            notes.append(f"skipped {child.name}: already exists in {new}")
            continue
        shutil.move(str(child), str(dest))
    # Remove the old store if it is now empty (leave it if anything was skipped).
    try:
        old.rmdir()
    except OSError:
        notes.append(f"{old} not empty after merge; left in place")
    notes.append("if you use cortex-sync, the git remote is unchanged; only the local path moved")
    return {"action": "moved", "from": str(old), "to": str(new), "notes": notes}


def cmd_migrate_store(args) -> int:
    rep = migrate(Path(os.path.expanduser("~")), write=getattr(args, "write", False))
    print(f"migrate-store: {rep['action']} {rep['from']} -> {rep['to']}")
    for n in rep["notes"]:
        print(f"  - {n}")
    return 1 if rep["action"] == "conflict" else 0
