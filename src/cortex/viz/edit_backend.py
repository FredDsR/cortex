"""Source-file mapping + hashing for the live edit server. Pure functions,
no HTTP. Enforces editable-kind and path-containment rules."""
from __future__ import annotations
import hashlib
from pathlib import Path

from cortex.model import World

EDITABLE_KINDS = frozenset({"task", "knowledge", "workbench", "session"})


def file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_path_for(world: World, canonical_id: str, workspaces_root: Path) -> Path:
    doc = world.docs.get(canonical_id)
    if doc is None:
        raise LookupError(f"unknown doc id: {canonical_id!r}")
    if doc.id.kind not in EDITABLE_KINDS:
        raise PermissionError(f"kind not editable: {doc.id.kind!r}")
    rel_path = doc.rel_path
    if rel_path is None:
        raise FileNotFoundError(f"no source file for {canonical_id!r}")
    # session docs may carry rel_path = the session dir when SUMMARY is absent;
    # a session is only editable when a real SUMMARY.md file exists.
    resolved = Path(rel_path).resolve()
    root_resolved = Path(workspaces_root).resolve()
    if root_resolved not in resolved.parents:
        raise PermissionError(f"path escapes workspaces root: {resolved}")
    if not resolved.is_file():
        raise FileNotFoundError(f"source file missing: {resolved}")
    return resolved
