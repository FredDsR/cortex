"""Address grammar for cross-doc references."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .model import DocId

RESERVED_WORDS = frozenset({"memory", "workbench"})


@dataclass(frozen=True)
class ResolveResult:
    resolved: bool
    doc_id: Optional[DocId] = None


def _strip(token: str) -> str:
    token = token.strip()
    if token.startswith("[") and token.endswith("]"):
        token = token[1:-1].strip()
    return token


def resolve(raw: str, *, referencing: DocId) -> ResolveResult:
    """Resolve a raw authored reference against the referencing doc's context."""
    token = _strip(raw)
    if not token:
        return ResolveResult(resolved=False)
    parts = token.split("/")
    if any(p == "" for p in parts):
        return ResolveResult(resolved=False)

    if "memory" in parts:
        idx = parts.index("memory")
        if idx == 0 and len(parts) == 2:
            return ResolveResult(True, DocId(
                kind="memory", workspace=referencing.workspace, slug=parts[1]))
        if idx == 1 and len(parts) == 3:
            return ResolveResult(True, DocId(
                kind="memory", workspace=parts[0], slug=parts[2]))
        return ResolveResult(resolved=False)

    if "workbench" in parts:
        idx = parts.index("workbench")
        if idx == 0 and len(parts) == 2:
            return ResolveResult(True, DocId(
                kind="workbench", workspace=referencing.workspace,
                session=referencing.session, slug=parts[1]))
        if idx == 1 and len(parts) == 3:
            return ResolveResult(True, DocId(
                kind="workbench", workspace=referencing.workspace,
                session=parts[0], slug=parts[2]))
        if idx == 2 and len(parts) == 4:
            return ResolveResult(True, DocId(
                kind="workbench", workspace=parts[0], session=parts[1], slug=parts[3]))
        return ResolveResult(resolved=False)

    n = len(parts)
    if n == 1:
        return ResolveResult(True, DocId(
            kind="task", workspace=referencing.workspace,
            session=referencing.session, slug=parts[0]))
    if n == 2:
        if parts[0] in RESERVED_WORDS or parts[1] in RESERVED_WORDS:
            return ResolveResult(resolved=False)
        return ResolveResult(True, DocId(
            kind="task", workspace=referencing.workspace,
            session=parts[0], slug=parts[1]))
    if n == 3:
        if any(p in RESERVED_WORDS for p in parts):
            return ResolveResult(resolved=False)
        return ResolveResult(True, DocId(
            kind="task", workspace=parts[0], session=parts[1], slug=parts[2]))

    return ResolveResult(resolved=False)
