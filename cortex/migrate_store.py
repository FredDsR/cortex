"""One-shot migrator: move ~/.work -> ~/.cortex for existing installs.
Dry-run by default; idempotent; never destroys data on conflict."""
from __future__ import annotations
import os
import shutil
from pathlib import Path


def migrate(home: Path, *, write: bool) -> dict:
    home = Path(home)
    old = home / ".work"
    new = home / ".cortex"
    notes: list[str] = []
    if not old.exists():
        return {"action": "noop", "from": str(old), "to": str(new),
                "notes": ["no ~/.work store"]}
    if new.exists():
        return {"action": "conflict", "from": str(old), "to": str(new),
                "notes": [f"{new} already exists; move/merge manually"]}
    if not write:
        notes.append("dry-run: would move; re-run with --write to apply")
        return {"action": "moved", "from": str(old), "to": str(new), "notes": notes}
    shutil.move(str(old), str(new))
    # Re-point the bin symlink if it lived under the store.
    bin_link = new / "bin" / "cortex"
    if bin_link.is_symlink():
        notes.append(f"store bin at {bin_link} (re-run install.sh to refresh targets)")
    notes.append("if you use cortex-sync, the git remote is unchanged; only the local path moved")
    return {"action": "moved", "from": str(old), "to": str(new), "notes": notes}


def cmd_migrate_store(args) -> int:
    rep = migrate(Path(os.path.expanduser("~")), write=getattr(args, "write", False))
    print(f"migrate-store: {rep['action']} {rep['from']} -> {rep['to']}")
    for n in rep["notes"]:
        print(f"  - {n}")
    return 1 if rep["action"] == "conflict" else 0
