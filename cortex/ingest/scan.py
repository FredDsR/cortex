"""One walk of a source tree, splitting it into the two halves `kb ingest`
treats differently: files a parser can transcribe exactly, and files that need
an agent's judgment.

Read-only. It returns paths and worklist lines; deciding what is in them is
`extract.py`'s job, and printing them is `cli.py`'s.
"""
from __future__ import annotations
import os
import re
from pathlib import Path

_PRUNE = {".git", "node_modules", ".cortex"}


def _walk_files(src: Path):
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in _PRUNE]
        for fn in files:
            yield Path(root) / fn


_API_HDR = re.compile(r"^##[ \t]+(API|Schema)\b", re.MULTILINE)


def scan(src: Path, only) -> tuple[list[Path], list[str]]:
    """One walk of the tree: returns (structured files sorted, worklist lines).
    Structured (deterministic) = OpenAPI/Swagger yaml/json + *.sql, honoring
    --only. Worklist (agent judgment) = *.prisma (case-sensitive, like bash
    -name), README*.md with a ## API/## Schema header, runbook* (case-insensitive,
    like bash -iname); always collected regardless of --only."""
    structured, prisma, readme, runbook = [], [], [], []
    for f in _walk_files(src):
        name = f.name
        low = name.lower()
        ext = low.rsplit(".", 1)[-1] if "." in low else ""
        is_api = (low.startswith("openapi") or low.startswith("swagger")) and ext in ("yml", "yaml", "json")
        if only != "sql" and is_api:
            structured.append(f)
        elif only != "openapi" and low.endswith(".sql"):
            structured.append(f)
        if name.endswith(".prisma"):                       # bash -name (case-sensitive)
            prisma.append(f"{f} - Prisma schema")
        elif low.startswith("readme") and low.endswith(".md"):
            try:
                if _API_HDR.search(f.read_text(encoding="utf-8", errors="replace")):
                    readme.append(f"{f} - has ## API/## Schema section")
            except OSError:
                pass
        elif low.startswith("runbook"):
            runbook.append(f"{f} - runbook")
    worklist = sorted(prisma) + sorted(readme) + sorted(runbook)
    return sorted(structured, key=str), worklist
